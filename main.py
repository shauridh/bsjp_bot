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



def job_bsjs(style: str) -> None:
	config = load_config()
	config = {**config, "watchlist": {**config.get("watchlist", {}), "style": style}}
	watchlist = generate_watchlist(config)
	logger.info(f"Menjalankan job {style} untuk {len(watchlist)} simbol")
	for symbol in watchlist:
		try:
			signals = run_strategies(symbol, config)
			if signals:
				process_signals(signals, symbol, config)
		except Exception as exc:
			logger.exception("Gagal memproses %s: %s", symbol, exc)


if __name__ == "__main__":

	from utils.telegram import send_startup_message, send_signal
	config = load_config()
	send_startup_message(config)

	# Kirim sinyal trading terbaru (BSJP/Swing) saat startup
	style = config.get("watchlist", {}).get("style", "BSJP")
	config["watchlist"]["style"] = style
	watchlist = generate_watchlist(config)
	if watchlist:
		symbol = watchlist[0]
		signals = run_strategies(symbol, config)
		if signals:
			# Kirim hanya sinyal pertama
			send_signal(signals[0], config)

	from zoneinfo import ZoneInfo
	scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Jakarta"))
	# BPJS: Beli Pagi Jual Sore (job pagi)
	scheduler.add_job(
		lambda: job_bsjs("BPJS"),
		"cron",
		day_of_week="mon-fri",
		hour=1,
		minute=0,
		max_instances=1,
		coalesce=True,
		timezone=ZoneInfo("Asia/Jakarta")
	)
	# BSJP: Beli Sore Jual Pagi (job sore)
	scheduler.add_job(
		lambda: job_bsjs("BSJP"),
		"cron",
		day_of_week="mon-fri",
		hour=8,
		minute=30,
		max_instances=1,
		coalesce=True,
		timezone=ZoneInfo("Asia/Jakarta")
	)
	scheduler.start()
	logger.info("Trading bot started. Press Ctrl+C to exit.")
	try:
		while True:
			time.sleep(60)
	except (KeyboardInterrupt, SystemExit):
		scheduler.shutdown()
		logger.info("Scheduler dimatikan.")
