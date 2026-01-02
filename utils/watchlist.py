"""Utility untuk menghasilkan watchlist berdasarkan gaya trading."""

from __future__ import annotations

import logging
from typing import List, Sequence

logger = logging.getLogger(__name__)

DEFAULT_STYLES = {
    "BSJP": ["BBCA.JK", "BMRI.JK", "BBRI.JK", "ASII.JK", "TLKM.JK"],
    "BPJS": ["BBCA.JK", "BMRI.JK", "UNVR.JK", "ICBP.JK", "PGAS.JK"],
    "SWING": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "AMZN", "META"],
}


def _normalize_symbols(symbols: Sequence[str]) -> List[str]:
    return sorted({symbol.strip().upper() for symbol in symbols if symbol})


def generate_watchlist(config: dict) -> List[str]:
    watch_cfg = config.get("watchlist", {})
    manual = watch_cfg.get("manual") or []
    if manual:
        symbols = _normalize_symbols(manual)
    else:
        style = (watch_cfg.get("style") or "SWING").upper()
        combined_styles = {**DEFAULT_STYLES, **{k.upper(): v for k, v in watch_cfg.get("style_sets", {}).items()}}
        symbols = _normalize_symbols(combined_styles.get(style, []))
        if not symbols:
            logger.warning("Tidak ada simbol untuk gaya %s. Menggunakan SWING.", style)
            symbols = _normalize_symbols(combined_styles.get("SWING", DEFAULT_STYLES["SWING"]))

    limit = watch_cfg.get("limit")
    if isinstance(limit, int) and limit > 0:
        symbols = symbols[:limit]

    if not symbols:
        logger.error("Watchlist kosong. Tambahkan simbol manual atau definisikan style_sets.")
    return symbols
