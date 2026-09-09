"""A tiny local HTTP endpoint the web app polls for detected rounds.

Deliberately a dumb sensor. The watcher reports what it saw - a list of round
outcomes in order - and the web app owns everything else: economies, sides,
halftime, match end. That keeps the game logic in one place rather than
reimplementing it here and letting the two drift apart.

Standard library only, because a JSON endpoint on localhost does not warrant a
web framework.
"""

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8731


class WatcherState:
    """Thread-safe list of what the detector has seen this match."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rounds: list[dict] = []
        # Identifies this run. Restarting the watcher empties the round list,
        # and a client tracking "how many have I applied" would otherwise stop
        # applying anything at all - its count would stay above the length of
        # a list that had gone back to zero.
        self._session = uuid.uuid4().hex[:12]
        # the last credit figure read off your HUD, or None when the
        # number was not on screen or could not be read confidently
        self._credits: int | None = None

    def add(self, outcome: str, planted: bool = False) -> None:
        with self._lock:
            self._rounds.append({"outcome": outcome, "planted": planted})

    def reset(self) -> None:
        with self._lock:
            self._rounds.clear()
            self._session = uuid.uuid4().hex[:12]
        # the last credit figure read off your HUD, or None when the
        # number was not on screen or could not be read confidently
        self._credits: int | None = None

    def set_credits(self, value: int | None) -> None:
        with self._lock:
            self._credits = value

    @property
    def credits(self) -> int | None:
        with self._lock:
            return self._credits

    @property
    def session(self) -> str:
        with self._lock:
            return self._session

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._rounds]


def make_handler(state: WatcherState):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            # the page is served from localhost:3000, the watcher lives here
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            self._send({})

        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/state"):
                self._send({
                    "watching": True,
                    "session": state.session,
                    "rounds": state.snapshot(),
                    "credits": state.credits,
                })
            else:
                self._send({"error": "not found"}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path.startswith("/reset"):
                state.reset()
                self._send({
                    "watching": True,
                    "session": state.session,
                    "rounds": [],
                })
            else:
                self._send({"error": "not found"}, status=404)

        def log_message(self, *args) -> None:
            """Silence per-request logging; the run loop prints what matters."""

    return Handler


def serve(state: WatcherState, port: int = PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
