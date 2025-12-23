# BSJP Sniper Bot

Telegram bot untuk strategi "Buy Afternoon Sell Morning" pada pasar saham Indonesia.

## Fitur
- Scan saham dengan GoAPI (Top Gainer/Most Active)
- Filter saham sesuai kriteria BSJP
- Kirim sinyal dan laporan performa ke Telegram
- Database SQLite
- Scheduler otomatis (APScheduler)
- Docker-ready (Coolify compatible)

## Setup
1. Copy `.env.example` ke `.env` dan isi variabelnya
2. Install dependencies: `pip install -r requirements.txt`
3. Jalankan dengan: `python main.py`

## Deployment
- Build Docker image: `docker build -t bsjp-sniper-bot .`
- Jalankan container: `docker run --env-file .env bsjp-sniper-bot`
