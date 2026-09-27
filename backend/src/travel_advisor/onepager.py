"""Client One-Pager generator — deterministic SVG report.

Turns the computed pricing, growth, and storyline results into a single fixed-layout
SVG a consultant could hand to a client: title, a price-by-day bar chart, the top
growth markets with allocations, and the storyline.

Pure and deterministic: same inputs → byte-identical SVG. No I/O, no clock, no
randomness, no external dependencies. This is the project's "curated artifact" —
an output of first-class quality generated straight from the engine.
"""

from __future__ import annotations

from decimal import Decimal
from html import escape

from .models import Allocation, MarketOpportunity, PricedDay

# Fixed canvas geometry so the layout is reproducible.
_W = 1200
_H = 780
_MARGIN = 40
_CHART_TOP = 150
_CHART_H = 260
_BAR_GAP = 6

_BG = "#0f172a"
_PANEL = "#1e293b"
_TEXT = "#e2e8f0"
_MUTED = "#94a3b8"
_ACCENT = "#38bdf8"


def _bar_color(delta_pct: float) -> str:
    if delta_pct >= 25:
        return "#b91c1c"
    if delta_pct >= 12:
        return "#ea580c"
    if delta_pct >= 4:
        return "#d97706"
    if delta_pct <= -4:
        return "#2563eb"
    return "#64748b"


def _price_bars(days: list[PricedDay]) -> str:
    if not days:
        return ""
    inner_w = _W - 2 * _MARGIN
    n = len(days)
    bar_w = (inner_w - (n - 1) * _BAR_GAP) / n
    max_price = max((d.price for d in days), default=1.0) or 1.0
    parts: list[str] = []
    for i, d in enumerate(days):
        h = (d.price / max_price) * _CHART_H
        x = _MARGIN + i * (bar_w + _BAR_GAP)
        y = _CHART_TOP + (_CHART_H - h)
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'rx="2" fill="{_bar_color(d.deltaPct)}"><title>{escape(d.date)}: '
            f'{d.price:.0f} ({d.deltaPct:+.0f}%)</title></rect>'
        )
        # date label every ~7th bar to avoid clutter
        if n <= 16 or i % 7 == 0:
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{_CHART_TOP + _CHART_H + 16:.1f}" '
                f'fill="{_MUTED}" font-size="10" text-anchor="middle">'
                f"{escape(d.date[5:])}</text>"
            )
    return "".join(parts)


def _opportunity_rows(markets: list[MarketOpportunity], allocations: list[Allocation]) -> str:
    amount_by_market = {a.market: a.amount for a in allocations}
    top = sorted(markets, key=lambda m: m.score, reverse=True)[:5]
    max_amt = max((float(amount_by_market.get(m.market, Decimal(0))) for m in top), default=1.0) or 1.0
    y0 = _CHART_TOP + _CHART_H + 70
    row_h = 34
    bar_max = 300
    parts: list[str] = []
    for i, m in enumerate(top):
        amt = amount_by_market.get(m.market, Decimal(0))
        y = y0 + i * row_h
        bar_w = (float(amt) / max_amt) * bar_max
        parts.append(
            f'<text x="{_MARGIN}" y="{y + 14:.0f}" fill="{_TEXT}" font-size="14" '
            f'font-weight="600">{escape(m.market)}</text>'
            f'<rect x="{_MARGIN + 60}" y="{y:.0f}" width="{bar_w:.1f}" height="18" rx="3" '
            f'fill="{_ACCENT}" />'
            f'<text x="{_MARGIN + 60 + bar_w + 8:.1f}" y="{y + 14:.0f}" fill="{_MUTED}" '
            f'font-size="12">€{amt}</text>'
        )
    return "".join(parts)


def _storyline_block(lines: list[str]) -> str:
    x = _W / 2 + 40
    y0 = _CHART_TOP + _CHART_H + 60
    parts = [
        f'<text x="{x}" y="{y0}" fill="{_TEXT}" font-size="15" font-weight="600">'
        f"Client storyline</text>"
    ]
    wrap_at = 58
    line_y = y0 + 26
    for line in lines:
        # naive word wrap for the fixed-width panel
        words = line.split()
        current = ""
        chunks: list[str] = []
        for w in words:
            if len(current) + len(w) + 1 > wrap_at:
                chunks.append(current)
                current = w
            else:
                current = f"{current} {w}".strip()
        if current:
            chunks.append(current)
        for j, chunk in enumerate(chunks):
            prefix = "• " if j == 0 else "  "
            parts.append(
                f'<text x="{x}" y="{line_y}" fill="{_MUTED}" font-size="12">'
                f"{escape(prefix + chunk)}</text>"
            )
            line_y += 18
        line_y += 4
    return "".join(parts)


def build_onepager_svg(
    *,
    route_label: str,
    period: str,
    days: list[PricedDay],
    markets: list[MarketOpportunity],
    allocations: list[Allocation],
    storyline: list[str],
) -> str:
    """Render the full client one-pager as a self-contained SVG string."""
    title = escape(route_label)
    subtitle = escape(f"Pricing & growth briefing — {period}")

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" height="{_H}" '
        f'viewBox="0 0 {_W} {_H}" font-family="system-ui, Segoe UI, Roboto, sans-serif">'
        f'<rect width="{_W}" height="{_H}" fill="{_BG}"/>'
        # header
        f'<text x="{_MARGIN}" y="52" fill="{_TEXT}" font-size="28" font-weight="700">'
        f"{title}</text>"
        f'<text x="{_MARGIN}" y="80" fill="{_MUTED}" font-size="15">{subtitle}</text>'
        f'<text x="{_MARGIN}" y="128" fill="{_TEXT}" font-size="16" font-weight="600">'
        f"Recommended price by day</text>"
        # price chart
        f"{_price_bars(days)}"
        # section titles
        f'<text x="{_MARGIN}" y="{_CHART_TOP + _CHART_H + 50}" fill="{_TEXT}" '
        f'font-size="16" font-weight="600">Top growth markets</text>'
        f"{_opportunity_rows(markets, allocations)}"
        f"{_storyline_block(storyline)}"
        # footer
        f'<text x="{_MARGIN}" y="{_H - 20}" fill="{_MUTED}" font-size="11">'
        f"Deterministic report generated from offline data + public holidays. "
        f"Prices are illustrative.</text>"
        f"</svg>"
    )
