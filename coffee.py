#!/usr/bin/env python3
import csv
import math

from pathlib import Path
from dataclasses import dataclass
from functools import cache

COST_OF_NOT_PAIRING = 100
COST_OF_PARING_WITHIN_ORG = 50
COST_OF_PARING_PREVIOUS_PARTNERS = 100


@dataclass(frozen=True)
class Person:
    name: str
    organisation: str


Round = list[Person]
Pairing = dict[Person, Person]
Cost = float


def coffee_pairs(
    people: Round, previous_pairings: list[Pairing]
) -> tuple[Cost, Pairing]:

    calls = set()

    # TODO: is this more or less expensive
    @cache
    def cost_of_paring(p1: Person, p2: Person):
        # if p1 == p2:
        #     raise Exception
        # s = frozenset({p1, p2})
        # if s in calls:
        #     print(s)
        #
        # calls.add(s)

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

    global_best = math.inf

    def recurse(mask, curr_cost):
        nonlocal global_best

        best_pairing = None

        # best case cost for rest of the branch is current cost (all remaining
        # pairs can be paired without penalty) plus COST_OF_NOT_PAIRING if
        # odd number of people left
        bound = curr_cost
        if sum(not p for p in mask) % 2 == 1:
            bound += COST_OF_NOT_PAIRING
        if bound >= global_best:
            return (math.inf, {})

        if all(mask) and curr_cost < global_best:
            # we're out of people and we have a new best soln
            global_best = curr_cost
            print(global_best)
            return global_best, {}

        i, p1 = next((i, p1) for (i, p1) in enumerate(people) if not mask[i])
        # candidates = sorted(
        #     [(j, p2) for (j, p2) in enumerate(people) if j != i and not mask[j]],
        #     key=lambda t: cost_of_paring(p1, t[1]),
        # )
        candidates = (
            (j, p2) for (j, p2) in enumerate(people) if j != i and not mask[j]
        )

        for j, p2 in candidates:
            if mask[j]:
                continue
            new_mask = mask.copy()
            new_mask[i] = new_mask[j] = True
            new_cost, new_pairs = recurse(new_mask, curr_cost + cost_of_paring(p1, p2))
            if new_cost == global_best:
                best_pairing = new_pairs | {p1: p2, p2: p1}

        new_mask = mask.copy()
        new_mask[i] = True
        new_cost, new_pairs = recurse(new_mask, curr_cost + COST_OF_NOT_PAIRING)
        if new_cost == global_best:
            best_pairing = new_pairs

        if best_pairing is None:
            return math.inf, {}
        return global_best, best_pairing

    # TODO: do the hardest first: sort people by some rank of how hard they are to pair, say:
    #     number of previous pairings + number of people in their company - number of people
    mask = [False] * len(people)

    return recurse(mask, 0)


def main():
    round: Round = []
    people_by_name: dict[str, Person] = {}

    with open("data/people.csv") as f:
        for row in csv.DictReader(f):
            # print(row)
            active = row["active"].casefold() == "true"
            del row["active"]
            p = Person(**row)

            people_by_name[p.name] = p
            if active:
                round.append(p)

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
    try:
        N = int(round_paths[-1].stem.removeprefix("round_")) + 1
    except IndexError:
        N = 1

    with Path("data").joinpath(f"round_{N:03d}.csv").open("w") as f:
        for p1, p2 in set(map(frozenset, pairings.items())):
            print(p1.name, p2.name, sep=",", file=f)


if __name__ == "__main__":
    main()
