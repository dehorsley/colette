import sys
import argparse
from os import PathLike
from textwrap import dedent
import warnings

from inspect import signature

from colette import solver
import colette.storage


def email(path: PathLike, round: int = None, preview=True):
    storage = colette.storage.FileStorage(path)
    people = storage.load_people()
    previous_solutions = storage.load_solutions(people)

    if round is None:
        # infer round from existing solution files
        round = len(previous_solutions)
        print(f"Sending emails for {round=}...")

    # todo detect email client

    ## outlook of macos

    email_class = None
    if sys.platform == "darwin":
        from colette.email import outlook_macos

        email_class = outlook_macos.OutlookMacOSEmail

    elif sys.platform == "linux":
        raise NotImplementedError("Linux email client not implemented")
    elif sys.platform == "win32":
        raise NotImplementedError("Windows email client not implemented")
    else:
        raise RuntimeError(f"Unsupported platform {sys.platform}")

    emailer = email_class("templates")

    solution = previous_solutions[round - 1]
    round_config = storage.load_round_config(round, people)
    emailer.send_email(solution, round_config, preview=preview)


def new_round_from_path(path: PathLike):
    storage = colette.storage.FileStorage(path)
    people = storage.load_people()
    previous_rounds = storage.load_solutions(people)

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
    storage.store_solution(solution, type="csv")


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
    email_parser.add_argument(
        "--no-preview",
        "-p",
        dest="preview",
        default=True,
        action="store_false",
        help="don't preview the email before sending",
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
