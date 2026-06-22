"""
DCA (dollar-cost averaging) "buy the dip" strategy.

Rule: on days the target symbol is trading below its previous close at the
target check time, buy a fixed dollar amount (default $10) of fractional
shares. On flat/up days, skip. At most one buy per calendar day.

This module only contains the decision logic — it does not place orders or
manage scheduling. See dca_runner.py for the script that evaluates this
logic against a live quote and (optionally) submits the order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .config import DCA_PARAMS, AGENTIC_ACCOUNT


@dataclass
class DCAConfig:
    symbol: str = DCA_PARAMS["symbols"][0]
    dollar_amount: float = DCA_PARAMS["dollar_amount"]
    account_number: str = DCA_PARAMS["account_number"]
    down_day_threshold_pct: float = DCA_PARAMS["down_day_threshold_pct"]
    target_hour: int = DCA_PARAMS["target_hour"]
    target_minute: int = DCA_PARAMS["target_minute"]

    def __post_init__(self):
        if self.account_number != AGENTIC_ACCOUNT:
            raise ValueError(
                f"DCA orders may only be placed in the agentic-allowed account "
                f"({AGENTIC_ACCOUNT}), got {self.account_number!r}."
            )
        if self.dollar_amount <= 0:
            raise ValueError("dollar_amount must be positive")


@dataclass
class DCADecision:
    symbol: str
    should_buy: bool
    reason: str
    dollar_amount: float
    account_number: str
    current_price: float
    previous_close: float
    change_pct: float


def is_down_day(current_price: float, previous_close: float, threshold_pct: float = 0.0) -> bool:
    """True if current_price is below previous_close by at least threshold_pct."""
    if previous_close <= 0:
        return False
    change_pct = (current_price - previous_close) / previous_close * 100
    return change_pct <= -abs(threshold_pct)


def plan_dca_purchase(
    config: DCAConfig,
    current_price: float,
    previous_close: float,
    already_bought_today: bool = False,
) -> DCADecision:
    """
    Decide whether today's DCA buy should fire.

    Parameters
    ----------
    current_price
        Live/last trade price for config.symbol at the check time (~10:30am).
    previous_close
        Prior session's official close for config.symbol.
    already_bought_today
        Pass True if a buy for this symbol/account has already executed
        today, to enforce the one-buy-per-day rule from the caller side
        (the runner script tracks this via a local log).
    """
    change_pct = (
        round((current_price - previous_close) / previous_close * 100, 3)
        if previous_close else 0.0
    )

    if already_bought_today:
        return DCADecision(
            symbol=config.symbol,
            should_buy=False,
            reason="Already bought today — one DCA purchase per day max.",
            dollar_amount=config.dollar_amount,
            account_number=config.account_number,
            current_price=current_price,
            previous_close=previous_close,
            change_pct=change_pct,
        )

    down = is_down_day(current_price, previous_close, config.down_day_threshold_pct)
    if not down:
        return DCADecision(
            symbol=config.symbol,
            should_buy=False,
            reason=f"{config.symbol} is not down vs previous close ({change_pct:+.2f}%) — skipping.",
            dollar_amount=config.dollar_amount,
            account_number=config.account_number,
            current_price=current_price,
            previous_close=previous_close,
            change_pct=change_pct,
        )

    return DCADecision(
        symbol=config.symbol,
        should_buy=True,
        reason=f"{config.symbol} is down {change_pct:+.2f}% vs previous close — buying ${config.dollar_amount:.2f}.",
        dollar_amount=config.dollar_amount,
        account_number=config.account_number,
        current_price=current_price,
        previous_close=previous_close,
        change_pct=change_pct,
    )


def already_ran_today(log_path, symbol: str, today: Optional[date] = None) -> bool:
    """Check a JSONL execution log for a successful buy of `symbol` today."""
    import json
    from pathlib import Path

    today = today or date.today()
    p = Path(log_path)
    if not p.exists():
        return False

    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                entry.get("symbol") == symbol
                and entry.get("status") == "filled_or_submitted"
                and entry.get("date") == today.isoformat()
            ):
                return True
    return False
