#!/usr/bin/env python3
import csv
import math
import random
import smtplib

from configparser import ConfigParser
from email.message import EmailMessage
from itertools import chain
from pathlib import Path
from dataclasses import dataclass
from functools import cache
from typing import TextIO

import mip

from jinja2 import Template, Environment

# NB: these must all be integers!
COST_OF_NOT_PAIRING = 50
COST_OF_PAIRING_WITHIN_ORG = 10

COST_OF_PAIRING_SAME_TYPE = 1  # as in role in pair: orgraniser or coffee buyer

# Should be a big number. Really don't want to pair people together *just* after they paired
COST_OF_PAIRING_PREVIOUS_PARTNER_ONE_ROUND_AGO = 1_000_000
# Cost of pairing players that were previously paired between 2 to N rounds ago
COST_OF_PAIRING_PREVIOUS_PARTNER_TWO_TO_N_ROUND_AGO = 50
# Number of round before a previous pairing doesn't matter anymore
COST_OF_PAIRING_PREVIOUS_PARTNER_N = 10


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


def find_optimal_pairs(N, weights) -> (float, list[tuple[int, int]]):
    """
    find_optimal_pairs finds an optimal set of pairs of integers between 0 and
    N-1 (incl) that minimize the sum of the weights specified for each pair.

    Returns the objective value and list of pairs.
    """

    pairs = [(i, j) for i in range(N) for j in range(i, N)]
    # note: people are excluded from the round by pairing with themselves

    def pairs_containing(k):
        return chain(((i, k) for i in range(k)), ((k, i) for i in range(k, N)))

    m = mip.Model()

    p = {(i, j): m.add_var(var_type=mip.BINARY) for i, j in pairs}

    # Constraint: a person can only be in one pair, so sum of all pairs with person k must be 1
    for k in range(N):
        m += mip.xsum(p[i, j] for i, j in pairs_containing(k)) == 1

    m.objective = mip.minimize(mip.xsum(weights[i, j] * p[i, j] for i, j in pairs))

    m.verbose = False
    status = m.optimize()
    if status != mip.OptimizationStatus.OPTIMAL:
        raise Exception("not optimal")

    return m.objective_value, [(i, j) for i, j in pairs if p[i, j].x > 0.5]


def new_round(
    players: list[Person],
    previous_rounds: list[Round],
    overrides: dict[frozenset[Person], int] = {},
) -> list[Pair]:
    """
    find_pairs finds the best (or a best) set of pairings based on the active players and
    the previous rounds.
    """

    def last_pairing(p: Person) -> Pair:
        """
        last_pairing finds the most recent pair person p participated in the
        list of previous_rounds, or None otherwise.
        """
        return next(
            (pairs[p] for pairs in reversed(previous_rounds) if p in pairs),
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
        if p1 == p2:
            return Pair(p1, p2)

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

    # weights contains the "cost" to the final solution of pairing
    # player i and j together. Takes into account if players are in the same organisation,
    # were previously assigned the same role, and were previously paired together.
    weights = {}

    # whys contains the list of explanations for the "costs" in weights. This
    # allows for reporting of non-preferred matches in the optimal solution.
    whys = {}

    N = len(players)
    for i in range(N):
        for j in range(i, N):
            p1 = players[i]
            p2 = players[j]
            cost = 0
            whys[i, j] = []

            ##
            # overrides
            if (s := frozenset({p1, p2})) in overrides:
                cost += overrides[s]
                whys[i, j].append(f"override values {overrides[s]}")

            ##
            # if partners were previously paired
            for n, pairing in enumerate(reversed(previous_rounds)):
                if n >= COST_OF_PAIRING_PREVIOUS_PARTNER_N:
                    break

                if p1 not in pairing:
                    continue
                if p2 not in pairing[p1]:
                    continue

                if i == j and pairing[p1].organiser != pairing[p1].buyer:
                    continue

                # TODO: maybe this should take into account the last time this pair
                # was *available* i.e. if someone goes in break, you don't want to
                # pair them up with the same person, when they came back even if
                # there was a large number of rounds between

                if n == 0:
                    cost += COST_OF_PAIRING_PREVIOUS_PARTNER_ONE_ROUND_AGO
                    whys[i, j].append(
                        f"were paired last round"
                        if i != j
                        else "was removed last round"
                    )
                elif n < COST_OF_PAIRING_PREVIOUS_PARTNER_N:
                    cost += COST_OF_PAIRING_PREVIOUS_PARTNER_TWO_TO_N_ROUND_AGO
                    whys[i, j].append(
                        f"were paired less than {n+1} rounds ago"
                        if i != j
                        else f"was removed last less than {n+1} rounds ago"
                    )

            if i == j:
                cost += COST_OF_NOT_PAIRING
                whys[i, j].append("removed from round")
                weights[i, j] = cost
                continue

            ##
            # same org
            if p1.organisation == p2.organisation:
                cost += COST_OF_PAIRING_WITHIN_ORG
                whys[i, j].append("are in the same organisation")

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
                    cost += COST_OF_PAIRING_SAME_TYPE
                    whys[i, j].append("were the same role last round")

            weights[i, j] = cost

    pairs = []
    cost, optimal_pair_indices = find_optimal_pairs(len(players), weights)
    for i, j in optimal_pair_indices:
        if weights[i, j] > 0:
            # TODO: something better than this, option to turn off or something
            if i == j:
                print(players[i].name, ", ".join(whys[i, j]))
            else:
                print(
                    f"{players[i].name} paired with {players[j].name} but players",
                    " and ".join(whys[i, j]),
                )
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
        row = {k: v.strip() for k, v in row.items()}
        row["active"] = row["active"].casefold() in {"true", "1"}
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


def load_overrides(f: TextIO, people_by_name) -> dict[frozenset[Person], int]:
    """
    load_overrides loads a list of overrides from a csv file. Overrides are
    specified as two names and the weight/cost associated with adding that pair
    to the round. Note a negative weight is valid and can be used to
    incentivise the pair to be added to the round.
    """
    overrides = {}
    for row in csv.reader(f):
        p1 = people_by_name[row[0].strip()]
        p2 = people_by_name[row[1].strip()]
        overrides[frozenset({p1, p2})] = int(row[2].strip())
    return overrides


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
        people_by_name = load_people(f)

    # get the previous rounds files ordered by numbered suffix
    round_paths = sorted(
        path.glob("round_*.csv"),
        key=lambda p: int(p.stem.removeprefix("round_")),
    )

    # round number to save
    N = 1
    if len(round_paths) > 0:
        N = int(round_paths[-1].stem.removeprefix("round_")) + 1
    print(f"Generating Round {N}!")

    # read all the previous rounds into a list of Rounds
    previous_rounds = []
    for p in round_paths:
        with p.open() as f:
            previous_rounds.append(load_round(f, people_by_name))

    overrides = {}
    if (p := path / "overrides.csv").exists():
        with p.open() as f:
            overrides = load_overrides(f, people_by_name)

    players = [p for p in people_by_name.values() if p.active]
    if len(players) == 0:
        raise Exception("no players!")
    round = new_round(players, previous_rounds, overrides=overrides)

    with (path / f"round_{N:03d}.csv").open("w") as f:
        save_round(round, f)


def email(path="data", round=None):
    """
    email function emails the participants of a round their role and
    counterpart, or gives them appology if unpaired. The round emailed is
    either the number specified in "round" or the latest in the path.
    """
    path = Path(path)

    with (path / "buyer.template").open() as f:
        buyer_template = Template(f.read())

    with (path / "organiser.template").open() as f:
        organiser_template = Template(f.read())

    with (path / "excluded.template").open() as f:
        excluded_template = Template(f.read())

    cfg = ConfigParser()
    cfg.read(path / "email.ini")

    if round is None:
        round_paths = sorted(
            path.glob("round_*.csv"),
            key=lambda p: int(p.stem.removeprefix("round_")),
        )

        if len(round_paths) == 0:
            raise Exception(f"No round_*.csv file round in path {path}")

        round = int(round_paths[-1].stem.removeprefix("round_"))

    print(f"Emailing players of round {round}!")

    with (path / "people.csv").open() as f:
        people_by_name = load_people(f)

    with (path / f"round_{round:03d}.csv").open() as f:
        pairs = load_round(f, people_by_name)

    def msg_from_template(address, pair, template):
        msg = EmailMessage()
        msg.set_content(template.render(organiser=p.organiser, buyer=p.buyer))

        msg["Subject"] = cfg["email"]["subject"]
        msg["From"] = cfg["email"]["from"]
        msg["To"] = address
        return msg

    # iterate over all unique pairs: NB each pair can be in the pairs dict at
    # most once, one time for each member.
    msgs = []
    for p in set(pairs.values()):
        if p.buyer == p.organiser:
            msgs.append(msg_from_template(p.buyer.email, p, excluded_template))
            continue
        msgs.append(msg_from_template(p.buyer.email, p, buyer_template))
        msgs.append(msg_from_template(p.organiser.email, p, organiser_template))

    s = smtplib.SMTP(cfg["email"]["server"], cfg["email"].getint("port", fallback=587))
    s.ehlo()

    if cfg["email"].getboolean("ssl", fallback=False):
        import ssl

        ctx = ssl.create_default_context()
        s.starttls(context=ctx)

    if "username" in cfg["email"]:
        s.login(cfg["email"]["username"], cfg["email"]["password"])

    for msg in msgs:
        s.send_message(msg)
    s.quit()
