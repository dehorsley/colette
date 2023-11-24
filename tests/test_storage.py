from pathlib import Path

import pytest

from colette.models import Person, RoundConfig
from colette.storage import FileStorage


@pytest.fixture
def file_storage(tmp_path):
    tmp_path = Path(tmp_path)
    return FileStorage(tmp_path)


@pytest.fixture
def people():
    return {
        "Alice": Person(
            name="Alice", organisation="Org1", active=True, email="alice@org1.com"
        ),
        "Bob": Person(
            name="Bob", organisation="Org2", active=False, email="bob@org2.com"
        ),
    }


def test_store_round_config(file_storage, tmp_path, people):
    tmp_path = Path(tmp_path)
    round_config = RoundConfig(number=1, people=people)
    file_storage.store_round_config(round_config)

    round_config_file = tmp_path / "round_000001.toml"
    assert round_config_file.exists()


def test_load_round_config(file_storage, tmp_path, people):
    round_number = 1

    round_config = RoundConfig(number=round_number, people=people)
    file_storage.store_round_config(round_config)

    round_config = file_storage.load_round_config(round_number, people)

    assert round_config.number == round_number


def test_load_solutions(file_storage, tmp_path, people):
    solutions = file_storage.load_solutions(people)

    assert len(solutions) == 0


def test_load_people(file_storage, tmp_path):
    people_file = tmp_path / "people.csv"
    people_file.write_text(
        "name,organisation,active,email\nAlice,Org1,True,alice@example.com"
    )

    people = file_storage.load_people()

    assert len(people) == 1
    assert "Alice" in people
    assert people["Alice"].name == "Alice"


def test_load_people_file_not_found(file_storage):
    with pytest.raises(FileNotFoundError):
        file_storage.load_people()
