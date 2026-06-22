"""JSON-friendly application logic for the Colette web GUI.

The functions in this module operate on a :class:`~colette.storage.FileStorage`
(the same on-disk format the CLI uses) and return plain ``dict``/``list``
structures suitable for serialising to JSON. Keeping the logic free of any HTTP
concerns makes it straightforward to unit-test and lets the thin server layer in
``server.py`` stay a simple router.
"""

from __future__ import annotations

import csv
import dataclasses
import datetime
import io

import tomlkit

from .. import solver
from ..__main__ import new_round_config
from ..email import render_messages
from ..models import Person, RoundConfig, Solution
from ..storage import FileStorage

# Canonical order of the cost fields, taken from the dataclass definition.
COST_FIELDS = [
    f.name for f in dataclasses.fields(RoundConfig) if f.name.startswith("cost_")
]
COST_DEFAULTS = {
    f.name: f.default
    for f in dataclasses.fields(RoundConfig)
    if f.name.startswith("cost_")
}


class ApiError(Exception):
    """An error with an associated HTTP status code and a user-facing message."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------------------- #
# serialisers
# --------------------------------------------------------------------------- #
def person_dict(p: Person) -> dict:
    return {
        "name": p.name,
        "organisation": p.organisation,
        "email": p.email,
        "active": p.active,
    }


def _pair_dict(pair, people: dict[str, Person], caviats: list[str]) -> dict:
    removed = pair.primary == pair.secondary

    def org(name: str) -> str:
        person = people.get(name)
        return person.organisation if person else ""

    return {
        "removed": removed,
        "primary": {"name": pair.primary.name, "organisation": org(pair.primary.name)},
        "secondary": None
        if removed
        else {
            "name": pair.secondary.name,
            "organisation": org(pair.secondary.name),
        },
        "caviats": list(caviats),
    }


def _solution_dict(solution: Solution, people: dict[str, Person]) -> dict:
    pairs = sorted(solution.pairs)
    return {
        "round": solution.round,
        "cost": solution.cost,
        "optimal": getattr(solution, "optimal", True),
        "pairs": [
            _pair_dict(p, people, solution.caviats.get(p, []))
            for p in pairs
            if p.primary != p.secondary
        ],
        "removed": [p.primary.name for p in pairs if p.primary == p.secondary],
    }


# --------------------------------------------------------------------------- #
# round-config (toml) helpers
# --------------------------------------------------------------------------- #
def _config_path(store: FileStorage, n: int):
    return store.path / f"round_{n:06d}.toml"


def _read_config_doc(store: FileStorage, n: int):
    path = _config_path(store, n)
    if not path.exists():
        raise ApiError(f"No configuration for round {n}", status=404)
    return tomlkit.parse(path.read_text())


def read_round_config(store: FileStorage, n: int) -> dict:
    """Return a JSON-friendly view of a round's TOML config for editing."""
    doc = _read_config_doc(store, n)

    removes = []
    for r in doc.get("remove", []):
        entry = {"name": r["name"], "until": None}
        if "until" in r:
            until = r["until"]
            entry["until"] = until.isoformat() if hasattr(until, "isoformat") else until
        removes.append(entry)

    overrides = []
    for o in doc.get("override", []):
        overrides.append({"pair": list(o["pair"]), "weight": o["weight"]})

    costs = {k: doc.get(k, COST_DEFAULTS[k]) for k in COST_FIELDS}

    date = doc.get("date")
    return {
        "number": doc.get("number", n),
        "date": date.isoformat() if hasattr(date, "isoformat") else date,
        "notes": doc.get("notes", ""),
        "costs": costs,
        "removes": removes,
        "overrides": overrides,
    }


def _coerce_until(value):
    """Interpret a remove block's ``until`` as an int round or a date."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ApiError("'until' must be a round number or a YYYY-MM-DD date")
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    try:
        return datetime.date.fromisoformat(text)
    except ValueError as e:
        raise ApiError(
            f"'until' must be a round number or a YYYY-MM-DD date, got {value!r}"
        ) from e


def _until_norm(value) -> str:
    """Comparable, stable string form of a remove block's ``until`` value."""
    if value is None or value == "":
        return ""
    if hasattr(value, "isoformat"):
        return "d:" + value.isoformat()
    if isinstance(value, bool):
        return "x:" + str(value)
    if isinstance(value, int):
        return "r:" + str(value)
    return "x:" + str(value)


def write_round_config(store: FileStorage, n: int, cfg: dict) -> dict:
    """Write a round's TOML config from a JSON-friendly representation.

    Edits the *existing* document in place so comments (e.g. a note explaining a
    removal), unknown keys and costs the caller didn't touch are preserved. The
    ``remove`` and ``override`` blocks are only rebuilt when their contents
    actually change, so comments on unchanged blocks survive too.

    All validation happens before anything is written, so a rejected edit leaves
    the file untouched.
    """
    path = _config_path(store, n)
    if not path.exists():
        raise ApiError(f"No configuration for round {n}", status=404)

    people = store.load_people()
    doc = tomlkit.parse(path.read_text())

    # --- validate everything up front (no writes yet) -------------------- #
    date_item = None
    date = cfg.get("date")
    if date:
        try:
            date_item = tomlkit.date(str(date).strip())
        except ValueError as e:
            raise ApiError(f"Invalid date {date!r}; expected YYYY-MM-DD") from e

    costs = cfg.get("costs") or {}
    for k, value in costs.items():
        if k in COST_DEFAULTS and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            raise ApiError(f"{k} must be an integer")

    built_overrides = []
    for o in cfg.get("overrides") or []:
        pair = o.get("pair") or []
        if len(pair) != 2:
            raise ApiError("Each override needs a pair of two names")
        for name in pair:
            if name not in people:
                raise ApiError(f"Unknown person {name!r} in override")
        weight = o.get("weight")
        if not isinstance(weight, int) or isinstance(weight, bool):
            raise ApiError("Override weight must be an integer")
        built_overrides.append((tuple(sorted(pair)), weight, list(pair)))

    built_removes = []
    for r in cfg.get("removes") or []:
        name = r.get("name")
        if name not in people:
            raise ApiError(f"Unknown person {name!r} in removal")
        built_removes.append((name, _coerce_until(r.get("until"))))

    # --- apply (in place) ------------------------------------------------ #
    doc["number"] = n
    if date_item is not None:
        doc["date"] = date_item
    elif "date" not in doc:
        doc["date"] = tomlkit.date(datetime.date.today().isoformat())

    notes = (cfg.get("notes") or "").strip()
    if notes:
        doc["notes"] = notes
    elif "notes" in doc:
        del doc["notes"]

    # only touch costs the caller actually sent, leaving the rest as-is
    for k, value in costs.items():
        if k in COST_DEFAULTS:
            doc[k] = value

    # overrides: rebuild only if the set of (pair, weight) changed
    existing_ov = sorted(
        (tuple(sorted(o["pair"])), int(o["weight"])) for o in doc.get("override", [])
    )
    desired_ov = sorted((key, weight) for key, weight, _ in built_overrides)
    if existing_ov != desired_ov:
        if built_overrides:
            aot = tomlkit.aot()
            for _key, weight, pair in built_overrides:
                aot.append(tomlkit.item({"pair": pair, "weight": weight}))
            doc["override"] = aot
        elif "override" in doc:
            del doc["override"]

    # removes: rebuild only if the set of (name, until) changed
    existing_rm = sorted(
        (r["name"], _until_norm(r.get("until"))) for r in doc.get("remove", [])
    )
    desired_rm = sorted((name, _until_norm(until)) for name, until in built_removes)
    if existing_rm != desired_rm:
        if built_removes:
            aot = tomlkit.aot()
            for name, until in built_removes:
                item = {"name": name}
                if isinstance(until, datetime.date):
                    item["until"] = tomlkit.date(until.isoformat())
                elif isinstance(until, int):
                    item["until"] = until
                aot.append(tomlkit.item(item))
            doc["remove"] = aot
        elif "remove" in doc:
            del doc["remove"]

    path.write_text(tomlkit.dumps(doc))
    return read_round_config(store, n)


# --------------------------------------------------------------------------- #
# people
# --------------------------------------------------------------------------- #
def list_people(store: FileStorage) -> list[dict]:
    # A brand-new working directory has no people.csv yet — treat that as an
    # empty list rather than an error so the GUI can start from scratch.
    return [person_dict(p) for p in _people_or_empty(store).values()]


def _validate_person_payload(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("Name is required")
    return {
        "name": name,
        "organisation": (data.get("organisation") or "").strip(),
        "email": (data.get("email") or "").strip(),
        "active": bool(data.get("active", True)),
    }


def add_person(store: FileStorage, data: dict) -> dict:
    fields = _validate_person_payload(data)
    try:
        people = store.load_people()
    except FileNotFoundError:
        people = {}
    if fields["name"] in people:
        raise ApiError(f"{fields['name']} already exists", status=409)
    people[fields["name"]] = Person(**fields)
    store.store_people(people)
    return person_dict(people[fields["name"]])


def add_people_bulk(store: FileStorage, text: str) -> dict:
    """Append many people pasted as ``name, organisation, email`` lines.

    Only adds new people — existing names (and duplicates within the paste) are
    skipped, never overwritten — so this is safe to run against a populated
    directory. A leading ``name,...`` header line is ignored.
    """
    if not isinstance(text, str) or not text.strip():
        raise ApiError("Paste at least one person")

    people = _people_or_empty(store)
    reader = csv.reader(io.StringIO(text))
    added, skipped, errors = [], [], []
    for i, row in enumerate(reader):
        if not row or all(not cell.strip() for cell in row):
            continue
        name = row[0].strip()
        if i == 0 and name.lower() == "name":
            continue  # header row
        if not name:
            errors.append(f"line {i + 1}: missing name")
            continue
        if name in people or name in added:
            skipped.append(name)
            continue
        people[name] = Person(
            name=name,
            organisation=row[1].strip() if len(row) > 1 else "",
            email=row[2].strip() if len(row) > 2 else "",
            active=True,
        )
        added.append(name)

    if added:
        store.store_people(people)
    return {"added": len(added), "skipped": len(skipped), "errors": errors}


def update_person(store: FileStorage, name: str, data: dict) -> dict:
    people = store.load_people()
    if name not in people:
        raise ApiError(f"Unknown person {name!r}", status=404)

    new_name = (data.get("name") or name).strip()
    if new_name != name and new_name in people:
        raise ApiError(f"{new_name} already exists", status=409)

    def field(key: str, default: str) -> str:
        value = data.get(key, default)
        return value.strip() if isinstance(value, str) else default

    current = people[name]
    updated = Person(
        name=new_name,
        organisation=field("organisation", current.organisation),
        email=field("email", current.email),
        active=bool(data.get("active", current.active)),
    )

    # Preserve ordering: rebuild the dict swapping the entry in place.
    people = {
        (updated.name if k == name else k): (updated if k == name else v)
        for k, v in people.items()
    }
    store.store_people(people)
    return person_dict(updated)


def delete_person(store: FileStorage, name: str) -> dict:
    people = store.load_people()
    if name not in people:
        raise ApiError(f"Unknown person {name!r}", status=404)

    solutions = store.load_solutions(people)
    for solution in solutions:
        if any(name in (p.primary.name, p.secondary.name) for p in solution.pairs):
            raise ApiError(
                f"{name} appears in round {solution.round} and can't be deleted. "
                "Mark them inactive instead.",
                status=409,
            )

    # Also refuse if a round config still references them (a remove or
    # override): deleting would orphan that reference and break the round.
    for f in sorted(store.path.glob("round_*.toml")):
        try:
            doc = tomlkit.parse(f.read_text())
        except Exception:
            continue
        referenced = {r.get("name") for r in doc.get("remove", [])}
        for o in doc.get("override", []):
            referenced.update(o.get("pair", []))
        if name in referenced:
            try:
                num = int(f.stem.split("_")[1])
            except (IndexError, ValueError):
                num = f.name
            raise ApiError(
                f"{name} is referenced in round {num}'s configuration and can't "
                "be deleted. Remove them from that round first, or mark them "
                "inactive instead.",
                status=409,
            )

    del people[name]
    store.store_people(people)
    return {"deleted": name}


# --------------------------------------------------------------------------- #
# status / rounds
# --------------------------------------------------------------------------- #
def _people_or_empty(store: FileStorage) -> dict[str, Person]:
    try:
        return store.load_people()
    except FileNotFoundError:
        return {}


def get_status(store: FileStorage) -> dict:
    people = _people_or_empty(store)
    solutions = store.load_solutions(people) if people else []
    next_round = len(solutions) + 1
    templates = store.path / "templates"
    return {
        "path": str(store.path.resolve()),
        "people_total": len(people),
        "people_active": sum(1 for p in people.values() if p.active),
        "rounds_solved": len(solutions),
        "last_round": solutions[-1].round if solutions else 0,
        "next_round": next_round,
        "next_config_exists": _config_path(store, next_round).exists(),
        "has_templates": (templates / "body.html").exists()
        and (templates / "subject.txt").exists(),
    }


def list_rounds(store: FileStorage) -> list[dict]:
    people = _people_or_empty(store)
    solutions = store.load_solutions(people) if people else []
    sol_by_round = {s.round: s for s in solutions}

    config_rounds = set()
    for f in store.path.glob("round_*.toml"):
        try:
            config_rounds.add(int(f.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue

    rounds = []
    for n in sorted(config_rounds | set(sol_by_round)):
        info = {
            "number": n,
            "has_config": n in config_rounds,
            "has_solution": n in sol_by_round,
            "date": None,
            "num_pairs": None,
            "num_removed": None,
            "cost": None,
        }
        if n in config_rounds:
            try:
                doc = _read_config_doc(store, n)
                date = doc.get("date")
                info["date"] = date.isoformat() if hasattr(date, "isoformat") else date
            except ApiError:
                pass
        if n in sol_by_round:
            sol = sol_by_round[n]
            info["num_pairs"] = sum(1 for p in sol.pairs if p.primary != p.secondary)
            info["num_removed"] = sum(1 for p in sol.pairs if p.primary == p.secondary)
            info["cost"] = sol.cost
        rounds.append(info)
    return rounds


def get_round(store: FileStorage, n: int) -> dict:
    people = _people_or_empty(store)
    result: dict = {"number": n, "config": None, "solution": None}

    if _config_path(store, n).exists():
        result["config"] = read_round_config(store, n)

    sol_path = store.path / f"solution_{n:06d}.toml"
    csv_path = store.path / f"solution_{n:06d}.csv"
    if sol_path.exists() or csv_path.exists():
        solutions = store.load_solutions(people)
        for sol in solutions:
            if sol.round == n:
                result["solution"] = _solution_dict(sol, people)
                break

    if result["config"] is None and result["solution"] is None:
        raise ApiError(f"No data for round {n}", status=404)
    return result


def create_round(store: FileStorage, date: str | None = None) -> dict:
    """Create the next round's config (mirrors ``colette new``)."""
    try:
        new_round_config(store.path, date=date)
    except RuntimeError as e:
        raise ApiError(str(e), status=409) from e
    except FileNotFoundError as e:
        raise ApiError(str(e), status=400) from e
    status = get_status(store)
    # ``new_round_config`` creates the config for the next (unsolved) round.
    return {"number": status["next_round"], **status}


def solve(store: FileStorage, regenerate: bool = False) -> dict:
    """Solve the next round, or regenerate the most recently solved round."""
    people = store.load_people()
    solutions = store.load_solutions(people)

    if regenerate:
        if not solutions:
            raise ApiError("There is no solved round to regenerate")
        target = solutions[-1].round
        previous = [s for s in solutions if s.round < target]
    else:
        target = len(solutions) + 1
        previous = solutions

    try:
        config = store.load_round_config(target, people)
    except FileNotFoundError as e:
        raise ApiError(
            f"No configuration for round {target}. Create the round first.",
            status=400,
        ) from e

    solution = solver.solve_round(config, previous_rounds=previous)
    store.store_solution(solution)
    store.store_solution(solution, type="csv")
    return _solution_dict(solution, people)


# --------------------------------------------------------------------------- #
# email
# --------------------------------------------------------------------------- #
def preview_emails(store: FileStorage, n: int) -> dict:
    people = store.load_people()
    templates = store.path / "templates"
    if not (templates / "body.html").exists():
        raise ApiError(
            "No email templates found. Add templates/body.html and "
            "templates/subject.txt to enable email.",
            status=400,
        )

    sol_path = store.path / f"solution_{n:06d}.toml"
    csv_path = store.path / f"solution_{n:06d}.csv"
    if not (sol_path.exists() or csv_path.exists()):
        raise ApiError(f"No solution for round {n}", status=404)

    solution = next(
        (s for s in store.load_solutions(people) if s.round == n),
        None,
    )
    if solution is None:
        raise ApiError(f"No solution for round {n}", status=404)

    config = store.load_round_config(n, people)

    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(templates)))
    messages = render_messages(solution, config, env=env)
    return {
        "round": n,
        "messages": [
            {
                "subject": m.subject,
                "body": m.body,
                "to": [{"name": r.name, "email": r.email} for r in m.to],
            }
            for m in messages
        ],
    }


# --------------------------------------------------------------------------- #
# history
# --------------------------------------------------------------------------- #
def get_history(store: FileStorage) -> dict:
    """Pairing history: repeat pairings and per-person partner lists."""
    people = _people_or_empty(store)
    solutions = store.load_solutions(people) if people else []

    pair_rounds: dict[tuple[str, str], list[int]] = {}
    partners: dict[str, dict[str, list[int]]] = {}

    for sol in solutions:
        for pair in sol.pairs:
            if pair.primary == pair.secondary:
                continue
            a, b = pair.primary.name, pair.secondary.name
            key = tuple(sorted((a, b)))
            pair_rounds.setdefault(key, []).append(sol.round)
            partners.setdefault(a, {}).setdefault(b, []).append(sol.round)
            partners.setdefault(b, {}).setdefault(a, []).append(sol.round)

    repeats = [
        {"pair": list(key), "count": len(rounds), "rounds": sorted(rounds)}
        for key, rounds in pair_rounds.items()
        if len(rounds) > 1
    ]
    repeats.sort(key=lambda r: (-r["count"], r["pair"]))

    partner_view = {
        name: sorted(
            (
                {"partner": partner, "rounds": sorted(rounds), "count": len(rounds)}
                for partner, rounds in plist.items()
            ),
            key=lambda d: (-d["count"], d["partner"]),
        )
        for name, plist in partners.items()
    }

    return {
        "rounds_count": len(solutions),
        "people": sorted(p.name for p in people.values()),
        "repeats": repeats,
        "partners": partner_view,
        "round_dates": _round_dates(store),
    }


def _round_dates(store: FileStorage) -> dict[str, str]:
    """Map round number -> ISO date (where a round config records one)."""
    dates: dict[str, str] = {}
    for f in store.path.glob("round_*.toml"):
        try:
            n = int(f.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        try:
            doc = tomlkit.parse(f.read_text())
        except Exception:
            continue
        d = doc.get("date")
        if d is not None:
            dates[str(n)] = d.isoformat() if hasattr(d, "isoformat") else str(d)
    return dates


# --------------------------------------------------------------------------- #
# email templates
# --------------------------------------------------------------------------- #
def get_templates(store: FileStorage) -> dict:
    templates = store.path / "templates"
    subject = templates / "subject.txt"
    body = templates / "body.html"
    return {
        "subject": subject.read_text() if subject.exists() else "",
        "body": body.read_text() if body.exists() else "",
        "has_subject": subject.exists(),
        "has_body": body.exists(),
    }


# Example data used for the live template preview, so you don't need a
# generated round to see what an email will look like.
_PREVIEW_PRIMARY = Person(
    name="Alex Taylor",
    organisation="Product",
    email="alex.taylor@example.com",
    active=True,
)
_PREVIEW_SECONDARY = Person(
    name="Sam Rivera",
    organisation="Design",
    email="sam.rivera@example.com",
    active=True,
)


def preview_template(subject: str, body: str) -> dict:
    """Render template text with example data for a live preview.

    Never raises on bad template syntax — returns the error in the payload so
    the editor can show it inline while you type.
    """
    from jinja2 import Environment

    env = Environment()  # autoescape off, matching the email renderer
    ctx = {
        "primary": _PREVIEW_PRIMARY,
        "secondary": _PREVIEW_SECONDARY,
        "round_config": RoundConfig(number=7, people={}, date=datetime.date.today()),
        "caviats": ["are in the same organisation"],
    }
    result = {
        "subject": "",
        "body": "",
        "to": [
            {"name": _PREVIEW_PRIMARY.name, "email": _PREVIEW_PRIMARY.email},
            {"name": _PREVIEW_SECONDARY.name, "email": _PREVIEW_SECONDARY.email},
        ],
        "error": None,
    }
    try:
        result["subject"] = env.from_string(subject or "").render(**ctx)
        result["body"] = env.from_string(body or "").render(**ctx)
    except Exception as e:
        result["error"] = str(e)
    return result


def save_templates(store: FileStorage, data: dict) -> dict:
    templates = store.path / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    subject = data.get("subject")
    body = data.get("body")
    if not isinstance(subject, str) and not isinstance(body, str):
        raise ApiError("Provide a subject and/or body to save")
    if isinstance(subject, str):
        (templates / "subject.txt").write_text(subject)
    if isinstance(body, str):
        (templates / "body.html").write_text(body)
    return get_templates(store)
