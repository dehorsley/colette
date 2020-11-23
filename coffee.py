#!/usr/bin/env python3
import csv
import math

from pathlib import Path
from dataclasses import dataclass
from collections.abc import Iterable

COST_OF_NOT_PAIRING = 100
COST_OF_PARING_WITHIN_ORG = 10
COST_OF_PARING_PREVIOUS_PARTNERS = 100


@dataclass(frozen=True)
class Person:
    name: str
    organisation: str


Round = set[Person]
Pairing = dict[Person, Person]
Cost = float


def coffee_pairs(
    people: Round, previous_pairings: list[Pairing]
) -> tuple[Cost, Pairing]:

    global_best = math.inf

    def cost_of_paring(p1: Person, p2: Person):
        cost = 0
        if p1.organisation == p2.organisation:
            cost += COST_OF_PARING_WITHIN_ORG
        for n, pairing in enumerate(previous_pairings):
            if p1 not in pairing:
                continue
            if pairing[p1] is not p2:
                continue
            cost += COST_OF_PARING_PREVIOUS_PARTNERS / (len(previous_pairings) - n)
        return cost

    def recurse(people, curr_cost):
        nonlocal global_best

        best_pairing = None

        # best case cost for rest of the branch is current cost (all remaining
        # pairs can be paired without penalty) plus COST_OF_NOT_PAIRING if
        # odd number of people left
        bound = curr_cost
        if len(people) % 2 == 1:
            bound += COST_OF_NOT_PAIRING
        if bound >= global_best:
            return (math.inf, {})

        if not people and curr_cost < global_best:
            global_best = curr_cost
            print(global_best)
            return global_best, {}

        p1, *rest = people
        rest = sorted(rest, key=lambda p2: cost_of_paring(p1, p2))

        for p2 in rest:
            new_cost, new_pairs = recurse(
                people - {p1, p2}, curr_cost + cost_of_paring(p1, p2)
            )
            if new_cost == global_best:
                best_pairing = new_pairs | {p1: p2, p2: p1}

        new_cost, new_pairs = recurse(people - {p1}, curr_cost + COST_OF_NOT_PAIRING)
        if new_cost == global_best:
            best_pairing = new_pairs

        if best_pairing is not None:
            return global_best, best_pairing

        return math.inf, {}

    return recurse(people, 0)


def main():
    round: Round = set()
    people_by_name: dict[str, Person] = {}

    with open("data/people.csv") as f:
        for row in csv.DictReader(f):
            # print(row)
            active = row["active"].casefold() == "true"
            del row["active"]
            p = Person(**row)

            people_by_name[p.name] = p
            if active:
                round.add(p)

    # get the previous rounds files ordered by numbered suffix
    round_paths = sorted(
        Path("data").glob("round_*.csv"),
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

    cost, pairings = coffee_pairs(round, previous_pairings)
    print(cost)

    # print unique pairs
    N = int(round_paths[-1].stem.removeprefix("round_")) + 1
    with Path("data").joinpath(f"round_{N:03d}.csv").open("w") as f:
        for p1, p2 in set(map(frozenset, pairings.items())):
            print(p1.name, p2.name, sep=",", file=f)


if __name__ == "__main__":
    main()
