"""Kirim sinyal ke Telegram menggunakan Bot API."""

from __future__ import annotations

import logging
import os
from textwrap import dedent
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


def _format_message(signal: Dict[str, Any]) -> str:
    lines = [
        f"📈 {signal.get('strategy', 'Strategy')}",
        f"Symbol : {signal.get('symbol', 'UNKNOWN')}",
        f"Entry  : {signal.get('entry')}",
        f"TP     : {signal.get('tp')}",
        f"SL     : {signal.get('sl')}",
    ]
    price = signal.get("data", {}).get("price")
    if price:
        lines.append(f"Last Price : {price}")
    if signal.get("chart_path"):
        lines.append(f"Chart : {signal['chart_path']}")
    return dedent("\n".join(lines))


def _get_token(telegram_cfg: dict) -> str | None:
    return (
        os.getenv("TELEGRAM_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or telegram_cfg.get("token")
    )


def _get_chat_id(telegram_cfg: dict) -> str | None:
    return (
        os.getenv("TELEGRAM_CHAT_ID")
        or os.getenv("TELEGRAM_CHANNEL_ID")
        or telegram_cfg.get("chat_id")
    )


def send_signal(signal: Dict[str, Any], config: dict) -> None:
    telegram_cfg = config.get("telegram", {})
    token = _get_token(telegram_cfg)
    chat_id = _get_chat_id(telegram_cfg)

    if not token or not chat_id:
        logger.warning("Telegram token/chat_id belum dikonfigurasi. Lewati pengiriman.")
        return

    message = _format_message(signal)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        response.raise_for_status()
        logger.info("Sinyal %s terkirim ke Telegram.", signal.get("symbol"))
    except requests.RequestException as exc:
        logger.error("Gagal mengirim sinyal Telegram: %s", exc)
