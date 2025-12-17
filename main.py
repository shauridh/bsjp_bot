import yfinance as yf
import pandas as pd
import requests
import time
import datetime
import os
import feedparser
import json
from urllib.parse import quote

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TRADES_FILE = "active_trades.json"

# --- LIST SAHAM RECEH (Liquid & Volatil) ---
AUTO_WATCHLIST = [
    'BUMI.JK', 'BRMS.JK', 'DEWA.JK', 'ENRG.JK', 'BIPI.JK', 'ELSA.JK',
    'APLN.JK', 'ASRI.JK', 'BKSL.JK', 'KIJA.JK', 'LPKR.JK', 'LPCK.JK', 
    'BEST.JK', 'DILD.JK', 'PTPP.JK', 'WIKA.JK', 'ADHI.JK', 
    'SCMA.JK', 'MNCN.JK', 'BMTR.JK', 'VIVA.JK', 'BUKA.JK', 'GOTO.JK',
    'MLPT.JK', 'WIRG.JK', 'MPPA.JK', 'RALS.JK', 'SIDO.JK', 'WOOD.JK', 
    'CLEO.JK', 'CAMP.JK', 'CARS.JK', 'IPCC.JK', 'IPCM.JK', 'TRAM.JK', 
    'GIAA.JK', 'KAEF.JK', 'IRRA.JK', 'SAME.JK', 'ZINC.JK', 'ANTM.JK',
    'HRUM.JK', 'TINS.JK'
]

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

# --- TELEGRAM & NEWS ---
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
                if any(x in entry.title for x in ["Rekomendasi", "Analisa", "Laba", "Dividen", "Jatuh", "Melesat", "Menguat", "IHSG", "Saham"]):
                    news_list.append(f"📰 <a href='{entry.link}'>{entry.title}</a>")
        return "\n".join(news_list) if news_list else ""
    except: return ""

# --- MONITORING (TRACKER) ---
def monitor_active_trades():
    trades = load_trades()
    if not trades: return

    print(f"🕵️ Monitoring {len(trades)} posisi aktif...")
    updated_trades = trades.copy()
    
    for ticker, data in trades.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if len(hist) == 0: continue
            
            curr_price = float(hist['Close'].iloc[-1])
            entry = data['entry']
            tp1 = data['tp1']
            tp2 = data['tp2']
            sl = data['sl']
            status = data.get('status', 'OPEN')
            
            pnl_pct = ((curr_price - entry) / entry) * 100
            
            msg = ""
            remove_trade = False

            if curr_price <= sl:
                msg = f"🥀 <b>STOP LOSS: {ticker.replace('.JK','')}</b>\nExit: {int(curr_price)} ({pnl_pct:.2f}%)\nPlan SL: {sl}"
                remove_trade = True
            elif curr_price >= tp2:
                msg = f"🚀 <b>TP 2 LUNAS: {ticker.replace('.JK','')}</b>\nHarga: {int(curr_price)} (+{pnl_pct:.2f}%)\nTarget tercapai!"
                remove_trade = True
            elif curr_price >= tp1 and status == 'OPEN':
                msg = f"💰 <b>TP 1 HIT: {ticker.replace('.JK','')}</b>\nHarga: {int(curr_price)} (+{pnl_pct:.2f}%)\nAmankan sebagian profit."
                updated_trades[ticker]['status'] = 'TP1_HIT'

            if msg: send_telegram(msg)
            if remove_trade: del updated_trades[ticker]
                
        except Exception as e: continue
            
    save_trades(updated_trades)

def send_daily_recap():
    trades = load_trades()
    if not trades:
        send_telegram("ℹ️ <b>REKAP SORE:</b> Tidak ada posisi terbuka.")
        return

    msg = "📒 <b>REKAP POSISI SORE INI:</b>\n\n"
    for ticker, data in trades.items():
        try:
            stock = yf.Ticker(ticker)
            curr_price = stock.history(period="1d")['Close'].iloc[-1]
            entry = data['entry']
            pnl = ((curr_price - entry) / entry) * 100
            icon = "🟢" if pnl >= 0 else "🔴"
            msg += f"{icon} <b>{ticker.replace('.JK','')}</b>: {int(curr_price)} ({pnl:+.1f}%)\n"
        except: msg += f"⚪ <b>{ticker}</b>: (Data Error)\n"
            
    send_telegram(msg)

# --- ANALISA UTAMA ---
def analyze_stock(ticker):
    try:
        trades = load_trades()
        if ticker in trades: return False

        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo", interval="1d")
        if len(df) < 50: return False

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
        
        if price > 800: return False
        
        signals = []
        signal_type = ""

        if prev['SMA20'] < prev['SMA50'] and last['SMA20'] > last['SMA50']:
            signals.append("✅ <b>GOLDEN CROSS</b>")
            signal_type = "SWING"
        if last['RSI'] < 30:
            signals.append(f"🎣 <b>RSI OVERSOLD: {last['RSI']:.1f}</b>")
            signal_type = "REBOUND"
        # Logika BSJP: Volume meledak & harga naik
        if vol > (avg_vol * 2.5) and price > prev['Close']:
            signals.append(f"🌇 <b>VOLUME MELEDAK ({int(vol/avg_vol)}x)</b>")
            signal_type = "BSJP"

        if signals:
            buy_price = int(price)
            sl_price = int(buy_price * 0.95)
            tp1_price = int(buy_price * 1.05)
            tp2_price = int(buy_price * 1.12)
            
            if signal_type == "REBOUND": sl_price = int(buy_price * 0.96)

            new_trade = {
                "entry": buy_price, "tp1": tp1_price, "tp2": tp2_price,
                "sl": sl_price, "date": str(datetime.date.today()), "status": "OPEN"
            }
            trades[ticker] = new_trade
            save_trades(trades)

            news_update = get_latest_news(ticker_clean)
            gf_link = f"https://www.google.com/finance/quote/{ticker_clean}:IDX"
            
            msg = f"📊 <b>SINYAL BARU: {ticker_clean}</b>\n"
            msg += "\n".join(signals)
            msg += f"\n\n🎯 <b>TRADING PLAN:</b>\n🟢 BUY: {buy_price}\n💰 TP1: {tp1_price} (5%)\n💰 TP2: {tp2_price} (12%)\n🛡️ SL: {sl_price} (-5%)"
            if news_update: msg += f"\n\n<b>Berita:</b>\n{news_update}"
            msg += f"\n🔗 <a href='{gf_link}'>Grafik</a>"
            
            send_telegram(msg)
            return True

    except Exception as e: pass
    return False

def run_bot():
    count_stock = len(AUTO_WATCHLIST)
    send_telegram(f"🤖 <b>BOT SAHAM JADWAL BARU</b>\nBSJP digeser ke 14:45 WIB.\nTracker & Screener Siap.")
    
    cycle = 0
    while True:
        now = datetime.datetime.now()
        jam = now.hour
        menit = now.minute
        hari_kerja = now.weekday() < 5 

        should_scan = False
        if cycle == 0: should_scan = True 
        
        if hari_kerja:
            # Pagi & Siang: Scan Normal
            if (jam == 9 and menit == 45) or (jam == 11 and menit == 0):
                if cycle % 60 == 0: should_scan = True

            # --- PERUBAHAN DI SINI ---
            # SORE: BSJP Digeser ke 14:45 WIB (Sesi 2 Masih Jalan)
            if jam == 14 and menit == 45 and cycle % 60 == 0:
                print(f"[{now.strftime('%H:%M')}] 🌇 Memulai Scan BSJP Sore...")
                should_scan = True

            # Monitoring per 30 menit
            market_open = (9 <= jam < 16)
            if market_open and cycle % 30 == 0: 
                monitor_active_trades()

            # Rekap Sore (Setelah market benar-benar tutup)
            if jam == 16 and menit == 15 and cycle % 60 == 0:
                send_daily_recap()

        if should_scan:
            print(f"[{now.strftime('%H:%M')}] 🚀 Scanning Saham...", flush=True)
            found = 0
            for stock in AUTO_WATCHLIST:
                if analyze_stock(stock): found += 1
                time.sleep(1.5) 
            print(f"Selesai. Sinyal Baru: {found}")

        if menit == 0 and cycle % 60 == 0:
            print(f"[{now.strftime('%H:%M')}] Standby...", flush=True)

        time.sleep(60) 
        cycle += 1

if __name__ == "__main__":
    run_bot()
