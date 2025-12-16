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

# --- LIST SAHAM LIKUID (THE LIQUID 100) ---
# List ini campuran Bluechip & Second Liner yang aman untuk swing/BSJP
TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BRIS", "ARTO", "BBHI", "BNGA", "PNBN", "BDMN", "BJBR",
    "ANTM", "INCO", "MDKA", "TINS", "MBMA", "NCKL", "HRUM", "BRMS", "PSAB",
    "ADRO", "PTBA", "ITMG", "UNTR", "INDY", "BUMI", "MEDC", "PGAS", "AKRA", "ELSA", "DOID", "KKGI",
    "ICBP", "INDF", "UNVR", "MYOR", "KLBF", "SIDO", "AMRT", "MIDI", "ACES", "MAPI", "MAPA", "ERAA", "CMRY",
    "GOTO", "EMTK", "BUKA", "WIRG", "MTDL", "BELI",
    "BSDE", "CTRA", "SMRA", "PWON", "ASRI", "PTPP", "WIKA", "ADHI", "WEGE", "TOTL",
    "TLKM", "EXCL", "ISAT", "JSMR", "META", "TOWR", "TBIG", "CENT",
    "ASII", "SMGR", "INTP", "JPFA", "CPIN", "INKP", "TKIM", "BRPT", "TPIA", "ESSA", "MAIN",
    "GJTL", "AUTO", "DRMA", "IMAS", "SRTG", "DEWA", "ENRG", "KIJA", "SSIA", "MAHA", 
    "GATR", "CUAN", "PANI", "BREN", "AMMN", "RAJA", "WINS", "HATM"
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
        # Ambil data 60 hari untuk analisa swing
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
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Trend (EMA 20 & 50)
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    return df

# --- TRADING PLAN & SCORING ---
def calculate_plan_and_score(df, ticker):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['close']
    
    # 1. Analisa Trend
    trend_status = "Sideways"
    trend_score = 0
    
    if price > last['EMA_20'] and last['EMA_20'] > last['EMA_50']:
        trend_status = "Strong Uptrend 🚀"
        trend_score = 30
    elif price > last['EMA_20']:
        trend_status = "Uptrend ✅"
        trend_score = 20
    elif price < last['EMA_50']:
        trend_status = "Downtrend 🔻"
        trend_score = -50 # JANGAN DIBELI
        
    # 2. Analisa Volume
    vol_ratio = last['volume'] / last['VOL_SMA_20'] if last['VOL_SMA_20'] > 0 else 0
    vol_score = 0
    if vol_ratio >= 2.0: vol_score = 40      # Ledakan Besar
    elif vol_ratio >= 1.5: vol_score = 30    # Akumulasi Kuat
    elif vol_ratio >= 1.25: vol_score = 20   # Akumulasi Awal
    
    # 3. Analisa Candle
    candle_score = 0
    if price > last['open']: candle_score = 20 # Candle Hijau
    change_pct = ((price - prev['close']) / prev['close']) * 100
    if 2.0 <= change_pct <= 8.0: candle_score += 10 # Kenaikan Ideal
    
    # TOTAL SCORE
    total_score = trend_score + vol_score + candle_score
    
    # --- HITUNG TRADING PLAN ---
    support = df['low'].tail(20).min()
    resistance = df['high'].tail(20).max()
    
    sl = int(support * 0.98)
    risk = price - sl
    if risk <= 0: risk = price * 0.05
    
    tp1 = int(price + (risk * 1.5))
    tp2 = int(price + (risk * 2.5))
    
    risk_pct = ((price - sl) / price) * 100
    risk_label = "Low Risk 🟢" if risk_pct < 5 else "Medium Risk 🟡"
    if risk_pct > 10: risk_label = "High Risk 🔴"

    return {
        "score": total_score,
        "status": trend_status,
        "risk_label": risk_label,
        "buy_area": f"{int(price*0.99)} - {int(price)}",
        "sl": sl, "tp1": tp1, "tp2": tp2,
        "change": round(change_pct, 2),
        "vol_x": round(vol_ratio, 1),
        "support": int(support),
        "resistance": int(resistance)
    }

# --- LOGIKA REKOMENDASI TERBAIK (HYBRID BSJP) ---
def analyze_best_recommendation():
    print("Menganalisa Rekomendasi Terbaik...")
    send_telegram("🤖 <b>SMART BSJP SCANNING...</b>\nStrategy: Trend + Vol Accumulation (>1.25x)")
    
    candidates = []
    
    for ticker in TICKERS:
        try:
            df = get_market_data(ticker)
            if df is None or len(df) < 50: continue
            
            df = add_indicators(df)
            last = df.iloc[-1]
            
            # --- FILTER AWAL (Jaring Lebar) ---
            # 1. Harga Minimal Hijau (Close > Open)
            if last['close'] <= last['open']: continue
            
            # 2. Volume Minimal 1.25x (Tidak perlu 2x, yg penting akumulasi)
            if last['VOL_SMA_20'] == 0: continue
            if (last['volume'] / last['VOL_SMA_20']) < 1.25: continue
            
            # 3. Value Transaksi Minimal 5 Milyar (Biar bisa keluar)
            value_tx = last['close'] * last['volume']
            if value_tx < 5_000_000_000: continue
            
            # --- HITUNG SKOR & PLAN ---
            data = calculate_plan_and_score(df, ticker)
            
            # Hanya masukkan yg skornya lumayan (Minimal 60)
            # Ini menyaring saham 'tanggung'
            if data['score'] >= 60:
                candidates.append({
                    'symbol': ticker,
                    'data': data
                })
            
            time.sleep(0.1) # Jeda dikit
        except: continue

    # Urutkan berdasarkan SKOR TERTINGGI (Prioritas)
    candidates.sort(key=lambda x: x['data']['score'], reverse=True)
    top = candidates[:5]
    
    if top:
        msg = f"💎 <b>TOP PICKS HARI INI</b>\n📅 {datetime.now().strftime('%d/%m/%Y')}\n"
        
        for c in top:
            d = c['data']
            msg += f"\n=========================\n"
            msg += f"🔥 <b>{c['symbol']}</b> (+{d['change']}%)\n"
            msg += f"🏆 Score: <b>{d['score']}</b>/100\n"
            msg += f"📊 Vol: {d['vol_x']}x Avg | {d['status']}\n"
            msg += f"⚖️ {d['risk_label']}\n\n"
            
            msg += f"📋 <b>TRADING PLAN:</b>\n"
            msg += f"🛒 Buy: {d['buy_area']}\n"
            msg += f"🎯 TP1: {d['tp1']} | TP2: {d['tp2']}\n"
            msg += f"🛑 SL: < {d['sl']} (Support: {d['support']})\n"
            
        msg += "\n=========================\n<i>Disclaimer On.</i>"
        send_telegram(msg)
    else:
        send_telegram("⚠️ Market Sepi. Tidak ada saham dengan Skor > 60.")

# --- JADWAL ---
def heartbeat():
    send_telegram("☀️ Bot Smart-BSJP Standby")

schedule.every().day.at("08:30").do(heartbeat)
schedule.every().day.at("14:50").do(analyze_best_recommendation)

if __name__ == "__main__":
    print("🤖 Bot Smart-BSJP Started...")
    
    # --- JALANKAN SEKALI SAAT START AGAR USER PUAS ---
    try:
        analyze_best_recommendation()
    except Exception as e:
        print(f"Error Direct Run: {e}")
        
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except:
            time.sleep(10)
