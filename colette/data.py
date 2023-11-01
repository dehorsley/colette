import csv
from pathlib import Path
from typing import TextIO
from dataclasses import dataclass


@dataclass(frozen=True)
class Person:
    name: str
    organisation: str
    active: bool
    email: str

    def from_csv_row(row: dict[str, str]) -> "Person":
        row = {k: v.strip() for k, v in row.items()}
        row["active"] = row["active"].casefold() in {"true", "1"}
        return Person(**row)


@dataclass(frozen=True)
class Pair:
    organiser: Person
    buyer: Person

    def __contains__(self, item):
        return self.organiser == item or self.buyer == item


@dataclass(frozen=True)
class Round:
    pairs: dict[Person, Pair]

    def __contains__(self, item):
        return item in self.pairs


@dataclass(frozen=True)
class Override:
    pair: frozenset[Person]
    weight: int


@dataclass(frozen=True)
class Overrides:
    pair_weights: dict[frozenset[Person], int]

    def __contains__(self, item):
        return item in self.pair_weights

    def __iter__(self):
        return iter(self.pair_weights)

    def __getitem__(self, item):
        return self.pair_weights[item]

    def __len__(self):
        return len(self.pair_weights)


@dataclass(frozen=True)
class Config:
    people: dict[str, Person]
    rounds: list[Round]
    overrides: Overrides

    def __contains__(self, item):
        return item in self.people

    def __getitem__(self, item):
        return self.people[item]

    def __iter__(self):
        return iter(self.people)

    def __len__(self):
        return len(self.people)


@dataclass(frozen=True)
class Solution:
    pairs: dict[Person, Pair]
    cost: int
    optimal_pair_indices: list[tuple[int, int]]
    config: Config
    why: dict[frozenset[Person], list[str]]


@dataclass(frozen=True)
class RoundConfig:
    people: dict[str, Person]
    previous_rounds: list[Round]
    overrides: Overrides
    notes: str

    def __contains__(self, item):
        return item in self.people

    def __getitem__(self, item):
        return self.people[item]

    def __iter__(self):
        return iter(self.people)

    def __len__(self):
        return len(self.people)


# load people from a csv file


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
