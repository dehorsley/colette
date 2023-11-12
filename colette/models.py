import io
import csv
import datetime
from copy import copy
from dataclasses import dataclass, field, replace
from os import PathLike
from typing import Union, TextIO

import tomlkit


@dataclass(frozen=True, order=True)
class Person:
    name: str
    organisation: str
    active: bool
    email: str

    @staticmethod
    def loads(s: str) -> dict[str, "Person"]:
        """
        Example CSV file:

        name,organisation,active,email
        Alice,Org1,True,alice@blag.com
        Bob,Org2,True,bob@org2.com
        Charlie,Org1,True,charlie@org1.com
        """

        f = io.StringIO(s)
        return Person.load(f)

    @staticmethod
    def load(f: TextIO) -> dict[str, "Person"]:
        """
        Load a dictionary of Person objects from a CSV file.

        Args:
            f (TextIO): A file-like object containing CSV data. Must have the
            following columns:

                    name,organisation,active,email

        Returns:
            dict[str, Person]: A dictionary of Person objects, keyed by name.

        Raises:
            KeyError: If the CSV file is missing any of the required columns.
        """
        people = {}

        reader = csv.DictReader(f, restval="")

        try:
            for i, row in enumerate(reader):
                name = row["name"]
                if name in people:
                    raise ValueError(f"Duplicate name {name} on line {i + 2}")

                if name == "":
                    raise ValueError(f"Missing name on line {i + 2}")

                org = row["organisation"]
                email = row["email"]
                active = row["active"].lower() in {"true", "yes", "1", ""}

                people[name] = Person(
                    name=name,
                    email=email,
                    organisation=org,
                    active=active,
                )

        except KeyError as e:
            raise KeyError(
                f"people.csv missing field '{e.args[0]}', "
                "must have at least the following fields:\n"
                "name, organisation, email, active"
            ) from e

        return people


@dataclass(frozen=True, order=True)
class Pair:
    primary: Person
    secondary: Person

    def __contains__(self, item):
        return self.primary == item or self.secondary == item


@dataclass
class Overrides:
    pair_weights: dict[frozenset[Person], int] = field(default_factory=dict)

    def __contains__(self, item):
        return item in self.pair_weights

    def __iter__(self):
        return iter(self.pair_weights)

    def __getitem__(self, item):
        return self.pair_weights[item]

    def __len__(self):
        return len(self.pair_weights)

    def get_weight(self, p1: str, p2: str) -> int:
        s = {p1, p2}
        for pair, weight in self.pair_weights.items():
            if s == {p.name for p in pair}:
                return weight


@dataclass(frozen=True)
class RoundConfig:
    number: int
    people: dict[str, Person]
    date: datetime.date = field(default_factory=datetime.date.today)
    overrides: Overrides = field(default_factory=Overrides)
    removals: list[tuple[Person, Union[int, datetime.date]]] = field(
        default_factory=list
    )
    notes: str = field(default="")

    # Cost of pairing people of the same type (primary/secondary) together,
    # should be quite low. Role meanings are up to the user, but can be used
    # for instance to assign one player an organiser role, and another a buyer
    # role.
    cost_of_pairing_same_type: int = field(default=1)

    # Cost of taking a person out of the round should be quite a lot higher than
    # the cost of pairing within org
    cost_of_not_pairing: int = field(default=50)

    # Cost of paring people within the same organisation. Should be lower than
    # cost_of_not_pairing
    cost_of_pairing_within_org: int = field(default=10)

    # Cost of paring with partner from last round.
    # Should be a big number. Really don't want to pair people together *just*
    # after they paired
    cost_of_pairing_previous_partner_one_round_ago: int = field(default=1_000_000)

    # Cost of pairing players that were previously paired between 2 to N rounds
    # ago
    cost_of_pairing_previous_partner_two_to_n_round_ago: int = field(default=50)

    # Number of round before a previous pairing doesn't matter anymore.
    # This should be roughtly the number of people in the pool - 1.
    cost_of_pairing_previous_partner_n: int = field(default=10)

    def __contains__(self, item):
        return item in self.people

    def __getitem__(self, item):
        return self.people[item]

    def __iter__(self):
        return iter(self.people)

    def __len__(self):
        return len(self.people)

    @staticmethod
    def load(path: PathLike, people: dict[str, Person]) -> "RoundConfig":
        with open(path) as f:
            return RoundConfig.loads(f.read(), people=people)

    @staticmethod
    def loads(s: str, people: dict[str, Person]) -> "RoundConfig":
        d = tomlkit.loads(s)

        people = copy(people)

        number = d.get("number", 1)

        round_date = d.get("date", datetime.date.today())

        # Remove people from the round
        for r in d.get("remove", []):
            # check only keys are name and until:
            for k in r.keys():
                if k not in {"name", "until"}:
                    raise ValueError(f"unknown key {k} in [[remove]] table")

            match r:
                case {"name": name, "until": int(round)}:
                    if round > number:
                        people[name] = replace(people[name], active=False)

                case {"name": name, "until": date}:
                    if date > round_date:
                        people[name] = replace(people[name], active=False)

                case {"name": name}:
                    people[name] = replace(people[name], active=False)

                case _:
                    raise ValueError("'remove' must be a dict with name and until keys")

        overrides = {}

        for o in d.get("override", []):
            for k in o.keys():
                if k not in {"pair", "weight"}:
                    raise ValueError(f"unknown key {k} in [[override]] table")
            match o:
                case {"pair": [p1, p2], "weight": int(weight)}:
                    pair = frozenset({people[p1], people[p2]})
                    overrides[pair] = weight
                case {"weight": _}:
                    raise ValueError("weight must be an integer")
                case {"pair": _}:
                    raise ValueError("pair must be a list of two names")

        # load costs, will dataclass defaults if not specified in toml
        costs = {k: d[k] for k in vars(RoundConfig) if k.startswith("cost_") and k in d}

        # check all costs are ints otherwise raise a type error:
        for k, v in costs.items():
            if not isinstance(v, int):
                raise TypeError(f"{k} must be an integer")

        return RoundConfig(
            number=number,
            people=people,
            date=round_date,
            overrides=Overrides(overrides),
            notes=d.get("notes", ""),
            **costs,
        )

    def dumps(self) -> str:
        doc = tomlkit.document()
        doc.add("number", self.number)
        doc.add("date", self.date)

        if self.notes:
            doc.add("notes", self.notes)

        doc.add(tomlkit.nl())
        doc.add(tomlkit.comment("costs"))
        doc.add(tomlkit.comment("you probably don't need to mess with these"))
        for k, v in vars(RoundConfig).items():
            if k.startswith("cost_"):
                doc.add(k, v)

        if len(self.overrides) > 0:
            override_table = tomlkit.aot()
            for pair, weight in self.overrides.pair_weights.items():
                override_table.append(
                    tomlkit.item(
                        {"pair": list([p.name for p in pair]), "weight": weight}
                    )
                )
            doc.add("override", override_table)

        if len(self.people) > 0:
            remove_table = tomlkit.aot()
            for name, person in self.people.items():
                if not person.active:
                    remove_table.append(tomlkit.item({"name": name}))
            doc.add("remove", remove_table)

        return tomlkit.dumps(doc)

    def dump(self, path: PathLike):
        with open(path, "w") as f:
            f.write(self.dumps())


@dataclass
class Solution:
    cost: int
    round: int
    pairs: frozenset[Pair]
    caviats: dict[Pair, list[str]]

    def __contains__(self, item):
        # if item is a set of people,
        # need to check both orders of the pair
        if isinstance(item, (frozenset, set)):
            if len(item) == 1:
                p = item.pop()
                return Pair(p, p) in self.pairs
            p1, p2 = item
            return Pair(p1, p2) in self.pairs or Pair(p2, p1) in self.pairs

        if isinstance(item, Person):
            for pair in self.pairs:
                if item in pair:
                    return True
            return False
        return item in self.pairs

    # subscript
    def __getitem__(self, item):
        if isinstance(item, Person):
            for pair in self.pairs:
                if item in pair:
                    return pair
            raise KeyError(f"{item} not in solution")
        raise TypeError("solution can only be subscripted by a Person")

    def dumps(self) -> str:
        doc = tomlkit.document()
        doc.add("cost", self.cost)
        doc.add("round", self.round)

        pair_table = tomlkit.aot()

        # sorted so that the output is deterministic
        pairs = sorted(self.pairs)

        for pair in pairs:
            d = {"primary": pair.primary.name, "secondary": pair.secondary.name}
            if pair in self.caviats:
                d["caviats"] = self.caviats[pair]
            pair_table.append(tomlkit.item(d))

        doc.add("pair", pair_table)

        return tomlkit.dumps(doc)

    def dump(self, path: PathLike):
        with open(path, "w") as f:
            f.write(self.dumps())

    @staticmethod
    def load(
        path: PathLike,
        people: dict[str, Person],
    ) -> "Solution":
        with open(path) as f:
            return Solution.loads(f.read(), people=people)

    @staticmethod
    def loads(
        s: str,
        people: dict[str, Person],
    ) -> "Solution":
        """
        Example toml file:

        cost = 10
        round = 10

        [[pair]]
        primary = "Alice"
        secondary = "Bob"
        caviats = ["override values 10"]

        [[pair]]
        primary = "Charlie"
        secondary = "Dave"
        caviats = ["paired last round"]
        """
        d = tomlkit.loads(s)

        cost = d["cost"]
        round = d["round"]
        raw_pairs = d["pair"]

        pairs = set()
        caviats = {}

        for p in raw_pairs:
            if "primary" not in p or "secondary" not in p:
                raise ValueError(
                    "pairs must be a list of dicts with 'primary' and 'secondary' keys"
                )
            p1 = p["primary"]
            p2 = p["secondary"]
            if p1 not in people:
                raise ValueError(f"unknown person {p1}")
            if p2 not in people:
                raise ValueError(f"unknown person {p2}")

            pair = Pair(primary=people[p1], secondary=people[p2])

            pairs.add(pair)

            if "caviats" in p:
                caviats[pair] = p["caviats"]

        return Solution(round=round, pairs=pairs, cost=cost, caviats=caviats)

    @staticmethod
    def loads_csv(s: str, people: dict[str, Person], round: int) -> "Solution":
        """
        older style csv file, round needs to be infered from filename

        optionaly add caviats by adding a semicolon separated list of caviats


        Example CSV file:

        primary,secondary
        Alice,Bob
        Charlie,Dave
        """
        csv_reader = csv.DictReader(s.split("\n"))

        pairs = set()

        caviats = {}

        for p in csv_reader:
            if "primary" not in p or "secondary" not in p:
                raise ValueError(
                    "pairs must be a list of dicts with 'primary' and 'secondary' keys"
                )
            p1 = p["primary"]
            p2 = p["secondary"]
            if p1 not in people:
                raise ValueError(f"unknown person {p1}")
            if p2 not in people:
                raise ValueError(f"unknown person {p2}")

            pair = Pair(primary=people[p1], secondary=people[p2])

            if "caviats" in p:
                caviats[pair] = p["caviats"].split(";")

            pairs.add(pair)
        return Solution(round=round, pairs=pairs, cost=-1, caviats=caviats)

    def dumps_csv(self) -> str:
        """
        older style csv file, round needs to be infered from filename


        Example CSV file:

        primary,secondary
        Alice,Bob
        Charlie,Dave
        """
        s = "primary,secondary,caviets\n"

        for pair in self.pairs:
            s += f"{pair.primary.name},{pair.secondary.name},"
            if pair in self.caviats:
                s += ";".join(self.caviats[pair])
            s += "\n"

        return s

    def dump_csv(self, path: PathLike):
        with open(path, "w") as f:
            f.write(self.dumps_csv())
