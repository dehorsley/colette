#!/usr/bin/env python3
import csv
import math
import random
import argparse

import mip

from inspect import signature
from itertools import chain
from pathlib import Path
from dataclasses import dataclass
from functools import cache
from typing import TextIO


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
    active: bool
    email: str


@dataclass(frozen=True)
class Pair:
    organiser: Person
    buyer: Person

    def __contains__(self, item):
        return self.organiser == item or self.buyer == item


Round = dict[Person, Pair]


def find_optimal_pairs_index(N, weights) -> (float, list[tuple[int, int]]):
    """
    find_optimal_pairs finds an optimal set of pairs of integers between 0 and
    N-1 (incl) that minimize the sum of the weights specified for each pair.

    Returns the objective value and list of pairs.
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
        raise Exception("not optimal")

    return m.objective_value, [(i, j) for i, j in pairs if p[i, j].x > 0.5]


def new_round(
    players: list[Person],
    previous_pairings: list[Round],
    overrides: dict[frozenset[Person], int] = {},
) -> list[Pair]:
    """
    find_pairs finds the best (or a best) set of pairings based on the active players and
    the previous rounds.
    """

    def last_pairing(p: Person) -> Pair:
        """
        last_pairing finds the most recent pair person p participated in in the
        list of previous_pairings, or None otherwise.
        """
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
        # overrides
        cost += overrides.get(frozenset({p1, p2}), 0)

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
    cost, optimal_pair_indices = find_optimal_pairs(len(players), weights)
    for i, j in optimal_pair_indices:
        pair = assign_roles(players[i], players[j])
        pairs.append(pair)

    return pairs


def load_people(f: TextIO) -> dict[str, Person]:
    """
    load_people reads a set of people from comma separated list in file like
    object f, and return a dictionary keyed by name.
    """
    people_by_name: dict[str, Person] = {}
    for row in csv.DictReader(f):
        # Convert string to bool
        row["active"] = row["active"].casefold() == "true"
        p = Person(**row)
        people_by_name[p.name] = p
    return people_by_name


def load_round(f: TextIO, people_by_name: dict[str, Person]) -> Round:
    """
    load_round reads a set of comma separated pairs from file-like object f and
    returns a dictionary of pairs.
    """
    previous_round: Round = {}
    for row in csv.DictReader(f):
        # TODO: a more useful error might be nice here if lookup fails
        p1 = people_by_name[row["organiser"]]
        p2 = people_by_name[row["buyer"]]
        pair = Pair(organiser=p1, buyer=p2)
        previous_round[p1] = pair
        previous_round[p2] = pair
    return previous_round


def load_overides(f: TextIO, people_by_name) -> dict[Person, float]:
    pass


def save_round(round: Round, f: TextIO):
    """
    save_round writes a set of comma separated lines of "organiser,buyer" pairs to
    the file like object f.
    """
    print("organiser", "buyer", sep=",", file=f)
    for pair in round:
        print(pair.organiser.name, pair.buyer.name, sep=",", file=f)


def new_round_from_path(path="data") -> Round:
    path = Path(path)

    with (path / "people.csv").open() as f:
        people_by_name = load_round(f)

    # get the previous rounds files ordered by numbered suffix
    round_paths = sorted(
        path.glob("round_*.csv"),
        key=lambda p: int(p.stem.removeprefix("round_")),
    )

    # read all the previous rounds into a list of Rounds
    previous_rounds = []
    for path in round_paths:
        with path.open() as f:
            previous_rounds.append(load_previous_round(f, people_by_name))

    players = [p for p in people_by_name.values() if p.active]
    round = new_round(players, previous_pairings)

    # round number to save
    N = 1
    if len(round_paths) > 0:
        N = int(round_paths[-1].stem.removeprefix("round_")) + 1

    with (path / f"round_{N:03d}.csv").open("w") as f:
        save_round(round, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "colette",
        description="""\
            Manage a series of coffee roulette sessions!
        """,
    )
    parser.add_argument(
        "--data",
        "-d",
        help="directory containing people and round data",
        default="data",
    )
    subparsers = parser.add_subparsers(title="commands")

    def new_func(n, data):
        print("new func called")

    new_parser = subparsers.add_parser(
        "new",
        description="""
            create a new round. The list of pairings is saved in round_N.csv in
            the data directory, where N is the current round, inferred from the
            CSV files in the data directory.
    """,
    )
    new_parser.add_argument("-n", help="round number", type=int)
    new_parser.set_defaults(func=new_func)

    email = subparsers.add_parser(
        "email",
        description="""
        email the participants of the last round — or the round specified — their partner and role.
        """,
    )

    def email_func():
        print("email_func called")

    email.set_defaults(func=email_func)

    args = parser.parse_args()
    if "func" not in vars(args):
        parser.print_help()
        sys.exit(1)

    args.func(
        **{k: v for k, v in vars(args).items() if k in signature(args.func).parameters}
    )
