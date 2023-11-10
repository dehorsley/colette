from colette.email import render_messages, Recipient
from colette.solver import RoundConfig, Pair, Person, Solution
from jinja2 import TemplateNotFound, Environment, DictLoader
from unittest.mock import patch
from textwrap import dedent
import pytest


@pytest.fixture
def round_config():
    people = {
        "Alice": Person("Alice", "Org1", True, "blag@example.com"),
        "Bob": Person("Bob", "Org2", True, "blag@example.com"),
        "Charlie": Person("Charlie", "Org1", True, "blag@example.com"),
        "Dave": Person("Dave", "Org2", True, "blag@example.com"),
    }

    overrides = {}
    return RoundConfig(
        number=3,
        people=people,
        overrides=overrides,
    )


@pytest.fixture
def solution(round_config):
    people = round_config.people
    pairs = {
        Pair(people["Alice"], people["Dave"]),
        Pair(people["Bob"], people["Charlie"]),
    }
    caviats = {
        Pair(people["Alice"], people["Dave"]): ["No peanuts"],
        Pair(people["Bob"], people["Charlie"]): ["No shellfish"],
    }
    return Solution(3, 2, pairs, caviats)


@pytest.fixture
def env():
    return Environment(
        loader=DictLoader(
            {
                "body.html": dedent(
                    """\
        Hi {{ primary.name }} and {{ secondary.name }},

        You're having lunch for this months round of CR.

        Cheers,
        Colette
        """
                ),
                "subject.txt": dedent(
                    """\
        Colette Round {{ round_config.number }} ({{ round_config.date.strftime('%b') }})
        """
                ),
            }
        )
    )


def test_render_messages(round_config, solution, env):
    msgs = render_messages(solution, round_config, env)

    assert len(msgs) == 2

    alice_dave_msg = next(
        msg
        for msg in msgs
        if msg.to
        == [
            Recipient("Alice", "blag@example.com"),
            Recipient("Dave", "blag@example.com"),
        ]
    )
    assert alice_dave_msg.subject == "Colette Round 3 (Nov)"
    assert "Hi Alice and Dave" in alice_dave_msg.body

    bob_charlie_msg = next(
        msg
        for msg in msgs
        if msg.to
        == [
            Recipient("Bob", "blag@example.com"),
            Recipient("Charlie", "blag@example.com"),
        ]
    )
    assert bob_charlie_msg.subject == "Colette Round 3 (Nov)"
    assert "Hi Bob and Charlie" in bob_charlie_msg.body


def test_render_messages_template_not_found(round_config, solution):
    with patch("colette.email.base.Environment.get_template") as mock_get_template:
        mock_get_template.side_effect = TemplateNotFound("foo")
        with pytest.raises(TemplateNotFound):
            render_messages(solution, round_config)
