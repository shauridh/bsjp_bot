"""Strategi Moving Average Crossover."""

from __future__ import annotations

import pandas as pd


def ma_crossover(data: dict, config: dict) -> dict | None:
    history = data.get("history")
    if not history:
        return None

    params = config.get("strategy_params", {}).get("ma_crossover", {})
    short_window = params.get("short_window", 9)
    long_window = params.get("long_window", 21)
    if short_window >= long_window:
        long_window = short_window + 5

    df = pd.DataFrame(history)
    df.sort_values("timestamp", inplace=True)
    df["short"] = df["close"].rolling(window=short_window).mean()
    df["long"] = df["close"].rolling(window=long_window).mean()
    recent = df.dropna(subset=["short", "long"]).tail(2)
    if len(recent) < 2:
        return None

    prev_short, prev_long = recent.iloc[0][["short", "long"]]
    curr_short, curr_long = recent.iloc[1][["short", "long"]]

    crossed_up = prev_short <= prev_long and curr_short > curr_long
    crossed_down = prev_short >= prev_long and curr_short < curr_long

    if not (crossed_up or crossed_down):
        return None

    last_close = recent.iloc[1]["close"]
    direction = "BUY" if crossed_up else "SELL"
    tp = last_close * (1.015 if direction == "BUY" else 0.985)
    sl = last_close * (0.985 if direction == "BUY" else 1.015)

    return {
        "symbol": data.get("symbol"),
        "strategy": f"MA Crossover ({direction})",
        "entry": round(last_close, 4),
        "tp": round(tp, 4),
        "sl": round(sl, 4),
        "data": data,
        "comment": f"MA{short_window}/{long_window} crossover {direction.lower()}",
    }
