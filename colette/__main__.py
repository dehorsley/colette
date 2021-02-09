import sys
import argparse

from inspect import signature

from colette import email, new_round_from_path


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
