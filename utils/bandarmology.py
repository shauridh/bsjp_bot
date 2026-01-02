"""Modul bandarmology: analisa broker summary IDX via GoAPI."""

import os
import logging
import requests

logger = logging.getLogger(__name__)

GOAPI_BROKER_ENDPOINT = "idx/{symbol}/broker-summary"


def fetch_broker_summary(symbol: str, config: dict) -> dict | None:
    goapi_cfg = config.get("data_sources", {}).get("goapi", {})
    token = os.getenv(goapi_cfg.get("token_env", "GOAPI_TOKEN_1")) or os.getenv("GOAPI_TOKEN_1") or os.getenv("GOAPI_TOKEN_2") or goapi_cfg.get("token")
    if not token:
        logger.info("Token GoAPI tidak diset. Lewati broker summary.")
        return None
    base_url = goapi_cfg.get("base_url", "https://api.goapi.io/stock/idx")
    headers = {goapi_cfg.get("auth_header", "X-API-KEY"): token}
    timeout = goapi_cfg.get("timeout", 8)
    url = f"{base_url}/{GOAPI_BROKER_ENDPOINT.format(symbol=symbol)}"
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json().get("data")
    except requests.RequestException as exc:
        logger.warning("Gagal mengambil broker summary %s: %s", symbol, exc)
        return None


def analyze_bandar(data: dict) -> dict:
    """
    Analisa sederhana: cari top buyer/seller, net buy/sell, dan status akumulasi/distribusi.
    """
    if not data or "brokers" not in data:
        return {"status": "Netral", "top_buyer": None, "top_seller": None, "net_buy": 0}
    brokers = data["brokers"]
    sorted_buy = sorted(brokers, key=lambda x: x.get("buy_value", 0), reverse=True)
    sorted_sell = sorted(brokers, key=lambda x: x.get("sell_value", 0), reverse=True)
    top_buyer = sorted_buy[0]["broker_code"] if sorted_buy else None
    top_seller = sorted_sell[0]["broker_code"] if sorted_sell else None
    net_buy = sum(b["buy_value"] - b["sell_value"] for b in brokers)
    status = "Akumulasi" if net_buy > 0 else ("Distribusi" if net_buy < 0 else "Netral")
    return {"status": status, "top_buyer": top_buyer, "top_seller": top_seller, "net_buy": net_buy}
