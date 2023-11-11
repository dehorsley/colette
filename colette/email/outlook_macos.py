# Sends an email using Microsoft Outlook on macOS.
from .base import Message
from appscript import app, k, ApplicationNotFoundError


def outlook_installed() -> bool:
    """Checks if Microsoft Outlook is installed on the system."""
    try:
        app("Microsoft Outlook")
        return True
    except ApplicationNotFoundError:
        return False


def send_email(msgs: list[Message], preview=False):
    outlook = app("Microsoft Outlook")

    for msg in msgs:
        body = msg.body
        subject = msg.subject

        outlook_msg = outlook.make(
            new=k.outgoing_message,
            with_properties={
                k.subject: subject,
                k.content: body,
            },
        )

        for recipient in msg.to:
            outlook_msg.make(
                new=k.recipient,
                with_properties={
                    k.email_address: {
                        k.address: recipient.email,
                        k.name: recipient.name,
                    },
                },
            )

        if preview:
            outlook_msg.open()
            outlook_msg.activate()
        else:
            outlook_msg.send()
