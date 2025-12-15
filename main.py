import os
import time
import requests
import pandas as pd
import pandas_ta as ta
import schedule
from datetime import datetime
import pytz

# --- KONFIGURASI ---
GOAPI_KEY = os.getenv("GOAPI_KEY", "YOUR_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# List Saham LQ45 / Bluechip (Bisa diupdate berkala)
TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNTR", "ICBP", 
    "INDF", "GOTO", "ADRO", "PTBA", "ANTM", "INCO", "MDKA", "PGAS",
    "UNVR", "KLBF", "SMGR", "INTP", "BRIS", "AMRT", "CPIN", "JPFA"
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error sending telegram: {e}")

def get_market_data(ticker):
    # Mengambil data daily (historical)
    url = f"https://api.goapi.io/stock/idx/{ticker}/historical"
    headers = {"X-API-KEY": GOAPI_KEY}
    
    try:
        # Ambil data 50 hari terakhir cukup untuk MA dan RSI
        params = {"to": datetime.now().strftime("%Y-%m-%d"), "limit": 50}
        res = requests.get(url, headers=headers, params=params).json()
        
        if res['status'] != 'success' or not res['data']['results']:
            return None
            
        df = pd.DataFrame(res['data']['results'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Konversi tipe data
        cols = ['open', 'high', 'low', 'close', 'volume']
        for c in cols:
            df[c] = df[c].astype(float)
            
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def calculate_technical(df):
    # RSI 14
    df['RSI'] = df.ta.rsi(length=14)
    # SMA Volume 20
    df['VOL_SMA_20'] = df.ta.sma(close=df['volume'], length=20)
    # EMA 20 & 50 (Trend)
    df['EMA_20'] = df.ta.ema(length=20)
    df['EMA_50'] = df.ta.ema(length=50)
    
    return df.iloc[-1] # Return data hari ini

def analyze_market():
    print(f"[{datetime.now()}] Memulai screening BSJP...")
    send_telegram("🔄 <b>BSJP Screening Started...</b>\nMohon tunggu hasil analisa.")
    
    candidates = []
    
    for ticker in TICKERS:
        df = get_market_data(ticker)
        if df is None: continue
        
        last = calculate_technical(df)
        prev_close = df.iloc[-2]['close']
        
        # --- LOGIKA SCREENING KETAT ---
        
        # 1. Perubahan Harga (+0.5% s/d +5%)
        change_pct = ((last['close'] - prev_close) / prev_close) * 100
        if not (0.5 <= change_pct <= 5.0): continue
        
        # 2. Harga > 100 (Likuiditas dasar)
        if last['close'] < 100: continue
        
        # 3. Volume Spike (> 1.5x Rata-rata 20 hari)
        vol_ratio = last['volume'] / last['VOL_SMA_20'] if last['VOL_SMA_20'] > 0 else 0
        if vol_ratio < 1.5: continue
        
        # 4. RSI Optimal (45-65) - Zona aman untuk swing pendek
        if not (45 <= last['RSI'] <= 65): continue
        
        # 5. Transaction Value > 10 Milyar (Estimasi kasar: Close * Vol)
        # GoAPI volume biasanya lembar saham.
        trx_val = last['close'] * last['volume']
        if trx_val < 10_000_000_000: continue

        # --- CONFIDENCE SCORING (0-100) ---
        score = 50 # Base score
        reasons = []
        
        # Volume boost
        if vol_ratio > 2.0: 
            score += 15
            reasons.append("🔥 Super High Vol")
        elif vol_ratio > 1.5:
            score += 10
            reasons.append("✅ High Vol")
            
        # Trend boost (Close > EMA20 > EMA50)
        if last['close'] > last['EMA_20'] > last['EMA_50']:
            score += 15
            reasons.append("📈 Strong Uptrend")
        
        # Candle shape (Close dekat High = Strong Buying Power)
        if last['close'] >= (last['high'] * 0.98):
            score += 10
            reasons.append("💪 Strong Close")
            
        # Batasi max score
        score = min(score, 99)
        
        if score >= 70:
            # Hitung TP/SL Cerdas (ATR based logic simplified)
            volatility = (last['high'] - last['low']) / last['close']
            tp_pct = max(2.5, volatility * 100 * 1.5) # Min 2.5%
            sl_pct = max(1.5, volatility * 100 * 0.8) # Min 1.5%
            
            candidates.append({
                'symbol': ticker,
                'price': int(last['close']),
                'change': round(change_pct, 2),
                'rsi': round(last['RSI'], 1),
                'vol_ratio': round(vol_ratio, 1),
                'score': score,
                'tp': int(last['close'] * (1 + tp_pct/100)),
                'sl': int(last['close'] * (1 - sl_pct/100)),
                'reasons': ", ".join(reasons)
            })
        
        # Delay agar tidak kena rate limit GoAPI
        time.sleep(0.5)

    # Sort by Score tertinggi & Ambil Top 3
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top_picks = candidates[:3]
    
    # --- KIRIM LAPORAN ---
    if top_picks:
        msg = "🚀 <b>BSJP PREMIUM SIGNAL</b> 🚀\n"
        msg += f"📅 {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n"
        
        for stock in top_picks:
            msg += f"💎 <b>{stock['symbol']}</b> (Score: {stock['score']}%)\n"
            msg += f"├ Price: {stock['price']} ({stock['change']}%)\n"
            msg += f"├ Vol Ratio: {stock['vol_ratio']}x | RSI: {stock['rsi']}\n"
            msg += f"├ 🎯 TP: {stock['tp']} | 🛑 SL: {stock['sl']}\n"
            msg += f"└ Note: {stock['reasons']}\n\n"
        
        msg += "<i>Disclaimer: Do your own research. High Risk.</i>"
    else:
        msg = "⚠️ <b>No BSJP Signal Today</b>\nPasar tidak memenuhi kriteria ketat (Safety First)."
        
    send_telegram(msg)

# --- SCHEDULER ---
def job():
    analyze_market()

# Set Timezone Jakarta
jkt_tz = pytz.timezone('Asia/Jakarta')

# Schedule jam 14:50 WIB
# Note: Library schedule menggunakan waktu sistem.
# Di Docker container, pastikan TZ diset atau gunakan logika datetime manual jika perlu presisi tinggi.
schedule.every().day.at("14:50").do(job)

if __name__ == "__main__":
    print("🤖 Bot Started. Waiting for schedule...")
    # Test run saat start (opsional, untuk debug)
    # analyze_market() 
    
    while True:
        schedule.run_pending()
        time.sleep(10)
