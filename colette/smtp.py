from .data import Solution
from configparser import ConfigParser
from email.message import EmailMessage
from pathlib import Path
import smtplib
from jinja2 import Template


def email(solution: Solution, path="data"):
    """
    email function emails the participants of a round their role and
    counterpart, or gives them appology if unpaired. The round emailed is
    either the number specified in "round" or the latest in the path.
    """
    path = Path(path)

    with (path / "buyer.template").open() as f:
        buyer_template = Template(f.read())

    with (path / "organiser.template").open() as f:
        organiser_template = Template(f.read())

    with (path / "excluded.template").open() as f:
        excluded_template = Template(f.read())

    cfg = ConfigParser()
    cfg.read(path / "email.ini")

    if round is None:
        round_paths = sorted(
            path.glob("round_*.csv"),
            key=lambda p: int(p.stem.removeprefix("round_")),
        )

        if len(round_paths) == 0:
            raise Exception(f"No round_*.csv file round in path {path}")

        round = int(round_paths[-1].stem.removeprefix("round_"))

    print(f"Emailing players of round {round}!")

    def msg_from_template(address, pair, template):
        msg = EmailMessage()
        msg.set_content(template.render(organiser=pair.organiser, buyer=pair.buyer))

        msg["Subject"] = cfg["email"]["subject"]
        msg["From"] = cfg["email"]["from"]
        msg["To"] = address
        return msg

    # iterate over all unique pairs: NB each pair can be in the pairs dict at
    # most once, one time for each member.
    msgs = []
    for p in set(solution.pairs.values()):
        if p.secondary == p.primary:
            msgs.append(msg_from_template(p.secondary.email, p, excluded_template))
            continue
        msgs.append(msg_from_template(p.secondary.email, p, buyer_template))
        msgs.append(msg_from_template(p.primary.email, p, organiser_template))

    s = smtplib.SMTP(cfg["email"]["server"], cfg["email"].getint("port", fallback=587))
    s.ehlo()

    if cfg["email"].getboolean("ssl", fallback=False):
        import ssl

        ctx = ssl.create_default_context()
        s.starttls(context=ctx)

    if "username" in cfg["email"]:
        s.login(cfg["email"]["username"], cfg["email"]["password"])

    for msg in msgs:
        s.send_message(msg)
    s.quit()
