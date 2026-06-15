"""
Position sizing and risk management.
Uses fixed-fractional risk: size each trade so the stop loss costs
at most risk_per_trade_pct of total portfolio value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .config import RISK_PARAMS


@dataclass
class PositionSize:
    symbol: str
    shares: float          # Fractional shares allowed on Robinhood market orders
    dollar_amount: float
    stop_loss_price: float
    take_profit_price: float
    risk_amount: float     # Maximum dollar loss if stop is hit
    reward_risk_ratio: float


def calculate_position_size(
    symbol: str,
    current_price: float,
    portfolio_value: float,
    buying_power: float,
    *,
    max_position_pct: float = RISK_PARAMS["max_position_pct"],
    risk_per_trade_pct: float = RISK_PARAMS["risk_per_trade_pct"],
    stop_loss_pct: float = RISK_PARAMS["stop_loss_pct"],
    take_profit_pct: float = RISK_PARAMS["take_profit_pct"],
    min_cash_reserve_pct: float = RISK_PARAMS["min_cash_reserve_pct"],
) -> Optional[PositionSize]:
    if current_price <= 0 or portfolio_value <= 0:
        return None

    # Spendable buying power after keeping cash reserve
    spendable = buying_power * (1.0 - min_cash_reserve_pct)
    if spendable < RISK_PARAMS["min_order_dollars"]:
        return None

    stop_distance_per_share = current_price * stop_loss_pct

    # 1. Risk-based sizing: how many shares can we lose stop_loss on
    #    before hitting 2% portfolio loss?
    risk_dollars = portfolio_value * risk_per_trade_pct
    shares_by_risk = risk_dollars / stop_distance_per_share

    # 2. Position-size cap
    max_position_dollars = portfolio_value * max_position_pct
    shares_by_cap = max_position_dollars / current_price

    # 3. Liquidity cap — can't spend more than spendable
    shares_by_liquidity = spendable / current_price

    shares = min(shares_by_risk, shares_by_cap, shares_by_liquidity)
    shares = max(0.0, shares)
    dollar_amount = round(shares * current_price, 2)

    if dollar_amount < RISK_PARAMS["min_order_dollars"]:
        return None

    stop_price = round(current_price * (1.0 - stop_loss_pct), 2)
    take_profit_price = round(current_price * (1.0 + take_profit_pct), 2)
    actual_risk = round(shares * stop_distance_per_share, 2)
    rr = take_profit_pct / stop_loss_pct  # e.g. 0.15/0.05 = 3.0

    return PositionSize(
        symbol=symbol,
        shares=round(shares, 6),
        dollar_amount=dollar_amount,
        stop_loss_price=stop_price,
        take_profit_price=take_profit_price,
        risk_amount=actual_risk,
        reward_risk_ratio=round(rr, 2),
    )


def check_portfolio_limits(
    open_positions: int,
    max_open_positions: int = RISK_PARAMS["max_open_positions"],
) -> Tuple[bool, str]:
    if open_positions >= max_open_positions:
        return False, f"Max open positions reached ({open_positions}/{max_open_positions})"
    return True, "OK"


def format_position_size(ps: PositionSize) -> str:
    return (
        f"{ps.symbol}: buy ${ps.dollar_amount:.2f} ({ps.shares:.4f} shares)\n"
        f"  Stop loss    : ${ps.stop_loss_price:.2f}\n"
        f"  Take profit  : ${ps.take_profit_price:.2f}\n"
        f"  Max risk     : ${ps.risk_amount:.2f}\n"
        f"  Reward/Risk  : {ps.reward_risk_ratio:.1f}x"
    )
