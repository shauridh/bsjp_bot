import requests
import pandas as pd
import time
import os
import datetime
from datetime import timedelta

# --- KONFIGURASI ---
API_KEY = os.getenv("GOAPI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL = "https://api.goapi.io"

HEADERS = {"X-API-KEY": API_KEY, "Accept": "application/json"}

# --- FUNGSI BANTUAN ---
def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, data=data, timeout=5)
    except: pass

def get_data_safe(endpoint, params=None):
    """Fungsi pembungkus request agar jika API Error tidak crash"""
    try:
        url = f"{BASE_URL}{endpoint}"
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        res_json = res.json()
        
        if res.status_code != 200 or res_json.get('status') != 'success':
            print(f"⚠️ API Warning: {res_json.get('message', 'Unknown Error')}")
            return None
            
        return res_json
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

def calculate_rsi(df, period=14):
    """Menghitung RSI Manual untuk deteksi Jenuh Jual"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 1. STRATEGI REBOUND (KOLABORASI TOP LOSER) ---
def scan_rebound_loser():
    print("📉 Scanning Top Loser Rebound...")
    # Menggunakan endpoint top_loser sesuai request
    res = get_data_safe("/stock/idx/top_loser")
    
    if res:
        candidates = res['data']['results'][:10] # Cek 10 saham terboncos
        found = False
        msg = "🪃 <b>SINYAL REBOUND (Bottom Fishing)</b>\n<i>Saham Top Loser + RSI Oversold</i>\n"
        
        for stock in candidates:
            ticker = stock['ticker']
            price = float(stock['close'])
            percent = float(stock['percent']) # Pasti minus
            
            # Filter: Jangan saham gocap (50)
            if price > 50:
                # Cek RSI (Butuh data historis)
                hist = get_data_safe(f"/stock/idx/{ticker}/historical", {'from': (datetime.date.today()-timedelta(days=60)), 'to': datetime.date.today()})
                
                if hist:
                    df = pd.DataFrame(hist['data']['results']).sort_values('date')
                    df['RSI'] = calculate_rsi(df)
                    last_rsi = df.iloc[-1]['RSI']
                    
                    # SYARAT: Top Loser TAPI RSI sudah di bawah 30 (Jenuh Jual)
                    # Ini indikasi potensi mantul (Rebound)
                    if last_rsi < 30:
                        msg += f"• <b>{ticker}</b> ({percent}%)\n  Harga: {price} | RSI: {last_rsi:.1f} (Oversold!)\n"
                        found = True
        
        if found: send_telegram(msg)

# --- 2. STRATEGI SCALPING (TRENDING) ---
def scan_scalping_trending():
    print("🚀 Scanning Trending...")
    res = get_data_safe("/stock/idx/trending")
    if res:
        results = res['data']['results'][:10]
        found = False
        msg = "🏎️ <b>SINYAL SCALPING (Trending)</b>\n"
        
        for stock in results:
            ticker = stock['symbol']
            price = float(stock['close'])
            percent = float(stock['change_pct']) if 'change_pct' in stock else 0
            
            # Syarat: Naik > 2% tapi < 20% (Belum ARA)
            if price > 50 and 2 < percent < 20:
                msg += f"• <b>{ticker}</b>: {price} (+{percent}%)\n"
                found = True
        
        if found: send_telegram(msg)
        return [s['symbol'] for s in results] # Return list buat dipakai BSJP
    return []

# --- 3. STRATEGI BSJP (BANDAR) ---
def analyze_bsjp(symbol_list):
    print("🌇 Analyzing BSJP...")
    today = datetime.date.today().strftime("%Y-%m-%d")
    count = 0
    
    for symbol in symbol_list:
        # Cek Broker Summary
        res = get_data_safe(f"/stock/idx/{symbol}/broker_summary", {'date': today})
        
        if res:
            data = res['data']
            avg_buy = float(data.get('avg_buy', 0) or 0)
            
            # Cek Harga Saat Ini
            price_res = get_data_safe("/stock/idx/prices", {'symbols': symbol})
            if price_res:
                curr_price = float(price_res['data'][0]['close'])
                
                if avg_buy > 0:
                    diff = ((curr_price - avg_buy) / avg_buy) * 100
                    # Syarat: Harga sedikit di atas bandar (0.1% - 4%)
                    if 0.1 < diff < 4.0:
                        send_telegram(
                            f"🌇 <b>SINYAL BSJP ({symbol})</b>\n"
                            f"Harga: {int(curr_price)}\n"
                            f"Avg Bandar: {int(avg_buy)}\n"
                            f"Selisih: +{diff:.2f}%\n"
                            f"<i>Status: Akumulasi (Bandar Hold)</i>"
                        )
                        count += 1
                        time.sleep(1) # Jeda sopan
    
    if count == 0:
        send_telegram("ℹ️ BSJP Info: Belum ada sinyal bandar yang kuat di saham trending hari ini.")

# --- ENGINE UTAMA ---
def run_bot():
    send_telegram("🤖 <b>BOT SAHAM IDX V2 AKTIF</b>\nFitur: Trending, Top Loser (Rebound), BSJP\nAPI: GoAPI Indonesia")
    
    cycle = 0
    trending_cache = [] # Simpan data trending buat BSJP sore
    
    while True:
        now = datetime.datetime.now()
        jam = now.hour
        menit = now.minute
        hari_kerja = now.weekday() < 5
        
        # Cek Koneksi API Sekali di awal jam kerja
        if jam == 8 and menit == 55 and cycle % 60 == 0:
            check = get_data_safe("/stock/idx/companies")
            if not check: send_telegram("⚠️ <b>PERINGATAN:</b> API GoAPI Sedang Down/Error!")

        if hari_kerja:
            # A. SCALPING TRENDING (09:00 - 14:30) - Tiap 30 Menit
            if 9 <= jam < 15 and cycle % 30 == 0:
                trending_cache = scan_scalping_trending()
            
            # B. BOTTOM FISHING / REBOUND (10:00 - 14:00) - Tiap 60 Menit
            # Cari saham Top Loser yang RSI-nya sudah hancur (Oversold)
            if 10 <= jam < 14 and cycle % 60 == 0:
                scan_rebound_loser()

            # C. BSJP (15:40 - 15:50) - GOLDEN TIME
            if jam == 15 and 40 <= menit <= 50 and cycle % 5 == 0:
                # Prioritas cek BSJP pada saham yang tadi siang Trending
                target_list = trending_cache if trending_cache else ['BBRI','BBCA','BMRI','GOTO','TLKM','ANTM']
                analyze_bsjp(target_list)
                time.sleep(600) # Tidur sampai sesi tutup

        print(f"[{now.strftime('%H:%M')}] Standby...", flush=True)
        time.sleep(60) # Cek setiap 1 menit
        cycle += 1

if __name__ == "__main__":
    run_bot()
