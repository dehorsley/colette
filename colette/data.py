import csv
from os import PathLike
from copy import copy
import datetime
from dataclasses import dataclass, replace, field

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
        Alice,Org1,True,
        Bob,Org2,True,
        Charlie,Org1,True,
        """

        people = {}
        lines = s.strip().split("\n")

        # check the first line is the header
        if lines[0] != "name,organisation,email,active":
            raise ValueError(
                "people.csv must have the following header:\n"
                "name,organisation,email,active"
            )

        for line in lines[1:]:
            name, org, email, active = line.split(",")
            name = name.strip()
            active = active.strip().lower() in {"true", "yes", "1"}
            people[name] = Person(
                name=name,
                email=email,
                organisation=org,
                active=active,
            )

        return people

    @staticmethod
    def load(path: PathLike) -> dict[str, "Person"]:
        with open(path) as f:
            return Person.loads(f.read())


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
                        print(f"removing {name} until round {round}")
                        people[name] = replace(people[name], active=False)

                case {"name": name, "until": date}:
                    if date > round_date:
                        print(f"removing {name} until {date}")
                        people[name] = replace(people[name], active=False)

                case {"name": name}:
                    print(f"removing {name}")
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

    def loads_csv(s: str, people: dict[str, Person], round: int) -> "Solution":
        """
        older style csv file, round needs to be infered from filename
        Example CSV file:

        primary,secondary
        Alice,Bob
        Charlie,Dave
        """
        csv_reader = csv.DictReader(s.split("\n"))

        pairs = set()

        for p in csv_reader:
            print(p)
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
        return Solution(round=round, pairs=pairs, cost=-1, caviats={})
