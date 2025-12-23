import requests
import os
from datetime import datetime
from database import add_signal
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('API_KEY')
GOAPI_URL = 'https://api.goapi.id/v1/stock/idx/summary/top_gainer'  # Bisa diganti ke most_active jika perlu

# Fraksi harga (tick size) logic sederhana
# Untuk simplifikasi, gunakan persentase saja

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

def scan_and_save(time_str):
    stocks = fetch_top_stocks()
    filtered = filter_stocks(stocks)
    today = datetime.now().date()
    signals = []
    for stock in filtered:
        tp, sl = calculate_tp_sl(stock['price'])
        add_signal(stock['code'], stock['price'], tp, sl, today, time_str)
        signals.append({
            'code': stock['code'],
            'price': stock['price'],
            'tp': tp,
            'sl': sl
        })
    return signals

def format_alert(signals, time_str):
    if not signals:
        return f"🚀 *BSJP SIGNAL [{time_str}]*\nTidak ada saham yang memenuhi kriteria."
    msg = f"🚀 *BSJP SIGNAL [{time_str}]*\n"
    for s in signals:
        msg += f"**CODE:** {s['code']}\n**Price:** {s['price']}\n**Plan:** TP {s['tp']} | SL {s['sl']}\n\n"
    return msg
