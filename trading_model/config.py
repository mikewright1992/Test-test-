"""
Trading model configuration.
Only the Agentic account (agentic_allowed=True) may receive trade orders.
"""

AGENTIC_ACCOUNT = "870949526"

RISK_PARAMS = {
    "max_position_pct": 0.20,       # Max 20% of portfolio in any single stock
    "risk_per_trade_pct": 0.02,     # Risk at most 2% of portfolio per trade
    "stop_loss_pct": 0.05,          # 5% stop loss below entry
    "take_profit_pct": 0.15,        # 15% take profit above entry
    "max_open_positions": 5,        # Hard cap on concurrent positions
    "min_cash_reserve_pct": 0.10,   # Always keep 10% in cash
    "min_order_dollars": 1.00,      # Minimum order size (Robinhood fractional floor)
}

SIGNAL_THRESHOLDS = {
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "rsi_neutral_bullish_max": 50,  # RSI between oversold and this is mildly bullish
    "macd_histogram_threshold": 0.0,
    "volume_spike_multiplier": 1.5, # Volume > 1.5x avg counts as confirmation
    "buy_score_min": 3,             # Min confluence score to generate a BUY signal
    "sell_score_max": -3,           # Max score (most negative) to generate a SELL signal
}

# Default watchlist — symbols to screen when none are specified
WATCHLIST = [
    "AAPL",  # Apple
    "MSFT",  # Microsoft
    "NVDA",  # NVIDIA
    "GOOGL", # Alphabet
    "AMZN",  # Amazon
    "META",  # Meta
    "TSLA",  # Tesla
    "AMD",   # Advanced Micro Devices
    "SPY",   # S&P 500 ETF
    "QQQ",   # Nasdaq-100 ETF
]

# Historical data settings
HISTORICALS_SPAN = "3month"    # 3 months of daily data
HISTORICALS_INTERVAL = "day"
HISTORICALS_BOUNDS = "regular" # Regular trading hours only

# DCA (dollar-cost averaging) strategy defaults
DCA_PARAMS = {
    "symbol": "VOO",
    "dollar_amount": 10.00,      # Buy exactly $10 worth per triggered day
    "account_number": AGENTIC_ACCOUNT,
    "down_day_threshold_pct": 0.0,  # Price below previous close by any amount counts as "down"
    "target_hour": 10,           # Target execution time, local market time (ET)
    "target_minute": 30,
}
