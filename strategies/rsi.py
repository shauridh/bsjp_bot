"""Strategi RSI sederhana."""

from __future__ import annotations

import pandas as pd
from utils.risk_management import compute_atr, dynamic_sl_tp


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
    elif rsi_value < oversold:
        direction = "BUY"
    else:
        return None

    # Risk management: ATR-based SL/TP
    atr = compute_atr(history, period=14)
    sl, tp = dynamic_sl_tp(price, atr, rr=1.5, direction=direction)

    return {
        "symbol": data.get("symbol"),
        "strategy": f"RSI {direction}",
        "entry": round(price, 4),
        "tp": tp,
        "sl": sl,
        "data": data,
        "comment": f"RSI={rsi_value:.2f} ATR={atr:.2f}",
    }
