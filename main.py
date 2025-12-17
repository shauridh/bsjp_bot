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

def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, data=data, timeout=5)
    except: pass

# --- FUNGSI PENCARI KANDIDAT DINAMIS ---
def get_trending_candidates():
    """Mencari 15 Saham yang sedang Trending/Ramai hari ini"""
    try:
        url = f"{BASE_URL}/stock/idx/trending"
        res = requests.get(url, headers=HEADERS).json()
        candidates = []
        if res.get('status') == 'success':
            # Ambil 15 teratas
            for item in res['data']['results'][:15]:
                ticker = item['symbol']
                # Filter Saham 'Sampah' (Harga < 50)
                # Anda bisa tambah filter lain, misal exclude 'GOTO' kalau tidak suka
                if float(item['close']) > 50: 
                    candidates.append(ticker)
        return candidates
    except: return []

# --- ANALISA BSJP (BANDARMOLOGY) ---
def analyze_bsjp(symbol):
    try:
        today = datetime.date.today().strftime("%Y-%m-%d")
        
        # 1. Cek Data Bandar
        url = f"{BASE_URL}/stock/idx/{symbol}/broker_summary"
        params = {'date': today}
        res = requests.get(url, headers=HEADERS, params=params).json()
        
        if res.get('status') == 'success':
            data = res['data']
            avg_buy = float(data.get('avg_buy', 0) or 0)
            
            # 2. Cek Harga Realtime
            curr_res = requests.get(f"{BASE_URL}/stock/idx/prices?symbols={symbol}", headers=HEADERS).json()
            curr_price = float(curr_res['data'][0]['close'])
            
            # LOGIKA BSJP:
            # Kita mau saham yang harga sekarang SEDIKIT di atas harga rata-rata Bandar.
            # Artinya Bandar sedang menjaga harga (Mark-up phase)
            
            if avg_buy > 0:
                diff = ((curr_price - avg_buy) / avg_buy) * 100
                
                # Syarat: 
                # 1. Harga diatas avg bandar (Positif)
                # 2. Tapi tidak kemahalan (Max beda 4%)
                if 0.1 < diff < 4.0:
                    send_telegram(
                        f"🌇 <b>SINYAL BSJP ({symbol})</b>\n"
                        f"Harga: {int(curr_price)}\n"
                        f"Avg Bandar: {int(avg_buy)}\n"
                        f"Selisih: +{diff:.2f}%\n"
                        f"<i>Saham ini sedang Trending & Diakumulasi!</i>"
                    )
                    return True # Ada sinyal
    except: pass
    return False

# --- ANALISA SWING (GOLDEN CROSS) ---
def analyze_swing(symbol):
    try:
        end_date = datetime.date.today()
        start_date = end_date - timedelta(days=100)
        url = f"{BASE_URL}/stock/idx/{symbol}/historical"
        params = {'from': start_date, 'to': end_date}
        res = requests.get(url, headers=HEADERS, params=params).json()
        
        if res.get('status') == 'success':
            df = pd.DataFrame(res['data']['results']).sort_values('date')
            df['SMA20'] = df['close'].rolling(20).mean()
            df['SMA50'] = df['close'].rolling(50).mean()
            
            if len(df) < 55: return

            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Golden Cross: MA20 memotong MA50 ke atas
            if prev['SMA20'] < prev['SMA50'] and last['SMA20'] > last['SMA50']:
                send_telegram(f"🧘 <b>SWING ALERT ({symbol})</b>\nGOLDEN CROSS DETECTED!\nMA20 crossing MA50 Up.")
    except: pass

# --- MAIN LOOP ---
def run_bot():
    send_telegram("🤖 <b>BOT SAHAM DINAMIS AKTIF</b>\nSource: Trending Stocks IDX\nBSJP Time: 15:40 WIB")
    
    cycle = 0
    while True:
        # Penyesuaian Waktu (Penting di VPS)
        # Tambahkan timedelta jika jam VPS bukan WIB (misal UTC+7)
        # Kode ini asumsi jam server sudah WIB atau kita pakai jam lokal sistem
        now = datetime.datetime.now()
        jam = now.hour
        menit = now.minute
        hari_kerja = now.weekday() < 5 # Senin-Jumat

        # A. SCALPING PAGI & SIANG (Cari Trending tiap 15 menit)
        market_open = (9 <= jam < 15)
        if hari_kerja and market_open and cycle % 15 == 0: 
            print(f"[{now.strftime('%H:%M')}] Scanning Trending for Scalping...")
            candidates = get_trending_candidates()
            # Info singkat 3 saham teratas trending saja biar gak spam
            if candidates:
                top3 = ", ".join(candidates[:3])
                # send_telegram(f"🔥 <b>TRENDING SAAT INI:</b> {top3}")
                # (Opsional: Nyalakan baris diatas jika ingin tau apa yg lagi rame)

        # B. BSJP (BELI SORE JUAL PAGI) - THE GOLDEN TIME
        # Kita set di 15:40 agar sempat analisa sebelum Pre-Closing (15:50)
        if hari_kerja and jam == 15 and 40 <= menit <= 50:
            if cycle % 5 == 0: # Cek per 5 menit dalam jendela waktu ini
                print("🔍 MENCARI MUTIARA BSJP...")
                # 1. Ambil List Saham Trending Hari Ini (Dinamis!)
                candidates = get_trending_candidates()
                send_telegram(f"🔍 <b>Menganalisa {len(candidates)} Saham Trending untuk BSJP...</b>")
                
                count = 0
                for emiten in candidates:
                    if analyze_bsjp(emiten): count += 1
                    time.sleep(1) # Jeda sopan
                
                if count == 0:
                    send_telegram("Hening. Tidak ada saham trending yang memenuhi kriteria BSJP aman hari ini.")
                
                # Tidur panjang sampai sesi BSJP selesai biar gak loop terus
                time.sleep(600) 

        # C. SWING (MALAM HARI)
        if hari_kerja and jam == 19 and menit == 0 and cycle % 60 == 0:
            print("Analisa Swing Malam...")
            # Untuk swing, kita pakai Top 20 Trending juga, atau bisa list manual
            candidates = get_trending_candidates()
            for emiten in candidates:
                analyze_swing(emiten)
                time.sleep(1)

        print(f"Standby... {now.strftime('%H:%M')}")
        time.sleep(60) # Cek setiap 1 menit
        cycle += 1

if __name__ == "__main__":
    run_bot()
