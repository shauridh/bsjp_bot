def fetch_today_ohlc(code):
    headers = {'Authorization': f'Bearer {API_KEY}'}
    today = datetime.now().date()
    try:
        resp = requests.get(GOAPI_DETAIL_URL.format(code=code), headers=headers, params={
            'date': today.strftime('%Y-%m-%d'),
            'range': '1d'
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        prices = data.get('data', [])
        if prices:
            ohlc = prices[0]
            return ohlc  # dict: open, high, low, close
    except Exception as e:
        print(f"API Error: {e}")
    return None

def evaluate_bpjs_today():
    today = datetime.now().date()
    signals = get_pending_signals(today, strategy='BPJS')
    results = []
    win_count = 0
    for signal in signals:
        ohlc = fetch_today_ohlc(signal.code)
        status = None
        if ohlc:
            high = ohlc.get('high')
            low = ohlc.get('low')
            close = ohlc.get('close')
            entry = signal.price
            if high is not None and low is not None and close is not None:
                if high >= signal.tp:
                    status = SignalStatus.WIN
                    win_count += 1
                elif low <= signal.sl:
                    status = SignalStatus.LOSS
                else:
                    # Floating: close > entry = win, else loss
                    if close > entry:
                        status = SignalStatus.WIN
                    else:
                        status = SignalStatus.LOSS
                update_signal_status(signal.id, status)
                results.append({
                    'code': signal.code,
                    'result': 'WIN' if status == SignalStatus.WIN else 'LOSS',
                    'close': close,
                    'entry': entry
                })
    total = len(signals)
    win_rate = int((win_count / total) * 100) if total else 0
    return results, win_rate

def format_bpjs_report(results, win_rate):
    msg = "☀️ *BPJS - DAILY RECAP*\nToday's Picks:\n"
    for r in results:
        if r['result'] == 'WIN':
            msg += f"✅ {r['code']}: WIN (Close: {r['close']}, Entry: {r['entry']})\n"
        else:
            msg += f"❌ {r['code']}: LOSS (Close: {r['close']}, Entry: {r['entry']})\n"
    msg += f"Win Rate: {win_rate}%"
    return msg
import requests
import os
from datetime import datetime, timedelta
from database import get_pending_signals, update_signal_status, SignalStatus
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('API_KEY')
GOAPI_DETAIL_URL = 'https://api.goapi.id/v1/stock/idx/{code}/historical'  # Endpoint untuk harga harian

def fetch_today_high_low(code):
    headers = {'Authorization': f'Bearer {API_KEY}'}
    today = datetime.now().date()
    try:
        resp = requests.get(GOAPI_DETAIL_URL.format(code=code), headers=headers, params={
            'date': today.strftime('%Y-%m-%d'),
            'range': '1d'
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        prices = data.get('data', [])
        if prices:
            high = prices[0].get('high')
            low = prices[0].get('low')
            return high, low
    except Exception as e:
        print(f"API Error: {e}")
    return None, None

def evaluate_signals():
    yesterday = datetime.now().date() - timedelta(days=1)
    signals = get_pending_signals(yesterday, strategy='BSJP')
    results = []
    win_count = 0
    for signal in signals:
        ohlc = fetch_today_ohlc(signal.code)
        status = None
        if ohlc:
            high = ohlc.get('high')
            low = ohlc.get('low')
            if high is not None and low is not None:
                if high >= signal.tp:
                    status = SignalStatus.WIN
                    win_count += 1
                elif low <= signal.sl:
                    status = SignalStatus.LOSS
                else:
                    status = SignalStatus.PENDING
                update_signal_status(signal.id, status)
                results.append({
                    'code': signal.code,
                    'result': 'WIN' if status == SignalStatus.WIN else 'LOSS' if status == SignalStatus.LOSS else 'PENDING'
                })
    total = len(signals)
    win_rate = int((win_count / total) * 100) if total else 0
    return results, win_rate

def format_report(results, win_rate):
    msg = "📊 *DAILY EVALUATION*\nYesterday's Picks:\n"
    for r in results:
        if r['result'] == 'WIN':
            msg += f"✅ {r['code']}: WIN (Hit TP)\n"
        elif r['result'] == 'LOSS':
            msg += f"❌ {r['code']}: LOSS (Hit SL)\n"
        else:
            msg += f"⏳ {r['code']}: PENDING\n"
    msg += f"Win Rate: {win_rate}%"
    return msg
