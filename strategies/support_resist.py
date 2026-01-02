"""Strategi support & resistance sederhana."""

from __future__ import annotations

import pandas as pd


def support_resist(data: dict, config: dict) -> dict | None:
    history = data.get("history")
    if not history:
        return None

    params = config.get("strategy_params", {}).get("support_resist", {})
    lookback = params.get("lookback", 20)
    tolerance = params.get("tolerance", 0.0075)

    df = pd.DataFrame(history).sort_values("timestamp").tail(lookback)
    if df.empty:
        return None

    recent_close = df["close"].iloc[-1]
    support = df["low"].min()
    resistance = df["high"].max()

    near_support = abs(recent_close - support) / support <= tolerance
    near_resistance = abs(recent_close - resistance) / resistance <= tolerance

    if near_support:
        direction = "BUY"
        entry = support * (1 + tolerance / 2)
        tp = resistance
        sl = support * (1 - tolerance)
    elif near_resistance:
        direction = "SELL"
        entry = resistance * (1 - tolerance / 2)
        tp = support
        sl = resistance * (1 + tolerance)
    else:
        return None

    return {
        "symbol": data.get("symbol"),
        "strategy": f"Support/Resist {direction}",
        "entry": round(entry, 4),
        "tp": round(tp, 4),
        "sl": round(sl, 4),
        "data": data,
        "comment": f"Support={support:.2f} Resistance={resistance:.2f}",
    }
