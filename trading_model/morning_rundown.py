"""
Morning rundown generator.

Called by Claude Code each morning with fresh Robinhood quotes (from
get_equity_quotes) and optional news items (dicts with 'symbol', 'headline',
'impact'). Produces a structured briefing: macro context, after-hours movers,
position-level P&L snapshot, and watchlist signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class NewsItem:
    symbol: str          # ticker or 'MACRO'
    headline: str
    impact: str          # 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    detail: str = ""


@dataclass
class PositionSnapshot:
    symbol: str
    shares: float
    avg_cost: float
    prev_close: float    # Yesterday's official close
    ah_price: float      # After-hours / pre-market price
    ah_change_pct: float
    ah_change_dollar: float
    total_pnl_pct: float # vs avg_cost


@dataclass
class MorningRundown:
    date: str
    macro_summary: str
    key_events: List[str]
    positions: List[PositionSnapshot]
    news_items: List[NewsItem]
    top_movers_ah: List[PositionSnapshot]  # Sorted by abs(ah_change_pct)

    def render(self) -> str:
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"  MORNING RUNDOWN — {self.date}")
        lines.append("=" * 60)

        lines.append("\nMACRO")
        lines.append("-" * 40)
        lines.append(self.macro_summary)

        if self.key_events:
            lines.append("\nKEY EVENTS TODAY")
            lines.append("-" * 40)
            for e in self.key_events:
                lines.append(f"  • {e}")

        if self.top_movers_ah:
            lines.append("\nPREMARKET / AFTER-HOURS MOVERS (your positions)")
            lines.append("-" * 40)
            for p in self.top_movers_ah:
                arrow = "▲" if p.ah_change_pct >= 0 else "▼"
                lines.append(
                    f"  {arrow} {p.symbol:<6}  {p.ah_change_pct:>+6.1f}%  "
                    f"${p.ah_price:.2f}  (was ${p.prev_close:.2f})"
                )

        if self.news_items:
            lines.append("\nSTOCK NEWS")
            lines.append("-" * 40)
            by_impact = {"BULLISH": [], "NEUTRAL": [], "BEARISH": []}
            for n in self.news_items:
                by_impact.get(n.impact, by_impact["NEUTRAL"]).append(n)

            for impact, items in by_impact.items():
                if not items:
                    continue
                icon = {"BULLISH": "✓", "BEARISH": "✗", "NEUTRAL": "○"}[impact]
                for n in items:
                    tag = f"[{n.symbol}]" if n.symbol != "MACRO" else "[MACRO]"
                    lines.append(f"  {icon} {tag} {n.headline}")
                    if n.detail:
                        lines.append(f"      → {n.detail}")

        lines.append("\nPORTFOLIO SNAPSHOT (after-hours)")
        lines.append("-" * 40)
        lines.append(
            f"  {'SYMBOL':<6}  {'SHS':>7}  {'PREV':>8}  {'AH':>8}  "
            f"{'AH%':>6}  {'VS COST':>8}"
        )
        for p in sorted(self.positions, key=lambda x: abs(x.ah_change_pct), reverse=True):
            lines.append(
                f"  {p.symbol:<6}  {p.shares:>7.4f}  ${p.prev_close:>7.2f}"
                f"  ${p.ah_price:>7.2f}  {p.ah_change_pct:>+5.1f}%  {p.total_pnl_pct:>+7.1f}%"
            )

        lines.append("=" * 60)
        return "\n".join(lines)


def build_rundown(
    quotes: List[Dict[str, Any]],
    positions_meta: List[Dict[str, Any]],
    news_items: List[NewsItem],
    macro_summary: str,
    key_events: Optional[List[str]] = None,
    date: Optional[str] = None,
) -> MorningRundown:
    """
    Parameters
    ----------
    quotes
        List of quote dicts from mcp__Robinhood__get_equity_quotes 'results'.
        Each dict must have 'symbol', 'last_trade_price',
        'last_non_reg_trade_price' (optional), 'adjusted_previous_close'.
    positions_meta
        List of dicts: {'symbol', 'shares', 'avg_cost'}.
    news_items
        Curated list of NewsItem objects for today.
    macro_summary
        One-paragraph macro context string.
    key_events
        Scheduled economic/earnings events for today.
    date
        Date string; defaults to today UTC.
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%A, %B %d %Y")

    quote_map: Dict[str, Dict[str, Any]] = {q["symbol"]: q for q in quotes}

    positions: List[PositionSnapshot] = []
    for meta in positions_meta:
        sym = meta["symbol"]
        q = quote_map.get(sym)
        if not q:
            continue
        prev_close = float(q.get("adjusted_previous_close", 0))
        reg_price = float(q.get("last_trade_price", prev_close))
        ah_raw = q.get("last_non_reg_trade_price")
        ah_price = float(ah_raw) if ah_raw else reg_price

        ah_chg_pct = (ah_price - prev_close) / prev_close * 100 if prev_close else 0
        ah_chg_dollar = meta["shares"] * (ah_price - prev_close)
        avg_cost = meta["avg_cost"]
        total_pnl_pct = (ah_price - avg_cost) / avg_cost * 100 if avg_cost else 0

        positions.append(PositionSnapshot(
            symbol=sym,
            shares=meta["shares"],
            avg_cost=avg_cost,
            prev_close=prev_close,
            ah_price=ah_price,
            ah_change_pct=ah_chg_pct,
            ah_change_dollar=ah_chg_dollar,
            total_pnl_pct=total_pnl_pct,
        ))

    top_movers = sorted(positions, key=lambda p: abs(p.ah_change_pct), reverse=True)[:8]

    return MorningRundown(
        date=date,
        macro_summary=macro_summary,
        key_events=key_events or [],
        positions=positions,
        news_items=news_items,
        top_movers_ah=top_movers,
    )
