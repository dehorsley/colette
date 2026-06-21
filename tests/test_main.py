import datetime
from textwrap import dedent

import pytest
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


def test_new_round_config_invalid_remove_until_raises_value_error(tmp_path):
    # Regression test for #20: an invalid 'until' value must raise a clear
    # ValueError, not blow up with a secondary exception (e.g. NameError) while
    # building the error message. The message should identify the offending
    # block by name and source line number.
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

    # A valid (still-pending) remove block, then one with an invalid 'until'.
    # The invalid block's [[remove]] header is on line 8.
    (tmp_path / "round_000001.toml").write_text(dedent("""\
            number = 1
            date = 2026-05-01

            [[remove]]
            name = "Bob"
            until = 99

            [[remove]]
            name = "Alice"
            until = "soon"
            """))

    with pytest.raises(ValueError) as excinfo:
        new_round_config(tmp_path, date="2026-05-08")

    message = str(excinfo.value)
    assert "Alice" in message
    assert "line 8" in message
