import os
import time
import requests
import pandas as pd
import schedule
from datetime import datetime
import pytz

# --- KONFIGURASI ---
GOAPI_KEY = os.getenv("GOAPI_KEY", "YOUR_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNTR", "ICBP", 
    "INDF", "GOTO", "ADRO", "PTBA", "ANTM", "INCO", "MDKA", "PGAS",
    "UNVR", "KLBF", "SMGR", "INTP", "BRIS", "AMRT", "CPIN", "JPFA"
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error telegram: {e}")

def get_market_data(ticker):
    url = f"https://api.goapi.io/stock/idx/{ticker}/historical"
    headers = {"X-API-KEY": GOAPI_KEY}
    try:
        params = {"to": datetime.now().strftime("%Y-%m-%d"), "limit": 60}
        res = requests.get(url, headers=headers, params=params).json()
        
        if res['status'] != 'success' or not res['data']['results']:
            return None
            
        df = pd.DataFrame(res['data']['results'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        cols = ['open', 'high', 'low', 'close', 'volume']
        for c in cols:
            df[c] = df[c].astype(float)
        return df
    except Exception:
        return None

# --- MANUAL INDICATOR CALCULATION (PENGGANTI PANDAS_TA) ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def add_indicators(df):
    # 1. RSI 14 (Manual Calculation with EWMA for smoother result like TA-Lib)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 2. Volume SMA 20
    df['VOL_SMA_20'] = df['volume'].rolling(window=20).mean()
    
    # 3. EMA 20 & 50
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    return df.iloc[-1]

def analyze_market():
    print(f"[{datetime.now()}] Screening started...")
    # send_telegram("🔄 <b>Checking Market...</b>") # Optional: nyalakan jika ingin notif start
    
    candidates = []
    
    for ticker in TICKERS:
        df = get_market_data(ticker)
        if df is None or len(df) < 50: continue
        
        try:
            prev_close = df.iloc[-2]['close']
            last = add_indicators(df)
            
            # --- LOGIKA SCREENING ---
            change_pct = ((last['close'] - prev_close) / prev_close) * 100
            
            # Filter Awal
            if not (0.5 <= change_pct <= 6.0): continue # Range diperlebar dikit
            if last['close'] < 100: continue
            
            # Volume Check
            vol_ratio = last['volume'] / last['VOL_SMA_20'] if last['VOL_SMA_20'] > 0 else 0
            if vol_ratio < 1.2: continue # Sedikit diperlonggar agar dapat sinyal
            
            # RSI Check
            if not (40 <= last['RSI'] <= 70): continue
            
            # --- SCORING ---
            score = 50
            reasons = []
            
            if vol_ratio > 1.5: 
                score += 15
                reasons.append("High Vol")
            
            if last['close'] > last['EMA_20'] > last['EMA_50']:
                score += 20
                reasons.append("Uptrend")
                
            if last['close'] >= (last['high'] * 0.98):
                score += 10
                reasons.append("Strong Close")
            
            score = min(score, 99)
            
            if score >= 70:
                # Simple TP/SL logic
                candidates.append({
                    'symbol': ticker,
                    'price': int(last['close']),
                    'change': round(change_pct, 2),
                    'rsi': round(last['RSI'], 1),
                    'vol': round(vol_ratio, 1),
                    'score': score,
                    'reasons': ", ".join(reasons)
                })
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            continue
            
        time.sleep(0.2) 

    # Sort & Send
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top = candidates[:3]
    
    if top:
        msg = f"🚀 <b>BSJP SIGNAL {datetime.now().strftime('%d/%m')}</b>\n\n"
        for s in top:
            msg += f"<b>{s['symbol']}</b> (Sc: {s['score']}%)\n"
            msg += f"Price: {s['price']} (+{s['change']}%)\n"
            msg += f"Vol: {s['vol']}x | RSI: {s['rsi']}\n"
            msg += f"<i>{s['reasons']}</i>\n\n"
        send_telegram(msg)
    else:
        print("No signal found.")

# Schedule
schedule.every().day.at("14:50").do(analyze_market)

if __name__ == "__main__":
    print("Bot Ready via Manual Pandas Calculation...")
    while True:
        schedule.run_pending()
        time.sleep(10)
