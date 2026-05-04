import datetime
from textwrap import dedent

import tomlkit

from colette.__main__ import new_round_config


def test_new_round_config_without_previous_remove_block(tmp_path):
    # Regression test for #23
    (tmp_path / "people.csv").write_text(dedent("""\
            name,organisation,email,active
            Alice,Org1,alice@example.com,True
            Bob,Org2,bob@example.com,True
            """))

    (tmp_path / "solution_000001.toml").write_text(dedent("""\
            cost = 0
            round = 1

            [[pair]]
            primary = "Alice"
            secondary = "Bob"
            """))

    # No [[remove]] block in previous config.
    (tmp_path / "round_000001.toml").write_text(dedent("""\
            number = 1
            date = 2026-05-01
            """))

    new_round_config(tmp_path, date="2026-05-08")

    created_config = tomlkit.parse((tmp_path / "round_000002.toml").read_text())
    assert created_config["number"] == 2
    assert created_config["date"] == datetime.date(2026, 5, 8)
