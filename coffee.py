#!/usr/bin/env python3
import csv
import math
import random

import mip

from itertools import chain
from pathlib import Path
from dataclasses import dataclass
from functools import cache

# NB: these must all be integers!
COST_OF_NOT_PAIRING = 100  # Currently not used
COST_OF_PARING_WITHIN_ORG = 5
COST_OF_PARING_PREVIOUS_PARTNERS = 100
COST_OF_PARING_SAME_TYPE = 2  # as in role: orgraniser or coffee buyer

random.seed(1987)  # for reproducability


@dataclass(frozen=True)
class Person:
    name: str
    organisation: str


@dataclass(frozen=True)
class Pair:
    organiser: Person
    buyer: Person

    def __contains__(self, item):
        return self.organiser == item or self.buyer == item


Round = list[Person]
Pairing = dict[Person, Pair]
Cost = float


def coffee_pairs(N, weights) -> Pairing:
    pairs = [(i, j) for i in range(N - 1) for j in range(i + 1, N)]

    def pairs_containing(k):
        return chain(((i, k) for i in range(k)), ((k, i) for i in range(k + 1, N)))

    m = mip.Model()

    p = {(i, j): m.add_var(var_type=mip.BINARY) for i, j in pairs}

    # Constraint: a person can only be in one pair, so sum of all pairs with person k must be 1
    for k in range(N):
        m += mip.xsum(p[i, j] for i, j in pairs_containing(k)) == 1

    m.objective = mip.minimize(mip.xsum(weights(i, j) * p[i, j] for i, j in pairs))

    m.verbose = False
    status = m.optimize()
    if status != mip.OptimizationStatus.OPTIMAL:
        raise Exception("not optimal" + status)
    print("Objective value =", m.objective_value)

    return [(i, j) for i, j in pairs if p[i, j].x > 0.5]


def main():
    round: Round = []
    people_by_name: dict[str, Person] = {}

    with open("test_data/people.csv") as f:
        for row in csv.DictReader(f):
            active = row["active"].casefold() == "true"
            del row["active"]
            p = Person(**row)

            people_by_name[p.name] = p
            if active:
                round.append(p)

    # get the previous rounds files ordered by numbered suffix
    round_paths = sorted(
        Path("test_data").glob("round_*.csv"),
        key=lambda p: int(p.stem.removeprefix("round_")),
    )

    # read all the previous rounds into a list of Pairings
    previous_pairings: list[Pairing] = []
    for path in round_paths:
        previous_pairing: Pairing = {}
        with path.open() as f:
            for row in csv.DictReader(f):
                # TODO: a more useful error might be nice here if lookup fails
                p1 = people_by_name[row["organiser"]]
                p2 = people_by_name[row["buyer"]]
                pair = Pair(p1, p2)
                previous_pairing[p1] = pair
                previous_pairing[p2] = pair
            previous_pairings.append(previous_pairing)

    def last_pairing(p: Person) -> Pair:
        return next(
            (pairings[p] for pairings in reversed(previous_pairings) if p in pairings),
            None,
        )

    def make_pair(p1: Person, p2: Person) -> Pair:
        """
        makes a pair, assigning roles based on previous assignments
        """

        p1_last_pair = last_pairing(p1)
        p2_last_pair = last_pairing(p2)

        if (p1_last_pair is None or p1 == p1_last_pair.organiser) and (
            p2_last_pair is None or p2 == p2_last_pair.buyer
        ):
            return Pair(organiser=p2, buyer=p1)

        if (p1_last_pair is None or p1 == p1_last_pair.buyer) and (
            p2_last_pair is None or p2 == p2_last_pair.organiser
        ):
            return Pair(organiser=p1, buyer=p2)

        # Perhaps random
        if random.random() < 0.5:
            return Pair(organiser=p1, buyer=p2)

        return Pair(organiser=p2, buyer=p1)

    def weights(i, j):
        p1 = round[i]
        p2 = round[j]
        cost = 0
        if p1.organisation == p2.organisation:
            cost += COST_OF_PARING_WITHIN_ORG

        # if partners were of the same type last time

        p1_last_pair = last_pairing(p1)
        p2_last_pair = last_pairing(p2)

        if p1_last_pair is not None and p2_last_pair is not None:
            if (
                p1 == p1_last_pair.organiser
                and p2 == p2_last_pair.organiser
                or p1 == p1_last_pair.buyer
                and p2 == p2_last_pair.buyer
            ):
                cost += COST_OF_PARING_SAME_TYPE

        # if partners were previously paired
        for n, pairing in enumerate(previous_pairings):
            if p1 not in pairing:
                continue
            if p2 not in pairing[p1]:
                continue

            # TODO: maybe this should take into account the last time this pair
            # was *available* i.e. if someone goes in break, you don't want to
            # pair them up with the same person, when they came back even if
            # there was a large number of rounds between

            if len(previous_pairings) - n == 1:
                cost += 1_000_000
            elif len(previous_pairings) - n < 20:
                cost += COST_OF_PARING_PREVIOUS_PARTNERS
        return cost

    pairings = coffee_pairs(len(round), weights)
    print(pairings)

    # Round number to save
    try:
        N = int(round_paths[-1].stem.removeprefix("round_")) + 1
    except IndexError:
        N = 1

    with Path("test_data").joinpath(f"round_{N:03d}.csv").open("w") as f:
        print("organiser", "buyer", sep=",", file=f)
        for i, j in pairings:
            pair = make_pair(round[i], round[j])
            print(pair.organiser.name, pair.buyer.name, sep=",", file=f)


if __name__ == "__main__":
    main()
