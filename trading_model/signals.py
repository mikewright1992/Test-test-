"""
Signal generation: combines multiple indicators into a confluence score.
Score range: -5 (strong sell) to +5 (strong buy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import SIGNAL_THRESHOLDS as T
from .indicators import (
    bollinger_bands,
    ema,
    macd,
    rsi,
    sma,
    volume_ratio,
)


@dataclass
class Signal:
    symbol: str
    action: str                     # "BUY" | "SELL" | "HOLD"
    score: int                      # Confluence score
    reasons: List[str]
    current_price: float
    rsi_value: Optional[float]
    trend: str                      # "BULLISH" | "BEARISH" | "NEUTRAL"
    indicators: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"{self.symbol}: {self.action}  (score {self.score:+d}, {self.trend})",
            f"  Price : ${self.current_price:.2f}",
        ]
        if self.rsi_value is not None:
            lines.append(f"  RSI   : {self.rsi_value:.1f}")
        for r in self.reasons:
            lines.append(f"  + {r}")
        return "\n".join(lines)


def _last(values: List[Optional[float]]) -> Optional[float]:
    for v in reversed(values):
        if v is not None:
            return v
    return None


def analyze(symbol: str, historicals: List[Dict[str, Any]]) -> Signal:
    """
    Analyze a list of historical candles (dicts with 'close_price', optionally
    'high_price', 'low_price', 'volume') and return a Signal.

    historicals must be sorted oldest-first (Robinhood's default order).
    """
    if len(historicals) < 30:
        return Signal(symbol, "HOLD", 0, ["Insufficient history (<30 candles)"], 0.0, None, "NEUTRAL")

    closes = [float(h["close_price"]) for h in historicals]
    highs = [float(h.get("high_price", h["close_price"])) for h in historicals]
    lows = [float(h.get("low_price", h["close_price"])) for h in historicals]
    volumes = [float(h["volume"]) for h in historicals if "volume" in h]

    current = closes[-1]
    score = 0
    reasons: List[str] = []
    indicator_snapshot: Dict[str, Any] = {}

    # --- RSI ---
    rsi_vals = rsi(closes)
    rsi_val = _last(rsi_vals)
    indicator_snapshot["rsi"] = rsi_val
    if rsi_val is not None:
        if rsi_val < T["rsi_oversold"]:
            score += 2
            reasons.append(f"RSI oversold ({rsi_val:.1f} < {T['rsi_oversold']})")
        elif rsi_val > T["rsi_overbought"]:
            score -= 2
            reasons.append(f"RSI overbought ({rsi_val:.1f} > {T['rsi_overbought']})")
        elif rsi_val <= T["rsi_neutral_bullish_max"]:
            score += 1
            reasons.append(f"RSI neutral-bullish ({rsi_val:.1f})")

    # --- MACD ---
    macd_line, signal_line, histogram = macd(closes)
    h_curr = _last(histogram)
    # Get second-to-last non-None histogram value for crossover detection
    non_none_hist = [v for v in histogram if v is not None]
    h_prev = non_none_hist[-2] if len(non_none_hist) >= 2 else None
    indicator_snapshot["macd_histogram"] = h_curr
    if h_curr is not None and h_prev is not None:
        if h_curr > 0 and h_prev <= 0:
            score += 2
            reasons.append("MACD bullish crossover")
        elif h_curr < 0 and h_prev >= 0:
            score -= 2
            reasons.append("MACD bearish crossover")
        elif h_curr > 0:
            score += 1
            reasons.append(f"MACD positive momentum ({h_curr:.4f})")
        else:
            score -= 1
            reasons.append(f"MACD negative momentum ({h_curr:.4f})")

    # --- EMA trend (20 vs 50) ---
    ema20_vals = ema(closes, 20)
    ema50_vals = ema(closes, 50)
    e20 = _last(ema20_vals)
    e50 = _last(ema50_vals)
    indicator_snapshot["ema20"] = e20
    indicator_snapshot["ema50"] = e50
    if e20 is not None and e50 is not None:
        if e20 > e50 and current > e20:
            score += 1
            reasons.append(f"Uptrend: price>${e20:.2f}=EMA20>${e50:.2f}=EMA50")
        elif e20 < e50 and current < e20:
            score -= 1
            reasons.append(f"Downtrend: price<{e20:.2f}=EMA20<{e50:.2f}=EMA50")

    # --- 200-day SMA (long-term bias) ---
    sma200_vals = sma(closes, min(200, len(closes) - 1))
    s200 = _last(sma200_vals)
    indicator_snapshot["sma200"] = s200
    if s200 is not None:
        if current > s200:
            score += 1
            reasons.append(f"Above 200-SMA (${s200:.2f}) — long-term uptrend")
        else:
            score -= 1
            reasons.append(f"Below 200-SMA (${s200:.2f}) — long-term downtrend")

    # --- Bollinger Bands ---
    upper_bb, mid_bb, lower_bb = bollinger_bands(closes)
    bb_upper = _last(upper_bb)
    bb_lower = _last(lower_bb)
    bb_mid = _last(mid_bb)
    indicator_snapshot["bb_upper"] = bb_upper
    indicator_snapshot["bb_lower"] = bb_lower
    if bb_upper is not None and bb_lower is not None and bb_mid is not None:
        bb_pct = (current - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
        indicator_snapshot["bb_pct"] = bb_pct
        if current <= bb_lower:
            score += 1
            reasons.append(f"At/below lower Bollinger Band (${bb_lower:.2f})")
        elif current >= bb_upper:
            score -= 1
            reasons.append(f"At/above upper Bollinger Band (${bb_upper:.2f})")

    # --- Volume confirmation ---
    if volumes:
        vol_vals = volume_ratio(volumes)
        vr = _last(vol_vals)
        indicator_snapshot["volume_ratio"] = vr
        if vr is not None and vr >= T["volume_spike_multiplier"]:
            if score > 0:
                score += 1
                reasons.append(f"High-volume confirmation ({vr:.1f}x avg)")
            elif score < 0:
                score -= 1
                reasons.append(f"High-volume selling pressure ({vr:.1f}x avg)")

    # --- Determine action ---
    buy_min = T["buy_score_min"]
    sell_max = T["sell_score_max"]

    if score >= buy_min:
        action, trend = "BUY", "BULLISH"
    elif score <= sell_max:
        action, trend = "SELL", "BEARISH"
    else:
        action = "HOLD"
        trend = "BULLISH" if score > 0 else ("BEARISH" if score < 0 else "NEUTRAL")

    return Signal(
        symbol=symbol,
        action=action,
        score=score,
        reasons=reasons,
        current_price=current,
        rsi_value=rsi_val,
        trend=trend,
        indicators=indicator_snapshot,
    )
