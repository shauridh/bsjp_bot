import os
import time
import requests
import pandas as pd
import schedule
from datetime import datetime
import pytz

# --- KONFIGURASI ---
GOAPI_KEY = os.getenv("GOAPI_KEY", "KOSONG")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "KOSONG")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "KOSONG")

# List Saham
TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNTR", "ICBP", 
    "INDF", "GOTO", "ADRO", "PTBA", "ANTM", "INCO", "MDKA", "PGAS",
    "UNVR", "KLBF", "SMGR", "INTP", "BRIS", "AMRT", "CPIN", "JPFA"
]

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram Token/Chat ID belum diset.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Gagal kirim telegram: {e}")

def get_market_data(ticker):
    url = f"https://api.goapi.io/stock/idx/{ticker}/historical"
    headers = {"X-API-KEY": GOAPI_KEY}
    try:
        # Ambil data 60 hari terakhir
        params = {"to": datetime.now().strftime("%Y-%m-%d"), "limit": 60}
        res = requests.get(url, headers=headers, params=params, timeout=10).json()
        
        if res.get('status') != 'success' or not res.get('data', {}).get('results'):
            return None
            
        df = pd.DataFrame(res['data']['results'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        for c in ['open', 'high', 'low', 'close', 'volume']:
            df[c] = df[c].astype(float)
        return df
    except Exception as e:
        print(f"Error data {ticker}: {e}")
        return None

def add_indicators(df):
    # RSI 14 Manual
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Simple Moving Average Volume
    df['VOL_SMA_20'] = df['volume'].rolling(window=20).mean()
    
    # EMA Trend
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    return df

def analyze_market():
    print(f"[{datetime.now()}] Memulai Screening...")
    # Notifikasi "Start Screening" juga dimatikan biar tenang
    # send_telegram("🔄 Screening dimulai...") 
    
    candidates = []
    
    for ticker in TICKERS:
        try:
            df = get_market_data(ticker)
            if df is None or len(df) < 50: continue
            
            df = add_indicators(df)
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 1. Cek Kenaikan Harga (0.5% - 6%)
            change_pct = ((last['close'] - prev['close']) / prev['close']) * 100
            if not (0.5 <= change_pct <= 6.0): continue
            
            # 2. Cek Volume
            vol_ratio = last['volume'] / last['VOL_SMA_20'] if last['VOL_SMA_20'] > 0 else 0
            if vol_ratio < 1.3: continue
            
            # 3. Cek RSI (45-68)
            if not (45 <= last['RSI'] <= 68): continue
            
            # 4. Transaksi > 5M
            if (last['close'] * last['volume']) < 5_000_000_000: continue

            # SCORING
            score = 50
            reasons = []
            
            if vol_ratio > 2.0:
                score += 15
                reasons.append("🔥 High Vol")
            elif vol_ratio > 1.5:
                score += 10
                reasons.append("✅ Vol Spike")
                
            if last['close'] > last['EMA_20'] > last['EMA_50']:
                score += 20
                reasons.append("📈 Uptrend")
                
            if last['close'] >= (last['high'] * 0.98):
                score += 10
                reasons.append("💪 Strong Close")
            
            if score >= 70:
                candidates.append({
                    'symbol': ticker,
                    'price': int(last['close']),
                    'change': round(change_pct, 2),
                    'score': score,
                    'tp': int(last['close'] * 1.03),
                    'sl': int(last['close'] * 0.98),
                    'reasons': ", ".join(reasons)
                })
            
            time.sleep(0.2) # Jeda sopan ke API
            
        except Exception as e:
            print(f"Skip {ticker}: {e}")
            continue

    # Kirim Hasil
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top = candidates[:3]
    
    if top:
        msg = f"🚀 <b>BSJP SIGNAL</b> 📅 {datetime.now().strftime('%d/%m')}\n\n"
        for s in top:
            msg += f"💎 <b>{s['symbol']}</b> (Score: {s['score']})\n"
            msg += f"Price: {s['price']} (+{s['change']}%)\n"
            msg += f"TP: {s['tp']} | SL: {s['sl']}\n"
            msg += f"<i>{s['reasons']}</i>\n\n"
        msg += "<i>Disclaimer On.</i>"
        send_telegram(msg)
    else:
        # Opsional: Kirim info kalau zonk, atau diam saja.
        print("No signal found.")

# --- JADWAL ---
def morning_check():
    send_telegram(f"☀️ <b>Bot Standby</b>\nServer Time: {datetime.now().strftime('%H:%M')} WIB")

# Setup Jadwal
schedule.every().day.at("08:30").do(morning_check)
schedule.every().day.at("14:50").do(analyze_market)

if __name__ == "__main__":
    print("🤖 SYSTEM STARTED (Silent Mode)")
    # SAYA HAPUS BAGIAN KIRIM TELEGRAM DISINI AGAR TIDAK SPAM
    
    # Loop Utama (Heart of the Bot)
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except Exception as e:
            # Jika ada error jadwal, print aja jangan crash
            print(f"Scheduler Error: {e}")
            time.sleep(10)
