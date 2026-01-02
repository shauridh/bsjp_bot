"""Modul risk management advanced: ATR, trailing stop, dynamic SL/TP."""

import pandas as pd


def compute_atr(history: list[dict], period: int = 14) -> float:
    df = pd.DataFrame(history)
    if df.empty or len(df) < period:
        return 0.0
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    atr = df['TR'].rolling(window=period).mean().iloc[-1]
    return float(atr) if not pd.isna(atr) else 0.0


def dynamic_sl_tp(entry: float, atr: float, rr: float = 1.5, direction: str = "BUY") -> tuple:
    if direction == "BUY":
        sl = entry - atr
        tp = entry + atr * rr
    else:
        sl = entry + atr
        tp = entry - atr * rr
    return round(sl, 4), round(tp, 4)


def trailing_stop(entry: float, price: float, atr: float, direction: str = "BUY") -> float:
    if direction == "BUY":
        return max(entry, price - atr * 0.5)
    else:
        return min(entry, price + atr * 0.5)
