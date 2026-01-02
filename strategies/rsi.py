"""Strategi RSI sederhana."""

from __future__ import annotations

import pandas as pd


def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = avg_loss.replace(0, 1e-9)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def rsi(data: dict, config: dict) -> dict | None:
    history = data.get("history")
    if not history:
        return None

    params = config.get("strategy_params", {}).get("rsi", {})
    period = params.get("period", 14)
    overbought = params.get("overbought", 70)
    oversold = params.get("oversold", 30)

    df = pd.DataFrame(history).sort_values("timestamp")
    df["rsi"] = _compute_rsi(df["close"], period)
    rsi_value = df["rsi"].iloc[-1]
    price = df["close"].iloc[-1]

    if pd.isna(rsi_value):
        return None

    if rsi_value > overbought:
        direction = "SELL"
        tp = price * 0.985
        sl = price * 1.015
    elif rsi_value < oversold:
        direction = "BUY"
        tp = price * 1.015
        sl = price * 0.985
    else:
        return None

    return {
        "symbol": data.get("symbol"),
        "strategy": f"RSI {direction}",
        "entry": round(price, 4),
        "tp": round(tp, 4),
        "sl": round(sl, 4),
        "data": data,
        "comment": f"RSI={rsi_value:.2f}",
    }
