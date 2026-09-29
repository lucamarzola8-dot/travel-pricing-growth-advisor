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
    "/routes": api.get_routes,
    "/price": api.get_price,
    "/optimize": api.get_optimize,
    "/growth": api.get_growth,
    "/storyline": api.get_storyline,
    "/simulate": api.get_simulate,
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

    def _send_text(self, body: str, content_type: str, filename: str | None = None) -> None:
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_svg(self, svg: str) -> None:
        self._send_text(svg, "image/svg+xml")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        raw = parse_qs(parsed.query)
        params = {k: v[0] for k, v in raw.items()}

        # SVG one-pager and Markdown report have non-JSON content types.
        if parsed.path == "/onepager":
            try:
                _status, svg, _ct = api.get_onepager(params)
                self._send_svg(svg)
            except api.BadRequest as exc:
                self._send(400, {"error": str(exc)})
            return
        if parsed.path == "/report":
            try:
                _status, md, ct = api.get_report(params)
                name = f"pricing-report-{params.get('route', 'route')}-{params.get('date', '')}.md"
                self._send_text(md, ct, filename=name)
            except api.BadRequest as exc:
                self._send(400, {"error": str(exc)})
            return

        handler = _ROUTES.get(parsed.path)
        if handler is None:
            self._send(404, {"error": f"unknown path: {parsed.path}"})
            return
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
    print("  GET /routes")
    print("  GET /price?route=MXP-BCN&date=2026-03-02")
    print("  GET /optimize?route=MXP-BCN&date=2026-03-02")
    print("  GET /growth?budget=100000")
    print("  GET /storyline?route=MXP-BCN&date=2026-03-02&budget=100000")
    print("  GET /onepager?route=MXP-BCN&date=2026-03-01&days=14&budget=100000")
    print("  GET /report?route=MXP-BCN&date=2026-03-01&days=14&budget=100000  (Markdown)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    serve()
