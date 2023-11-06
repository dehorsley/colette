import warnings
from dataclasses import dataclass, field
from jinja2 import Environment, FileSystemLoader

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


def render_messages(solution: Solution, round_config: RoundConfig) -> list[Message]:
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
