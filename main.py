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
        # Ambil data 200 hari
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
    # 1. Volume MA 20
    df['VOL_SMA_20'] = df['volume'].rolling(window=20).mean()
    # 2. Price MA 5
    df['MA_5'] = df['close'].rolling(window=5).mean()
    # 3. EMA 20 (Visual Trend)
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    return df

# --- TRADING PLAN CALCULATOR ---
def calculate_trading_plan(df, price, high_period):
    support = df['low'].tail(20).min()
    resistance = df['high'].tail(20).max()
    
    sl = int(support * 0.98)
    risk = price - sl
    if risk <= 0: risk = price * 0.05
    
    tp1 = int(price + (risk * 1.5))
    tp2 = int(price + (risk * 2.5))
    
    high_ratio = price / high_period 
    trend_txt = "Strong Uptrend 🚀" if price > df.iloc[-1]['EMA_20'] else "Reversal/Weak ⚠️"
    
    return {
        "status": trend_txt,
        "high_ratio": high_ratio,
        "buy_area": f"{int(price*0.99)} - {int(price)}",
        "sl": sl, "tp1": tp1, "tp2": tp2,
        "support": int(support), "resistance": int(resistance)
    }

# --- LOGIKA UTAMA SCREENER PDF ---
def analyze_bsjp_pdf_rules():
    print("Mulai Screening BSJP (Mode PDF)...")
    send_telegram("🔍 <b>SCREENING BSJP (PDF RULES)</b>\nSedang mengecek volume meledak...")
    
    candidates = []
    
    for ticker in TICKERS:
        try:
            df = get_market_data(ticker)
            if df is None or len(df) < 30: continue
            
            df = add_indicators(df)
            last = df.iloc[-1]
            
            # --- RULE FILTER PDF ---
            if last['close'] <= 50: continue
            
            value_tx = last['close'] * last['volume']
            if value_tx < 5_000_000_000: continue
            
            if last['close'] < last['MA_5']: continue
            
            highest_price = df['high'].max()
            if last['close'] < (0.7 * highest_price): continue
            
            if last['VOL_SMA_20'] == 0: continue
            vol_ratio = last['volume'] / last['VOL_SMA_20']
            
            # SYARAT UTAMA: VOLUME > 2x Volume Rata-Rata
            if vol_ratio >= 2.0:
                plan = calculate_trading_plan(df, last['close'], highest_price)
                
                candidates.append({
                    'symbol': ticker,
                    'price': int(last['close']),
                    'change': round(((last['close'] - df.iloc[-2]['close'])/df.iloc[-2]['close'])*100, 2),
                    'vol_x': round(vol_ratio, 1),
                    'val_b': round(value_tx / 1_000_000_000, 1),
                    'plan': plan
                })
            
            time.sleep(0.2)
        except: continue

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
            msg += f"📋 <b>PLAN:</b> Buy {p['buy_area']}\n"
            msg += f"🎯 TP1: {p['tp1']} | TP2: {p['tp2']}\n"
            msg += f"🛑 SL: < {p['sl']}\n"
        send_telegram(msg)
    else:
        send_telegram("⚠️ <b>ZONK!</b> Tidak ada saham Vol > 2x Avg hari ini.")

# --- JADWAL ---
def heartbeat():
    send_telegram("☀️ Bot BSJP Standby")

schedule.every().day.at("08:30").do(heartbeat)
# Saya ubah ke 14:45 untuk besok
schedule.every().day.at("14:45").do(analyze_bsjp_pdf_rules)

if __name__ == "__main__":
    print("🤖 Bot BSJP Started...")
    
    # --- [PENTING] BARIS INI AKAN MENJALANKAN BOT LANGSUNG SAAT START ---
    # Tidak perlu menunggu jadwal, langsung jalan sekarang.
    try:
        analyze_bsjp_pdf_rules() 
    except Exception as e:
        print(f"Error direct run: {e}")
    # --------------------------------------------------------------------

    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except:
            time.sleep(10)
