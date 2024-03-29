import sys
from unittest.mock import MagicMock, call, patch

import pytest

from colette.email.base import Message, Recipient

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="Mail.app is only available on macOS",
)


@pytestmark
def test_send_email():
    from appscript import k

    from colette.email.mail_macos import send_email

    # Create a mock Message object
    msg = Message(
        subject="Test Subject",
        body="Test Body",
        to=[
            Recipient(name="Alice", email="alice@example.com"),
            Recipient(name="Bob", email="bob@example.com"),
        ],
    )

    # Mock the Mail.app object
    mail_mock = MagicMock()
    mail_mock.make.return_value = mail_mock
    mail_mock.send.return_value = None
    with patch("colette.email.mail_macos.app", return_value=mail_mock):
        # Call the send_email function
        send_email([msg], preview=False)

    # Check that the Mail.app object was called correctly

    calls = [
        call(
            new=k.outgoing_message,
            with_properties={
                k.subject: "Test Subject",
                k.content: "Test Body",
            },
        ),
        call(
            new=k.recipient,
            with_properties={
                k.email_address: {
                    k.address: "alice@example.com",
                    k.name: "Alice",
                },
            },
        ),
        call(
            new=k.recipient,
            with_properties={
                k.email_address: {
                    k.address: "bob@example.com",
                    k.name: "Bob",
                },
            },
        ),
    ]

    mail_mock.make.assert_has_calls(calls, any_order=False)

    mail_mock.send.assert_called_once_with()


@pytestmark
def test_mail_installed():
    from appscript import ApplicationNotFoundError

    from colette.email.mail_macos import mail_installed

    # Test that mail_installed returns True when Mail.app is installed
    assert mail_installed() is True

    # Test that mail_installed returns False when Mail.app is not installed
    with patch(
        "colette.email.mail_macos.app",
        side_effect=ApplicationNotFoundError("Mail"),
    ):
        assert mail_installed() is False
