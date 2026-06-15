#!/usr/bin/env python3
"""
Top-level convenience runner.

This script is designed to be called BY Claude Code after it fetches
Robinhood data via MCP tools. The typical flow is:

1. Claude Code calls mcp__Robinhood__get_portfolio (account 870949526)
2. Claude Code calls mcp__Robinhood__get_equity_positions (account 870949526)
3. Claude Code calls mcp__Robinhood__get_equity_historicals for each symbol
4. Claude Code calls mcp__Robinhood__get_equity_quotes for real-time prices
5. Claude Code assembles the data and calls run_full_analysis() below
6. For BUY/SELL recommendations, Claude Code calls review_equity_order
   then place_equity_order (account 870949526 only)

Alternatively, pass JSON files from step 1-4 to the CLI:
    python -m trading_model.cli --watchlist \
        --portfolio-json  data/portfolio.json  \
        --positions-json  data/positions.json  \
        --historicals-json data/historicals.json
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from trading_model.analysis import TradeRecommendation, print_report, run_analysis
from trading_model.portfolio import PortfolioState, build_portfolio_state


def run_full_analysis(
    account_number: str,
    portfolio_data: Dict[str, Any],
    positions_data: Dict[str, Any],
    historicals_by_symbol: Dict[str, List[Dict[str, Any]]],
    quotes_by_symbol: Optional[Dict[str, float]] = None,
    verbose: bool = True,
) -> List[TradeRecommendation]:
    """
    Entry point for programmatic use from Claude Code.

    Parameters
    ----------
    account_number
        Must be the agentic_allowed=True account: '870949526'
    portfolio_data
        'data' dict from mcp__Robinhood__get_portfolio response
    positions_data
        'data' dict from mcp__Robinhood__get_equity_positions response
    historicals_by_symbol
        {symbol: list_of_candle_dicts} — candles sorted oldest-first.
        Candle dict keys: 'close_price' (required), 'high_price',
        'low_price', 'volume' (all optional but improve signal quality).
    quotes_by_symbol
        Optional real-time override prices from get_equity_quotes.
        {symbol: last_trade_price_as_float}
    verbose
        If True, prints the full report to stdout.
    """
    portfolio = build_portfolio_state(account_number, portfolio_data, positions_data)
    recommendations = run_analysis(portfolio, historicals_by_symbol, quotes_by_symbol)
    if verbose:
        print_report(recommendations, portfolio)
    return recommendations


if __name__ == "__main__":
    import sys
    from trading_model.cli import main
    sys.exit(main())
