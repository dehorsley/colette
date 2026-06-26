"""A small, dependency-free web server for the Colette GUI.

Uses only the standard library: a :class:`http.server.ThreadingHTTPServer`
serves a single-page app (static files under ``static/``) and a JSON API backed
by :mod:`colette.web.api`. It is intended to be run locally by a single user, so
it binds to localhost and has no authentication.
"""

from __future__ import annotations

import json
import re
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from ..storage import FileStorage
from . import api

STATIC_DIR = Path(__file__).parent / "static"

# Map file extensions to the content types we serve.
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}


def _route(method, pattern):
    """Decorator registering a handler for ``method`` and a path ``pattern``."""

    def decorator(func):
        func._route = (method, re.compile(f"^{pattern}$"))
        return func

    return decorator


class Handler(BaseHTTPRequestHandler):
    server_version = "Colette/1.0"

    # Routing table, built lazily from methods decorated with ``@_route``.
    _routes = None

    @classmethod
    def _build_routes(cls):
        if cls._routes is None:
            routes = []
            for name in dir(cls):
                attr = getattr(cls, name)
                route = getattr(attr, "_route", None)
                if route is not None:
                    routes.append((route[0], route[1], attr))
            cls._routes = routes
        return cls._routes

    # -- helpers ---------------------------------------------------------- #
    @property
    def store(self) -> FileStorage:
        return self.server.store  # type: ignore[attr-defined]

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message, status):
        self._send_json({"error": message}, status=status)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise api.ApiError(f"Invalid JSON body: {e}") from e

    def log_message(self, format, *args):  # noqa: A002 - signature from base class
        # Keep the console quiet for the common static/asset noise; the
        # ThreadingHTTPServer default would print every request.
        pass

    # -- dispatch --------------------------------------------------------- #
    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = parsed.path

        if not path.startswith("/api/"):
            if method == "GET":
                return self._serve_static(path)
            return self._send_error_json("Not found", HTTPStatus.NOT_FOUND)

        for route_method, pattern, func in self._build_routes():
            if route_method != method:
                continue
            match = pattern.match(path)
            if match is None:
                continue
            try:
                body = self._read_body() if method in ("POST", "PUT") else {}
                status, payload = func(self, match, body)
                return self._send_json(payload, status=status)
            except api.ApiError as e:
                return self._send_error_json(e.message, e.status)
            except FileNotFoundError as e:
                return self._send_error_json(str(e), HTTPStatus.BAD_REQUEST)
            except Exception as e:  # pragma: no cover - defensive
                import traceback

                traceback.print_exc()
                return self._send_error_json(
                    f"{type(e).__name__}: {e}", HTTPStatus.INTERNAL_SERVER_ERROR
                )

        return self._send_error_json("Not found", HTTPStatus.NOT_FOUND)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    # -- static files ----------------------------------------------------- #
    def _serve_static(self, path):
        rel = path.lstrip("/") or "index.html"
        target = (STATIC_DIR / rel).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return self._send_error_json("Forbidden", HTTPStatus.FORBIDDEN)

        if not target.is_file():
            # Fall back to the SPA shell for client-side routes.
            target = STATIC_DIR / "index.html"
            if not target.is_file():
                return self._send_error_json("Not found", HTTPStatus.NOT_FOUND)

        data = target.read_bytes()
        content_type = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- routes ----------------------------------------------------------- #
    @_route("GET", r"/api/status")
    def _status(self, match, body):
        return HTTPStatus.OK, api.get_status(self.store)

    @_route("GET", r"/api/people")
    def _list_people(self, match, body):
        return HTTPStatus.OK, api.list_people(self.store)

    @_route("POST", r"/api/people")
    def _add_person(self, match, body):
        return HTTPStatus.CREATED, api.add_person(self.store, body)

    @_route("POST", r"/api/people/import")
    def _import_people(self, match, body):
        return HTTPStatus.OK, api.add_people_bulk(self.store, body.get("text", ""))

    @_route("PUT", r"/api/people/(?P<name>.+)")
    def _update_person(self, match, body):
        name = unquote(match.group("name"))
        return HTTPStatus.OK, api.update_person(self.store, name, body)

    @_route("DELETE", r"/api/people/(?P<name>.+)")
    def _delete_person(self, match, body):
        name = unquote(match.group("name"))
        return HTTPStatus.OK, api.delete_person(self.store, name)

    @_route("GET", r"/api/rounds")
    def _list_rounds(self, match, body):
        return HTTPStatus.OK, api.list_rounds(self.store)

    @_route("POST", r"/api/rounds")
    def _create_round(self, match, body):
        return HTTPStatus.CREATED, api.create_round(self.store, body.get("date"))

    @_route("POST", r"/api/rounds/solve")
    def _solve(self, match, body):
        return HTTPStatus.OK, api.solve(
            self.store,
            bool(body.get("regenerate")),
            body.get("max_seconds"),
        )

    @_route("GET", r"/api/rounds/(?P<n>\d+)")
    def _get_round(self, match, body):
        return HTTPStatus.OK, api.get_round(self.store, int(match.group("n")))

    @_route("PUT", r"/api/rounds/(?P<n>\d+)/config")
    def _update_config(self, match, body):
        return HTTPStatus.OK, api.write_round_config(
            self.store, int(match.group("n")), body
        )

    @_route("GET", r"/api/rounds/(?P<n>\d+)/emails")
    def _emails(self, match, body):
        return HTTPStatus.OK, api.preview_emails(self.store, int(match.group("n")))

    @_route("GET", r"/api/history")
    def _history(self, match, body):
        return HTTPStatus.OK, api.get_history(self.store)

    @_route("GET", r"/api/templates")
    def _get_templates(self, match, body):
        return HTTPStatus.OK, api.get_templates(self.store)

    @_route("PUT", r"/api/templates")
    def _save_templates(self, match, body):
        return HTTPStatus.OK, api.save_templates(self.store, body)

    @_route("POST", r"/api/templates/preview")
    def _preview_template(self, match, body):
        return HTTPStatus.OK, api.preview_template(
            body.get("subject", ""), body.get("body", "")
        )


class ColetteServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, path):
        super().__init__(server_address, Handler)
        self.store = FileStorage(path)


def serve(path=".", host="127.0.0.1", port=8080, open_browser=True):
    """Start the Colette web GUI server (blocking)."""
    server = ColetteServer((host, port), path)
    actual_port = server.server_address[1]
    url = f"http://{host}:{actual_port}/"
    print(f"Colette web GUI serving {Path(path).resolve()}")
    print(f"  → {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
