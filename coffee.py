#!/usr/bin/env python3
import csv
import math

import mip

from itertools import chain
from pathlib import Path
from dataclasses import dataclass
from functools import cache

# NB: these must all be integers!
COST_OF_NOT_PAIRING = 100  # Currently not used
COST_OF_PARING_WITHIN_ORG = 1
COST_OF_PARING_PREVIOUS_PARTNERS = 10

# TODO: class people as "organisers" or "coffee buyers" and prefer to alternate


@dataclass(frozen=True)
class Person:
    name: str
    organisation: str


Round = list[Person]
Pairing = dict[Person, Person]
Cost = float


def coffee_pairs(people: Round, previous_pairings: list[Pairing]) -> Pairing:
    def weight_of_pair(p1: Person, p2: Person):
        cost = 0
        if p1.organisation == p2.organisation:
            cost += COST_OF_PARING_WITHIN_ORG

        for n, pairing in enumerate(previous_pairings):
            if p1 not in pairing:
                continue
            if pairing[p1] is not p2:
                continue

            # TODO: this should take into account the last time this pair was *available*
            # i.e. if someone goes in break, you don't want to pair them up with the same person,
            # when they came back even if there was a large number of rounds between

            if len(previous_pairings) - n == 1:
                cost += 1_000_000
            elif len(previous_pairings) - n < 20:
                cost += COST_OF_PARING_PREVIOUS_PARTNERS
        return cost

    N = len(people)
    pairs = [(i, j) for i in range(N - 1) for j in range(i + 1, N)]

    def pairs_containing(k):
        return chain(((i, k) for i in range(k)), ((k, i) for i in range(k + 1, N)))

    m = mip.Model()

    p = {(i, j): m.add_var(var_type=mip.BINARY) for i, j in pairs}

    # Constraint: a person can only be in one pair, so sum of all pairs with person k must be 1
    for k in range(N):
        m += mip.xsum(p[i, j] for i, j in pairs_containing(k)) == 1

    m.objective = mip.minimize(
        mip.xsum(weight_of_pair(people[i], people[j]) * p[i, j] for i, j in pairs)
    )

    m.verbose = False
    status = m.optimize()
    if status != mip.OptimizationStatus.OPTIMAL:
        raise Exception("not optimal" + status)
    print("Objective value =", m.objective_value)

    pairing = {}
    for (i, j) in pairs:
        if p[i, j].x < 0.5:
            continue
        pairing[people[j]] = people[i]
        pairing[people[i]] = people[j]

    return pairing


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
            for row in csv.reader(f):
                # TODO: a more useful error might be nice here if lookup fails
                p1, p2 = people_by_name[row[0]], people_by_name[row[1]]
                previous_pairing[p1] = p2
                previous_pairing[p2] = p1
            previous_pairings.append(previous_pairing)

    pairings = coffee_pairs(round, previous_pairings)

    try:
        N = int(round_paths[-1].stem.removeprefix("round_")) + 1
    except IndexError:
        N = 1

    with Path("test_data").joinpath(f"round_{N:03d}.csv").open("w") as f:
        for p1, p2 in set(map(frozenset, pairings.items())):
            print(p1.name, p2.name, sep=",", file=f)


if __name__ == "__main__":
    main()
