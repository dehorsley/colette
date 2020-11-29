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

COST_OF_PARING_SAME_TYPE = 2  # as in role in pair: orgraniser or coffee buyer

# Should be a big number. Really don't want to pair people together *just* after they paired. If we introduce
# not pairing some players, that might be preferred
COST_OF_PARING_PREVIOUS_PARTNER_ONE_ROUND_AGO = 1_000_000
# Cost of pairing players that were previously paired between 2 to N rounds ago
COST_OF_PARING_PREVIOUS_PARTNER_TWO_TO_N_ROUND_AGO = 100
# Number of round before a previous pairing doesn't matter anymore
COST_OF_PARING_PREVIOUS_PARTNER_N = 10


random.seed(1987)  # for reproducibility


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


def find_optimal_pairs(N, weights) -> list[tuple[int, int]]:
    """
    find_optimal_pairs finds an optimal set of pairs of integers between 0 and
    N-1 (incl) that minimize the sum of the weights specified for each pair.
    """

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


def find_pairs(players: list[Person], previous_pairings: list[Pairing]) -> list[Pair]:
    """
    find_pairs finds the best (or a best) set of pairings based on the active players and
    the previous rounds.
    """

    def last_pairing(p: Person) -> Pair:
        return next(
            (pairings[p] for pairings in reversed(previous_pairings) if p in pairings),
            None,
        )

    def assign_roles(p1: Person, p2: Person) -> Pair:
        """
        assign_roles makes a Pair object, assigning role "organiser" or "buyer"
        to the players based on their previous assignments:

        - If the players were assigned a different role from each other last
          time they played, or one player hasn't played, they will swap roles.

        - If both were assigned the same role in their previous pairings, or
          neither have previously played, then they will be randomly assigned
          roles with equal probability.
        """

        p1_last_pair = last_pairing(p1)
        p2_last_pair = last_pairing(p2)

        if p1_last_pair is None and p2_last_pair is None:
            if random.random() < 0.5:
                return Pair(organiser=p1, buyer=p2)
            return Pair(organiser=p2, buyer=p1)

        if (p1_last_pair is None or p1 == p1_last_pair.buyer) and (
            p2_last_pair is None or p2 == p2_last_pair.organiser
        ):
            return Pair(organiser=p1, buyer=p2)

        if (p1_last_pair is None or p1 == p1_last_pair.organiser) and (
            p2_last_pair is None or p2 == p2_last_pair.buyer
        ):
            return Pair(organiser=p2, buyer=p1)

        # Perhaps random
        if random.random() < 0.5:
            return Pair(organiser=p1, buyer=p2)

        return Pair(organiser=p2, buyer=p1)

    def weights(i, j):
        """
        weights calculates the "cost" to the final solution of pairing
        player i and j together. Takes into account if players are in the same organisation,
        were previously assigned the same role, and were previously paired together.
        """

        p1 = players[i]
        p2 = players[j]
        cost = 0

        ##
        # same org

        if p1.organisation == p2.organisation:
            cost += COST_OF_PARING_WITHIN_ORG

        ##
        # if partners were of the same type in their last round

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

        ##
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
                cost += COST_OF_PARING_PREVIOUS_PARTNER_ONE_ROUND_AGO
            elif len(previous_pairings) - n < COST_OF_PARING_PREVIOUS_PARTNER_N:
                cost += COST_OF_PARING_PREVIOUS_PARTNER_TWO_TO_N_ROUND_AGO
        return cost

    pairs = []
    optimal_pair_indexs = find_optimal_pairs(len(players), weights)
    for i, j in optimal_pair_indexs:
        pair = assign_roles(players[i], players[j])
        pairs.append(pair)

    return pairs


def main():
    players: Round = []
    people_by_name: dict[str, Person] = {}

    with open("test_data/people.csv") as f:
        for row in csv.DictReader(f):
            active = row["active"].casefold() == "true"
            del row["active"]
            p = Person(**row)

            people_by_name[p.name] = p
            if active:
                players.append(p)

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

    pairs = find_pairs(players, previous_pairings)

    # round number to save
    N = 1
    if len(round_paths) > 0:
        N = int(round_paths[-1].stem.removeprefix("round_")) + 1

    with Path("test_data").joinpath(f"round_{N:03d}.csv").open("w") as f:
        print("organiser", "buyer", sep=",", file=f)
        for pair in pairs:
            print(pair.organiser.name, pair.buyer.name, sep=",", file=f)


if __name__ == "__main__":
    main()
