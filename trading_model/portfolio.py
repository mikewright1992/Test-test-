"""
Portfolio state model. Populated from Robinhood MCP data
(get_portfolio + get_equity_positions responses).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OpenPosition:
    symbol: str
    shares: float
    average_buy_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    def update_price(self, price: float) -> None:
        self.current_price = price
        cost = self.average_buy_price * self.shares
        value = price * self.shares
        self.unrealized_pnl = value - cost
        self.unrealized_pnl_pct = (self.unrealized_pnl / cost * 100) if cost else 0.0


@dataclass
class PortfolioState:
    account_number: str
    total_value: float
    equity_value: float
    cash: float
    buying_power: float
    open_positions: List[OpenPosition] = field(default_factory=list)

    @property
    def position_count(self) -> int:
        return len(self.open_positions)

    @property
    def invested_pct(self) -> float:
        if self.total_value <= 0:
            return 0.0
        return (self.equity_value / self.total_value) * 100

    def summary(self) -> str:
        lines = [
            f"Portfolio ({self.account_number})",
            f"  Total value  : ${self.total_value:.2f}",
            f"  Equity       : ${self.equity_value:.2f} ({self.invested_pct:.1f}%)",
            f"  Cash         : ${self.cash:.2f}",
            f"  Buying power : ${self.buying_power:.2f}",
            f"  Positions    : {self.position_count}",
        ]
        if self.open_positions:
            lines.append("  Holdings:")
            for p in self.open_positions:
                pnl_str = f"{p.unrealized_pnl_pct:+.1f}%" if p.current_price else "—"
                lines.append(f"    {p.symbol:6s}  {p.shares:.4f} sh @ avg ${p.average_buy_price:.2f}  PnL: {pnl_str}")
        return "\n".join(lines)


def build_portfolio_state(
    account_number: str,
    portfolio_data: Dict[str, Any],
    positions_data: Dict[str, Any],
) -> PortfolioState:
    """
    Build a PortfolioState from raw Robinhood MCP response dicts.

    portfolio_data  — the 'data' dict from get_portfolio response
    positions_data  — the 'data' dict from get_equity_positions response
    """
    port = portfolio_data
    total_value = float(port.get("total_value", 0))
    equity_value = float(port.get("equity_value", 0))
    cash = float(port.get("cash", 0))
    bp_obj = port.get("buying_power", {})
    buying_power = float(bp_obj.get("buying_power", cash))

    positions: List[OpenPosition] = []
    for p in positions_data.get("positions", []):
        sym = p.get("symbol", "")
        shares = float(p.get("quantity", 0))
        avg_cost = float(p.get("average_buy_price", 0))
        if shares > 0 and sym:
            positions.append(OpenPosition(symbol=sym, shares=shares, average_buy_price=avg_cost))

    return PortfolioState(
        account_number=account_number,
        total_value=total_value,
        equity_value=equity_value,
        cash=cash,
        buying_power=buying_power,
        open_positions=positions,
    )
