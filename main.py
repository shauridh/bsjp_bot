#!/usr/bin/env python3
import schedule
import time
from datetime import datetime
import sys

from config import GOAPI_KEY, TELEGRAM_TOKEN, CHAT_ID
from screener import SimpleBSJPScreener
from notifier import TelegramNotifier

def run_screening():
    """Jalankan screening dan kirim notifikasi"""
    print(f"\n⏰ Screening started at {datetime.now().strftime('%H:%M')}")
    
    # 1. Screening saham
    screener = SimpleBSJPScreener(GOAPI_KEY)
    signals = screener.screen_all_stocks()
    
    # 2. Kirim ke Telegram
    notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
    success = notifier.send_signals(signals)
    
    if success:
        print("✅ Notifikasi terkirim ke Telegram")
    else:
        print("❌ Gagal mengirim notifikasi")

def main():
    """Program utama"""
    print("=" * 50)
    print("🤖 BSJP SIMPLE BOT")
    print("=" * 50)
    
    # Cek API keys
    if not GOAPI_KEY or GOAPI_KEY == "your_goapi_api_key_here":
        print("❌ ERROR: GOAPI_API_KEY belum diisi di .env")
        return
    
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "your_telegram_bot_token_here":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN belum diisi di .env")
        return
    
    # Mode: run now atau schedule
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        print("🚀 Running screening now...")
        run_screening()
    else:
        # Jadwalkan setiap hari jam 14:50
        schedule.every().day.at("14:50").do(run_screening)
        
        # Juga jadwalkan test message jam 09:00
        schedule.every().day.at("09:00").do(
            lambda: TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID).send_test_message()
        )
        
        print("⏰ Bot berjalan. Menunggu jam 14:50...")
        print("Tekan Ctrl+C untuk berhenti")
        
        # Test run
        print("\n🔧 Test run...")
        notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
        notifier.send_test_message()
        
        # Loop utama
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check setiap menit

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot dihentikan")
