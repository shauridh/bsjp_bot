import os
import time
import requests
import pandas as pd
import schedule
from datetime import datetime
import pytz

# --- KONFIGURASI ---
GOAPI_KEY = os.getenv("GOAPI_KEY", "ISI_API_KEY_DISINI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ISI_TOKEN_DISINI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "ISI_CHAT_ID_DISINI")

# List Saham LQ45 / Bluechip Pilihan
TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNTR", "ICBP", 
    "INDF", "GOTO", "ADRO", "PTBA", "ANTM", "INCO", "MDKA", "PGAS",
    "UNVR", "KLBF", "SMGR", "INTP", "BRIS", "AMRT", "CPIN", "JPFA"
]

# --- FUNGSI TELEGRAM ---
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Error sending telegram: {e}")

# --- FUNGSI DATA ---
def get_market_data(ticker):
    url = f"https://api.goapi.io/stock/idx/{ticker}/historical"
    headers = {"X-API-KEY": GOAPI_KEY}
    try:
        # Ambil 60 hari data untuk kalkulasi EMA/RSI yang akurat
        params = {"to": datetime.now().strftime("%Y-%m-%d"), "limit": 60}
        res = requests.get(url, headers=headers, params=params, timeout=10).json()
        
        if res['status'] != 'success' or not res['data']['results']:
            return None
            
        df = pd.DataFrame(res['data']['results'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Konversi ke float
        cols = ['open', 'high', 'low', 'close', 'volume']
        for c in cols:
            df[c] = df[c].astype(float)
        return df
    except Exception:
        return None

# --- RUMUS TEKNIKAL MANUAL (PENGGANTI LIBRARY) ---
def add_indicators(df):
    # 1. RSI 14 (Rumus Wilder's Smoothing)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Menggunakan EWMA untuk meniru standar RSI di TradingView/Library
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 2. SMA Volume 20
    df['VOL_SMA_20'] = df['volume'].rolling(window=20).mean()
    
    # 3. EMA 20 & 50
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    return df

# --- LOGIKA UTAMA ---
def analyze_market():
    print(f"[{datetime.now()}] 🔄 Screening dimulai...")
    send_telegram("🔄 <b>BSJP Screening Started...</b>\nMencari sinyal potensial...")
    
    candidates = []
    
    for ticker in TICKERS:
        try:
            df = get_market_data(ticker)
            if df is None or len(df) < 50: continue
            
            # Hitung indikator manual
            df = add_indicators(df)
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # --- FILTERING ---
            
            # 1. Harga Naik (0.5% - 6%)
            change_pct = ((last['close'] - prev['close']) / prev['close']) * 100
            if not (0.5 <= change_pct <= 6.0): continue
            
            # 2. Harga > 100 perak
            if last['close'] < 100: continue
            
            # 3. Volume Spike (> 1.3x rata-rata)
            vol_ratio = last['volume'] / last['VOL_SMA_20'] if last['VOL_SMA_20'] > 0 else 0
            if vol_ratio < 1.3: continue
            
            # 4. RSI Zona Buy (45-68)
            if not (45 <= last['RSI'] <= 68): continue
            
            # 5. Value Transaksi > 5 Miliar
            if (last['close'] * last['volume']) < 5_000_000_000: continue

            # --- SCORING ---
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
                    'rsi': round(last['RSI'], 1),
                    'vol': round(vol_ratio, 1),
                    'score': score,
                    'reasons': ", ".join(reasons)
                })
                
            time.sleep(0.2) # Jeda agar API tidak limit
            
        except Exception as e:
            print(f"Skip {ticker}: {e}")
            continue

    # Kirim Hasil
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top3 = candidates[:3]
    
    if top3:
        msg = f"🚀 <b>BSJP PREMIUM SIGNAL</b> 📅 {datetime.now().strftime('%d/%m')}\n\n"
        for s in top3:
            tp = int(s['price'] * 1.03)
            sl = int(s['price'] * 0.98)
            msg += f"💎 <b>{s['symbol']}</b> (Score: {s['score']})\n"
            msg += f"Price: {s['price']} (+{s['change']}%)\n"
            msg += f"RSI: {s['rsi']} | Vol: {s['vol']}x\n"
            msg += f"🎯 TP: {tp} | 🛑 SL: {sl}\n"
            msg += f"<i>{s['reasons']}</i>\n\n"
        msg += "<i>Disclaimer On. High Risk.</i>"
        send_telegram(msg)
    else:
        send_telegram("⚠️ <b>No Signal Today</b>\nPasar tidak kondusif (High Risk).")

# --- JADWAL & HEARTBEAT ---
def morning_check():
    msg = f"☀️ <b>Bot Standby</b>\nJam: {datetime.now().strftime('%H:%M')} WIB\nMenunggu sesi sore."
    send_telegram(msg)

def log_alive():
    print(f"[ALIVE] {datetime.now().strftime('%H:%M:%S')}")

schedule.every().day.at("08:30").do(morning_check)
schedule.every().day.at("14:50").do(analyze_market)
schedule.every(1).hours.do(log_alive)

if __name__ == "__main__":
    print("🤖 Bot Started (Pure Pandas Mode)...")
    send_telegram("✅ <b>Deploy Berhasil!</b>\nBot BSJP aktif dengan mode Manual Calculation.")
    
    while True:
        schedule.run_pending()
        time.sleep(10)
