import argparse
import configparser
import os
import sys
from inspect import signature
from os import PathLike
from textwrap import dedent

import tomlkit

from . import __version__, solver, storage
from .email import render_messages


def email(path: PathLike, round: int = None, preview=True):
    stor = storage.FileStorage(path)
    people = stor.load_people()
    previous_solutions = stor.load_solutions(people)

    if round is None:
        # infer round from existing solution files
        round = len(previous_solutions)
        print(f"Sending emails for {round=}...")

    # check for email.ini and parse it
    if os.path.exists("email.ini"):
        from .email.smtp import SmtpClient

        config = configparser.ConfigParser()
        config.read("email.ini")
        send_email = SmtpClient(config).send_email

    # TODO detect email client

    # if email.ini exists, use that
    # if not, try to detect email client
    # if not, ask user to select email client

    if sys.platform == "darwin":
        from colette.email.outlook_macos import send_email
    elif sys.platform == "win32":
        from colette.email.outlook_windows import send_email
    else:
        raise RuntimeError(f"Unsupported platform {sys.platform}")

    solution = previous_solutions[round - 1]
    round_config = stor.load_round_config(round, people)
    msgs = render_messages(solution, round_config)
    send_email(msgs, preview=preview)


def new_round_config(path: PathLike, date: str = None):
    if date is None:
        date = input("Date of next round (YYYY-MM-DD): ")

    date = tomlkit.date(date.strip())

    store = storage.FileStorage(path)
    people = store.load_people()
    previous_rounds = store.load_solutions(people)

    last_round = len(previous_rounds)
    new_round = last_round + 1

    previous_round_config_path = store.path / f"round_{last_round:06d}.toml"

    if previous_round_config_path.exists():
        new_round_config = tomlkit.parse(previous_round_config_path.read_text())

        new_round_config["number"] = new_round
        new_round_config["date"] = date

        # remove [[remove]] blocks whose 'until' date or round has passed
        n_removed = 0
        for i, remove_block in list(enumerate(new_round_config["remove"])):
            # we do it this way to preserve comments

            name = remove_block["name"]
            if isinstance(remove_block["until"], tomlkit.items.Date):
                if remove_block["until"] < date:
                    print(f"Adding {name} back into the pool")
                    del new_round_config["remove"][i - n_removed]
                    n_removed += 1
                continue

            if isinstance(remove_block["until"], tomlkit.items.Integer):
                if remove_block["until"] < new_round:
                    print(f"Adding {name} back into the pool")
                    del new_round_config["remove"][i - n_removed]
                    n_removed += 1
                continue

            # error if neither date nor round
            raise ValueError(
                f"Invalid 'until' value for remove block {i}: {remove_block['until']}"
                f"of type {type(remove_block['until'])}"
            )

    else:
        new_round_config = tomlkit.document()

        new_round_config["number"] = new_round
        new_round_config["date"] = date

    # save new round config
    new_round_config_path = store.path / f"round_{new_round:06d}.toml"
    if new_round_config_path.exists():
        raise RuntimeError(f"Round config {new_round_config_path} already exists")
    new_round_config_path.write_text(tomlkit.dumps(new_round_config))

    print(f"Created round config for round {new_round}")


def pair_from_path(path: PathLike):
    store = storage.FileStorage(path)
    people = store.load_people()
    previous_rounds = store.load_solutions(people)

    next_round = len(previous_rounds) + 1

    # If there is a round config for the next round, load that
    try:
        round_config = store.load_round_config(next_round, people)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"No round config found for round {next_round}. Create one with `colette new`"
        ) from e

    solution = solver.solve_round(round_config, previous_rounds=previous_rounds)

    print(f"Found pairing for round {next_round}!")

    if solution.cost > 0:
        print(f"Total cost: {solution.cost}")
        ## print caveats
        for pair, caveats in solution.caviats.items():
            if len(caveats) == 0:
                continue

            if pair.primary == pair.secondary:
                print(f"{pair.primary.name}")
            else:
                print(f"{pair.primary.name} and {pair.secondary.name}")
            for caveat in caveats:
                print(f"  - {caveat}")

    store.store_solution(solution)
    store.store_solution(solution, type="csv")


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
        help="create a new round configuration",
        description=dedent(
            """\
            create a new round configuration. If a previous round configuration
            (ie round_nnnnnn.toml) exists, it will be copied and updated with the
            following:

            - round number will be incremented
            - [[remove]] blocks whose 'unitl' date or round has passed will be removed

            TIP: do this early and you can add [[remove]] blocks throughout the
            period between rounds as people go on leave, etc.
            """
        ),
    )
    new_parser.add_argument(
        "date",
        help="date of the next round (YYYY-MM-DD)",
    )
    new_parser.set_defaults(func=new_round_config)

    pair_parser = subparsers.add_parser(
        "pair",
        help="create pairs for a round",
        description=dedent(
            """\
            create pairs for a round. If no round is specified, the last round without a
            solution will be used. If no round config exists, a new one will
            be created and solved.
            """
        ),
    )
    pair_parser.set_defaults(func=pair_from_path)

    email_parser = subparsers.add_parser(
        "email",
        help="email the participants of a round",
        description=dedent(
            """\
        email the participants of the last round — or the round specified —
        their partner and role.  
        """
        ),
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

    version_parser = subparsers.add_parser(
        "version",
        help="print the version number",
    )
    version_parser.set_defaults(func=lambda: print(__version__))

    args = parser.parse_args()
    if "func" not in vars(args):
        parser.print_help()
        sys.exit(1)

    args.func(
        **{k: v for k, v in vars(args).items() if k in signature(args.func).parameters}
    )


if __name__ == "__main__":
    main()
