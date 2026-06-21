"""
Robinhood Trading Model
Agentic account: 870949526 (agentic_allowed=True)
"""

from .config import AGENTIC_ACCOUNT, RISK_PARAMS, SIGNAL_THRESHOLDS, WATCHLIST
from .indicators import sma, ema, rsi, macd, bollinger_bands, volume_ratio
from .signals import analyze, Signal
from .risk import calculate_position_size, check_portfolio_limits, PositionSize
from .portfolio import PortfolioState, build_portfolio_state
from .analysis import run_analysis, TradeRecommendation
from .dca import DCAConfig, DCADecision, plan_dca_purchase, is_down_day

__all__ = [
    "AGENTIC_ACCOUNT",
    "RISK_PARAMS",
    "SIGNAL_THRESHOLDS",
    "WATCHLIST",
    "sma", "ema", "rsi", "macd", "bollinger_bands", "volume_ratio",
    "analyze", "Signal",
    "calculate_position_size", "check_portfolio_limits", "PositionSize",
    "PortfolioState", "build_portfolio_state",
    "run_analysis", "TradeRecommendation",
    "DCAConfig", "DCADecision", "plan_dca_purchase", "is_down_day",
]
