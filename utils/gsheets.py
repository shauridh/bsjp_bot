"""Logging sinyal ke Google Sheets dan CSV lokal."""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

LOCAL_LOG = Path("data/signal_log.csv")


def _ensure_local_log(row: List[Any]) -> None:
    header = ["timestamp", "symbol", "entry", "tp", "sl", "strategy", "comment"]
    file_exists = LOCAL_LOG.exists()
    LOCAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOCAL_LOG.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if not file_exists:
            writer.writerow(header)
        writer.writerow(row)


def _get_credentials(config: dict) -> ServiceAccountCredentials | None:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    json_from_env = os.getenv("GSHEETS_CREDENTIALS_JSON")
    if json_from_env:
        data = json.loads(json_from_env)
        return ServiceAccountCredentials.from_json_keyfile_dict(data, scopes)

    creds_file = os.getenv("GSHEETS_CREDENTIALS_FILE") or config.get("gsheets", {}).get("credentials")
    if creds_file and Path(creds_file).exists():
        return ServiceAccountCredentials.from_json_keyfile_name(creds_file, scopes)
    logger.warning("File kredensial Google Sheets tidak ditemukan.")
    return None


@lru_cache(maxsize=1)
def _get_client(config: dict) -> gspread.Client | None:
    credentials = _get_credentials(config)
    if not credentials:
        return None
    return gspread.authorize(credentials)


def log_signal(signal: Dict[str, Any], config: dict) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    comment = signal.get("comment", "")
    row = [
        timestamp,
        signal.get("symbol"),
        signal.get("entry"),
        signal.get("tp"),
        signal.get("sl"),
        signal.get("strategy"),
        comment,
    ]

    _ensure_local_log(row)

    spreadsheet_id = os.getenv("GSHEETS_SPREADSHEET_ID") or config.get("gsheets", {}).get("spreadsheet_id")
    if not spreadsheet_id:
        logger.info("Spreadsheet ID tidak di-set. Lewati append Google Sheets.")
        return

    client = _get_client(config)
    if not client:
        return

    try:
        sheet = client.open_by_key(spreadsheet_id).sheet1
        sheet.append_row(row, value_input_option="USER_ENTERED")
        logger.info("Sinyal %s tercatat di Google Sheets.", signal.get("symbol"))
    except Exception as exc:  # gspread lempar exception umum
        logger.error("Gagal append Google Sheets: %s", exc)
