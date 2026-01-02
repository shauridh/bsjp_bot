"""Entry point trading bot."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from strategies.ma_crossover import ma_crossover
from strategies.rsi import rsi
from strategies.support_resist import support_resist
from strategies.volume_spike import volume_spike
from utils.chart import generate_chart
from utils.fetch_data import fetch_data
from utils.gsheets import log_signal
from utils.telegram import send_signal
from utils.watchlist import generate_watchlist

load_dotenv()

logging.basicConfig(
	level=os.getenv("LOG_LEVEL", "INFO"),
	format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("trade-bot")


def load_config() -> dict:
	config_path = Path(__file__).with_name("config.yaml")
	with config_path.open("r", encoding="utf-8") as handle:
		return yaml.safe_load(handle) or {}


def run_strategies(symbol: str, config: dict) -> list[dict]:
	data = fetch_data(symbol, config)
	if not data:
		logger.warning("Tidak ada data untuk %s, melewati strategi.", symbol)
		return []

	signals = []
	for strategy in config.get("strategies", []):
		if strategy == "ma_crossover":
			signal = ma_crossover(data, config)
		elif strategy == "rsi":
			signal = rsi(data, config)
		elif strategy == "support_resist":
			signal = support_resist(data, config)
		elif strategy == "volume_spike":
			signal = volume_spike(data, config)
		else:
			logger.debug("Strategi %s tidak dikenali", strategy)
			signal = None
		if signal:
			signals.append(signal)
	return signals


def process_signals(signals: list[dict], symbol: str, config: dict) -> None:
	for signal in signals:
		chart_path = generate_chart(signal.get("data", {}), symbol, config)
		if chart_path:
			signal = {**signal, "chart_path": chart_path}
		log_signal(signal, config)
		send_signal(signal, config)


def job() -> None:
	config = load_config()
	watchlist = generate_watchlist(config)
	logger.info("Menjalankan job untuk %s simbol", len(watchlist))
	for symbol in watchlist:
		try:
			signals = run_strategies(symbol, config)
			if signals:
				process_signals(signals, symbol, config)
		except Exception as exc:  # noqa: BLE001
			logger.exception("Gagal memproses %s: %s", symbol, exc)


if __name__ == "__main__":
	scheduler = BackgroundScheduler()
	interval = load_config().get("scheduler", {}).get("interval_minutes", 15)
	scheduler.add_job(job, "interval", minutes=interval, max_instances=1, coalesce=True)
	scheduler.start()
	logger.info("Trading bot started. Press Ctrl+C to exit.")
	try:
		while True:
			time.sleep(60)
	except (KeyboardInterrupt, SystemExit):
		scheduler.shutdown()
		logger.info("Scheduler dimatikan.")
