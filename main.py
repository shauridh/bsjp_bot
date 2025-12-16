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

# List Saham LQ45 / Bluechip (Bisa ditambah saham gorengan jika berani sesi 1)
TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNTR", "ICBP", 
    "INDF", "GOTO", "ADRO", "PTBA", "ANTM", "INCO", "MDKA", "PGAS",
    "UNVR", "KLBF", "SMGR", "INTP", "BRIS", "AMRT", "CPIN", "JPFA"
]

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, data=data, timeout=10)
    except: pass

def get_market_data(ticker):
    url = f"https://api.goapi.io/stock/idx/{ticker}/historical"
    headers = {"X-API-KEY": GOAPI_KEY}
    try:
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
    except: return None

def add_indicators(df):
    # Volume MA 20
    df['VOL_SMA_20'] = df['volume'].rolling(window=20).mean()
    
    # RSI & EMA
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    return df

# --- [BARU] LOGIKA BUY SESI 1 (MORNING MOMENTUM) ---
def analyze_morning_entry():
    print(f"[{datetime.now()}] Analisa Pagi (Scalping)...")
    send_telegram("☀️ <b>MORNING SCALPING (09:20 WIB)</b>\nMencari saham momentum tinggi...")
    
    candidates = []
    
    for ticker in TICKERS:
        try:
            df = get_market_data(ticker)
            if df is None or len(df) < 50: continue
            
            df = add_indicators(df)
            last = df.iloc[-1]   # Data Hari Ini (Realtime running)
            prev = df.iloc[-2]   # Data Kemarin
            
            # 1. HARGA HARUS HIJAU (Open < Close)
            if last['close'] <= last['open']: continue
            
            # 2. Syarat Kenaikan (Minimal 1% tapi jangan > 5% takut guyur)
            change_pct = ((last['close'] - prev['close']) / prev['close']) * 100
            if not (1.0 <= change_pct <= 5.0): continue
            
            # 3. VOLUME SHOCK (Inti Strategi)
            # Jam 09:20 (baru 20 menit), volume harus sudah > 20% rata-rata harian
            # Kalau volume segini gede di awal, berarti demand kuat.
            vol_target = last['VOL_SMA_20'] * 0.20 
            if last['volume'] < vol_target: continue

            candidates.append({
                'symbol': ticker,
                'price': int(last['close']),
                'change': round(change_pct, 2),
                'vol_progress': round((last['volume'] / last['VOL_SMA_20']) * 100, 1)
            })
            time.sleep(0.2)
        except: continue

    # Kirim Sinyal
    candidates.sort(key=lambda x: x['vol_progress'], reverse=True)
    top = candidates[:3]
    
    if top:
        msg = "⚡ <b>FAST TRADE SIGNAL (High Risk)</b>\n"
        msg += "<i>Strategy: Morning Volume Spike</i>\n\n"
        for c in top:
            # TP Pendek untuk Scalping
            tp = int(c['price'] * 1.02) # Cuan 2% bungkus
            sl = int(c['price'] * 0.98) # Rugi 2% buang
            msg += f"🚀 <b>{c['symbol']}</b> (+{c['change']}%)\n"
            msg += f"Vol: {c['vol_progress']}% of Daily Avg\n"
            msg += f"TP: {tp} | SL: {sl}\n\n"
        msg += "<i>Valid sampai jam 10:00. Disiplin!</i>"
        send_telegram(msg)
    else:
        send_telegram("⚠️ Pagi sepi. Tidak ada ledakan volume.")

# --- LOGIKA SESI 2 (BSJP) ---
def analyze_bsjp():
    send_telegram("🚀 <b>BSJP SCREENING (14:50 WIB)</b>...")
    candidates = []
    for ticker in TICKERS:
        try:
            df = get_market_data(ticker)
            if df is None or len(df) < 50: continue
            df = add_indicators(df)
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            change_pct = ((last['close'] - prev['close']) / prev['close']) * 100
            vol_ratio = last['volume'] / last['VOL_SMA_20'] if last['VOL_SMA_20'] > 0 else 0
            
            # Syarat BSJP
            if not (0.5 <= change_pct <= 6.0): continue
            if vol_ratio < 1.3: continue
            if not (45 <= last['RSI'] <= 68): continue
            
            score = 50
            if vol_ratio > 2.0: score += 15
            if last['close'] > last['EMA_20'] > last['EMA_50']: score += 20
            
            if score >= 70:
                candidates.append({
                    'symbol': ticker,
                    'price': int(last['close']),
                    'change': round(change_pct, 2),
                    'score': score
                })
            time.sleep(0.2)
        except: continue

    candidates.sort(key=lambda x: x['score'], reverse=True)
    top = candidates[:3]
    
    if top:
        msg = f"💎 <b>BSJP SIGNAL</b> 📅 {datetime.now().strftime('%d/%m')}\n\n"
        for c in top:
            tp = int(c['price'] * 1.03)
            sl = int(c['price'] * 0.98)
            msg += f"<b>{c['symbol']}</b> (Sc: {c['score']})\n"
            msg += f"Price: {c['price']} (+{c['change']}%)\n"
            msg += f"🎯 TP: {tp} | 🛑 SL: {sl}\n\n"
        send_telegram(msg)
    else:
        send_telegram("⚠️ Market tidak cocok untuk BSJP.")

# --- JADWAL ---
def morning_check():
    send_telegram("☀️ <b>Bot Ready</b>\n09:20 -> Scalping Signal\n14:50 -> BSJP Signal")

schedule.every().day.at("08:30").do(morning_check)
schedule.every().day.at("09:20").do(analyze_morning_entry) # Sinyal Pagi
schedule.every().day.at("14:50").do(analyze_bsjp)          # Sinyal Sore

if __name__ == "__main__":
    print("🤖 Bot Saham (Scalp + BSJP) Started...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
