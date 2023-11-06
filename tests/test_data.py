import datetime
from pathlib import Path

import pytest
import tomlkit
from textwrap import dedent

from colette.models import RoundConfig, Solution, Pair, Person


@pytest.fixture(scope="session")
def people():
    people_csv_data = dedent(
        """name,organisation,email,active
    Alice,someplace,alice@example.com,True
    Bob,anotherplace,bob@example.com,True
    Charlie,someplace,charlie@example.com,True
    Dave,someplace,dave@example.com,True
    Eve,someother,Eve@example.com,True
    Frank,anotherplace,frank@blag.com,True
    """
    )

    return Person.loads(people_csv_data)


def test_loads(people: dict[str, Person]):
    print(people)

    s = tomlkit.dumps(
        {
            "number": 2,
            "date": datetime.date(2022, 1, 1),
            "remove": [
                {"name": "Alice", "until": 3},
                {"name": "Bob", "until": datetime.date(2022, 1, 1)},
                {"name": "Charlie"},
                {"name": "Dave", "until": datetime.date(2021, 1, 1)},
                {"name": "Eve", "until": datetime.date(2022, 1, 2)},
                {"name": "Frank", "until": 2},
            ],
            "override": [
                {"pair": ["Alice", "Bob"], "weight": 10},
                {"pair": ["Charlie", "Dave"], "weight": 5},
                {"pair": ["Eve", "Frank"], "weight": -10},
            ],
            "notes": "This is a test",
        }
    )

    config = RoundConfig.loads(s, people=people)

    assert config.number == 2
    assert len(config.people) == 6
    print([p.name for p in config.people.values() if p.active])

    # Alice, Charlie and Eve should be removed
    assert not config.people["Alice"].active
    assert not config.people["Charlie"].active
    assert not config.people["Eve"].active

    # Bob, Dave and Frank should be active
    assert config.people["Bob"].active
    assert config.people["Dave"].active
    assert config.people["Frank"].active

    assert len([p for p in config.people.values() if p.active]) == 3
    assert config.date == datetime.date(2022, 1, 1)
    assert config.overrides.get_weight("Alice", "Bob") == 10
    assert config.overrides.get_weight("Charlie", "Dave") == 5
    assert config.notes == "This is a test"

    # Check that giving an unknown key to [[remove]] raises an error
    s = """
    number = 2
    date = 2022-01-01
    
    [[remove]]
    name = "Alice"
    round = 3
    """

    with pytest.raises(ValueError):
        RoundConfig.loads(s, people=people)

    # Check that giving an unknown key to [[override]] raises an error
    s = """
    number = 2
    date = 2022-01-01

    [[override]]
    pair = ["Alice", "Bob"]
    weight = 10
    blag = 10
    """

    with pytest.raises(ValueError):
        RoundConfig.loads(s, people=people)


@pytest.fixture()
def solution(people):
    pairs = frozenset(
        {
            Pair(primary=people["Alice"], secondary=people["Bob"]),
            Pair(primary=people["Charlie"], secondary=people["Dave"]),
            Pair(primary=people["Eve"], secondary=people["Frank"]),
        }
    )

    caviats = {
        Pair(primary=people["Alice"], secondary=people["Bob"]): ["override values 10"],
        Pair(primary=people["Charlie"], secondary=people["Dave"]): [
            "paired last round"
        ],
    }

    return Solution(round=1, pairs=pairs, cost=10, caviats=caviats)


def test_solution_dumps(solution):
    toml_str = solution.dumps()
    print(toml_str)
    d = tomlkit.loads(toml_str)

    assert d["cost"] == 10

    pairs = d["pair"]
    assert len(pairs) == 3

    alice_bob = pairs[0]
    assert alice_bob["primary"] == "Alice"
    assert alice_bob["secondary"] == "Bob"
    assert alice_bob["caviats"] == ["override values 10"]

    charlie_dave = pairs[1]
    assert charlie_dave["primary"] == "Charlie"
    assert charlie_dave["secondary"] == "Dave"
    assert charlie_dave["caviats"] == ["paired last round"]

    eve_frank = pairs[2]
    assert eve_frank["primary"] == "Eve"
    assert eve_frank["secondary"] == "Frank"
    assert "caviats" not in eve_frank


def test_solution_loads(people):
    toml_str = """
    cost = 10
    round = 1

    [[pair]]
    primary = "Alice"
    secondary = "Bob"
    caviats = ["override values 10"]

    [[pair]]
    primary = "Charlie"
    secondary = "Dave"
    caviats = ["paired last round"]

    [[pair]]
    primary = "Eve"
    secondary = "Frank"
    """

    s = Solution.loads(people=people, s=toml_str)

    assert s.cost == 10

    pairs = s.pairs
    assert len(pairs) == 3

    alice = people["Alice"]
    bob = people["Bob"]
    charlie = people["Charlie"]
    dave = people["Dave"]
    eve = people["Eve"]
    frank = people["Frank"]

    # Check that all pairs are in the loads pairs
    assert Pair(alice, bob) in pairs
    assert Pair(charlie, dave) in pairs
    assert Pair(eve, frank) in pairs


def test_loads_with_costs(people):
    config = RoundConfig.loads(
        tomlkit.dumps(
            {
                "number": 2,
                "date": datetime.date(2022, 1, 1),
                "remove": [
                    {"name": "Alice", "until": 2},
                    {"name": "Bob", "until": datetime.date(2022, 1, 1)},
                    {"name": "Charlie"},
                    {"name": "Dave", "until": datetime.date(2021, 1, 1)},
                ],
                "override": [
                    {"pair": ["Alice", "Bob"], "weight": 10},
                    {"pair": ["Charlie", "Dave"], "weight": 5},
                    {"pair": ["Eve", "Frank"], "weight": -10},
                ],
                "cost_of_pairing_same_type": 2,
                "cost_of_not_pairing": 100,
                "cost_of_pairing_within_org": 20,
                "cost_of_pairing_previous_partner_one_round_ago": 1000000,
                "cost_of_pairing_previous_partner_two_to_n_round_ago": 500,
                "cost_of_pairing_previous_partner_n": 15,
                "notes": "This is a test",
            }
        ),
        people=people,
    )

    assert config.number == 2
    assert len(config.people) == 6
    assert config.date == datetime.date(2022, 1, 1)
    assert config.overrides.get_weight("Alice", "Bob") == 10
    assert config.overrides.get_weight("Charlie", "Dave") == 5
    assert config.notes == "This is a test"
    assert config.cost_of_pairing_same_type == 2
    assert config.cost_of_not_pairing == 100
    assert config.cost_of_pairing_within_org == 20
    assert config.cost_of_pairing_previous_partner_one_round_ago == 1000000
    assert config.cost_of_pairing_previous_partner_two_to_n_round_ago == 500
    assert config.cost_of_pairing_previous_partner_n == 15


def test_loads_with_invalid_costs(people):
    with pytest.raises(TypeError):
        RoundConfig.loads(
            tomlkit.dumps(
                {
                    "number": 2,
                    "date": datetime.date(2022, 1, 1),
                    "cost_of_pairing_same_type": 2.5,  # invalid type
                    "cost_of_not_pairing": "100",  # invalid type
                    "cost_of_pairing_within_org": 20,
                    "cost_of_pairing_previous_partner_one_round_ago": 1000000,
                    "cost_of_pairing_previous_partner_two_to_n_round_ago": 500,
                    "cost_of_pairing_previous_partner_n": 15,
                    "notes": "This is a test",
                }
            ),
            people=people,
        )


def test_people_loads_invalid_header():
    people_csv_data = """name,organisation,email,active
    Alice,someplace,alice@example.com,True
    Bob,anotherplace,bob@example.com,True
    Charlie,someplace,charlie@example.com,True
    Dave,someplace,dave@example.com,True
    Eve,someother,Eve@example.com,True
    Frank,anotherplace,frank@blag.com,True
    """

    # Change the header to an invalid one
    people_csv_data = people_csv_data.replace(
        "name,organisation,email,active", "name,organisation,active,email"
    )

    with pytest.raises(ValueError):
        Person.loads(people_csv_data)


def test_loads_invalid_csv():
    people_csv_data = """name,organisation,email,active
    Alice,someplace,alice@example.com,True
    Bob,anotherplace,bob@example.com,True
    Charlie,someplace,charlie@example.com,True
    Dave,someplace,dave@example.com,True
    Eve,someother,Eve@example.com,True
    Frank,anotherplace,frank@blag.com,True
    """

    # Remove the email field from one of the rows
    people_csv_data = people_csv_data.replace(
        "alice@example.com,True", "alice@example.com,True,"
    )

    with pytest.raises(ValueError):
        Person.loads(people_csv_data)


def test_loads_valid_csv():
    people_csv_data = """name,organisation,email,active
    Alice,someplace,alice@example.com,True
    Bob,anotherplace,bob@example.com,True
    Charlie,someplace,charlie@example.com,True
    Dave,someplace,dave@example.com,True
    Eve,someother,Eve@example.com,True
    Frank,anotherplace,frank@blag.com,True
    """

    people = Person.loads(people_csv_data)

    assert len(people) == 6
    assert "Alice" in people
    assert "Bob" in people
    assert "Charlie" in people
    assert "Dave" in people
    assert "Eve" in people
    assert "Frank" in people


def test_loads_empty_csv():
    people_csv_data = "name,organisation,email,active"

    people = Person.loads(people_csv_data)

    assert len(people) == 0


def test_loads_csv(people):
    csv_data = dedent(
        """\
        primary,secondary
        Alice,Bob
        Charlie,Dave
        """,
    )
    print(csv_data)

    solution = Solution.loads_csv(csv_data, people, round=1)

    assert solution.round == 1
    assert solution.cost == -1
    assert solution.caviats == {}

    pairs = solution.pairs
    assert len(pairs) == 2

    alice = people["Alice"]
    bob = people["Bob"]
    charlie = people["Charlie"]
    dave = people["Dave"]

    # Check that all pairs are in the loads pairs
    assert Pair(alice, bob) in pairs
    assert Pair(charlie, dave) in pairs

    # Check that unknown people raise an error
    csv_data = dedent(
        """
        primary,secondary
        Alice,Bob
        Charlie,Unknown
        """
    )

    with pytest.raises(ValueError):
        Solution.loads_csv(csv_data, people, round=1)
