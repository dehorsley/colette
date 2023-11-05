import sys
import argparse
from os import PathLike
from textwrap import dedent
import warnings

from inspect import signature

# from colette import email
from colette import solver
import colette.storage
from dataclasses import replace


def email():
    raise NotImplementedError()


def new_round_from_path(path: PathLike):
    storage = colette.storage.FileStorage(path)
    people = storage.load_people()
    previous_rounds = storage.load_previous_rounds(people)

    next_round = len(previous_rounds) + 1

    # If there is a round config for the next round, load that
    try:
        round_config = storage.load_round_config(next_round, people)
    except FileNotFoundError as e:
        # make warning

        warnings.warn(
            dedent(
                f"""
            No round config for round {next_round}. Creating a basic config at {e.filename}.

            If you wish to customise this round, please edit this file and delete
            the solution file at {e.filename.replace("round", "solution")} 
            """
            )
        ),

        round_config = solver.RoundConfig(
            number=next_round,
            people=people,
            overrides={},
        )

        storage.store_round_config(round_config)

    solution = solver.solve_round(round_config, previous_rounds=previous_rounds)
    storage.store_solution(solution)


def main():
    parser = argparse.ArgumentParser(
        "colette",
        description="""\
            Manage a series of coffee roulette sessions!
        """,
    )
    parser.add_argument(
        "--path",
        "-p",
        help="path to directory containing people and round data (default '.')",
        default=".",
    )
    subparsers = parser.add_subparsers(title="commands")

    new_parser = subparsers.add_parser(
        "new",
        help="create a new round",
        description="""
            create a new round. The list of pairings is saved in round_N.csv in
            the data directory, where N is the current round, inferred from the
            CSV files in the data directory.
    """,
    )
    new_parser.set_defaults(func=new_round_from_path)

    email_parser = subparsers.add_parser(
        "email",
        help="email the participants of a round",
        description="""
        email the participants of the last round — or the round specified — their partner and role.
        """,
    )
    email_parser.add_argument(
        "--round",
        "-n",
        help="the number of the round to send the email notification to.",
        type=int,
    )

    email_parser.set_defaults(func=email)

    args = parser.parse_args()
    if "func" not in vars(args):
        parser.print_help()
        sys.exit(1)

    args.func(
        **{k: v for k, v in vars(args).items() if k in signature(args.func).parameters}
    )


if __name__ == "__main__":
    main()
