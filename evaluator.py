import yfinance as yf
import pandas as pd
from database import get_signals, update_signal_status
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evaluator")

def evaluate_bpjs():
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    signals = get_signals(strategy='BPJS', status='PENDING', date=today)
    for sig in signals:
        ticker = sig['ticker']
        entry = sig['entry_price']
        tp = sig['target_tp']
        try:
            hist = None
            for _ in range(2):
                try:
                    yf_ticker = yf.Ticker(f"{ticker}.JK")
                    hist = yf_ticker.history(period="1d", interval="1d")
                    if not hist.empty:
                        break
                except Exception as e:
                    logger.warning(f"yfinance error for {ticker}: {e}")
                    time.sleep(2)
            if hist is None or hist.empty:
                continue
            high = hist.iloc[-1]['High']
            if high >= tp:
                update_signal_status(sig['id'], 'WIN')
            else:
                update_signal_status(sig['id'], 'LOSS')
        except Exception as e:
            logger.error(f"Eval error for {ticker}: {e}")

def evaluate_bsjp():
    yesterday = (pd.Timestamp.now() - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    signals = get_signals(strategy='BSJP', status='PENDING', date=yesterday)
    for sig in signals:
        ticker = sig['ticker']
        entry = sig['entry_price']
        tp = sig['target_tp']
        try:
            hist = None
            for _ in range(2):
                try:
                    yf_ticker = yf.Ticker(f"{ticker}.JK")
                    hist = yf_ticker.history(period="2d", interval="1d")
                    if not hist.empty and len(hist) > 1:
                        break
                except Exception as e:
                    logger.warning(f"yfinance error for {ticker}: {e}")
                    time.sleep(2)
            if hist is None or hist.empty or len(hist) < 2:
                continue
            today_row = hist.iloc[-1]
            high = today_row['High']
            if high >= tp:
                update_signal_status(sig['id'], 'WIN')
            else:
                update_signal_status(sig['id'], 'LOSS')
        except Exception as e:
            logger.error(f"Eval error for {ticker}: {e}")
