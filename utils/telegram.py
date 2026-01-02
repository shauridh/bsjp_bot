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
    ]
    # Risk management: Antri jika harga turun dari entry tapi belum kena SL
    entry = signal.get("entry")
    sl = signal.get("sl")
    price = signal.get("data", {}).get("price")
    antri = None
    if entry and sl and price:
        try:
            entry = float(entry)
            sl = float(sl)
            price = float(price)
            if price < entry and price > sl:
                drop_pct = (entry - price) / entry * 100
                if drop_pct >= 1.0:  # threshold 1% drop
                    antri = f"{price:.2f} ({drop_pct:.2f}%)"
        except Exception:
            pass
    lines.append(f"Antri  : {antri if antri else '-'}")
    lines.append(f"TP     : {signal.get('tp')}")
    lines.append(f"SL     : {signal.get('sl')}")
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


# Fungsi notifikasi startup/deploy

def send_startup_message(config: dict) -> None:
    import datetime
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Jakarta")
        now = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S WIB")
    except ImportError:
        # Fallback jika zoneinfo tidak tersedia
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    telegram_cfg = config.get("telegram", {})
    token = _get_token(telegram_cfg)
    chat_id = _get_chat_id(telegram_cfg)
    if not token or not chat_id:
        logger.warning("Telegram token/chat_id belum dikonfigurasi. Lewati pengiriman startup.")
        return
    message = f"✅ Bot IDX Alpha Trader sudah aktif (deploy/restart) — {now}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        response.raise_for_status()
        logger.info("Pesan startup terkirim ke Telegram.")
    except requests.RequestException as exc:
        logger.error("Gagal mengirim pesan startup Telegram: %s", exc)
