import os
import requests
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from database import insert_signal
from dotenv import load_dotenv
import logging
import time

load_dotenv()

GOAPI_KEY = os.getenv('GOAPI_KEY')
GOAPI_BASE_URL = os.getenv('GOAPI_BASE_URL')

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scanner")

# --- GoAPI Bulk Fetch ---
def fetch_top_gainers():
    url = f"{GOAPI_BASE_URL}/topgainers"
    headers = {"Authorization": f"Bearer {GOAPI_KEY}"}
    try:
        logger.info("Fetching top gainers from GoAPI...")
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched {len(data.get('data', []))} top gainers.")
        return data.get('data', [])
    except Exception as e:
        logger.error(f"GoAPI fetch error: {e}")
        return []

# --- Local Basic Filter ---
def basic_filter(stock, min_price=50, min_vol=1):
    try:
        price = float(stock.get('last', 0))
        volume = float(stock.get('volume', 0))
        return price > min_price and volume > min_vol
    except Exception:
        return False

# --- YFinance Technical Validation ---
def validate_trend(ticker, retries=2, sleep=2):
    for attempt in range(retries):
        try:
            yf_ticker = yf.Ticker(f"{ticker}.JK")
            hist = yf_ticker.history(period="30d", interval="1d")
            if hist.empty or len(hist) < 20:
                return None
            hist['EMA20'] = ta.ema(hist['Close'], length=20)
            hist['RSI14'] = ta.rsi(hist['Close'], length=14)
            return hist
        except Exception as e:
            logger.warning(f"yfinance error for {ticker} (attempt {attempt+1}): {e}")
            time.sleep(sleep)
    return None

def hybrid_scan(strategy):
    logger.info(f"Starting hybrid_scan for {strategy}")
    gainers = fetch_top_gainers()
    logger.info(f"Total gainers fetched: {len(gainers)}")
    candidates = [s for s in gainers if basic_filter(s)]
    logger.info(f"Candidates after basic filter: {len(candidates)}")
    results = []
    for stock in candidates:
        ticker = stock['code']
        logger.info(f"Validating trend for {ticker}")
        hist = validate_trend(ticker)
        if hist is None:
            logger.info(f"No valid history for {ticker}")
            continue
        last_row = hist.iloc[-1]
        open_price = last_row['Open']
        last_price = last_row['Close']
        daily_change = (last_price - open_price) / open_price * 100
        ema20 = last_row['EMA20']
        rsi14 = last_row['RSI14']
        logger.info(f"{ticker} | open: {open_price}, close: {last_price}, change: {daily_change:.2f}%, ema20: {ema20}, rsi14: {rsi14}")
        # Strategy-specific rules
        if strategy == 'BPJS':
            if not (2 <= daily_change <= 10):
                logger.info(f"{ticker} filtered out: daily_change {daily_change:.2f}% not in 2-10%.")
                continue
            if last_price < open_price:
                logger.info(f"{ticker} filtered out: not green candle.")
                continue
            if last_price <= ema20:
                logger.info(f"{ticker} filtered out: price <= EMA20.")
                continue
            if rsi14 >= 70:
                logger.info(f"{ticker} filtered out: RSI >= 70.")
                continue
            tp = last_price * 1.025
            sl = last_price * 0.98
        elif strategy == 'BSJP':
            if not (2 <= daily_change <= 15):
                logger.info(f"{ticker} filtered out: daily_change {daily_change:.2f}% not in 2-15%.")
                continue
            # Strong close near high
            high = last_row['High']
            if (high - last_price) / high > 0.01:
                logger.info(f"{ticker} filtered out: not strong close near high.")
                continue
            if last_price <= ema20:
                logger.info(f"{ticker} filtered out: price <= EMA20.")
                continue
            if rsi14 >= 70:
                logger.info(f"{ticker} filtered out: RSI >= 70.")
                continue
            tp = last_price * 1.03
            sl = last_price * 0.98
        else:
            logger.info(f"Unknown strategy: {strategy}")
            continue
        # Save to DB
        insert_signal(
            ticker=ticker,
            strategy=strategy,
            signal_date=pd.Timestamp.now().strftime('%Y-%m-%d'),
            entry_price=last_price,
            target_tp=tp,
            limit_sl=sl
        )
        logger.info(f"Signal saved for {ticker} ({strategy})")
        results.append({
            'ticker': ticker,
            'entry_price': last_price,
            'tp': tp,
            'sl': sl
        })
    logger.info(f"Total signals for {strategy}: {len(results)}")
    return results
