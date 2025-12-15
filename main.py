#!/usr/bin/env python3
import schedule
import time
from datetime import datetime
import sys
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import optimized modules
from screener_optimized import OptimizedBSJPScreener
from notifier_optimized import OptimizedTelegramNotifier

# Configuration
GOAPI_KEY = os.getenv("GOAPI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def run_optimized_screening():
    """Jalankan screening optimized"""
    print(f"\n{'='*60}")
    print(f"🎯 OPTIMIZED BSJP SCREENING - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    
    # Check market condition first
    screener = OptimizedBSJPScreener(GOAPI_KEY)
    market_condition = screener.get_market_condition()
    
    print(f"📊 Kondisi Pasar: {market_condition.get('condition')}")
    print(f"📈 IHSG Change: {market_condition.get('change', 0):+.2f}%")
    print(f"💡 Rekomendasi: {market_condition.get('recommendation')}")
    
    # Jika pasar bearish kuat, skip screening
    if market_condition.get('condition') in ['STRONG_BEARISH', 'BEARISH']:
        print("❌ Pasar bearish, skipping screening...")
        
        # Kirim notifikasi market condition saja
        notifier = OptimizedTelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
        message = f"""
⚠️ <b>MARKET ALERT - NO SCREENING</b>
📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}

Kondisi pasar <b>{market_condition.get('condition')}</b>
IHSG: {market_condition.get('change', 0):+.2f}%

<b>REKOMENDASI:</b> {market_condition.get('recommendation')}

<i>Screening hari ini dilewati untuk menghindari risk tinggi.
Better safe than sorry! 🔒</i>
"""
        notifier.send_message(message)
        return
    
    # Run screening
    print("\n🔍 Memulai screening optimized...")
    signals = screener.screen_with_high_winrate()
    
    # Send to Telegram
    notifier = OptimizedTelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
    success = notifier.send_signals(signals, market_condition)
    
    if success:
        print("✅ Notifikasi terkirim ke Telegram")
    else:
        print("❌ Gagal mengirim notifikasi")
    
    # Log summary
    print(f"\n📋 SUMMARY:")
    print(f"• Saham discan: {len(screener.get_ihsg_stocks())}")
    print(f"• Sinyal ditemukan: {len(signals)}")
    print(f"• Confidence rata-rata: {sum(s['confidence'] for s in signals)/len(signals) if signals else 0:.1f}%")
    print(f"• Waktu: {datetime.now().strftime('%H:%M:%S')}")

def main():
    """Program utama"""
    print("🤖 BSJP OPTIMIZED BOT - Winrate 75-85%")
    print("=" * 50)
    
    # Validate API keys
    if not GOAPI_KEY or GOAPI_KEY == "your_goapi_api_key_here":
        print("❌ ERROR: GOAPI_API_KEY belum diisi di .env")
        print("💡 Dapatkan di: https://goapi.io/")
        return
    
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "your_telegram_bot_token_here":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN belum diisi di .env")
        print("💡 Buat via @BotFather di Telegram")
        return
    
    if not CHAT_ID or CHAT_ID == "your_telegram_chat_id_here":
        print("❌ ERROR: TELEGRAM_CHAT_ID belum diisi di .env")
        print("💡 Dapatkan Chat ID via @userinfobot")
        return
    
    # Run mode
    if len(sys.argv) > 1:
        if sys.argv[1] == "--now":
            print("🚀 Running optimized screening now...")
            run_optimized_screening()
        elif sys.argv[1] == "--test":
            print("🧪 Test mode...")
            notifier = OptimizedTelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
            notifier.send_message("🤖 <b>BSJP Optimized Bot - Test Successful</b>\n\nBot siap berjalan!")
        elif sys.argv[1] == "--morning":
            print("⏰ Sending morning reminder...")
            notifier = OptimizedTelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
            notifier.send_morning_reminder()
    else:
        # Schedule mode
        print("⏰ Scheduling optimized screening...")
        
        # Main screening at 14:50
        schedule.every().day.at("14:50").do(run_optimized_screening)
        
        # Morning reminder at 09:00
        schedule.every().day.at("09:00").do(
            lambda: OptimizedTelegramNotifier(TELEGRAM_TOKEN, CHAT_ID).send_morning_reminder()
        )
        
        # Market check at 14:30
        schedule.every().day.at("14:30").do(
            lambda: print(f"⏰ Market check at {datetime.now().strftime('%H:%M')}")
        )
        
        print("✅ Scheduled:")
        print("   • 14:50 → Optimized Screening")
        print("   • 09:00 → Morning Reminder")
        print("\n📱 Bot berjalan. Menunggu waktu screening...")
        print("   Tekan Ctrl+C untuk berhenti")
        
        # Initial test
        print("\n🔧 Initial test...")
        notifier = OptimizedTelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
        notifier.send_message("🤖 <b>BSJP Optimized Bot Started</b>\n\nTarget Winrate: 75-85%\nScreening time: 14:50 WIB")
        
        # Main loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n👋 Bot dihentikan")

if __name__ == "__main__":
    main()
