#!/usr/bin/env python3
"""Optional Google Trends enrichment for the demand signal.

Refreshes each market's ``demand_index`` in ``data/markets.json`` from real Google
Trends search interest, using the public ``pytrends`` client (no API key). This is
an **offline-first, opt-in** tool: it updates the seed file that the app reads; the
app itself never calls the network at request time.

Usage (from the repo root):

    python scripts/enrich_demand.py --dry-run     # show what would change
    python scripts/enrich_demand.py               # write updates into markets.json

Requires the optional dependency:  pip install pytrends

Design notes:
- If ``pytrends`` is not installed or the network is unavailable, the script prints
  a clear message and leaves ``markets.json`` untouched (seed stays valid).
- Raw interest is normalized to 0-100 by ``travel_advisor.growth.normalize_interest``
  (pure, unit-tested), so the enrichment reuses the same logic the app trusts.
- It preserves every other field and records ``demand_source`` and ``updated_at``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Make the backend package importable when run from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "backend" / "src"))

from travel_advisor.growth import normalize_interest  # noqa: E402

_MARKETS_FILE = _REPO_ROOT / "data" / "markets.json"


def _search_term(city: str) -> str:
    """The Google Trends query used as the demand proxy for a destination."""
    return f"flights to {city}"


def fetch_interest(cities: dict[str, str]) -> dict[str, float]:
    """Query Google Trends for each market's city. Returns {code: raw_interest}.

    Raises RuntimeError with a friendly message if pytrends is missing or the
    request fails, so the caller can leave the seed untouched.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError as exc:  # pytrends not installed
        raise RuntimeError(
            "pytrends is not installed. Install the optional extra with "
            "`pip install pytrends` to enable Google Trends enrichment."
        ) from exc

    try:
        pytrends = TrendReq(hl="en-GB", tz=0)
        interest: dict[str, float] = {}
        # Trends compares up to 5 terms at a time; batch the cities.
        codes = list(cities)
        for i in range(0, len(codes), 5):
            batch = codes[i : i + 5]
            terms = [_search_term(cities[c]) for c in batch]
            pytrends.build_payload(terms, timeframe="today 3-m", geo="")
            df = pytrends.interest_over_time()
            for c, term in zip(batch, terms):
                interest[c] = float(df[term].mean()) if term in df else 0.0
        return interest
    except Exception as exc:  # network / rate-limit / parsing
        raise RuntimeError(f"Google Trends request failed: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich demand_index from Google Trends.")
    parser.add_argument(
        "--dry-run", action="store_true", help="print changes without writing the file"
    )
    args = parser.parse_args()

    data = json.loads(_MARKETS_FILE.read_text(encoding="utf-8"))
    markets = data.get("markets", [])
    cities = {m["code"]: m.get("city", m["code"]) for m in markets}

    try:
        raw = fetch_interest(cities)
    except RuntimeError as exc:
        print(f"[skip] {exc}")
        print("       markets.json left unchanged (offline seed remains the source of truth).")
        return 0

    normalized = normalize_interest(raw)
    today = date.today().isoformat()

    changes = []
    for m in markets:
        code = m["code"]
        if code in normalized:
            old = m.get("demand_index")
            new = normalized[code]
            changes.append((code, old, new))
            m["demand_index"] = new
            m["demand_source"] = "google_trends"
            m["updated_at"] = today

    for code, old, new in changes:
        print(f"{code}: demand_index {old} -> {new}")

    if args.dry_run:
        print("\n[dry-run] no file written.")
        return 0

    _MARKETS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nUpdated {len(changes)} markets in {_MARKETS_FILE}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
