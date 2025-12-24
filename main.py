import os
import logging
from datetime import datetime
import pytz
import threading
from telegram import Bot
from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from scanner import hybrid_scan
from evaluator import evaluate_bpjs, evaluate_bsjp
from database import init_db
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')  # Set this in your .env or hardcode for now



# Custom Jakarta timezone log formatter
class JakartaFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        tz = pytz.timezone('Asia/Jakarta')
        ct = datetime.fromtimestamp(record.created, tz)
        if datefmt:
            s = ct.strftime(datefmt)
        else:
            s = ct.isoformat(sep=" ", timespec="seconds")
        return s

formatter = JakartaFormatter('[%(asctime)s] %(levelname)s:%(name)s:%(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)

init_db()
bot = Bot(token=TELEGRAM_TOKEN)

# --- Alert helpers ---
def send_alert(strategy, results):
    if not results:
        logger.info(f"No candidates for {strategy} at this run.")
        return
    if strategy == 'BPJS':
        prefix = '☀️ [BPJS - MORNING]'
        tp_pct = '+2.5%'
        sl_pct = '-2.0%'
    else:
        prefix = '🌇 [BSJP - AFTERNOON]'
        tp_pct = '+3.0%'
        sl_pct = '-2.0%'
    msg = f"{prefix}\n"
    for r in results:
        msg += f"{r['ticker']}: Entry {r['entry_price']:.2f}, TP {tp_pct}, SL {sl_pct}\n"
    logger.info(f"Sending alert for {strategy}: {msg}")
    try:
        bot.send_message(chat_id=CHAT_ID, text=msg)
        logger.info("Alert sent successfully.")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

# --- Scheduler jobs ---
def scan_and_alert(strategy):
    logger.info(f"Running scan_and_alert for {strategy}")
    results = hybrid_scan(strategy)
    logger.info(f"Scan results for {strategy}: {results}")
    send_alert(strategy, results)

def start_scheduler():
    scheduler = BackgroundScheduler(timezone='Asia/Jakarta')
    # BPJS: 09:15, 09:30, 09:45, 10:00 WIB
    for t in ['09:15', '09:30', '09:45', '10:00']:
        h, m = t.split(':')
        scheduler.add_job(scan_and_alert, CronTrigger(hour=int(h), minute=int(m)), args=['BPJS'], id=f'bpjs_{t}')
    # BPJS Eval: 16:30 WIB
    scheduler.add_job(evaluate_bpjs, CronTrigger(hour=16, minute=30), id='bpjs_eval')
    # BSJP: 14:45, 15:00, 15:15, 15:30, 15:45 WIB
    for t in ['14:45', '15:00', '15:15', '15:30', '15:45']:
        h, m = t.split(':')
        scheduler.add_job(scan_and_alert, CronTrigger(hour=int(h), minute=int(m)), args=['BSJP'], id=f'bsjp_{t}')
    # BSJP Eval: 10:00 WIB (next day)
    scheduler.add_job(evaluate_bsjp, CronTrigger(hour=10, minute=0), id='bsjp_eval')
    scheduler.start()
    logger.info("Scheduler started. Bot is running.")

def main():
    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    # Kirim notifikasi awal ke Telegram sebagai test
    try:
        bot.send_message(chat_id=CHAT_ID, text="🚦 IDX Trading Bot started (startup test notification)")
        logger.info("Startup test notification sent to Telegram.")
    except Exception as e:
        logger.error(f"Failed to send startup test notification: {e}")

    # Minimal Telegram bot for /start
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    async def start(update, context):
        await update.message.reply_text("IDX Trading Bot is running.")
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
