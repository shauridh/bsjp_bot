
import os
import requests
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from database import insert_signal
from dotenv import load_dotenv
import logging
import time

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scanner")

load_dotenv()
GOAPI_KEY = os.getenv('GOAPI_KEY')
GOAPI_BASE_URL = os.getenv('GOAPI_BASE_URL')
# Logger info moved to avoid initialization issues

# --- GoAPI Bulk Fetch ---
def fetch_top_gainers():
    url = f"{GOAPI_BASE_URL}/top_gainer?api_key={GOAPI_KEY}"
    try:
        logger.info("Fetching top gainers from GoAPI...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched {len(data.get('data', []))} top gainers.")
        return data.get('data', [])
    except Exception as e:
        logger.error(f"GoAPI fetch error: {e}")
        return []

def fetch_top_losers():
    url = f"{GOAPI_BASE_URL}/top_loser?api_key={GOAPI_KEY}"
    try:
        logger.info("Fetching top losers from GoAPI...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched {len(data.get('data', []))} top losers.")
        return data.get('data', [])
    except Exception as e:
        logger.error(f"GoAPI fetch error: {e}")
        return []

def fetch_trending():
    url = f"{GOAPI_BASE_URL}/trending?api_key={GOAPI_KEY}"
    try:
        logger.info("Fetching trending stocks from GoAPI...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched {len(data.get('data', []))} trending stocks.")
        return data.get('data', [])
    except Exception as e:
        logger.error(f"GoAPI fetch error: {e}")
        return []


# --- YFinance IDX Universe Fetch ---
def fetch_yf_universe():
    # Sumber: https://finance.yahoo.com/lookup/stocks; exchange: JK
    # Atau gunakan list statis jika scraping tidak memungkinkan
    # Kompas100 per Desember 2025 (update sesuai kebutuhan)
    kompas100 = [
        'ACES','ACST','ADHI','ADRO','AGII','AKRA','AMRT','ANTM','APLN','ASII','ASRI','BBCA','BBNI','BBRI','BBTN','BFIN','BJBR','BJTM','BMRI','BNGA','BNII','BRIS','BRPT','BSDE','BTPS','BUDI','CPIN','CTRA','DMAS','DOID','DSNG','ELSA','ERAA','EXCL','FREN','GGRM','GJTL','GOTO','HEAL','HMSP','ICBP','INCO','INDF','INDY','INKP','INTP','IPCM','ITMG','JPFA','JSMR','KIJA','KLBF','LPKR','LPPF','MAPI','MDKA','MEDC','MIKA','MNCN','MPPA','MTDL','MYOR','PGAS','PNLF','PPRE','PPRO','PRDA','PTBA','PTPP','PWON','RAJA','RALS','ROTI','SCMA','SIDO','SMGR','SMRA','SSMS','TCPI','TINS','TKIM','TLKM','TOWR','TPIA','TRAM','TUGU','UNTR','UNVR','WEGE','WIKA','WSBP','WSKT','WTON'
    ]
    logger.info(f"Fetched {len(kompas100)} tickers from yfinance universe (Kompas100 list).")
    return kompas100

def fetch_prices(codes):
    # codes: list of stock codes, e.g. ['BBCA','BBRI']
    codes_param = ','.join(codes)
    url = f"{GOAPI_BASE_URL}/prices?codes={codes_param}&api_key={GOAPI_KEY}"
    try:
        logger.info(f"Fetching prices for {codes_param} from GoAPI...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched prices for {len(data.get('data', []))} stocks.")
        return data.get('data', [])
    except Exception as e:
        logger.error(f"GoAPI fetch error: {e}")
        return []

def fetch_historical(symbol):
    url = f"{GOAPI_BASE_URL}/{symbol}/historical?api_key={GOAPI_KEY}"
    try:
        logger.info(f"Fetching historical for {symbol} from GoAPI...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched {len(data.get('data', []))} historical records for {symbol}.")
        return data.get('data', [])
    except Exception as e:
        logger.error(f"GoAPI fetch error: {e}")
        return []

def fetch_profile(symbol):
    url = f"{GOAPI_BASE_URL}/{symbol}/profile?api_key={GOAPI_KEY}"
    try:
        logger.info(f"Fetching profile for {symbol} from GoAPI...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Fetched profile for {symbol}.")
        return data.get('data', {})
    except Exception as e:
        logger.error(f"GoAPI fetch error: {e}")
        return {}

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
            hist = yf_ticker.history(period="60d", interval="1d")
            if hist.empty or len(hist) < 20:
                return None
            hist['EMA20'] = ta.ema(hist['Close'], length=20)
            hist['EMA50'] = ta.ema(hist['Close'], length=50)
            hist['RSI14'] = ta.rsi(hist['Close'], length=14)
            hist['MA5'] = ta.sma(hist['Close'], length=5)
            hist['MA20V'] = ta.sma(hist['Volume'], length=20)
            hist['avg_vol5'] = hist['Volume'].rolling(window=5).mean()
            hist['52w_high'] = hist['High'].rolling(window=252, min_periods=1).max()
            return hist
        except Exception as e:
            logger.warning(f"yfinance error for {ticker} (attempt {attempt+1}): {e}")
            time.sleep(sleep)
    return None

def hybrid_scan(strategy):
    logger.info(f"Starting hybrid_scan for {strategy}")
    # Screening seluruh universe IDX dari yfinance (LQ45 demo list, bisa diganti full IDX)
    tickers = fetch_yf_universe()
    logger.info(f"Total tickers fetched: {len(tickers)}")
    results = []
    for ticker in tickers:
        logger.info(f"Validating trend for {ticker}")
        hist = validate_trend(ticker)
        if hist is None:
            logger.info(f"No valid history for {ticker}")
            continue
        # Simulasikan struktur 'stock' agar filter tetap jalan
        last_row = hist.iloc[-1]
        stock = {
            'code': ticker,
            'last': last_row['Close'],
            'volume': last_row['Volume']
        }
        if not basic_filter(stock, min_price=50, min_vol=10000):
            logger.info(f"{ticker} filtered out: basic filter.")
            continue
        last_row = hist.iloc[-1]
        open_price = last_row['Open']
        last_price = last_row['Close']
        high = last_row['High']
        low = last_row['Low']
        daily_change = (last_price - open_price) / open_price * 100
        ema20 = last_row['EMA20']
        ema50 = last_row['EMA50']
        rsi14 = last_row['RSI14']
        volume = last_row['Volume']
        avg_vol5 = last_row['avg_vol5'] if not pd.isna(last_row['avg_vol5']) else 0
        ma5 = last_row['MA5'] if not pd.isna(last_row['MA5']) else 0
        ma20v = last_row['MA20V'] if not pd.isna(last_row['MA20V']) else 0
        high_52w = last_row['52w_high'] if not pd.isna(last_row['52w_high']) else 0
        lower_shadow = min(open_price, last_price) - low
        range_harian = high - low if high - low != 0 else 1
        ipo_filter = False  # Default, skip IPO filter (but log info)
        # Exclude ARA/ARB
        if daily_change > 25 or daily_change < -25:
            logger.info(f"{ticker} filtered out: daily_change {daily_change:.2f}% ARA/ARB.")
            continue
        # Exclude volume kecil dan volume tidak spike
        if volume < 10000:
            logger.info(f"{ticker} filtered out: volume {volume} < 10.000.")
            continue
        if avg_vol5 > 0 and volume < 1.5 * avg_vol5:
            logger.info(f"{ticker} filtered out: volume {volume} tidak > 1.5x avg5 {avg_vol5:.0f}.")
            continue
        # Exclude IPO < 3 bulan (jika data IPO tersedia, skip jika tidak)
        # (GoAPI/yfinance tidak selalu sediakan, jadi hanya log info)
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
            # Breakout: close > high kemarin
            if len(hist) > 1 and last_price <= hist.iloc[-2]['High']:
                logger.info(f"{ticker} filtered out: close {last_price} <= high kemarin {hist.iloc[-2]['High']} (no breakout).")
                continue
            tp = last_price * 1.025
            sl = last_price * 0.98
        elif strategy == 'BSJP':
            # 1. 1 Day Volume Change > 1 (volume hari ini > volume kemarin)
            if len(hist) > 1 and volume <= hist.iloc[-2]['Volume']:
                logger.info(f"{ticker} filtered out: volume {volume} <= volume kemarin {hist.iloc[-2]['Volume']}.")
                continue
            # 2. Price > 50
            if last_price <= 50:
                logger.info(f"{ticker} filtered out: price {last_price} <= 50.")
                continue
            # 3. Near 52 Week High > 0.7 (close > 70% dari 52w high)
            if high_52w == 0 or (last_price / high_52w) <= 0.7:
                logger.info(f"{ticker} filtered out: close {last_price} / 52w high {high_52w} <= 0.7.")
                continue
            # 4. Value > 5,000,000,000 (close * volume)
            if last_price * volume <= 5_000_000_000:
                logger.info(f"{ticker} filtered out: value {last_price * volume:.0f} <= 5M.")
                continue
            # 5. Price > 1 x Price MA5
            if ma5 == 0 or last_price <= ma5:
                logger.info(f"{ticker} filtered out: price {last_price} <= MA5 {ma5}.")
                continue
            # 6. Volume > 2 x Volume MA20
            if ma20v == 0 or volume <= 2 * ma20v:
                logger.info(f"{ticker} filtered out: volume {volume} <= 2x MA20 {ma20v}.")
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
