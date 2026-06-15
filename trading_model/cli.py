"""
CLI for the trading model.

Usage (via Claude Code with Robinhood MCP):
    python -m trading_model.cli --symbols AAPL MSFT NVDA
    python -m trading_model.cli --watchlist          # uses config.WATCHLIST
    python -m trading_model.cli --report-only        # analysis only, no trade prompts

The data fetching (get_equity_historicals, get_portfolio, etc.) is done
by Claude Code using the Robinhood MCP tools; this script handles the
analysis and reporting on that data.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from . import AGENTIC_ACCOUNT, WATCHLIST
from .analysis import TradeRecommendation, print_report, run_analysis
from .portfolio import PortfolioState, build_portfolio_state


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="trading_model",
        description="Robinhood trading model — analysis and signal generation",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--symbols", nargs="+", metavar="SYM", help="Symbols to analyse")
    group.add_argument("--watchlist", action="store_true", help="Use the default watchlist from config.py")

    parser.add_argument(
        "--portfolio-json",
        metavar="FILE",
        help="Path to JSON file containing get_portfolio MCP response (data key)",
    )
    parser.add_argument(
        "--positions-json",
        metavar="FILE",
        help="Path to JSON file containing get_equity_positions MCP response (data key)",
    )
    parser.add_argument(
        "--historicals-json",
        metavar="FILE",
        help="Path to JSON file containing {symbol: [candles]} dict",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print the report and exit — do not prompt for trade execution",
    )
    parser.add_argument(
        "--account",
        default=AGENTIC_ACCOUNT,
        help=f"Account number to analyse (default: {AGENTIC_ACCOUNT})",
    )
    return parser.parse_args(argv)


def load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    symbols: List[str] = args.symbols if args.symbols else (WATCHLIST if args.watchlist else [])
    if not symbols and not args.historicals_json:
        print("Specify --symbols, --watchlist, or --historicals-json", file=sys.stderr)
        return 1

    # Load or build placeholder portfolio state
    if args.portfolio_json and args.positions_json:
        port_data = load_json(args.portfolio_json)
        pos_data = load_json(args.positions_json)
        portfolio = build_portfolio_state(args.account, port_data, pos_data)
    else:
        # Minimal placeholder — useful when running analysis offline
        portfolio = PortfolioState(
            account_number=args.account,
            total_value=0.0,
            equity_value=0.0,
            cash=0.0,
            buying_power=0.0,
        )
        print(
            "WARNING: No portfolio data provided — position sizing will be $0. "
            "Pass --portfolio-json and --positions-json for accurate sizing.",
            file=sys.stderr,
        )

    # Load historicals
    if args.historicals_json:
        historicals_by_symbol: Dict[str, List[Dict[str, Any]]] = load_json(args.historicals_json)
    else:
        print(
            "No --historicals-json provided. In Claude Code, fetch data via "
            "mcp__Robinhood__get_equity_historicals for each symbol, save to JSON, then re-run.",
            file=sys.stderr,
        )
        return 1

    recommendations = run_analysis(portfolio, historicals_by_symbol)
    print_report(recommendations, portfolio)

    if not args.report_only:
        actionable = [r for r in recommendations if r.is_actionable()]
        if actionable:
            print()
            print("Actionable trade(s) ready. To execute, ask Claude Code:")
            for r in actionable:
                ps = r.position_size
                if ps:
                    print(
                        f"  Place a market BUY for {ps.shares:.4f} shares of "
                        f"{r.signal.symbol} (~${ps.dollar_amount:.2f}) on account {args.account}"
                    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
