import warnings
from dataclasses import dataclass, field
from jinja2 import Environment, FileSystemLoader
from typing import Optional

from ..models import RoundConfig, Solution


@dataclass
class Recipient:
    name: str
    email: str


@dataclass
class Message:
    subject: str
    body: str
    to: list[Recipient]
    cc: list[Recipient] = field(default_factory=list)
    bcc: list[Recipient] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)


def render_messages(
    solution: Solution,
    round_config: RoundConfig,
    env: Optional[Environment] = None,
) -> list[Message]:
    """
    Renders email messages for each pair in the solution.

    Args:
        solution (Solution): The solution object containing pairs and caviats.
        round_config (RoundConfig): The round configuration object.
        env (Environment, optional): A Jinja2 environment object. Defaults to a
        new FileSystemLoader environment for the "templates" directory.

    Returns:
        list[Message]: A list of Message objects containing the rendered email messages.
    """
    if env is None:
        env = Environment(loader=FileSystemLoader("templates"))
    body_template = env.get_template("body.html")
    subject_template = env.get_template("subject.txt")

    msgs = []
    pairs = sorted(solution.pairs)
    for pair in pairs:
        if pair.primary == pair.secondary:
            warnings.warn(f"{pair.primary} removed from round but won't be emailed")
            # TODO: handle this case
            continue

        primary = pair.primary
        secondary = pair.secondary

        body = body_template.render(
            primary=primary,
            secondary=secondary,
            caviats=solution.caviats.get(pair, []),
            round_config=round_config,
        )

        subject = subject_template.render(
            primary=primary,
            secondary=secondary,
            round_config=round_config,
        )

        msg = Message(
            subject=subject,
            body=body,
            to=[
                Recipient(primary.name, primary.email),
                Recipient(secondary.name, secondary.email),
            ],
        )

        msgs.append(msg)

    return msgs
