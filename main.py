import requests
import time
import datetime
import os
import json
import pandas as pd
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

# --- FUNGSI BANTUAN ---
def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    print(f"🔔 Notif: {message.splitlines()[0]}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": "True"}
    try: requests.post(url, data=data, timeout=10)
    except: pass

def get_goapi(endpoint, params=None):
    try:
        url = f"{BASE_URL}{endpoint}"
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        data = res.json()
        return data.get('data')
    except: return None

# --- INTI LOGIKA SCREENING ANDA ---
def check_user_criteria(ticker):
    """
    Menerjemahkan Gambar Screening Rules Anda ke Python:
    1. Price > 50
    2. Value > 500.000.000
    3. Price > MA 5 (Uptrend)
    4. Volume > 2x Volume MA 20 (Volume Spike)
    """
    # Ambil data historis 30 hari terakhir untuk hitung MA
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=45) # Ambil lebih utk buffer libur
    
    hist_data = get_goapi(f"/stock/idx/{ticker}/historical", {
        'from': start_date.strftime("%Y-%m-%d"),
        'to': today.strftime("%Y-%m-%d")
    })
    
    if not hist_data or 'results' not in hist_data: return None

    # Olah Data dengan Pandas
    df = pd.DataFrame(hist_data['results'])
    df['close'] = pd.to_numeric(df['close'])
    df['volume'] = pd.to_numeric(df['volume'])
    df = df.sort_values('date') # Urutkan dari lama ke baru

    if len(df) < 20: return None # Data kurang untuk MA20

    # --- HITUNG INDIKATOR (SESUAI GAMBAR) ---
    # 1. Price MA 5
    df['MA5_Price'] = df['close'].rolling(window=5).mean()
    
    # 2. Volume MA 20
    df['MA20_Vol'] = df['volume'].rolling(window=20).mean()
    
    # Ambil data hari terakhir (Latest)
    last = df.iloc[-1]
    
    current_price = last['close']
    current_vol = last['volume']
    ma5_price = last['MA5_Price']
    ma20_vol = last['MA20_Vol']
    
    # Hitung Transaction Value (Perkiraan: Close * Volume)
    current_value = current_price * current_vol

    # --- PENGECEKAN SYARAT (FILTERING) ---
    reasons = []
    
    # Rule 1: Price > 50
    if current_price <= 50: return None
    
    # Rule 2: Value > 500 Juta
    if current_value < 500_000_000: return None
    
    # Rule 3: Price > MA 5 (Strong Uptrend)
    if current_price <= ma5_price: return None
    
    # Rule 4: Volume > 2x MA 20 Vol (Ledakan Volume)
    if current_vol <= (ma20_vol * 2): return None

    # Jika lolos semua filter di atas, berarti saham ini EMAS!
    return {
        "price": int(current_price),
        "vol_ratio": round(current_vol / ma20_vol, 1), # Misal 3.5x
        "ma5": int(ma5_price),
        "val": current_value
    }

# --- JOB UTAMA: CARI BSJP ---
def run_bsjp_scanner():
    print("💎 Memulai Scan BSJP Spesial...")
    
    # 1. Ambil Kandidat dari Top Gainer (1 Request)
    # Kenapa Top Gainer? Karena saham "Near 52 Week High" biasanya ada di sini.
    gainers = get_goapi("/stock/idx/top_gainer")
    if not gainers: return
    
    # Ambil 10 teratas saja biar hemat kuota
    candidates = [x['ticker'] for x in gainers['results'][:10]]
    
    found_count = 0
    trades = load_trades()
    today_str = str(datetime.date.today())

    msg = "💎 <b>SINYAL BSJP PREMIUM</b>\n<i>(Price > MA5 & Vol > 2x MA20)</i>\n\n"
    
    for ticker in candidates:
        if ticker in trades: continue # Skip yg udah punya
        
        # Cek Kriteria User (1 Request per ticker)
        result = check_user_criteria(ticker)
        
        if result:
            # Lolos Screening!
            price = result['price']
            vol_x = result['vol_ratio']
            
            # Setup Plan
            tp1 = int(price * 1.04) # Cuan 4%
            tp2 = int(price * 1.08) # Cuan 8%
            sl = int(price * 0.96)  # SL 4%
            
            msg += f"🔥 <b>{ticker}</b>: {price}\n"
            msg += f"   📊 Vol: {vol_x}x Rata-rata\n"
            msg += f"   💰 Value: {int(result['val']/1000000000)} Milyar\n"
            msg += f"   🎯 TP: {tp1} | SL: {sl}\n\n"
            
            # Simpan
            trades[ticker] = {
                "entry": price, "tp1": tp1, "tp2": tp2, "sl": sl,
                "date": today_str, "status": "OPEN"
            }
            save_trades(trades)
            found_count += 1
            
        time.sleep(1) # Jeda dikit
        
    if found_count > 0:
        msg += "<i>Segera HK sebelum 14:50!</i>"
        send_telegram(msg)
    else:
        print("Zonk. Tidak ada saham yg lolos filter ketat ini.")

# --- JOB MONITORING (HEMAT) ---
def run_monitor():
    trades = load_trades()
    if not trades: return
    
    # Cek Harga Massal (1 Request)
    symbols = ",".join(trades.keys())
    price_data = get_goapi("/stock/idx/prices", {'symbols': symbols})
    if not price_data: return
    
    curr_prices = {x['symbol']: float(x['close']) for x in price_data['results']}
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

# --- SCHEDULER ---
def run_bot():
    send_telegram("🤖 <b>BOT BSJP (USER STRATEGY) AKTIF</b>\nFilter: Price>MA5 & Vol>2xMA20\nJadwal: 14:45 WIB")
    
    last_scan_date = ""
    
    while True:
        now = datetime.datetime.now()
        jam = now.hour
        menit = now.minute
        hari_kerja = now.weekday() < 5
        today_date = now.strftime("%Y-%m-%d")
        
        if hari_kerja:
            
            # 1. WAKTU BSJP (14:45) - Cuma sekali sehari
            # Kita kunci pakai tanggal biar gak running berkali-kali di menit yg sama
            if jam == 14 and menit >= 45 and last_scan_date != today_date:
                run_bsjp_scanner()
                last_scan_date = today_date # Tandai hari ini sudah scan
                
            # 2. MONITORING PAGI (09:30) & SIANG (13:30)
            # Cukup 2x sehari biar hemat kuota
            if (jam == 9 and menit == 30) or (jam == 13 and menit == 30):
                if now.second < 10: # Biar cuma jalan sekali di menit itu
                    run_monitor()
                    time.sleep(10)

        # Standby
        time.sleep(50)

if __name__ == "__main__":
    run_bot()
