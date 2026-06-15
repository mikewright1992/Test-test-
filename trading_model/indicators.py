"""
Pure-Python technical indicators. No external dependencies.
All functions return lists aligned to the input length; early entries
where insufficient history exists are None.
"""

import statistics
from typing import List, Optional, Tuple


def sma(prices: List[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * (period - 1)
    for i in range(period - 1, len(prices)):
        result.append(sum(prices[i - period + 1 : i + 1]) / period)
    return result


def ema(prices: List[float], period: int) -> List[Optional[float]]:
    if len(prices) < period:
        return [None] * len(prices)
    result: List[Optional[float]] = [None] * (period - 1)
    k = 2.0 / (period + 1)
    ema_val = sum(prices[:period]) / period
    result.append(ema_val)
    for price in prices[period:]:
        ema_val = price * k + ema_val * (1 - k)
        result.append(ema_val)
    return result


def rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    if len(prices) <= period:
        return [None] * len(prices)
    result: List[Optional[float]] = [None] * period
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [abs(min(d, 0.0)) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")
        result.append(100.0 - (100.0 / (1 + rs)))

    return result


def macd(
    prices: List[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)

    macd_line: List[Optional[float]] = []
    for f, s in zip(ema_fast, ema_slow):
        macd_line.append(f - s if f is not None and s is not None else None)

    valid_macd = [v for v in macd_line if v is not None]
    if len(valid_macd) < signal_period:
        nones: List[Optional[float]] = [None] * len(macd_line)
        return macd_line, nones, nones

    raw_signal = ema(valid_macd, signal_period)
    leading_nones = len(macd_line) - len(valid_macd)
    signal_line: List[Optional[float]] = [None] * (leading_nones + signal_period - 1)
    signal_line += raw_signal[signal_period - 1 :]

    histogram: List[Optional[float]] = []
    for m, sg in zip(macd_line, signal_line):
        histogram.append(m - sg if m is not None and sg is not None else None)

    return macd_line, signal_line, histogram


def bollinger_bands(
    prices: List[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    mid = sma(prices, period)
    upper: List[Optional[float]] = [None] * (period - 1)
    lower: List[Optional[float]] = [None] * (period - 1)

    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        std = statistics.pstdev(window)
        upper.append(mid[i] + std_dev * std)  # type: ignore[operator]
        lower.append(mid[i] - std_dev * std)  # type: ignore[operator]

    return upper, mid, lower


def volume_ratio(volumes: List[float], period: int = 20) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * period
    for i in range(period, len(volumes)):
        avg_vol = sum(volumes[i - period : i]) / period
        result.append(volumes[i] / avg_vol if avg_vol > 0 else 1.0)
    return result


def atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> List[Optional[float]]:
    """Average True Range — useful for volatility-adjusted stop placement."""
    if len(closes) < 2:
        return [None] * len(closes)

    true_ranges: List[float] = []
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hpc = abs(highs[i] - closes[i - 1])
        lpc = abs(lows[i] - closes[i - 1])
        true_ranges.append(max(hl, hpc, lpc))

    result: List[Optional[float]] = [None] * period  # includes the missing day 0
    if len(true_ranges) < period:
        return result + [None] * (len(closes) - period)

    atr_val = sum(true_ranges[:period]) / period
    result.append(atr_val)
    for tr in true_ranges[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
        result.append(atr_val)

    return result
