__all__ = [
    'scan_and_save',
    'scan_bpjs_market',
    'format_alert',
]

import requests
import os
from datetime import datetime, timedelta
from database import add_signal
from dotenv import load_dotenv
import yfinance as yf
import pandas_ta as ta
import pandas as pd

load_dotenv()
API_KEY = os.getenv('API_KEY')
GOAPI_URL = 'https://api.goapi.id/v1/stock/idx/summary/top_gainer'  # Bisa diganti ke most_active jika perlu
def validate_trend(ticker):
    try:
        yf_ticker = f"{ticker}.JK"
        end = datetime.now()
        start = end - timedelta(days=62)
        df = yf.download(yf_ticker, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), progress=False)
        if df.empty or len(df) < 20:
            return False, None, None, None
        df['EMA20'] = ta.ema(df['Close'], length=20)
        df['RSI14'] = ta.rsi(df['Close'], length=14)
        current = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else current
        price = current['Close']
        ema20 = current['EMA20']
        rsi14 = current['RSI14']
        volume_yesterday = prev['Volume']
        # Validation rules
        if pd.isna(ema20) or pd.isna(rsi14):
            return False, None, None, None
        uptrend = price > ema20
        rsi_safe = rsi14 < 70
        vol_ok = volume_yesterday > 0
        if uptrend and rsi_safe and vol_ok:
            return True, ema20, rsi14, volume_yesterday
        return False, ema20, rsi14, volume_yesterday
    except Exception as e:
        print(f"TA Error for {ticker}: {e}")
        return False, None, None, None

def fetch_top_stocks():
    headers = {'Authorization': f'Bearer {API_KEY}'}
    try:
        resp = requests.get(GOAPI_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get('data', [])
    except Exception as e:
        print(f"API Error: {e}")
        return []

def filter_stocks(stocks):
    filtered = []
    for stock in stocks:
        price = stock.get('close')
        change_pct = stock.get('change_percent')
        volume = stock.get('volume')
        value = stock.get('value')
        code = stock.get('code')
        # Filter: Price > 50, Change 2-15%, High Volume
        if price and price > 50 and change_pct and 2 < change_pct < 15:
            if volume and value and volume > 100000 and value > 10000000:
                filtered.append({
                    'code': code,
                    'price': price,
                    'change_pct': change_pct,
                    'volume': volume,
                    'value': value
                })
    return filtered

def calculate_tp_sl(price):
    tp = round(price * 1.03)
    sl = round(price * 0.98)
    return tp, sl


# BSJP: Sore, BPJS: Pagi
def scan_and_save(time_str, stocks=None):
    if stocks is None:
        stocks = fetch_top_stocks()
    filtered = filter_stocks(stocks)
    today = datetime.now().date()
    signals = []
    for stock in filtered:
        valid, ema20, rsi14, vol_yest = validate_trend(stock['code'])
        if not valid:
            continue
        tp, sl = calculate_tp_sl(stock['price'])
        add_signal(stock['code'], stock['price'], tp, sl, today, time_str, strategy='BSJP')
        signals.append({
            'code': stock['code'],
            'price': stock['price'],
            'tp': tp,
            'sl': sl,
            'ema20': ema20,
            'rsi14': rsi14,
            'trend': 'Bullish' if stock['price'] > ema20 else 'Bearish',
            'rsi_status': 'Safe' if rsi14 < 70 else 'Overbought'
        })
    return signals

# BPJS: Beli Pagi Jual Sore
def filter_bpjs_stocks(stocks):
    filtered = []
    for stock in stocks:
        price = stock.get('close')
        open_price = stock.get('open')
        change_pct = stock.get('change_percent')
        volume = stock.get('volume')
        value = stock.get('value')
        code = stock.get('code')
        # BPJS: Price > 50, Change 2-10%, Green Candle, High Volume
        if price and price > 50 and change_pct and 2 < change_pct < 10:
            if open_price and price >= open_price:
                if volume and value and volume > 100000 and value > 10000000:
                    filtered.append({
                        'code': code,
                        'price': price,
                        'open': open_price,
                        'change_pct': change_pct,
                        'volume': volume,
                        'value': value
                    })
    return filtered

def calculate_bpjs_tp_sl(price, open_price):
    tp = round(price * 1.025)
    sl = min(round(price * 0.98), open_price)
    return tp, sl

def scan_bpjs_market(time_str, stocks=None):
    if stocks is None:
        stocks = fetch_top_stocks()
    filtered = filter_bpjs_stocks(stocks)
    today = datetime.now().date()
    signals = []
    for stock in filtered:
        valid, ema20, rsi14, vol_yest = validate_trend(stock['code'])
        if not valid:
            continue
        tp, sl = calculate_bpjs_tp_sl(stock['price'], stock['open'])
        add_signal(stock['code'], stock['price'], tp, sl, today, time_str, strategy='BPJS')
        signals.append({
            'code': stock['code'],
            'price': stock['price'],
            'open': stock['open'],
            'tp': tp,
            'sl': sl,
            'ema20': ema20,
            'rsi14': rsi14,
            'trend': 'Bullish' if stock['price'] > ema20 else 'Bearish',
            'rsi_status': 'Safe' if rsi14 < 70 else 'Overbought'
        })
    return signals


def format_alert(signals, time_str, strategy='BSJP'):
    if strategy == 'BPJS':
        header = f"☀️ *[BPJS - MORNING ALERT {time_str}]*"
    else:
        header = f"🚀 *BSJP SIGNAL [{time_str}]*"
    if not signals:
        return f"{header}\nTidak ada saham yang memenuhi kriteria."
    msg = f"{header}\n"
    for s in signals:
        msg += (
            f"💎 **{s['code']}** ({s['price']})\n"
            f"📈 Trend: > EMA20 ({s['trend']})\n"
            f"📊 RSI: {int(s['rsi14']) if s['rsi14'] is not None else '-'} ({s['rsi_status']})\n"
            f"🎯 TP: {s['tp']} | 🛡 SL: {s['sl']}\n\n"
        )
    return msg
