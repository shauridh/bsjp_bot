import requests
import time
import datetime
import os
import json
import pandas as pd
import traceback # Untuk melacak error agar bot tidak mati
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

# --- FUNGSI TELEGRAM (SAFE) ---
def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    # Print ke log server juga
    print(f"🔔 TELEGRAM: {message.splitlines()[0]}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": "True"}
    try: requests.post(url, data=data, timeout=10)
    except Exception as e: print(f"Gagal kirim telegram: {e}")

# --- WRAPPER API (SAFE) ---
def get_goapi(endpoint, params=None):
    try:
        url = f"{BASE_URL}{endpoint}"
        res = requests.get(url, headers=HEADERS, params=params, timeout=15)
        
        # Cek status code
        if res.status_code != 200:
            print(f"⚠️ API Error {res.status_code}: {res.text}")
            return None
            
        data = res.json()
        if data.get('status') == 'error':
            print(f"⚠️ API Status Error: {data.get('message')}")
            return None
            
        return data.get('data')
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

# --- LOGIKA SCREENING (SAFE MODE) ---
def check_user_criteria(ticker):
    try:
        # Ambil data historis
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=60)
        
        hist_data = get_goapi(f"/stock/idx/{ticker}/historical", {
            'from': start_date.strftime("%Y-%m-%d"),
            'to': today.strftime("%Y-%m-%d")
        })
        
        if not hist_data or 'results' not in hist_data: return None

        # Olah Data
        df = pd.DataFrame(hist_data['results'])
        if len(df) < 20: return None # Data kurang

        # Pastikan kolom angka dibaca sebagai angka
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        df = df.sort_values('date') 

        # Hitung Indikator
        df['MA5_Price'] = df['close'].rolling(window=5).mean()
        df['MA20_Vol'] = df['volume'].rolling(window=20).mean()
        
        last = df.iloc[-1]
        
        # Cek Rules (Pakai try-except di sini juga biar aman)
        price = float(last['close'])
        vol = float(last['volume'])
        ma5 = float(last['MA5_Price'])
        ma20_vol = float(last['MA20_Vol'])
        value = price * vol
        
        # Logic Screening User
        if price <= 50: return None
        if value < 500_000_000: return None
        if price <= ma5: return None
        if vol <= (ma20_vol * 2): return None

        return {
            "price": int(price),
            "vol_ratio": round(vol / ma20_vol, 1),
            "val": value
        }
    except Exception as e:
        # Error kecil di satu saham biarkan saja, lanjut ke saham lain
        return None

def run_bsjp_scanner():
    print("💎 Memulai Scan BSJP...")
    try:
        # 1. Ambil Top Gainer
        gainers = get_goapi("/stock/idx/top_gainer")
        if not gainers: 
            send_telegram("⚠️ Gagal ambil data Top Gainer (Cek Kuota/API).")
            return
        
        # --- PERBAIKAN UTAMA DI SINI ---
        # Handle kemungkinan struktur data berbeda (ticker vs symbol)
        results = gainers.get('results', [])
        candidates = []
        for x in results[:10]:
            # Coba ambil 'ticker', kalau gak ada ambil 'symbol'
            if 'ticker' in x: candidates.append(x['ticker'])
            elif 'symbol' in x: candidates.append(x['symbol'])
        
        if not candidates:
            print("Tidak menemukan field 'ticker' atau 'symbol' di API Response")
            return

        found_count = 0
        trades = load_trades()
        today_str = str(datetime.date.today())
        
        msg = "💎 <b>HASIL SCAN BSJP</b>\n\n"
        
        for ticker in candidates:
            res = check_user_criteria(ticker)
            if res:
                price = res['price']
                tp1 = int(price * 1.04)
                sl = int(price * 0.96)
                
                msg += f"🔥 <b>{ticker}</b>: {price}\n"
                msg += f"   📊 Vol: {res['vol_ratio']}x Avg\n"
                msg += f"   🎯 TP: {tp1} | SL: {sl}\n\n"
                
                # Simpan
                if ticker not in trades:
                    trades[ticker] = {
                        "entry": price, "tp1": tp1, "tp2": int(price*1.08),
                        "sl": sl, "date": today_str, "status": "OPEN"
                    }
                found_count += 1
            time.sleep(1) # Jeda wajib!
            
        if found_count > 0:
            save_trades(trades)
            msg += "<i>Segera cek chart & entry!</i>"
            send_telegram(msg)
        else:
            # Tetap kirim laporan kalau ZONK, biar tau bot jalan
            send_telegram("ℹ️ <b>BSJP ZONK:</b> Tidak ada saham yang lolos filter hari ini.")
            
    except Exception as e:
        # INI PENTING: Lapor error ke Telegram daripada restart
        err_msg = traceback.format_exc()
        send_telegram(f"❌ <b>BOT ERROR (BSJP):</b>\n<pre>{err_msg}</pre>")

# --- MONITORING (HEMAT) ---
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
    except:
        pass # Error monitoring skip saja

# --- SCHEDULER UTAMA (ANTI-SPAM) ---
def run_bot():
    send_telegram("🤖 <b>BOT RESTART (SAFE MODE)</b>\nSiap monitoring...")
    
    last_run_minute = -1
    
    while True:
        try:
            now = datetime.datetime.now()
            jam = now.hour
            menit = now.minute
            hari_kerja = now.weekday() < 5
            
            # Kunci: Hanya jalan jika menit berubah
            # (Ini memperbaiki masalah "Jebakan Detik" dan "Spam")
            if menit != last_run_minute:
                
                if hari_kerja:
                    # Jadwal BSJP (15:00)
                    if jam == 15 and menit == 00:
                        run_bsjp_scanner()
                        last_run_minute = menit # Kunci agar tidak loop

                    # Monitoring (09:30 & 13:30)
                    elif (jam == 9 and menit == 30) or (jam == 13 and menit == 30):
                        print(f"Checking monitor at {jam}:{menit}")
                        run_monitor()
                        last_run_minute = menit

            # Heartbeat (biar process ga mati)
            time.sleep(10)
            
        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(60) # Tidur dulu kalau error parah

if __name__ == "__main__":
    run_bot()
