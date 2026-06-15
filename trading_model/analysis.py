"""
Main analysis pipeline.

Takes pre-fetched market data (historicals + quotes) and portfolio state,
runs signals + risk sizing, and returns ranked trade recommendations.

Data fetching is intentionally NOT done here — that happens through
the Robinhood MCP tools (get_equity_historicals, get_equity_quotes, etc.)
so that Claude Code can call them directly and pass results in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import RISK_PARAMS
from .portfolio import PortfolioState
from .risk import PositionSize, calculate_position_size, check_portfolio_limits, format_position_size
from .signals import Signal, analyze


@dataclass
class TradeRecommendation:
    signal: Signal
    position_size: Optional[PositionSize]
    blocked: bool = False
    block_reason: str = ""

    def is_actionable(self) -> bool:
        return not self.blocked and self.position_size is not None

    def summary(self) -> str:
        lines = [self.signal.summary()]
        if self.blocked:
            lines.append(f"  BLOCKED: {self.block_reason}")
        elif self.position_size:
            lines.append("  " + format_position_size(self.position_size).replace("\n", "\n  "))
        return "\n".join(lines)


def run_analysis(
    portfolio: PortfolioState,
    historicals_by_symbol: Dict[str, List[Dict[str, Any]]],
    quotes_by_symbol: Optional[Dict[str, float]] = None,
) -> List[TradeRecommendation]:
    """
    Parameters
    ----------
    portfolio
        Current portfolio state (from build_portfolio_state).
    historicals_by_symbol
        {symbol: [candle_dict, ...]} sorted oldest-first.
        Each candle must have 'close_price'; optionally 'high_price',
        'low_price', 'volume'.
    quotes_by_symbol
        Optional real-time prices to override the last close.
        {symbol: price}

    Returns
    -------
    List of TradeRecommendation, sorted by signal score descending.
    """
    open_symbols = {p.symbol for p in portfolio.open_positions}
    recommendations: List[TradeRecommendation] = []

    for symbol, historicals in historicals_by_symbol.items():
        signal = analyze(symbol, historicals)

        # Override price with real-time quote if available
        if quotes_by_symbol and symbol in quotes_by_symbol:
            signal.current_price = quotes_by_symbol[symbol]

        if signal.action == "HOLD":
            continue

        # SELL signal — only relevant if we hold the position
        if signal.action == "SELL":
            if symbol not in open_symbols:
                continue
            recommendations.append(
                TradeRecommendation(signal=signal, position_size=None)
            )
            continue

        # BUY signal — check risk limits
        ok, reason = check_portfolio_limits(portfolio.position_count)
        if not ok:
            recommendations.append(
                TradeRecommendation(signal=signal, position_size=None, blocked=True, block_reason=reason)
            )
            continue

        if symbol in open_symbols:
            recommendations.append(
                TradeRecommendation(
                    signal=signal,
                    position_size=None,
                    blocked=True,
                    block_reason="Already holding this position",
                )
            )
            continue

        ps = calculate_position_size(
            symbol=symbol,
            current_price=signal.current_price,
            portfolio_value=portfolio.total_value,
            buying_power=portfolio.buying_power,
        )
        if ps is None:
            recommendations.append(
                TradeRecommendation(
                    signal=signal,
                    position_size=None,
                    blocked=True,
                    block_reason="Insufficient buying power for minimum order",
                )
            )
            continue

        recommendations.append(TradeRecommendation(signal=signal, position_size=ps))

    recommendations.sort(key=lambda r: r.signal.score, reverse=True)
    return recommendations


def print_report(recommendations: List[TradeRecommendation], portfolio: PortfolioState) -> None:
    print("=" * 60)
    print("TRADING MODEL ANALYSIS REPORT")
    print("=" * 60)
    print(portfolio.summary())
    print()

    buys = [r for r in recommendations if r.signal.action == "BUY"]
    sells = [r for r in recommendations if r.signal.action == "SELL"]

    if buys:
        print("BUY SIGNALS")
        print("-" * 40)
        for r in buys:
            print(r.summary())
            print()

    if sells:
        print("SELL SIGNALS")
        print("-" * 40)
        for r in sells:
            print(r.summary())
            print()

    if not buys and not sells:
        print("No actionable signals — all screened symbols are HOLD.")

    print("=" * 60)
    actionable = [r for r in recommendations if r.is_actionable()]
    print(f"Actionable trades: {len(actionable)}")
    if actionable:
        total_deploy = sum(r.position_size.dollar_amount for r in actionable if r.position_size)
        print(f"Total capital to deploy: ${total_deploy:.2f}")
        print(f"Buying power remaining after trades: ${portfolio.buying_power - total_deploy:.2f}")
