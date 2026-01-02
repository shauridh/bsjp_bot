"""Membuat chart harga sederhana untuk lampiran sinyal."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger(__name__)


def generate_chart(data: Dict[str, Any], symbol: str, config: dict) -> str | None:
    history = data.get("history")
    if not history:
        logger.info("History kosong untuk %s. Chart tidak dibuat.", symbol)
        return None

    df = pd.DataFrame(history)
    if "timestamp" not in df or "close" not in df:
        logger.warning("History tidak memiliki kolom timestamp/close. Chart dilewati.")
        return None

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.sort_values("timestamp", inplace=True)

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(df["timestamp"], df["close"], color="#38BDF8", linewidth=1.4, label="Close")
    ax.fill_between(df["timestamp"], df["close"], color="#38BDF8", alpha=0.1)
    ax.set_title(f"{symbol} Close Price")
    ax.set_ylabel("Price")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left")

    charts_dir = Path(config.get("charts", {}).get("output_dir", "data/charts"))
    charts_dir.mkdir(parents=True, exist_ok=True)
    file_path = charts_dir / f"{symbol}_{datetime.now(timezone.utc):%Y%m%d%H%M%S}.png"

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(file_path, dpi=150)
    plt.close(fig)

    logger.info("Chart %s tersimpan di %s", symbol, file_path)
    return str(file_path)
