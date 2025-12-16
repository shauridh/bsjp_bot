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
TICKERS = [
    # BANKING
    "BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BRIS", "ARTO", "BBHI", "BNGA", "PNBN", "BDMN", "BJBR",
    # MINERAL & METAL
    "ANTM", "INCO", "MDKA", "TINS", "MBMA", "NCKL", "HRUM", "BRMS", "PSAB",
    # ENERGY
    "ADRO", "PTBA", "ITMG", "UNTR", "INDY", "BUMI", "MEDC", "PGAS", "AKRA", "ELSA", "DOID", "KKGI",
    # CONSUMER & RETAIL
    "ICBP", "INDF", "UNVR", "MYOR", "KLBF", "SIDO", "AMRT", "MIDI", "ACES", "MAPI", "MAPA", "ERAA", "CMRY",
    # TECH & DIGITAL
    "GOTO", "EMTK", "BUKA", "WIRG", "MTDL", "BELI",
    # PROPERTY & CONSTRUCTION
    "BSDE", "CTRA", "SMRA", "PWON", "ASRI", "PTPP", "WIKA", "ADHI", "WEGE", "TOTL",
    # INFRA & TELCO
    "TLKM", "EXCL", "ISAT", "JSMR", "META", "TOWR", "TBIG", "CENT",
    # BASIC IND
    "ASII", "SMGR", "INTP", "JPFA", "CPIN", "INKP", "TKIM", "BRPT", "TPIA", "ESSA", "MAIN",
    # TRADERS FAVORITE (VOLATILE)
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
        # Ambil data 60 hari untuk perhitungan swing support
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
    
    # RSI (Relative Strength Index)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # EMA Trend
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    return df

# --- SWING TRADING PLAN CALCULATOR ---
def calculate_trading_plan(df, price):
    # 1. Support & Resistance (Low/High 20 hari)
    support_swing = df['low'].tail(20).min()
    resistance_swing = df['high'].tail(20).max()
    
    # 2. Stop Loss (2% di bawah support)
    sl = int(support_swing * 0.98)
    
    # 3. Hitung TP Berjenjang
    risk = price - sl
    if risk <= 0: risk = price * 0.05 # Fallback logic
    
    tp1 = int(price + (risk * 1.5))
    tp2 = int(price + (risk * 2.5))
    tp3 = int(price + (risk * 3.5))
    
    # 4. Kondisi Trend
    last = df.iloc[-1]
    trend_status = "Sideways ➡️"
    if last['close'] > last['EMA_20'] > last['EMA_50']:
        trend_status = "Strong Uptrend 🚀"
    elif last['close'] < last['EMA_20'] and last['close'] > last['EMA_50']:
        trend_status = "Buy On Weakness ⚠️"
    elif last['close'] < last['EMA_50']:
        trend_status = "Downtrend 🔻"
        
    # 5. Risk Label
    risk_pct = ((price - sl) / price) * 100
    risk_label = "🟢 Low Risk" if risk_pct < 5.0 else "🔴 High Risk"
    
    return {
        "status": trend_status,
        "risk_label": risk_label,
        "buy_area": f"{int(price*0.99)} - {int(price)}",
        "support": int(support_swing),
        "resistance": int(resistance_swing),
        "sl": sl,
        "tp1": tp1, "tp2": tp2, "tp3": tp3
    }

# --- JADWAL 1: PAGI (SCALPING 09:20) ---
def analyze_morning_entry():
    print(f"[{datetime.now()}] Scanning Morning Scalp...")
    candidates = []
    
    for ticker in TICKERS:
        try:
            df = get_market_data(ticker)
            if df is None: continue
            df = add_indicators(df)
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Logic Pagi (Volatile):
            if last['close'] <= last['open']: continue
            change_pct = ((last['close'] - prev['close']) / prev['close']) * 100
            if not (1.0 <= change_pct <= 6.0): continue # Range aman
            
            # Vol shock
            vol_target = last['VOL_SMA_20'] * 0.20
            if last['volume'] < vol_target: continue

            candidates.append({
                'symbol': ticker,
                'price': int(last['close']),
                'change': round(change_pct, 2),
                'vol': round((last['volume']/last['VOL_SMA_20'])*100, 1)
            })
            time.sleep(0.2)
        except: continue

    candidates.sort(key=lambda x: x['vol'], reverse=True)
    top = candidates[:5]
    
    if top:
        msg = "⚡ <b>MORNING SCALPING (09:20 WIB)</b>\n"
        msg += "<i>High Risk - Fast Trade Strategy</i>\n\n"
        for c in top:
            tp = int(c['price'] * 1.02)
            sl = int(c['price'] * 0.98)
            msg += f"🚀 <b>{c['symbol']}</b> (+{c['change']}%)\n"
            msg += f"Vol Progress: {c['vol']}%\n"
            msg += f"TP: {tp} | SL: {sl}\n\n"
        send_telegram(msg)

# --- JADWAL 2: SORE (BSJP + SWING PLAN 14:50) ---
def analyze_bsjp_swing():
    send_telegram("📊 <b>MARKET CLOSE DASHBOARD</b>\nScreening Data...")
    
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
            
            # --- FILTER DIPERLONGGAR (Agar Data Masuk) ---
            # 1. Harus Hijau (Change > 0.1%)
            # 2. Volume minimal 80% dari rata-rata (0.8x) -> Tidak harus 1.3x kalau market sepi
            if (change_pct >= 0.1) and (vol_ratio >= 0.8):
                
                plan = calculate_trading_plan(df, last['close'])
                
                candidates.append({
                    'symbol': ticker,
                    'price': int(last['close']),
                    'change': round(change_pct, 2),
                    'vol_x': round(vol_ratio, 1),
                    'plan': plan
                })
            
            time.sleep(0.2)
        except: continue

    # Urutkan dari Volume Rasio Tertinggi
    candidates.sort(key=lambda x: x['vol_x'], reverse=True)
    top = candidates[:5] 
    
    if top:
        msg = f"💎 <b>REKOMENDASI SAHAM HARI INI</b>\n📅 {datetime.now().strftime('%d/%m/%Y')}\n"
        
        for c in top:
            p = c['plan']
            msg += f"\n=========================\n"
            msg += f"🔥 <b>{c['symbol']}</b> (+{c['change']}%)\n"
            msg += f"Vol: {c['vol_x']}x Rata-rata\n"
            msg += f"Kondisi: <b>{p['status']}</b>\n"
            msg += f"Resiko: {p['risk_label']}\n\n"
            
            msg += f"📋 <b>TRADING PLAN:</b>\n"
            msg += f"🛒 Buy Area: {p['buy_area']}\n"
            msg += f"🛡 Support: {p['support']} | 🚧 Resist: {p['resistance']}\n"
            msg += f"🎯 TP1: {p['tp1']} | TP2: {p['tp2']} | TP3: {p['tp3']}\n"
            msg += f"🛑 Stop Loss: < {p['sl']}\n"
            
        msg += "\n=========================\n<i>Disclaimer On. Do Your Own Research.</i>"
        send_telegram(msg)
    else:
        send_telegram("⚠️ Market Sangat Sepi. Tidak ada saham hijau dengan volume valid.")

# --- JADWAL ---
def heartbeat():
    send_telegram("☀️ <b>Super Bot Saham Online</b>\nList: 100+ Saham Likuid\nJadwal: 09:20 & 14:50")

# Setup Jadwal
schedule.every().day.at("08:30").do(heartbeat)
schedule.every().day.at("09:20").do(analyze_morning_entry) 
schedule.every().day.at("15:05").do(analyze_bsjp_swing)

if __name__ == "__main__":
    print("🤖 Bot Started...")
    
    # -- JIKA INGIN TES LANGSUNG, HAPUS TANDA PAGAR DI BAWAH INI --
    # analyze_bsjp_swing() 
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
