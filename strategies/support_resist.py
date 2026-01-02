"""Strategi support & resistance sederhana."""

from __future__ import annotations

import pandas as pd
from utils.bandarmology import fetch_broker_summary, analyze_bandar
from utils.haka_power import fetch_haka_power, analyze_haka


def support_resist(data: dict, config: dict) -> dict | None:
    history = data.get("history")
    symbol = data.get("symbol", "")
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

    # Bandarmology & HAKA Power integration for IDX symbols
    bandar_info = None
    haka_info = None
    if symbol.endswith(".JK"):
        broker_data = fetch_broker_summary(symbol, config)
        bandar_info = analyze_bandar(broker_data) if broker_data else None
        haka_data = fetch_haka_power(symbol, config)
        haka_info = analyze_haka(haka_data) if haka_data else None

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

    comment = f"Support={support:.2f} Resistance={resistance:.2f}"
    if bandar_info:
        comment += f" | Bandar: {bandar_info['status']} Top Buyer: {bandar_info['top_buyer']} Top Seller: {bandar_info['top_seller']} Net Buy: {bandar_info['net_buy']:.0f}"
    if haka_info:
        comment += f" | HAKA: {haka_info['momentum']} Power: {haka_info['power']:.0f}"

    return {
        "symbol": symbol,
        "strategy": f"Support/Resist {direction}",
        "entry": round(entry, 4),
        "tp": round(tp, 4),
        "sl": round(sl, 4),
        "data": data,
        "comment": comment,
    }
