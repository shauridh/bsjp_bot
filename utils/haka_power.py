"""Modul HAKA Power: running trade/momentum IDX."""

import os
import logging
import requests

logger = logging.getLogger(__name__)

GOAPI_HAKA_ENDPOINT = "idx/{symbol}/running-trade"


def fetch_haka_power(symbol: str, config: dict) -> dict | None:
    goapi_cfg = config.get("data_sources", {}).get("goapi", {})
    token = os.getenv(goapi_cfg.get("token_env", "GOAPI_TOKEN")) or goapi_cfg.get("token")
    if not token:
        logger.info("Token GoAPI tidak diset. Lewati running trade.")
        return None
    base_url = goapi_cfg.get("base_url", "https://api.goapi.id/v1/stock")
    headers = {goapi_cfg.get("auth_header", "X-API-KEY"): token}
    timeout = goapi_cfg.get("timeout", 8)
    url = f"{base_url}/{GOAPI_HAKA_ENDPOINT.format(symbol=symbol)}"
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json().get("data")
    except requests.RequestException as exc:
        logger.warning("Gagal ambil running trade %s: %s", symbol, exc)
        return None


def analyze_haka(data: dict) -> dict:
    """
    Analisa sederhana: deteksi momentum beli/jual dari running trade.
    """
    if not data or "trades" not in data:
        return {"momentum": "Netral", "power": 0}
    trades = data["trades"]
    buy_power = sum(t["buy_value"] for t in trades if t["type"] == "buy")
    sell_power = sum(t["sell_value"] for t in trades if t["type"] == "sell")
    power = buy_power - sell_power
    momentum = "HAKA BUY" if power > 0 else ("HAKA SELL" if power < 0 else "Netral")
    return {"momentum": momentum, "power": power}
