import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from scanner import scan_and_save, scan_bpjs_market, format_alert
from evaluator import evaluate_signals, evaluate_bpjs_today, format_report, format_bpjs_report
import time

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
bot = Bot(token=TELEGRAM_TOKEN)

# WIB = UTC+7
def send_telegram_message(text):
    try:
        bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        print(f"Telegram Error: {e}")


# Unified scanner job for both strategies
def scanner_job(time_str, strategy='BSJP'):
    if strategy == 'BPJS':
        signals = scan_bpjs_market(time_str)
        msg = format_alert(signals, time_str, strategy='BPJS')
    else:
        signals = scan_and_save(time_str)
        msg = format_alert(signals, time_str, strategy='BSJP')
    send_telegram_message(msg)


# Unified evaluator job for both strategies
def evaluator_job(strategy='BSJP'):
    if strategy == 'BPJS':
        results, win_rate = evaluate_bpjs_today()
        msg = format_bpjs_report(results, win_rate)
    else:
        results, win_rate = evaluate_signals()
        msg = format_report(results, win_rate)
    send_telegram_message(msg)

if __name__ == "__main__":
    scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
    # BSJP Scanner tasks (Afternoon)
    for t in ["14:45", "15:00", "15:15", "15:30", "15:45"]:
        hour, minute = map(int, t.split(":"))
        scheduler.add_job(scanner_job, 'cron', hour=hour, minute=minute, args=[t, 'BSJP'], id=f"scanner_bsjp_{t}")
    # BPJS Scanner tasks (Morning)
    for t in ["09:15", "09:30", "09:45", "10:00"]:
        hour, minute = map(int, t.split(":"))
        scheduler.add_job(scanner_job, 'cron', hour=hour, minute=minute, args=[t, 'BPJS'], id=f"scanner_bpjs_{t}")
    # BSJP Evaluator (Next Day 10:00)
    scheduler.add_job(evaluator_job, 'cron', hour=10, minute=0, args=['BSJP'], id="evaluator_bsjp")
    # BPJS Evaluator (Same Day 16:30)
    scheduler.add_job(evaluator_job, 'cron', hour=16, minute=30, args=['BPJS'], id="evaluator_bpjs")
    scheduler.start()
    print("BSJP & BPJS Sniper Bot is running...")
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
