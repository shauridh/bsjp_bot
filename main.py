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

# --- LIST KHUSUS SAHAM MURAH (< Rp 700) ---
# Syarat: Liquid (Ada Volume), Bukan Gocap Mati (50), Sering Rame
AUTO_WATCHLIST = [
    # SAHAM BAKRIE & ENERGY (Sering Rame)
    'BUMI.JK', 'BRMS.JK', 'DEWA.JK', 'ENRG.JK', 'BIPI.JK', 'ELSA.JK',
    
    # PROPERTI & KONSTRUKSI (Lagi Murah)
    'APLN.JK', 'ASRI.JK', 'BKSL.JK', 'KIJA.JK', 'LPKR.JK', 'LPCK.JK', 
    'BEST.JK', 'DILD.JK', 'PTPP.JK', 'WIKA.JK', 'ADHI.JK', 'WG.JK',
    
    # MEDIA & TECH
    'SCMA.JK', 'MNCN.JK', 'BMTR.JK', 'VIVA.JK', 'BUKA.JK', 'GOTO.JK',
    'MLPT.JK', 'WIRG.JK',
    
    # RETAIL & CONSUMER
    'MPPA.JK', 'RALS.JK', 'SIDO.JK', 'WOOD.JK', 'CLEO.JK', 'CAMP.JK',
    
    # TRANSPORT & LAINNYA
    'CARS.JK', 'IPCC.JK', 'IPCM.JK', 'TRAM.JK', 'GIAA.JK', 'KAEF.JK',
    'IRRA.JK', 'SAME.JK', 'ZINC.JK', 'ANTM.JK', # ANTM kadang <1500 tapi liquid
    'HRUM.JK', 'TINS.JK'
]

def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    ticker_name = message.splitlines()[0] if message else "Log"
    print(f"🔔 Notif: {ticker_name}")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": "True"}
    try: requests.post(url, data=data, timeout=10)
    except: pass

def get_latest_news(ticker_clean):
    try:
        query = quote(f"Saham {ticker_clean}")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"
        feed = feedparser.parse(rss_url)
        news_list = []
        if feed.entries:
            for entry in feed.entries[:2]: 
                if any(x in entry.title for x in ["Rekomendasi", "Analisa", "Laba", "Dividen", "Jatuh", "Melesat", "Menguat", "IHSG", "Saham", "Emiten"]):
                    news_list.append(f"📰 <a href='{entry.link}'>{entry.title}</a>")
        return "\n".join(news_list) if news_list else ""
    except: return ""

def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo", interval="1d")
        
        if len(df) < 50: return False

        # --- INDIKATOR ---
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['VolAvg'] = df['Volume'].rolling(window=20).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = float(last['Close'])
        vol = float(last['Volume'])
        avg_vol = float(last['VolAvg'])
        ticker_clean = ticker.replace(".JK", "")
        
        # FILTER HARGA MAKSIMAL 800 (Jaga-jaga kalau ada yang naik tinggi)
        if price > 800: return False
        
        signals = []
        signal_type = ""

        # 1. GOLDEN CROSS
        if prev['SMA20'] < prev['SMA50'] and last['SMA20'] > last['SMA50']:
            signals.append(f"✅ <b>GOLDEN CROSS</b>\nTrend reversal. Potensi naik.")
            signal_type = "SWING"

        # 2. RSI OVERSOLD
        if last['RSI'] < 30:
            signals.append(f"🎣 <b>RSI OVERSOLD: {last['RSI']:.1f}</b>\nSudah murah banget.")
            signal_type = "REBOUND"

        # 3. VOLUME SPIKE (Paling Penting buat Saham Murah)
        if vol > (avg_vol * 2.5) and price > prev['Close']:
            signals.append(f"🌇 <b>VOLUME MELEDAK ({int(vol/avg_vol)}x)</b>\nBandar lagi main barang ini.")
            signal_type = "BSJP"

        # --- TRADING PLAN ---
        if signals:
            buy_price = int(price)
            
            # SL = Lebih longgar buat saham murah (volatil) -> 5%
            sl_price = int(buy_price * 0.95)
            
            # TP = Target lebih optimis -> 5% & 10%
            tp1_price = int(buy_price * 1.05)
            tp2_price = int(buy_price * 1.10)
            
            if signal_type == "REBOUND": # Kalau nangkep pisau jatuh, SL ketat
                 sl_price = int(buy_price * 0.96)

            news_update = get_latest_news(ticker_clean)
            gf_link = f"https://www.google.com/finance/quote/{ticker_clean}:IDX"
            
            msg = f"📊 <b>SINYAL: {ticker_clean}</b>\nHarga: {int(price)}\n"
            msg += "\n".join(signals)
            
            msg += f"\n\n🎯 <b>PLAN (Saham Murah):</b>\n"
            msg += f"🟢 <b>BUY:</b> {int(price)}\n"
            msg += f"💰 <b>TP 1:</b> {tp1_price} (5%)\n"
            msg += f"💰 <b>TP 2:</b> {tp2_price} (10%)\n"
            msg += f"🛡️ <b>SL:</b> {sl_price} (Cutloss)\n"

            if news_update:
                msg += f"\n<b>Berita:</b>\n{news_update}"
            msg += f"\n\n🔗 <a href='{gf_link}'>Grafik</a>"
            
            send_telegram(msg)
            return True

    except Exception as e:
        pass
    return False

def run_bot():
    count_stock = len(AUTO_WATCHLIST)
    send_telegram(f"🤖 <b>BOT SAHAM RECEH (<700) AKTIF</b>\nMemantau {count_stock} Saham Murah Meriah.\nFitur: Volume Spike, Golden Cross")
    
    cycle = 0
    while True:
        now = datetime.datetime.now()
        jam = now.hour
        menit = now.minute
        hari_kerja = now.weekday() < 5 

        should_scan = False
        if cycle == 0: should_scan = True 
        
        if hari_kerja:
            if jam == 9 and menit == 20 and cycle % 60 == 0: should_scan = True
            if jam == 12 and menit == 15 and cycle % 60 == 0: should_scan = True
            if jam == 14 and menit == 45 and cycle % 60 == 0: should_scan = True

        if should_scan:
            print(f"[{now.strftime('%H:%M')}] 🚀 Scanning Saham Receh...")
            found = 0
            for stock in AUTO_WATCHLIST:
                if analyze_stock(stock): found += 1
                time.sleep(1.5) 
            
            print(f"Selesai. Sinyal: {found}")
            if found == 0 and jam == 16:
                send_telegram("ℹ️ Pasar Sepi: Belum ada gorengan matang hari ini.")

        if menit == 0 and cycle % 60 == 0:
            print(f"[{now.strftime('%H:%M')}] Standby...", flush=True)

        time.sleep(60) 
        cycle += 1

if __name__ == "__main__":
    run_bot()
