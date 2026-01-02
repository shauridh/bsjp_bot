"""Modul news sentiment & corporate action IDX."""

import requests
import logging
import os

logger = logging.getLogger(__name__)

IDX_NEWS_API = "https://www.idx.co.id/umbraco/api/News/GetNewsByStockCode?stockCode={symbol}"  # Contoh endpoint
CORP_ACTION_API = "https://api.goapi.id/v1/stock/idx/{symbol}/corporate-action"  # GoAPI


def fetch_news_sentiment(symbol: str) -> dict:
    """Ambil berita terbaru dan analisa sentimen sederhana."""
    try:
        url = IDX_NEWS_API.format(symbol=symbol.replace('.JK', ''))
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        news = resp.json()
        # Dummy sentiment: positif jika ada kata 'dividen', 'naik', negatif jika 'rugi', 'turun'
        sentiment = "Netral"
        for item in news:
            title = item.get("Title", "").lower()
            if any(word in title for word in ["dividen", "naik", "laba", "akumulasi"]):
                sentiment = "Positif"
                break
            if any(word in title for word in ["rugi", "turun", "right issue", "dilusi"]):
                sentiment = "Negatif"
                break
        return {"sentiment": sentiment, "news": news[:3]}
    except Exception as exc:
        logger.warning("Gagal ambil news sentiment %s: %s", symbol, exc)
        return {"sentiment": "Netral", "news": []}


def fetch_corporate_action(symbol: str, config: dict) -> dict:
    """Ambil corporate action terbaru via GoAPI."""
    goapi_cfg = config.get("data_sources", {}).get("goapi", {})
    token = os.getenv(goapi_cfg.get("token_env", "GOAPI_TOKEN_1")) or os.getenv("GOAPI_TOKEN_1") or os.getenv("GOAPI_TOKEN_2") or goapi_cfg.get("token")
    if not token:
        logger.info("Token GoAPI tidak diset. Lewati corporate action.")
        return {}
    base_url = goapi_cfg.get("base_url", "https://api.goapi.io/stock/idx")
    headers = {goapi_cfg.get("auth_header", "X-API-KEY"): token}
    timeout = goapi_cfg.get("timeout", 8)
    url = CORP_ACTION_API.format(symbol=symbol)
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data
    except Exception as exc:
        logger.warning("Gagal ambil corporate action %s: %s", symbol, exc)
        return {}
