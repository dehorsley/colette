import datetime
import json
import threading
import urllib.error
import urllib.request
from contextlib import closing
from textwrap import dedent

import pytest

from colette.storage import FileStorage
from colette.web import api
from colette.web.server import ColetteServer


@pytest.fixture
def store(tmp_path):
    (tmp_path / "people.csv").write_text(
        dedent("""\
        name,organisation,email,active
        Alice,Org1,alice@example.com,TRUE
        Bob,Org2,bob@example.com,TRUE
        Charlie,Org1,charlie@example.com,TRUE
        Dave,Org2,dave@example.com,FALSE
        """)
    )
    return FileStorage(tmp_path)


@pytest.fixture
def store_with_round(store):
    (store.path / "round_000001.toml").write_text(
        dedent("""\
        number = 1
        date = 2026-05-01
        """)
    )
    (store.path / "solution_000001.toml").write_text(
        dedent("""\
        cost = 0
        round = 1

        [[pair]]
        primary = "Alice"
        secondary = "Bob"

        [[pair]]
        primary = "Charlie"
        secondary = "Dave"
        """)
    )
    return store


# --------------------------------------------------------------------------- #
# people
# --------------------------------------------------------------------------- #
def test_get_status(store):
    s = api.get_status(store)
    assert s["people_total"] == 4
    assert s["people_active"] == 3
    assert s["rounds_solved"] == 0
    assert s["next_round"] == 1
    assert s["next_config_exists"] is False


def test_list_people(store):
    people = api.list_people(store)
    assert [p["name"] for p in people] == ["Alice", "Bob", "Charlie", "Dave"]
    assert people[3]["active"] is False


def test_add_person(store):
    api.add_person(store, {"name": "Eve", "organisation": "Org3", "email": "e@x.com"})
    people = {p["name"]: p for p in api.list_people(store)}
    assert "Eve" in people
    assert people["Eve"]["active"] is True


def test_add_person_requires_name(store):
    with pytest.raises(api.ApiError):
        api.add_person(store, {"organisation": "x"})


def test_add_duplicate_person(store):
    with pytest.raises(api.ApiError) as e:
        api.add_person(store, {"name": "Alice"})
    assert e.value.status == 409


def test_update_person_active_and_rename(store):
    api.update_person(store, "Bob", {"active": False})
    assert {p["name"]: p["active"] for p in api.list_people(store)}["Bob"] is False

    api.update_person(store, "Bob", {"name": "Bobby"})
    names = [p["name"] for p in api.list_people(store)]
    assert "Bobby" in names and "Bob" not in names
    # ordering preserved
    assert names == ["Alice", "Bobby", "Charlie", "Dave"]


def test_delete_unpaired_person(store):
    api.delete_person(store, "Dave")
    assert "Dave" not in [p["name"] for p in api.list_people(store)]


def test_delete_paired_person_blocked(store_with_round):
    with pytest.raises(api.ApiError) as e:
        api.delete_person(store_with_round, "Alice")
    assert e.value.status == 409


# --------------------------------------------------------------------------- #
# rounds
# --------------------------------------------------------------------------- #
def test_list_and_get_round(store_with_round):
    rounds = api.list_rounds(store_with_round)
    assert len(rounds) == 1
    assert rounds[0]["number"] == 1
    assert rounds[0]["has_solution"] is True
    assert rounds[0]["num_pairs"] == 2

    detail = api.get_round(store_with_round, 1)
    assert detail["config"]["date"] == "2026-05-01"
    assert len(detail["solution"]["pairs"]) == 2


def test_create_round(store_with_round):
    result = api.create_round(store_with_round, date="2026-06-01")
    assert result["number"] == 2
    cfg = api.read_round_config(store_with_round, 2)
    assert cfg["date"] == "2026-06-01"


def test_write_round_config_roundtrip(store_with_round):
    api.create_round(store_with_round, date="2026-06-01")
    api.write_round_config(
        store_with_round,
        2,
        {
            "date": "2026-06-08",
            "notes": "hello",
            "removes": [{"name": "Charlie", "until": "2026-12-01"}, {"name": "Dave"}],
            "overrides": [{"pair": ["Alice", "Bob"], "weight": -50}],
            "costs": {},
        },
    )
    cfg = api.read_round_config(store_with_round, 2)
    assert cfg["date"] == "2026-06-08"
    assert cfg["notes"] == "hello"
    assert {r["name"] for r in cfg["removes"]} == {"Charlie", "Dave"}
    charlie = next(r for r in cfg["removes"] if r["name"] == "Charlie")
    assert charlie["until"] == "2026-12-01"
    assert cfg["overrides"][0]["pair"] == ["Alice", "Bob"]
    assert cfg["overrides"][0]["weight"] == -50

    # the round config must still load through the model layer
    people = store_with_round.load_people()
    loaded = store_with_round.load_round_config(2, people)
    assert loaded.number == 2
    assert loaded.date == datetime.date(2026, 6, 8)


def test_write_round_config_self_override_sit_out(store_with_round):
    # "Allow to sit out" is modelled as a self-pairing override; the backend
    # must accept it and round-trip it (regression for GUI feedback #2).
    api.create_round(store_with_round, date="2026-06-01")
    api.write_round_config(
        store_with_round,
        2,
        {"overrides": [{"pair": ["Charlie", "Charlie"], "weight": -50}], "costs": {}},
    )
    cfg = api.read_round_config(store_with_round, 2)
    assert cfg["overrides"] == [{"pair": ["Charlie", "Charlie"], "weight": -50}]

    # must still load through the model layer and be solvable
    people = store_with_round.load_people()
    loaded = store_with_round.load_round_config(2, people)
    assert len(loaded.overrides) == 1
    result = api.solve(store_with_round)
    assert result["round"] == 2


def test_write_round_config_unknown_person(store_with_round):
    api.create_round(store_with_round, date="2026-06-01")
    with pytest.raises(api.ApiError):
        api.write_round_config(store_with_round, 2, {"removes": [{"name": "Nobody"}]})


def test_write_round_config_invalid_until(store_with_round):
    api.create_round(store_with_round, date="2026-06-01")
    with pytest.raises(api.ApiError):
        api.write_round_config(
            store_with_round,
            2,
            {"removes": [{"name": "Charlie", "until": "soon"}]},
        )


def test_solve_creates_solution(store_with_round):
    api.create_round(store_with_round, date="2026-06-01")
    result = api.solve(store_with_round)
    assert result["round"] == 2
    assert (store_with_round.path / "solution_000002.toml").exists()
    assert (store_with_round.path / "solution_000002.csv").exists()
    assert len(api.list_rounds(store_with_round)) == 2


def test_solve_result_reports_optimal(store_with_round):
    api.create_round(store_with_round, date="2026-06-01")
    result = api.solve(store_with_round)
    # small instance solves to proven optimality
    assert result["optimal"] is True


def test_solve_regenerate(store_with_round):
    api.create_round(store_with_round, date="2026-06-01")
    api.solve(store_with_round)
    # regenerate should overwrite, not create round 3
    api.solve(store_with_round, regenerate=True)
    assert not (store_with_round.path / "solution_000003.toml").exists()


def test_solve_without_config_errors(store_with_round):
    with pytest.raises(api.ApiError):
        api.solve(store_with_round)


# --------------------------------------------------------------------------- #
# email + history
# --------------------------------------------------------------------------- #
def test_preview_emails_without_templates(store_with_round):
    with pytest.raises(api.ApiError):
        api.preview_emails(store_with_round, 1)


def test_preview_emails(store_with_round):
    templates = store_with_round.path / "templates"
    templates.mkdir()
    (templates / "subject.txt").write_text("Round {{ round_config.number }}")
    (templates / "body.html").write_text(
        "<html><body>Hi {{ primary.name }} and {{ secondary.name }}</body></html>"
    )
    result = api.preview_emails(store_with_round, 1)
    assert len(result["messages"]) == 2
    subjects = {m["subject"] for m in result["messages"]}
    assert subjects == {"Round 1"}
    assert all(len(m["to"]) == 2 for m in result["messages"])


def test_templates_roundtrip(store_with_round):
    assert api.get_templates(store_with_round) == {
        "subject": "",
        "body": "",
        "has_subject": False,
        "has_body": False,
    }
    saved = api.save_templates(
        store_with_round,
        {"subject": "Hi {{ primary.name }}", "body": "<p>hello</p>"},
    )
    assert saved["has_subject"] and saved["has_body"]
    assert (store_with_round.path / "templates" / "subject.txt").read_text() == (
        "Hi {{ primary.name }}"
    )
    again = api.get_templates(store_with_round)
    assert again["body"] == "<p>hello</p>"


def test_save_templates_requires_content(store_with_round):
    with pytest.raises(api.ApiError):
        api.save_templates(store_with_round, {})


def test_preview_template_renders_with_example_data():
    res = api.preview_template(
        "Round {{ round_config.number }}",
        "<p>Hi {{ primary.name }} and {{ secondary.name }}</p>",
    )
    assert res["error"] is None
    assert res["subject"] == "Round 7"
    assert "Alex Taylor" in res["body"]
    assert "Sam Rivera" in res["body"]
    assert [r["name"] for r in res["to"]] == ["Alex Taylor", "Sam Rivera"]


def test_preview_template_reports_error_without_raising():
    res = api.preview_template("ok", "{% bad jinja %}")
    assert res["error"]  # non-empty error message
    # must not raise — the editor shows the error inline while typing


def test_get_history_includes_round_dates(store_with_round):
    h = api.get_history(store_with_round)
    # round 1 has a config with a date; it should appear in the map
    assert h["round_dates"].get("1") == "2026-05-01"


def test_get_history(store_with_round):
    # add a second round repeating Alice/Bob
    (store_with_round.path / "solution_000002.toml").write_text(
        dedent("""\
        cost = 0
        round = 2

        [[pair]]
        primary = "Alice"
        secondary = "Bob"
        """)
    )
    h = api.get_history(store_with_round)
    assert h["rounds_count"] == 2
    repeat = next(r for r in h["repeats"] if set(r["pair"]) == {"Alice", "Bob"})
    assert repeat["count"] == 2
    assert repeat["rounds"] == [1, 2]
    assert {p["partner"] for p in h["partners"]["Alice"]} == {"Bob"}


# --------------------------------------------------------------------------- #
# HTTP integration
# --------------------------------------------------------------------------- #
@pytest.fixture
def live_server(store_with_round):
    server = ColetteServer(("127.0.0.1", 0), store_with_round.path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def _get(url):
    with closing(urllib.request.urlopen(url)) as resp:
        return resp.status, resp.read()


def test_http_status_endpoint(live_server):
    status, body = _get(f"{live_server}/api/status")
    assert status == 200
    assert json.loads(body)["people_total"] == 4


def test_http_serves_index(live_server):
    status, body = _get(f"{live_server}/")
    assert status == 200
    assert b"<title>Colette" in body


def test_http_serves_static_js(live_server):
    status, body = _get(f"{live_server}/app.js")
    assert status == 200
    assert b"Colette web GUI" in body


def test_http_post_create_round(live_server):
    req = urllib.request.Request(
        f"{live_server}/api/rounds",
        data=json.dumps({"date": "2026-06-01"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with closing(urllib.request.urlopen(req)) as resp:
        assert resp.status == 201
        assert json.loads(resp.read())["number"] == 2


def test_http_unknown_api_404(live_server):
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(f"{live_server}/api/nope")
    assert e.value.code == 404


# --------------------------------------------------------------------------- #
# data integrity — make absolutely sure edits never corrupt existing data
# --------------------------------------------------------------------------- #
def _people_snapshot(store):
    """All people as plain comparable dicts, keyed by name."""
    return {
        name: {
            "organisation": p.organisation,
            "email": p.email,
            "active": p.active,
        }
        for name, p in store.load_people().items()
    }


def test_add_person_preserves_all_others(store):
    before = _people_snapshot(store)
    api.add_person(store, {"name": "Eve", "organisation": "Org3", "email": "e@x.com"})
    after = _people_snapshot(store)
    # every original person is byte-for-byte the same
    for name, record in before.items():
        assert after[name] == record
    assert after["Eve"] == {
        "organisation": "Org3",
        "email": "e@x.com",
        "active": True,
    }


def test_update_person_only_changes_target(store):
    before = _people_snapshot(store)
    api.update_person(store, "Bob", {"organisation": "Changed"})
    after = _people_snapshot(store)
    for name in ("Alice", "Charlie", "Dave"):
        assert after[name] == before[name]
    assert after["Bob"]["organisation"] == "Changed"
    assert after["Bob"]["email"] == before["Bob"]["email"]


def test_add_first_person_creates_people_csv(tmp_path):
    fresh = FileStorage(tmp_path)
    assert not (tmp_path / "people.csv").exists()
    api.add_person(fresh, {"name": "Alice", "organisation": "Org", "email": "a@x"})
    assert (tmp_path / "people.csv").exists()
    assert list(fresh.load_people()) == ["Alice"]


# --------------------------------------------------------------------------- #
# new / empty working directory
# --------------------------------------------------------------------------- #
def test_empty_directory_status_and_lists(tmp_path):
    fresh = FileStorage(tmp_path)
    status = api.get_status(fresh)
    assert status["people_total"] == 0
    assert status["rounds_solved"] == 0
    assert status["next_round"] == 1
    assert status["next_config_exists"] is False
    assert status["has_templates"] is False
    # the list endpoints must not error on a brand-new directory
    assert api.list_people(fresh) == []
    assert api.list_rounds(fresh) == []
    assert api.get_history(fresh)["rounds_count"] == 0
    assert api.get_templates(fresh)["subject"] == ""


def test_list_people_empty_when_no_file(tmp_path):
    # regression: this used to raise FileNotFoundError
    assert api.list_people(FileStorage(tmp_path)) == []


def test_add_person_into_nonexistent_directory(tmp_path):
    target = tmp_path / "brand" / "new" / "dir"
    fresh = FileStorage(target)
    api.add_person(fresh, {"name": "Alice", "organisation": "Org", "email": "a@x"})
    assert (target / "people.csv").exists()
    assert list(fresh.load_people()) == ["Alice"]


def test_save_templates_into_nonexistent_directory(tmp_path):
    fresh = FileStorage(tmp_path / "fresh")
    api.save_templates(fresh, {"subject": "Hi", "body": "<p>x</p>"})
    assert (tmp_path / "fresh" / "templates" / "subject.txt").exists()


def test_from_scratch_flow(tmp_path):
    # full first-time journey: empty dir → add people → create round → solve
    fresh = FileStorage(tmp_path)
    for name in ("Alice", "Bob", "Charlie", "Dave"):
        api.add_person(
            fresh, {"name": name, "organisation": "Org", "email": f"{name}@x"}
        )
    api.create_round(fresh, date="2026-06-01")
    assert (tmp_path / "round_000001.toml").exists()
    result = api.solve(fresh)
    assert result["round"] == 1
    assert len(result["pairs"]) == 2
    assert api.get_status(fresh)["rounds_solved"] == 1


def test_create_round_without_people_errors(tmp_path):
    with pytest.raises(api.ApiError):
        api.create_round(FileStorage(tmp_path))


# --------------------------------------------------------------------------- #
# bulk import (setting up a new directory)
# --------------------------------------------------------------------------- #
def test_bulk_import_into_empty_directory(tmp_path):
    fresh = FileStorage(tmp_path)
    result = api.add_people_bulk(
        fresh,
        "Alice Smith, Engineering, alice@example.com\nBob Jones, Sales\nCharlie Day",
    )
    assert result["added"] == 3
    assert result["skipped"] == 0
    people = fresh.load_people()
    assert list(people) == ["Alice Smith", "Bob Jones", "Charlie Day"]
    assert people["Alice Smith"].organisation == "Engineering"
    assert people["Alice Smith"].email == "alice@example.com"
    assert people["Charlie Day"].organisation == ""
    assert people["Bob Jones"].active is True


def test_bulk_import_skips_existing_and_duplicates(store):
    result = api.add_people_bulk(store, "Alice, X\nEve, New\nEve, Again")
    assert result["added"] == 1  # only Eve once
    assert result["skipped"] == 2  # existing Alice + duplicate Eve
    # existing Alice must be untouched (not overwritten with org "X")
    assert store.load_people()["Alice"].organisation == "Org1"


def test_bulk_import_ignores_header_and_blank_lines(tmp_path):
    fresh = FileStorage(tmp_path)
    result = api.add_people_bulk(fresh, "name,organisation,email\n\nAlice,Org\n\nBob\n")
    assert result["added"] == 2
    assert list(fresh.load_people()) == ["Alice", "Bob"]


def test_bulk_import_quoted_comma_name(tmp_path):
    fresh = FileStorage(tmp_path)
    api.add_people_bulk(fresh, '"Smith, AJ", Sales EU, aj@example.com')
    people = fresh.load_people()
    assert "Smith, AJ" in people
    assert people["Smith, AJ"].organisation == "Sales EU"


def test_bulk_import_empty_text_errors(tmp_path):
    with pytest.raises(api.ApiError):
        api.add_people_bulk(FileStorage(tmp_path), "   \n  ")


def test_update_unknown_person_404(store):
    with pytest.raises(api.ApiError) as e:
        api.update_person(store, "Ghost", {"organisation": "x"})
    assert e.value.status == 404


def test_delete_unknown_person_404(store):
    with pytest.raises(api.ApiError) as e:
        api.delete_person(store, "Ghost")
    assert e.value.status == 404


def test_delete_person_referenced_in_override_blocked(store):
    (store.path / "round_000001.toml").write_text(
        dedent("""\
        number = 1
        date = 2026-05-01

        [[override]]
        pair = ["Alice", "Bob"]
        weight = -100
        """)
    )
    before = (store.path / "people.csv").read_text()
    with pytest.raises(api.ApiError) as e:
        api.delete_person(store, "Bob")
    assert e.value.status == 409
    assert (store.path / "people.csv").read_text() == before


def test_delete_person_referenced_in_config_blocked(store):
    # Dave is unpaired (no solutions) but listed in a future round's config —
    # deleting would orphan that reference, so it must be refused.
    (store.path / "round_000001.toml").write_text(
        dedent("""\
        number = 1
        date = 2026-05-01

        [[remove]]
        name = "Dave"
        until = 2027-01-01
        """)
    )
    before = (store.path / "people.csv").read_text()
    with pytest.raises(api.ApiError) as e:
        api.delete_person(store, "Dave")
    assert e.value.status == 409
    assert (store.path / "people.csv").read_text() == before


def test_delete_person_preserves_all_others(store):
    before = _people_snapshot(store)
    api.delete_person(store, "Dave")
    after = _people_snapshot(store)
    assert "Dave" not in after
    for name in ("Alice", "Bob", "Charlie"):
        assert after[name] == before[name]


def test_people_csv_survives_special_characters(store):
    # Commas, quotes and unicode must round-trip exactly — a naive CSV writer
    # would shift columns and silently corrupt every following field.
    tricky = {
        "name": 'O\'Brien, "Bob"',
        "organisation": "R&D, Eastern Europe",
        "email": "bøb@example.com",
    }
    api.add_person(store, tricky)
    reloaded = store.load_people()
    assert tricky["name"] in reloaded
    person = reloaded[tricky["name"]]
    assert person.organisation == "R&D, Eastern Europe"
    assert person.email == "bøb@example.com"
    # the other people must be untouched
    assert {"Alice", "Bob", "Charlie", "Dave"} <= set(reloaded)


def test_active_flag_roundtrips_both_directions(store):
    api.update_person(store, "Dave", {"active": True})
    assert store.load_people()["Dave"].active is True
    api.update_person(store, "Alice", {"active": False})
    assert store.load_people()["Alice"].active is False


def test_rename_collision_rejected_and_file_unchanged(store):
    before = (store.path / "people.csv").read_text()
    with pytest.raises(api.ApiError) as e:
        api.update_person(store, "Bob", {"name": "Alice"})
    assert e.value.status == 409
    assert (store.path / "people.csv").read_text() == before


def test_add_duplicate_does_not_modify_file(store):
    before = (store.path / "people.csv").read_text()
    with pytest.raises(api.ApiError):
        api.add_person(store, {"name": "Alice"})
    assert (store.path / "people.csv").read_text() == before


def test_write_round_config_preserves_comments_on_unchanged_blocks(store):
    # Regression: editing the date must not wipe a human note on a removal.
    (store.path / "round_000001.toml").write_text(
        dedent("""\
        number = 1
        date = 2026-05-01

        [[remove]]
        # on parental leave
        name = "Dave"
        until = 2027-01-01
        """)
    )
    api.write_round_config(
        store,
        1,
        {
            "date": "2026-05-08",
            "removes": [{"name": "Dave", "until": "2027-01-01"}],
        },
    )
    text = (store.path / "round_000001.toml").read_text()
    assert "# on parental leave" in text
    assert "2026-05-08" in text
    cfg = api.read_round_config(store, 1)
    assert cfg["removes"] == [{"name": "Dave", "until": "2027-01-01"}]


def test_write_round_config_preserves_unknown_keys_and_costs(store):
    (store.path / "round_000001.toml").write_text(
        dedent("""\
        number = 1
        date = 2026-05-01
        cost_of_not_pairing = 1000
        custom_extra = "keep me"
        """)
    )
    # client sends no costs and no custom key — both must survive
    api.write_round_config(store, 1, {"date": "2026-05-08"})
    text = (store.path / "round_000001.toml").read_text()
    assert 'custom_extra = "keep me"' in text
    assert api.read_round_config(store, 1)["costs"]["cost_of_not_pairing"] == 1000


def test_write_round_config_rejected_edit_leaves_file_intact(store):
    (store.path / "round_000001.toml").write_text(
        dedent("""\
        number = 1
        date = 2026-05-01
        """)
    )
    before = (store.path / "round_000001.toml").read_text()
    with pytest.raises(api.ApiError):
        api.write_round_config(store, 1, {"removes": [{"name": "Ghost"}]})
    assert (store.path / "round_000001.toml").read_text() == before


def test_write_round_config_full_feature_roundtrip_and_solves(store):
    (store.path / "round_000001.toml").write_text("number = 1\ndate = 2026-05-01\n")
    api.write_round_config(
        store,
        1,
        {
            "date": "2026-05-08",
            "notes": "monthly",
            "removes": [
                {"name": "Dave", "until": 5},
                {"name": "Charlie", "until": "2026-12-01"},
            ],
            "overrides": [
                {"pair": ["Alice", "Bob"], "weight": -100},
                {"pair": ["Alice", "Alice"], "weight": -900},
            ],
            "costs": {"cost_of_not_pairing": 1000},
        },
    )
    cfg = api.read_round_config(store, 1)
    assert cfg["notes"] == "monthly"
    dave = next(r for r in cfg["removes"] if r["name"] == "Dave")
    assert dave["until"] == 5
    charlie = next(r for r in cfg["removes"] if r["name"] == "Charlie")
    assert charlie["until"] == "2026-12-01"
    assert cfg["costs"]["cost_of_not_pairing"] == 1000
    # must load through the model and be solvable
    people = store.load_people()
    store.load_round_config(1, people)
    result = api.solve(store)
    assert result["round"] == 1


def test_solve_does_not_touch_people_or_config(store):
    (store.path / "round_000001.toml").write_text("number = 1\ndate = 2026-05-01\n")
    people_before = (store.path / "people.csv").read_text()
    config_before = (store.path / "round_000001.toml").read_text()
    api.solve(store)
    assert (store.path / "people.csv").read_text() == people_before
    assert (store.path / "round_000001.toml").read_text() == config_before


def test_templates_survive_special_characters(store):
    body = "<p>Hi {{ primary.name }} — café ☕</p>\n<p>Line two, with comma</p>"
    api.save_templates(store, {"subject": "Røund {{ n }}", "body": body})
    again = api.get_templates(store)
    assert again["subject"] == "Røund {{ n }}"
    assert again["body"] == body
