from configparser import ConfigParser
from email.message import EmailMessage
import smtplib

from .base import Message


class SMTPConnection:
    """
    A context manager for establishing an SMTP connection and sending email messages.

    Args:
        cfg (ConfigParser): A configuration object containing email server settings.

    Attributes:
        cfg (ConfigParser): The configuration object passed to the constructor.
        server (smtplib.SMTP): The SMTP server connection object.

    Methods:
        __enter__(): Establishes an SMTP connection and logs in if necessary.
        __exit__(): Closes the SMTP connection.
        send_message(msg: EmailMessage): Sends an email message using the SMTP connection.
    """

    def __init__(self, cfg: ConfigParser):
        self.cfg = cfg
        self.server = None

    def __enter__(self):
        self.server = smtplib.SMTP(
            self.cfg["email"]["server"], self.cfg["email"].getint("port", fallback=587)
        )
        self.server.ehlo()

        if self.cfg["email"].getboolean("ssl", fallback=False):
            import ssl

            ctx = ssl.create_default_context()
            self.server.starttls(context=ctx)

        if "username" in self.cfg["email"]:
            self.server.login(
                self.cfg["email"]["username"], self.cfg["email"]["password"]
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.server.quit()

    def send_message(self, msg: EmailMessage):
        self.server.send_message(msg)


class SmtpClient:
    """
    A class for sending emails using SMTP protocol.

    Args:
        config (ConfigParser): Configuration object containing email settings.

    """

    def __init__(self, config: ConfigParser):
        self._cfg = config

    def _make_message(self, msg: Message) -> EmailMessage:
        email_msg = EmailMessage()
        email_msg.set_content(msg.body)
        email_msg["Subject"] = msg.subject
        email_msg["From"] = self._cfg["email"]["from"]
        email_msg["To"] = ";".join([f"{r.name} <{r.email}>" for r in msg.to])
        return email_msg

    def send_email(self, msgs: list[Message], preview=False):
        """
        Sends email messages.

        Args:
            msgs (list[Message]): List of Message objects to be sent.
            preview (bool, optional): If True, prints the email messages instead of sending them. Defaults to False.
        """
        email_msgs = [self._make_message(msg) for msg in msgs]

        if preview:
            for msg in email_msgs:
                print(msg)
                return

        with SMTPConnection(self._cfg) as connection:
            for msg in email_msgs:
                connection.server.send_message(msg)
