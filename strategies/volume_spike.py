"""Strategi volume spike sederhana."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd
from utils.risk_management import compute_atr, dynamic_sl_tp, trailing_stop


def volume_spike(data: Dict[str, Any], config: dict) -> Dict[str, Any] | None:
    history = data.get("history")
    if not history:
        return None

    params = config.get("strategy_params", {}).get("volume_spike", {})
    lookback = max(int(params.get("lookback", 20)), 5)
    spike_multiplier = float(params.get("spike_multiplier", 1.8))
    buffer_pct = float(params.get("buffer_pct", 0.0125))

    df = pd.DataFrame(history)
    required_cols = {"timestamp", "close", "volume"}
    if not required_cols.issubset(df.columns):
        return None

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.sort_values("timestamp", inplace=True)
    if len(df) < lookback + 1:
        return None

    recent = df.iloc[-1]
    prev_close = df["close"].iloc[-2]
    window = df.tail(lookback + 1).iloc[:-1]
    avg_volume = window["volume"].mean()
    if avg_volume <= 0:
        return None

    if recent["volume"] < avg_volume * spike_multiplier:
        return None

    price_change = 0.0
    if prev_close:
        price_change = (recent["close"] - prev_close) / prev_close
    direction = "BUY" if price_change >= 0 else "SELL"
    entry = float(recent["close"])
    # Risk management: ATR-based SL/TP
    atr = compute_atr(history, period=14)
    sl, tp = dynamic_sl_tp(entry, atr, rr=1.5, direction=direction)
    # Trailing stop (info only)
    trailing = trailing_stop(entry, entry, atr, direction=direction)

    comment = (
        f"Volume spike {recent['volume']:.0f} vs avg {avg_volume:.0f} "
        f"({spike_multiplier}x). change={price_change:.2%} | ATR={atr:.2f} Trailing={trailing:.2f}"
    )

    return {
        "symbol": data.get("symbol"),
        "strategy": f"Volume Spike {direction}",
        "entry": round(entry, 4),
        "tp": tp,
        "sl": sl,
        "data": data,
        "comment": comment,
    }
