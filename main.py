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

# --- LIST SAHAM (LIQUID 100) ---
# Kita gunakan list likuid agar screening Value > 5 Milyar lebih efektif
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
        # Ambil data 200 hari (agar bisa cek Near 52 Week High / Harga Tertinggi Tahunan)
        params = {"to": datetime.now().strftime("%Y-%m-%d"), "limit": 200}
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
    # 1. Volume MA 20 (Sesuai Syarat PDF)
    df['VOL_SMA_20'] = df['volume'].rolling(window=20).mean()
    
    # 2. Price MA 5 (Sesuai Syarat PDF)
    df['MA_5'] = df['close'].rolling(window=5).mean()
    
    # 3. EMA untuk Trend Tambahan (Visual)
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    return df

# --- CALCULATOR TRADING PLAN ---
def calculate_trading_plan(df, price, high_period):
    # Support Resistance Simple
    support = df['low'].tail(20).min()
    resistance = df['high'].tail(20).max()
    
    # Stop Loss (Sedikit di bawah support)
    sl = int(support * 0.98)
    
    # TP Berjenjang
    risk = price - sl
    if risk <= 0: risk = price * 0.05
    tp1 = int(price + (risk * 1.5))
    tp2 = int(price + (risk * 2.5))
    
    # Cek Posisi terhadap High (Near 52 Week High)
    # Rasio harga sekarang dibanding harga tertinggi periode ini
    high_ratio = price / high_period 
    
    # Kondisi Trend
    trend_txt = "Strong Uptrend 🚀" if price > df.iloc[-1]['EMA_20'] else "Reversal/Weak ⚠️"
    
    return {
        "status": trend_txt,
        "high_ratio": high_ratio,
        "buy_area": f"{int(price*0.99)} - {int(price)}",
        "sl": sl,
        "tp1": tp1, 
        "tp2": tp2,
        "support": int(support),
        "resistance": int(resistance)
    }

# --- LOGIKA UTAMA SESUAI PDF ---
def analyze_bsjp_pdf_rules():
    send_telegram("🔍 <b>SCREENING BSJP (PDF RULES)</b>\nMencari saham momentum volume meledak > 2x...")
    
    candidates = []
    
    for ticker in TICKERS:
        try:
            df = get_market_data(ticker)
            if df is None or len(df) < 30: continue
            
            df = add_indicators(df)
            last = df.iloc[-1]
            
            # --- RULE 1: HARGA > 50 ---
            if last['close'] <= 50: continue
            
            # --- RULE 2: VALUE TRANSAKSI > 5 MILYAR ---
            value_tx = last['close'] * last['volume']
            if value_tx < 5_000_000_000: continue
            
            # --- RULE 3: PRICE > MA 5 (Short Term Uptrend) ---
            if last['close'] < last['MA_5']: continue
            
            # --- RULE 4: NEAR HIGH (> 70% dari High Tertinggi) ---
            highest_price = df['high'].max() # High selama 200 hari terakhir
            if last['close'] < (0.7 * highest_price): continue
            
            # --- RULE 5 (THE KILLER): VOLUME > 2x VOLUME MA 20 ---
            # Volume hari ini harus 2 kali lipat rata-rata
            if last['VOL_SMA_20'] == 0: continue
            vol_ratio = last['volume'] / last['VOL_SMA_20']
            
            if vol_ratio >= 2.0: # WAJIB DI ATAS 2.0 SESUAI PDF
                
                plan = calculate_trading_plan(df, last['close'], highest_price)
                
                candidates.append({
                    'symbol': ticker,
                    'price': int(last['close']),
                    'change': round(((last['close'] - df.iloc[-2]['close'])/df.iloc[-2]['close'])*100, 2),
                    'vol_x': round(vol_ratio, 1),
                    'val_b': round(value_tx / 1_000_000_000, 1), # Dalam Milyar
                    'plan': plan
                })
            
            time.sleep(0.2)
        except: continue

    # Urutkan dari Volume Spike Tertinggi
    candidates.sort(key=lambda x: x['vol_x'], reverse=True)
    top = candidates[:5]
    
    if top:
        msg = f"💎 <b>HASIL SCREENER BSJP (PDF)</b>\n📅 {datetime.now().strftime('%d/%m/%Y')}\n"
        
        for c in top:
            p = c['plan']
            msg += f"\n=========================\n"
            msg += f"🔥 <b>{c['symbol']}</b> (+{c['change']}%)\n"
            msg += f"📊 Vol Spike: <b>{c['vol_x']}x</b> Avg\n"
            msg += f"💰 Value: {c['val_b']} Milyar\n"
            msg += f"📈 Posisi: {int(p['high_ratio']*100)}% dari High\n"
            
            msg += f"📋 <b>TRADING PLAN:</b>\n"
            msg += f"🛒 Buy Area: {p['buy_area']}\n"
            msg += f"🎯 TP1: {p['tp1']} | TP2: {p['tp2']}\n"
            msg += f"🛑 Stop Loss: < {p['sl']}\n"
            
        msg += "\n=========================\n<i>Rule: Price>MA5, Vol>2xMA20, Val>5M</i>"
        send_telegram(msg)
    else:
        send_telegram("⚠️ <b>ZONK!</b> Tidak ada saham yang lolos filter ketat PDF hari ini.\n(Syarat Vol > 2x Avg tidak terpenuhi)")

# --- JADWAL ---
def heartbeat():
    send_telegram("☀️ <b>Bot BSJP Standby</b>\nMode: Strict PDF Rules (Vol > 2x)")

# Jadwal cek sore
schedule.every().day.at("08:30").do(heartbeat)
[span_7](start_span)schedule.every().day.at("15:16").do(analyze_bsjp_pdf_rules) # Sesuai PDF jam 14:45[span_7](end_span)

if __name__ == "__main__":
    print("🤖 Bot BSJP (PDF Rule) Started...")
    
    # UNCOMMENT BAWAH INI JIKA MAU TES SEKARANG
    # analyze_bsjp_pdf_rules()
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except:
            time.sleep(10)
