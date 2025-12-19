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

# --- FUNGSI TELEGRAM ---
def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    print(f"🔔 TELEGRAM: {message.splitlines()[0]}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": "True"}
    try: requests.post(url, data=data, timeout=10)
    except Exception as e: print(f"Gagal kirim telegram: {e}")

# --- WRAPPER API ---
def get_goapi(endpoint, params=None):
    try:
        url = f"{BASE_URL}{endpoint}"
        res = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if res.status_code != 200: return None
        data = res.json()
        if data.get('status') == 'error': return None
        return data.get('data')
    except: return None

# --- LOGIKA SCREENING (BSJP) ---
def check_user_criteria(ticker):
    try:
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=60)
        
        hist_data = get_goapi(f"/stock/idx/{ticker}/historical", {
            'from': start_date.strftime("%Y-%m-%d"),
            'to': today.strftime("%Y-%m-%d")
        })
        
        if not hist_data or 'results' not in hist_data: return None

        df = pd.DataFrame(hist_data['results'])
        if len(df) < 20: return None

        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        df = df.sort_values('date') 

        df['MA5_Price'] = df['close'].rolling(window=5).mean()
        df['MA20_Vol'] = df['volume'].rolling(window=20).mean()
        
        last = df.iloc[-1]
        
        price = float(last['close'])
        vol = float(last['volume'])
        ma5 = float(last['MA5_Price'])
        ma20_vol = float(last['MA20_Vol'])
        value = price * vol
        
        # Filter Rules (Sesuai Gambar User)
        if price <= 50: return None
        if value < 500_000_000: return None
        if price <= ma5: return None
        if vol <= (ma20_vol * 2): return None

        return {
            "price": int(price),
            "vol_ratio": round(vol / ma20_vol, 1),
            "val": value
        }
    except: return None

def run_bsjp_scanner(session_name="Sesi 1"):
    print(f"💎 Memulai Scan BSJP ({session_name})...")
    try:
        gainers = get_goapi("/stock/idx/top_gainer")
        if not gainers: 
            send_telegram(f"⚠️ Gagal Scan {session_name} (API Error).")
            return
        
        results = gainers.get('results', [])
        candidates = []
        for x in results:
            if 'ticker' in x: candidates.append(x['ticker'])
            elif 'symbol' in x: candidates.append(x['symbol'])
        
        # Ambil 5 Teratas Saja (Hemat Kuota)
        candidates = candidates[:5]
        
        found_count = 0
        trades = load_trades()
        today_str = str(datetime.date.today())
        
        msg = f"💎 <b>HASIL BSJP ({session_name})</b>\n"
        msg += "<i>Filter: Price>MA5 & Vol>2xMA20</i>\n\n"
        
        for ticker in candidates:
            res = check_user_criteria(ticker)
            if res:
                price = res['price']
                tp1 = int(price * 1.04)
                sl = int(price * 0.96)
                
                msg += f"🔥 <b>{ticker}</b>: {price}\n"
                msg += f"   📊 Vol: {res['vol_ratio']}x Avg\n"
                msg += f"   🎯 TP: {tp1} | SL: {sl}\n\n"
                
                if ticker not in trades:
                    trades[ticker] = {
                        "entry": price, "tp1": tp1, "tp2": int(price*1.08),
                        "sl": sl, "date": today_str, "status": "OPEN"
                    }
                found_count += 1
            time.sleep(1) 
            
        if found_count > 0:
            save_trades(trades)
            msg += "<i>Cek chart sebelum entry!</i>"
            send_telegram(msg)
        else:
            send_telegram(f"ℹ️ <b>BSJP {session_name}:</b> Nihil (Filter Ketat).")
            
    except Exception as e:
        err_msg = traceback.format_exc()
        send_telegram(f"❌ <b>BOT ERROR:</b>\n<pre>{err_msg}</pre>")

# --- MONITORING (FEEDBACK CEPAT) ---
def run_monitor():
    try:
        trades = load_trades()
        if not trades: return
        
        # 1 Request untuk cek SEMUA harga saham yg kita punya (Hemat!)
        symbols = ",".join(trades.keys())
        price_data = get_goapi("/stock/idx/prices", {'symbols': symbols})
        if not price_data: return
        
        curr_prices = {x['symbol']: float(x['close']) for x in price_data.get('results', [])}
        updated_trades = trades.copy()
        notif_sent = False
        
        for ticker, data in trades.items():
            if ticker not in curr_prices: continue
            price = curr_prices[ticker]
            pnl = ((price - data['entry']) / data['entry']) * 100
            
            msg = ""
            remove = False
            
            # CEK STOP LOSS
            if price <= data['sl']:
                msg = f"🥀 <b>CUT LOSS SEKARANG: {ticker}</b>\n"
                msg += f"Exit: {int(price)} ({pnl:.2f}%)\n"
                msg += f"<i>Jangan ditahan, buang!</i>"
                remove = True
            
            # CEK TP 2 (LUNAS)
            elif price >= data['tp2']:
                msg = f"🚀 <b>TP 2 LUNAS: {ticker}</b>\n"
                msg += f"Exit: {int(price)} (+{pnl:.2f}%)\n"
                msg += f"<i>Amankan semua profit!</i>"
                remove = True
                
            # CEK TP 1 (AMANKAN)
            elif price >= data['tp1'] and data['status'] == 'OPEN':
                msg = f"💰 <b>TP 1 HIT: {ticker}</b>\n"
                msg += f"Harga: {int(price)} (+{pnl:.2f}%)\n"
                msg += f"<i>Jual 50% lot sekarang!</i>"
                updated_trades[ticker]['status'] = 'TP1_HIT'
                
            if msg: 
                send_telegram(msg)
                notif_sent = True
            if remove: del updated_trades[ticker]
            
        save_trades(updated_trades)
        if notif_sent: print("Notifikasi TP/SL Terkirim!")
        
    except: pass

# --- SCHEDULER CERDAS (Smart Schedule) ---
def run_bot():
    send_telegram("🤖 <b>BOT AGRESIF PAGI AKTIF</b>\nMonitor Tiap 3 Menit (09:00-09:20)\nMonitor Tiap Jam (Siang)\nScan BSJP: 14:45 & 15:30")
    
    # Variabel kontrol waktu
    last_monitor_minute = -1
    last_scan_time = ""

    while True:
        try:
            now = datetime.datetime.now()
            jam = now.hour
            menit = now.minute
            hari_kerja = now.weekday() < 5
            
            if hari_kerja:
                current_time_str = f"{jam}:{menit}"
                
                # --- 1. JADWAL SCANNING (BSJP) ---
                # Scan 14:45
                if jam == 14 and menit == 45 and last_scan_time != "14:45":
                    run_bsjp_scanner("14:45")
                    last_scan_time = "14:45"
                
                # Scan 15:30 (Final)
                elif jam == 15 and menit == 30 and last_scan_time != "15:30":
                    run_bsjp_scanner("FINAL")
                    last_scan_time = "15:30"

                # --- 2. JADWAL MONITORING (TP/SL) ---
                # Logika: "Seberapa sering kita monitor?"
                should_monitor = False
                
                # FASE 1: AGRESIF PAGI (09:00 - 09:20)
                # Cek setiap 3 menit (09:00, 09:03, 09:06 ...)
                if jam == 9 and menit < 20:
                    if menit % 3 == 0: should_monitor = True

                # FASE 2: SANTAI SIANG (09:20 - 15:50)
                # Cek setiap 1 jam (Menit ke-0)
                elif 9 <= jam < 16:
                    if menit == 0: should_monitor = True
                
                # Eksekusi Monitor (Pastikan tidak dobel di menit yang sama)
                if should_monitor and menit != last_monitor_minute:
                    print(f"[{now.strftime('%H:%M')}] 🕵️ Cek TP/SL...")
                    run_monitor()
                    last_monitor_minute = menit

            time.sleep(20) # Cek waktu tiap 20 detik
            
        except Exception as e:
            print(f"Error Loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
