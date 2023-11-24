from abc import ABC, abstractmethod
from os import PathLike
from pathlib import Path
from textwrap import dedent

from .models import Person, RoundConfig, Solution


class Storage(ABC):
    @abstractmethod
    def store_round_config(self, round_config: RoundConfig):
        raise NotImplementedError()

    @abstractmethod
    def store_solution(self, solution: Solution):
        raise NotImplementedError()

    @abstractmethod
    def store_people(self, people: dict[str, Person]):
        raise NotImplementedError()

    @abstractmethod
    def load_round_config(
        self, round_number: int, people: dict[str, Person]
    ) -> RoundConfig:
        raise NotImplementedError()

    @abstractmethod
    def load_solution(self, round_number: int, people: dict[str, Person]) -> Solution:
        raise NotImplementedError()

    @abstractmethod
    def load_solutions(self, people: dict[str, Person]) -> list[Solution]:
        raise NotImplementedError()

    @abstractmethod
    def load_people(self) -> dict[str, Person]:
        raise NotImplementedError()

    @abstractmethod
    def num_rounds(self) -> int:
        raise NotImplementedError()

    @abstractmethod
    def num_people(self) -> int:
        raise NotImplementedError()

    @abstractmethod
    def previous_solution(self) -> Solution:
        raise NotImplementedError()


class FileStorage(Storage):
    def __init__(self, path: PathLike):
        self.path = Path(path)

    def store_round_config(self, round_config: RoundConfig):
        round_config_file = self.path / f"round_{round_config.number:06d}.toml"
        round_config.dump(round_config_file)

    def store_solution(self, solution: Solution, type="toml"):
        if type == "toml":
            solution_file = self.path / f"solution_{solution.round:06d}.toml"
            solution.dump(solution_file)
        elif type == "csv":
            solution_file = self.path / f"solution_{solution.round:06d}.csv"
            solution.dump_csv(solution_file)
        else:
            raise ValueError(f"Unknown solution type {type}")

    def store_people(self, people: dict[str, Person]):
        path = self.path / "people.csv"
        Person.dump_csv(path, people.values())

    def load_round_config(
        self,
        round_number: int,
        people: dict[str, Person],
    ) -> RoundConfig:
        round_config_file = self.path / f"round_{round_number:06d}.toml"
        return RoundConfig.load(round_config_file, people)

    def load_solution(
        self,
        round_number: int,
        people: dict[str, Person],
    ) -> Solution:
        solution_file = self.path / f"solution_{round_number:06d}.toml"
        return Solution.load(solution_file, people)

    def load_solutions(self, people) -> list[Solution]:
        toml_solutions = [
            Solution.load(file, people) for file in self.path.glob("solution_*.toml")
        ]

        csv_files = self.path.glob("solution_*.csv")
        for csv_file in csv_files:
            toml_file = csv_file.with_suffix(".toml")
            if toml_file.exists():
                continue

            round = int(csv_file.stem.split("_")[1])

            toml_solutions.append(
                Solution.loads_csv(csv_file.read_text(), people, round)
            )
        toml_solutions.sort(key=lambda s: s.round)

        return toml_solutions

    def load_people(self) -> dict[str, Person]:
        path = self.path / "people.csv"

        if not path.exists():
            raise FileNotFoundError(
                dedent(
                    f"""
                    people.csv not found at {path.absolute()}
                    Please create a people.csv file with the following columns:

                        name,organisation,available,email

                    and at least one row of data.
                    """
                )
            )

        with path.open() as f:
            people = Person.load(f)

        return people

    def num_rounds(self) -> int:
        raise NotImplementedError()

    def num_people(self) -> int:
        people = self.load_people()
        return len(people)

    def previous_solution(self) -> Solution:
        raise NotImplementedError()
