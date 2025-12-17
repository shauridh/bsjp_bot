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
    # OTHERS
    'SRTG.JK', 'ESSA.JK', 'INKP.JK', 'TKIM.JK', 'SMGR.JK', 'INTP.JK'
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
        # Ambil data historis 3 bulan ke belakang
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
        
        signals = []
        signal_type = ""

        # 1. GOLDEN CROSS (Swing)
        if prev['SMA20'] < prev['SMA50'] and last['SMA20'] > last['SMA50']:
            signals.append(f"✅ <b>GOLDEN CROSS (Swing)</b>\nTrend baru mau naik.")
            signal_type = "SWING"

        # 2. RSI OVERSOLD (Rebound)
        if last['RSI'] < 30:
            signals.append(f"🎣 <b>RSI OVERSOLD: {last['RSI']:.1f}</b>\nPotensi Pantulan (Rebound).")
            signal_type = "REBOUND"

        # 3. VOLUME SPIKE (BSJP)
        if vol > (avg_vol * 2.5) and price > prev['Close']:
            signals.append(f"🌇 <b>SINYAL BSJP (Volume)</b>\nVol: {int(vol/avg_vol)}x Lipat Avg.")
            signal_type = "BSJP"

        # --- HITUNG PLAN TRADING (TP & SL) ---
        if signals:
            # Rumus Default (Risk Reward 1:2)
            buy_price = price
            
            # SL = Cutloss di -4%
            sl_price = int(buy_price * 0.96)
            
            # TP1 = Cuan Bungkus +3%
            tp1_price = int(buy_price * 1.03)
            
            # TP2 = Let Profit Run +8%
            tp2_price = int(buy_price * 1.08)
            
            # Jika sinyal REBOUND (RSI < 30), SL harus lebih ketat karena lawan arus
            if signal_type == "REBOUND":
                 sl_price = int(buy_price * 0.97) # SL -3%
                 tp1_price = int(buy_price * 1.025) # TP +2.5%

            news_update = get_latest_news(ticker_clean)
            gf_link = f"https://www.google.com/finance/quote/{ticker_clean}:IDX"
            
            # FORMAT PESAN LENGKAP
            msg = f"📊 <b>SINYAL: {ticker_clean}</b>\n"
            msg += f"Harga Skrg: {int(price)}\n\n"
            msg += "\n".join(signals)
            
            msg += f"\n\n🎯 <b>TRADING PLAN:</b>\n"
            msg += f"🟢 <b>BUY:</b> {int(price)} - {int(price*1.01)}\n"
            msg += f"💰 <b>TP 1:</b> {tp1_price} (3-4%)\n"
            msg += f"💰 <b>TP 2:</b> {tp2_price} (8%+)\n"
            msg += f"🛡️ <b>SL:</b> {sl_price} (Cutloss)\n"

            if news_update:
                msg += f"\n<b>Berita Terkait:</b>\n{news_update}"
            msg += f"\n\n🔗 <a href='{gf_link}'>Cek Grafik</a>"
            
            send_telegram(msg)
            return True

    except Exception as e:
        pass
    return False

def run_bot():
    count_stock = len(AUTO_WATCHLIST)
    send_telegram(f"🤖 <b>BOT UPDATE (TP/SL) AKTIF</b>\nMemantau {count_stock} Saham.\nFitur: Sinyal + Trading Plan Lengkap")
    
    cycle = 0
    while True:
        now = datetime.datetime.now()
        jam = now.hour
        menit = now.minute
        hari_kerja = now.weekday() < 5 

        should_scan = False
        if cycle == 0: should_scan = True 
        
        if hari_kerja:
            if jam == 9 and menit == 45 and cycle % 60 == 0: should_scan = True
            if jam == 12 and menit == 15 and cycle % 60 == 0: should_scan = True
            if jam == 14 and menit == 45 and cycle % 60 == 0: should_scan = True

        if should_scan:
            print(f"[{now.strftime('%H:%M')}] 🚀 Scanning Pasar...")
            found = 0
            for stock in AUTO_WATCHLIST:
                if analyze_stock(stock): found += 1
                time.sleep(1.5) 
            
            print(f"Scan Selesai. Sinyal: {found}")
            if found == 0 and jam == 16:
                send_telegram("ℹ️ Penutupan: Tidak ada sinyal kuat hari ini.")

        if menit == 0 and cycle % 60 == 0:
            print(f"[{now.strftime('%H:%M')}] Standby...", flush=True)

        time.sleep(60) 
        cycle += 1

if __name__ == "__main__":
    run_bot()
