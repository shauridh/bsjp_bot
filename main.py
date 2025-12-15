import os
import time
import requests
import pandas as pd
import pandas_ta as ta
import schedule
from datetime import datetime
import pytz

# --- KONFIGURASI ---
GOAPI_KEY = os.getenv("GOAPI_KEY", "ISI_API_KEY_DISINI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ISI_TOKEN_DISINI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "ISI_CHAT_ID_DISINI")

# List Saham LQ45 / Bluechip
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
        print(f"Error sending telegram: {e}")

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
        
        for c in ['open', 'high', 'low', 'close', 'volume']:
            df[c] = df[c].astype(float)
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def analyze_market():
    print(f"[{datetime.now()}] 🔄 Memulai Screening BSJP...")
    send_telegram("🔄 <b>Analisa Pasar Dimulai...</b>\nMohon tunggu sinyal potensial.")

    candidates = []
    
    for ticker in TICKERS:
        df = get_market_data(ticker)
        if df is None or len(df) < 50: continue
        
        # --- TEKNIKAL PANDAS TA ---
        df['RSI'] = df.ta.rsi(length=14)
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)
        df['VOL_SMA'] = df.ta.sma(close=df['volume'], length=20)
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- LOGIKA SCREENING ---
        change_pct = ((last['close'] - prev['close']) / prev['close']) * 100
        
        # Filter Dasar
        if not (0.5 <= change_pct <= 6.0): continue
        if last['close'] < 100: continue
        
        # Filter Volume & RSI
        vol_ratio = last['volume'] / last['VOL_SMA'] if last['VOL_SMA'] > 0 else 0
        if vol_ratio < 1.3: continue 
        if not (45 <= last['RSI'] <= 68): continue # Zona aman
        
        # Filter Transaksi Value (> 5M)
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
                'score': score,
                'tp': int(last['close'] * 1.03),
                'sl': int(last['close'] * 0.98),
                'reasons': ", ".join(reasons)
            })
            
        time.sleep(0.2)

    candidates.sort(key=lambda x: x['score'], reverse=True)
    top_picks = candidates[:3]
    
    if top_picks:
        msg = f"🚀 <b>BSJP PREMIUM SIGNAL</b> 📅 {datetime.now().strftime('%d/%m')}\n\n"
        for c in top_picks:
            msg += f"💎 <b>{c['symbol']}</b> (Score: {c['score']})\n"
            msg += f"Price: {c['price']} (+{c['change']}%)\n"
            msg += f"🎯 TP: {c['tp']} | 🛑 SL: {c['sl']}\n"
            msg += f"Notes: {c['reasons']}\n\n"
        msg += "<i>Disclaimer On. DYOR.</i>"
        send_telegram(msg)
    else:
        send_telegram("⚠️ <b>No Signal Today</b>\nPasar tidak memenuhi kriteria keamanan (High Risk).")
        print("No candidates found.")

# --- FITUR DETAK JANTUNG ---
def morning_check():
    msg = (
        "☀️ <b>Selamat Pagi!</b>\n"
        "Bot BSJP aktif dan siap memantau pasar hari ini.\n"
        f"Server Time: {datetime.now().strftime('%H:%M')} WIB"
    )
    send_telegram(msg)
    print("[HEARTBEAT] Morning check sent.")

def log_alive():
    # Print ke console Coolify saja, jangan kirim ke Telegram (biar tidak spam)
    print(f"[HEARTBEAT] Bot is alive at {datetime.now().strftime('%H:%M:%S')}")

# --- JADWAL ---
# 1. Cek pagi jam 08:30 WIB
schedule.every().day.at("08:30").do(morning_check)

# 2. Analisa jam 14:50 WIB
schedule.every().day.at("14:50").do(analyze_market)

# 3. Log console setiap 1 jam
schedule.every(1).hours.do(log_alive)

if __name__ == "__main__":
    print("🤖 Bot Starting...")
    
    # Kirim notifikasi saat pertama kali DEPLOY/RESTART
    start_msg = (
        "🤖 <b>Bot BSJP Online!</b>\n"
        "Status: System Restarted / Deployed.\n"
        "Menunggu jadwal screening berikutnya."
    )
    send_telegram(start_msg)
    
    # Loop utama
    while True:
        schedule.run_pending()
        time.sleep(10)
