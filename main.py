import yfinance as yf
import pandas as pd
import requests
import time
import datetime
import os
import feedparser
from urllib.parse import quote

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- LIST SAHAM OTOMATIS (75 Saham Teraktif IDX) ---
AUTO_WATCHLIST = [
    # BANKS
    'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BRIS.JK', 'BBTN.JK', 'ARTO.JK',
    # ENERGY & MINING
    'ADRO.JK', 'PTBA.JK', 'ITMG.JK', 'PGAS.JK', 'MEDC.JK', 'AKRA.JK', 'ANTM.JK', 
    'INCO.JK', 'MDKA.JK', 'TINS.JK', 'HRUM.JK', 'BUMI.JK', 'ENRG.JK', 'MBMA.JK',
    # INFRA & TELCO
    'TLKM.JK', 'EXCL.JK', 'ISAT.JK', 'TOWR.JK', 'TBIG.JK', 'JSMR.JK', 'PGEO.JK',
    # CONSUMER & RETAIL
    'ASII.JK', 'UNTR.JK', 'ICBP.JK', 'INDF.JK', 'MYOR.JK', 'KLBF.JK', 'UNVR.JK', 
    'AMRT.JK', 'MAPI.JK', 'ACES.JK', 'CPIN.JK', 'JPFA.JK',
    # TECH & DIGITAL
    'GOTO.JK', 'BUKA.JK', 'EMTK.JK', 'SCMA.JK',
    # PROPERTY & CONSTRUCTION
    'BSDE.JK', 'CTRA.JK', 'PWON.JK', 'SMRA.JK', 'PANI.JK',
    # BIG CAPS / CONGLOMERATE
    'AMMN.JK', 'BREN.JK', 'TPIA.JK', 'BRPT.JK', 'CUAN.JK', 'GGRM.JK', 'HMSP.JK',
    # OTHERS (High Volatility)
    'SRTG.JK', 'ESSA.JK', 'INKP.JK', 'TKIM.JK', 'SMGR.JK', 'INTP.JK'
]

def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    # Log ke console agar terlihat di Coolify
    ticker_name = message.splitlines()[0] if message else "Log"
    print(f"🔔 Notif: {ticker_name}")
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": "True"}
    try: requests.post(url, data=data, timeout=10)
    except: pass

def get_latest_news(ticker_clean):
    try:
        # Mencari berita spesifik saham di Google News Indonesia
        query = quote(f"Saham {ticker_clean}")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"
        feed = feedparser.parse(rss_url)
        news_list = []
        if feed.entries:
            # Ambil maksimal 2 berita teratas
            for entry in feed.entries[:2]: 
                # Filter kata kunci relevan agar tidak spam iklan
                if any(x in entry.title for x in ["Rekomendasi", "Analisa", "Laba", "Dividen", "Jatuh", "Melesat", "Menguat", "IHSG", "Saham", "Emiten"]):
                    news_list.append(f"📰 <a href='{entry.link}'>{entry.title}</a>")
        return "\n".join(news_list) if news_list else ""
    except: return ""

def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Ambil data historis 3 bulan ke belakang (Interval Harian)
        df = stock.history(period="3mo", interval="1d")
        
        if len(df) < 50: return False

        # --- INDIKATOR TEKNIKAL ---
        # Moving Averages
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        # Volume Average
        df['VolAvg'] = df['Volume'].rolling(window=20).mean()
        
        # RSI (Relative Strength Index)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # Data Terakhir (Hari Ini) dan Kemarin
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = last['Close']
        vol = last['Volume']
        avg_vol = last['VolAvg']
        ticker_clean = ticker.replace(".JK", "")
        
        signals = []

        # 1. GOLDEN CROSS (Swing)
        # Syarat: Garis MA20 memotong ke ATAS garis MA50
        if prev['SMA20'] < prev['SMA50'] and last['SMA20'] > last['SMA50']:
            signals.append(f"✅ <b>GOLDEN CROSS (Swing)</b>\nTrend baru mau naik. Hold mingguan.")

        # 2. RSI OVERSOLD (Rebound)
        # Syarat: RSI di bawah 30 (Jenuh Jual / Murah)
        if last['RSI'] < 30:
            signals.append(f"🎣 <b>RSI OVERSOLD: {last['RSI']:.1f}</b>\nSaham bagus harga murah (Diskon).")

        # 3. VOLUME SPIKE (Pengganti BSJP/Bandar)
        # Syarat: Volume hari ini > 2.5x Rata-rata Volume 20 Hari DAN Harga Naik
        if vol > (avg_vol * 2.5) and price > prev['Close']:
            signals.append(f"🌇 <b>SINYAL BSJP (Volume Spike)</b>\nVol: {int(vol/avg_vol)}x Lipat Avg\nSmart Money masuk. Potensi naik besok.")

        # --- JIKA ADA SINYAL, KIRIM TELEGRAM ---
        if signals:
            news_update = get_latest_news(ticker_clean)
            gf_link = f"https://www.google.com/finance/quote/{ticker_clean}:IDX"
            
            msg = f"📊 <b>SINYAL: {ticker_clean}</b>\nHarga: {int(price)}\n"
            msg += "\n".join(signals)
            if news_update:
                msg += f"\n\n<b>Berita Terkait:</b>\n{news_update}"
            msg += f"\n\n🔗 <a href='{gf_link}'>Cek Grafik</a>"
            
            send_telegram(msg)
            return True

    except Exception as e:
        # Error dilewatkan agar tidak menghentikan loop
        pass
    return False

def run_bot():
    count_stock = len(AUTO_WATCHLIST)
    send_telegram(f"🤖 <b>BOT SAHAM IDX (AUTO-LIST) AKTIF</b>\nMemantau {count_stock} Saham Liquid.\nFitur: Swing, RSI Rebound, BSJP (Volume)")
    
    cycle = 0
    while True:
        now = datetime.datetime.now()
        jam = now.hour
        menit = now.minute
        hari_kerja = now.weekday() < 5 # Senin - Jumat (0-4)

        should_scan = False
        
        # Test Run: Scan sekali saat bot baru dinyalakan/restart
        if cycle == 0: should_scan = True 
        
        if hari_kerja:
            # JADWAL SCANNING (Waktu WIB disesuaikan delay data 15 menit)
            
            # 1. Pagi (10:57): Cek saham yang langsung ngegas pagi-pagi
            if jam == 9 and menit == 45 and cycle % 60 == 0: should_scan = True
            
            # 2. Siang (12:15): Cek penutupan sesi 1 (Istirahat)
            if jam == 12 and menit == 15 and cycle % 60 == 0: should_scan = True
            
            # 3. Sore (14:45): BSJP TIME! Data penutupan sudah final.
            if jam == 16 and menit == 15 and cycle % 60 == 0: should_scan = True

        if should_scan:
            print(f"[{now.strftime('%H:%M')}] 🚀 Scanning Pasar...")
            
            found = 0
            for stock in AUTO_WATCHLIST:
                if analyze_stock(stock): found += 1
                time.sleep(1.5) # Jeda 1.5 detik per saham agar IP aman dari blokir
            
            print(f"Scan Selesai. Sinyal: {found}")
            
            # Laporan jika pasar sepi saat penutupan
            if found == 0 and jam == 16:
                send_telegram("ℹ️ Penutupan: Tidak ada sinyal BSJP yang kuat hari ini.")

        # Log standby per jam agar kita tahu bot masih hidup di server
        if menit == 0 and cycle % 60 == 0:
            print(f"[{now.strftime('%H:%M')}] Standby...", flush=True)

        time.sleep(60) # Cek loop setiap 1 menit
        cycle += 1

if __name__ == "__main__":
    run_bot()
