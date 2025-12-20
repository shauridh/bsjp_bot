import requests
import time
import datetime
import os
import json
import pandas as pd
import traceback
from urllib.parse import quote

# --- KONFIGURASI ---
API_KEY = os.getenv("GOAPI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TRADES_FILE = "active_trades.json"

BASE_URL = "https://api.goapi.io"
HEADERS = {
    "X-API-KEY": API_KEY,
    "Accept": "application/json"
}

# --- DATABASE MANAGER ---
def load_trades():
    if not os.path.exists(TRADES_FILE): return {}
    try:
        with open(TRADES_FILE, 'r') as f:
            return json.load(f)
    except: return {}

def save_trades(trades):
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=4)

def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    print(f"🔔 TELEGRAM: {message.splitlines()[0]}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": "True"}
    try: requests.post(url, data=data, timeout=10)
    except: pass

def get_goapi(endpoint, params=None):
    try:
        url = f"{BASE_URL}{endpoint}"
        res = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if res.status_code != 200: return None
        data = res.json()
        if data.get('status') == 'error': return None
        return data.get('data')
    except: return None

# --- TEKNIKAL ANALISIS ENGINE ---
def get_technical_data(ticker):
    """Mengambil dan menghitung indikator teknikal"""
    try:
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=60)
        
        hist_data = get_goapi(f"/stock/idx/{ticker}/historical", {
            'from': start_date.strftime("%Y-%m-%d"),
            'to': today.strftime("%Y-%m-%d")
        })
        
        if not hist_data or 'results' not in hist_data: return None

        df = pd.DataFrame(hist_data['results'])
        if len(df) < 30: return None

        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df = df.sort_values('date') 

        # Indikator Dasar
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['Vol_MA20'] = df['volume'].rolling(window=20).mean()
        
        # Indikator Swing (High/Low 10 hari terakhir)
        df['Swing_High'] = df['high'].rolling(window=10).max()
        df['Swing_Low'] = df['low'].rolling(window=10).min()

        return df
    except: return None

# --- STRATEGI 1: AGGRESSIVE BREAKOUT (User Original) ---
def check_breakout_setup(df):
    last = df.iloc[-1]
    
    price = float(last['close'])
    vol = float(last['volume'])
    ma5 = float(last['MA5'])
    ma20_vol = float(last['Vol_MA20'])
    value = price * vol
    
    # Syarat: Price > MA5 & Volume Meledak 2x Lipat
    if price > 50 and value > 500_000_000:
        if price > ma5 and vol > (ma20_vol * 2):
            return {
                "type": "🔥 BREAKOUT",
                "price": int(price),
                "desc": f"Vol {round(vol/ma20_vol,1)}x Avg (Agresif)",
                "tp": int(price * 1.04),
                "sl": int(price * 0.96)
            }
    return None

# --- STRATEGI 2: PULLBACK / RETEST (New Request) ---
def check_pullback_setup(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = float(last['close'])
    vol = float(last['volume'])
    ma20 = float(last['MA20'])
    vol_ma20 = float(last['Vol_MA20'])
    
    swing_high = float(last['Swing_High'])
    swing_low = float(last['Swing_Low'])
    
    # Syarat 1: Masih Uptrend (Harga di atas MA20)
    if price < ma20: return None
    
    # Syarat 2: Sedang Koreksi (Harga < Swing High)
    # Ini simulasi "Retest" atau "Flag"
    if price >= swing_high: return None # Ini breakout, bukan pullback
    
    # Syarat 3: COMPRESSION (Volume Kering)
    # Volume hari ini di bawah rata-rata (Penjual lemah)
    if vol > vol_ma20: return None 
    
    # Syarat 4: Fibonacci Retracement Area (Golden Zone)
    # Cek apakah harga ada di area 50% - 61.8% dari range swing
    fib_50 = swing_low + 0.5 * (swing_high - swing_low)
    fib_618 = swing_low + 0.618 * (swing_high - swing_low)
    
    # Kita toleransi range sedikit di atas Fib 50
    if price >= fib_50:
        return {
            "type": "🧲 PULLBACK / RETEST",
            "price": int(price),
            "desc": "Vol Kering + Dekat Support (Low Risk)",
            "tp": int(swing_high), # Target balik ke High
            "sl": int(ma20 * 0.98) # SL di bawah MA20
        }
        
    return None

# --- SCANNER ENGINE ---
def run_bsjp_scanner(session_name="Sesi 1"):
    print(f"💎 Scan Hybrid ({session_name})...")
    try:
        # Kita ambil Top Gainer & Trending untuk pool kandidat
        candidates = []
        
        # 1. Dari Top Gainer (Untuk cari Breakout)
        gainers = get_goapi("/stock/idx/top_gainer")
        if gainers:
            res = gainers.get('results', [])[:5] # Ambil 5
            for x in res:
                if 'ticker' in x: candidates.append(x['ticker'])
                elif 'symbol' in x: candidates.append(x['symbol'])
                
        # 2. Dari Trending (Untuk cari Pullback)
        # Saham trending biasanya liquid tapi mungkin lagi merah (koreksi)
        trending = get_goapi("/stock/idx/trending")
        if trending:
            res = trending.get('results', [])[:5] # Ambil 5
            for x in res:
                s = x['symbol']
                if s not in candidates: candidates.append(s)

        # Hapus duplikat & Batasi max 8 saham total (Hemat Kuota)
        candidates = list(set(candidates))[:8]
        
        trades = load_trades()
        today_str = str(datetime.date.today())
        
        msg = f"💎 <b>HASIL SCAN ({session_name})</b>\n\n"
        found_count = 0
        
        for ticker in candidates:
            df = get_technical_data(ticker)
            if df is not None:
                setup = None
                
                # Cek Setup 1: Breakout
                setup = check_breakout_setup(df)
                
                # Jika bukan breakout, Cek Setup 2: Pullback
                if not setup:
                    setup = check_pullback_setup(df)
                
                if setup:
                    price = setup['price']
                    msg += f"<b>{ticker}</b> ({setup['type']})\n"
                    msg += f"   Entry: {price}\n"
                    msg += f"   Info: {setup['desc']}\n"
                    msg += f"   🎯 TP: {setup['tp']} | SL: {setup['sl']}\n\n"
                    
                    if ticker not in trades:
                        trades[ticker] = {
                            "entry": price, "tp1": int(price*1.03), "tp2": setup['tp'],
                            "sl": setup['sl'], "date": today_str, "status": "OPEN"
                        }
                    found_count += 1
            
            time.sleep(1) # Jeda
            
        if found_count > 0:
            save_trades(trades)
            msg += "<i>Disiplin plan sesuai tipe setup!</i>"
            send_telegram(msg)
        else:
            send_telegram(f"ℹ️ <b>Scan {session_name}:</b> Tidak ada setup (Breakout/Pullback) yang valid.")
            
    except Exception as e:
        err_msg = traceback.format_exc()
        send_telegram(f"❌ <b>BOT ERROR:</b>\n<pre>{err_msg}</pre>")

# --- MONITORING ---
def run_monitor():
    try:
        trades = load_trades()
        if not trades: return
        
        symbols = ",".join(trades.keys())
        price_data = get_goapi("/stock/idx/prices", {'symbols': symbols})
        if not price_data: return
        
        curr_prices = {x['symbol']: float(x['close']) for x in price_data.get('results', [])}
        updated_trades = trades.copy()
        
        for ticker, data in trades.items():
            if ticker not in curr_prices: continue
            price = curr_prices[ticker]
            pnl = ((price - data['entry']) / data['entry']) * 100
            
            msg = ""
            remove = False
            
            if price <= data['sl']:
                msg = f"🥀 <b>CUT LOSS: {ticker}</b>\nExit: {int(price)} ({pnl:.2f}%)"
                remove = True
            elif price >= data['tp2']:
                msg = f"🚀 <b>TP 2 LUNAS: {ticker}</b>\nExit: {int(price)} (+{pnl:.2f}%)"
                remove = True
            elif price >= data['tp1'] and data['status'] == 'OPEN':
                msg = f"💰 <b>TP 1 HIT: {ticker}</b>\nHarga: {int(price)} (+{pnl:.2f}%)"
                updated_trades[ticker]['status'] = 'TP1_HIT'
                
            if msg: send_telegram(msg)
            if remove: del updated_trades[ticker]
            
        save_trades(updated_trades)
    except: pass

# --- SCHEDULER ---
def run_bot():
    send_telegram("🤖 <b>BOT HYBRID (BREAKOUT + RETEST) AKTIF</b>\nSiap mencari 2 tipe setup sesuai request.")
    
    last_monitor_minute = -1
    last_scan_time = ""

    while True:
        try:
            now = datetime.datetime.now()
            jam = now.hour
            menit = now.minute
            hari_kerja = now.weekday() < 5
            
            if hari_kerja:
                # 1. JADWAL SCAN (14:45 & 15:30)
                if jam == 14 and menit == 45 and last_scan_time != "14:45":
                    run_bsjp_scanner("14:45")
                    last_scan_time = "14:45"
                elif jam == 15 and menit == 30 and last_scan_time != "15:30":
                    run_bsjp_scanner("FINAL")
                    last_scan_time = "15:30"

                # 2. JADWAL MONITORING
                should_monitor = False
                if jam == 9 and menit < 20: # Agresif pagi
                    if menit % 3 == 0: should_monitor = True
                elif 9 <= jam < 16: # Santai siang
                    if menit == 0: should_monitor = True
                
                if should_monitor and menit != last_monitor_minute:
                    run_monitor()
                    last_monitor_minute = menit

            time.sleep(20)
            
        except Exception as e:
            print(f"Error Loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
