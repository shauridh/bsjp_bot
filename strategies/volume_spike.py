"""Strategi volume spike sederhana."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd


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
    tp = entry * (1 + buffer_pct * 2) if direction == "BUY" else entry * (1 - buffer_pct * 2)
    sl = entry * (1 - buffer_pct) if direction == "BUY" else entry * (1 + buffer_pct)

    comment = (
        f"Volume spike {recent['volume']:.0f} vs avg {avg_volume:.0f} "
        f"({spike_multiplier}x). change={price_change:.2%}"
    )

    return {
        "symbol": data.get("symbol"),
        "strategy": f"Volume Spike {direction}",
        "entry": round(entry, 4),
        "tp": round(tp, 4),
        "sl": round(sl, 4),
        "data": data,
        "comment": comment,
    }
