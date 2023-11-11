# Sends an email using Mail.app on macOS.
from .base import Message
from appscript import app, k, ApplicationNotFoundError
from warnings import warn


def mail_installed() -> bool:
    """Checks if Mail.app is installed on the system."""
    try:
        app("Mail")
        return True
    except ApplicationNotFoundError:
        return False


def send_email(msgs: list[Message], preview=False):
    """\
    Sends an email using Mail.app on macOS.
    """
    mail = app("Mail")

    for msg in msgs:
        body = msg.body
        # if body looks like html: warn our Mail.app implementation doesn't support html
        if body.strip().startswith("<html>"):
            warn("Mail.app messaging doesn't support html")

        subject = msg.subject

        mail_msg = mail.make(
            new=k.outgoing_message,
            with_properties={
                k.subject: subject,
                k.content: body,
            },
        )

        for recipient in msg.to:
            mail_msg.make(
                new=k.recipient,
                with_properties={
                    k.email_address: {
                        k.address: recipient.email,
                        k.name: recipient.name,
                    },
                },
            )

        if preview:
            mail_msg.open()
            mail_msg.activate()
        else:
            mail_msg.send()
