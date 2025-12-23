import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot, ParseMode
from scanner import scan_and_save, format_alert
from evaluator import evaluate_signals, format_report
import time

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
bot = Bot(token=TELEGRAM_TOKEN)

# WIB = UTC+7
def send_telegram_message(text):
    try:
        bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print(f"Telegram Error: {e}")

def scanner_job(time_str):
    signals = scan_and_save(time_str)
    msg = format_alert(signals, time_str)
    send_telegram_message(msg)

def evaluator_job():
    results, win_rate = evaluate_signals()
    msg = format_report(results, win_rate)
    send_telegram_message(msg)

if __name__ == "__main__":
    scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
    # Scanner tasks
    for t in ["14:45", "15:00", "15:15", "15:30", "15:45"]:
        hour, minute = map(int, t.split(":"))
        scheduler.add_job(scanner_job, 'cron', hour=hour, minute=minute, args=[t], id=f"scanner_{t}")
    # Evaluator task
    scheduler.add_job(evaluator_job, 'cron', hour=10, minute=0, id="evaluator")
    scheduler.start()
    print("BSJP Sniper Bot is running...")
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
