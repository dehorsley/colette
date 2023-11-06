# Sends an email using Microsoft Outlook on macOS.
from ..models import Solution, RoundConfig

from .base import Email
from appscript import app, k
from jinja2 import Environment, FileSystemLoader


class OutlookMacOSEmail(Email):
    def __init__(self, template: str):
        self.template = template
        self.env = Environment(loader=FileSystemLoader("templates"))

    def send_email(self, solution: Solution, round_config: RoundConfig, preview=False):
        body_template = self.env.get_template("body.html")
        subject_template = self.env.get_template("subject.txt")

        outlook = app("Microsoft Outlook")

        msgs = []
        pairs = sorted(solution.pairs)
        for pair in pairs:
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

            msg = outlook.make(
                new=k.outgoing_message,
                with_properties={
                    k.subject: subject,
                    k.content: body,
                },
            )

            # set the recipient, subject, and body of the email
            msg.make(
                new=k.recipient,
                with_properties={
                    k.email_address: {
                        k.address: primary.email,
                        k.name: primary.name,
                    },
                },
            )

            msg.make(
                new=k.recipient,
                with_properties={
                    k.email_address: {
                        k.address: secondary.email,
                        k.name: secondary.name,
                    },
                },
            )

            msgs.append(msg)

        if preview:
            for msg in msgs:
                msg.open()
                msg.activate()
        else:
            for msg in msgs:
                msg.send()
