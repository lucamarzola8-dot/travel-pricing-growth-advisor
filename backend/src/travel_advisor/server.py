"""Local development HTTP server for the Travel Pricing & Growth Advisor.

Uses only the Python standard library (no extra dependencies) so the frontend has
a real API to call during development. In production these same handlers run in
Lambda behind API Gateway; here they run in-process.

Run with:  python -m travel_advisor.server   (from backend/, with src on the path)
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import api

_ROUTES = {
    "/price": api.get_price,
    "/growth": api.get_growth,
    "/storyline": api.get_storyline,
}


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:  # noqa: N802 - CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        handler = _ROUTES.get(parsed.path)
        if handler is None:
            self._send(404, {"error": f"unknown path: {parsed.path}"})
            return
        raw = parse_qs(parsed.query)
        params = {k: v[0] for k, v in raw.items()}
        try:
            status, body = handler(params)
        except api.BadRequest as exc:
            status, body = 400, {"error": str(exc)}
        self._send(status, body)

    def log_message(self, *args) -> None:  # keep the dev console quiet
        pass


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"Travel Advisor API running on http://{host}:{port}")
    print("  GET /price?route=MXP-BCN&date=2026-03-02")
    print("  GET /growth?budget=100000")
    print("  GET /storyline?route=MXP-BCN&date=2026-03-02&budget=100000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    serve()
