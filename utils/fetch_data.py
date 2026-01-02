"""Data fetcher untuk gabungan yfinance + GoAPI dengan caching sederhana."""

from __future__ import annotations

import copy
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE: Dict[str, Dict[str, Any]] = {}


def _env_truthy(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_enabled(source_cfg: Any) -> bool:
    if isinstance(source_cfg, dict):
        return source_cfg.get("enabled", True)
    return bool(source_cfg)


def _read_cache(symbol: str, ttl: int) -> Dict[str, Any] | None:
    cached = _CACHE.get(symbol)
    if not cached:
        return None
    age = (datetime.now(timezone.utc) - cached["timestamp"]).total_seconds()
    if age <= ttl:
        return copy.deepcopy(cached["data"])
    return None


def _write_cache(symbol: str, payload: Dict[str, Any]) -> None:
    _CACHE[symbol] = {
        "timestamp": datetime.now(timezone.utc),
        "data": copy.deepcopy(payload),
    }


def _build_history(records: pd.DataFrame, window: int) -> list[dict[str, Any]]:
    trimmed = records.tail(window).reset_index()
    trimmed.rename(columns={"Date": "timestamp"}, inplace=True)
    trimmed["timestamp"] = pd.to_datetime(trimmed["timestamp"]).dt.tz_localize(None)
    return [
        {
            "timestamp": row["timestamp"].isoformat(),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]),
        }
        for _, row in trimmed.iterrows()
    ]


def _hydrate_from_yfinance(symbol: str, cfg: dict[str, Any], payload: dict[str, Any]) -> None:
    period = cfg.get("period", "7d")
    interval = cfg.get("interval", "1h")
    history_window = cfg.get("history_window", 160)
    ticker = yf.Ticker(symbol)
    history = ticker.history(period=period, interval=interval, actions=False)
    if history.empty:
        logger.warning("yfinance tidak mengembalikan data untuk %s", symbol)
        return
    latest = history.iloc[-1]
    payload.setdefault("symbol", symbol)
    payload["price"] = float(latest["Close"])
    payload["volume"] = float(latest["Volume"])
    payload["timestamp"] = latest.name.to_pydatetime().replace(tzinfo=timezone.utc).isoformat()
    payload["history"] = _build_history(history, history_window)


def _hydrate_from_goapi(symbol: str, cfg: dict[str, Any], payload: dict[str, Any]) -> None:
    token = os.getenv(cfg.get("token_env", "GOAPI_TOKEN")) or cfg.get("token")
    if not token:
        logger.info("Token GoAPI tidak diset. Lewati sumber GoAPI.")
        return
    base_url = cfg.get("base_url", "https://api.goapi.id/v1/stock")
    headers = {cfg.get("auth_header", "X-API-KEY"): token}
    timeout = cfg.get("timeout", 8)

    def _request(path: str) -> dict[str, Any] | None:
        url = f"{base_url}/{path.format(symbol=symbol)}"
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json().get("data")

    try:
        price_data = _request(cfg.get("price_endpoint", "idx/{symbol}"))
        if price_data:
            payload.setdefault("symbol", symbol)
            payload.setdefault("price", float(price_data.get("close", price_data.get("last_price", 0))))
            payload.setdefault("volume", float(price_data.get("volume", 0)))
            ts = price_data.get("updated_at") or price_data.get("date")
            if ts:
                payload["timestamp"] = ts
        ohlcv_data = _request(cfg.get("ohlcv_endpoint", "idx/{symbol}/ohlcv/latest"))
        if ohlcv_data and "history" not in payload:
            payload["history"] = ohlcv_data
    except requests.RequestException as exc:
        logger.warning("Gagal mengambil data GoAPI untuk %s: %s", symbol, exc)


def fetch_data(symbol: str, config: dict[str, Any]) -> Dict[str, Any] | None:
    """Mengambil data harga dengan prioritas yfinance lalu GoAPI."""

    symbol = symbol.upper()
    sources = config.get("data_sources", {})
    cache_ttl = int(sources.get("cache_ttl", 300))
    env_mock = _env_truthy(os.getenv("MOCK_DATA"))
    use_mock = env_mock or sources.get("mock", False)

    cached = _read_cache(symbol, cache_ttl)
    if cached:
        return cached

    if use_mock:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "symbol": symbol,
            "price": 100.0,
            "volume": 1000,
            "timestamp": now,
            "history": [
                {
                    "timestamp": now,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.5,
                    "close": 100.5,
                    "volume": 1000,
                }
            ],
        }
        _write_cache(symbol, payload)
        return payload

    payload: Dict[str, Any] = {}
    yfinance_cfg = sources.get("yfinance", {})
    if _is_enabled(yfinance_cfg):
        try:
            _hydrate_from_yfinance(symbol, yfinance_cfg if isinstance(yfinance_cfg, dict) else {}, payload)
        except Exception as exc:  # yfinance memunculkan Exception generic
            logger.warning("Gagal mengambil data yfinance untuk %s: %s", symbol, exc)

    goapi_cfg = sources.get("goapi", {})
    if _is_enabled(goapi_cfg):
        _hydrate_from_goapi(symbol, goapi_cfg if isinstance(goapi_cfg, dict) else {}, payload)

    if not payload:
        logger.error("Tidak ada data pasar untuk %s", symbol)
        return None

    _write_cache(symbol, payload)
    return payload
