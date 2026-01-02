---
goal: Trade Bot Automation v1 Implementation Plan
version: 1.0
date_created: 2026-01-02
last_updated: 2026-01-02
owner: trade-bot-team
status: 'Planned'
tags: [feature, trading, automation]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Rencana ini menjabarkan langkah terstruktur untuk membangun aplikasi trade bot Python yang menganalisis watchlist otomatis, menjalankan strategi teknikal multi-lapisan, dan mengirim sinyal entry/TP/SL ke Telegram serta Google Sheets untuk pencatatan lalu dideploy di Coolify.

## 1. Requirements & Constraints

- **REQ-001**: Sistem harus menghasilkan sinyal entry, take profit, dan stop loss untuk setiap simbol dalam watchlist.
- **REQ-002**: Data harga harus berasal dari kombinasi yfinance (historikal) dan goapi (real-time Indonesia) dengan fallback otomatis.
- **REQ-003**: Minimum empat strategi teknikal (MA crossover, RSI, support/resistance, volume spike) dapat dikonfigurasi on/off melalui `config.yaml`.
- **REQ-004**: Setiap sinyal valid harus dikirim ke Telegram bot serta disimpan ke Google Sheets dan CSV lokal.
- **REQ-005**: Watchlist harus dibuat otomatis berdasarkan parameter gaya trading (BSJP, BPJS, Swing) dan berjalan terjadwal.
- **SEC-001**: Semua token/API key harus dimuat dari environment variable atau secrets Coolify, bukan hardcode di repo.
- **CON-001**: goapi memiliki batas 30 request per hari sehingga butuh batching, caching, dan prioritisasi simbol.
- **CON-002**: Target runtime Python >=3.10 dan siap dijalankan sebagai container di Coolify.
- **GUD-001**: Struktur project modular (`main.py`, `strategies/`, `utils/`, `data/`) agar mudah diekstensi.
- **PAT-001**: Ikuti pola pipeline fetch -> analyze -> signal -> notify/log dengan pemisahan lapisan jelas.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Menyusun kerangka proyek, konfigurasi, dan dependensi dasar.

| Task     | Description                                                                                                                                              | Completed | Date |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-001 | Buat struktur folder `trade-bot/` lengkap dengan `main.py`, `strategies/`, `utils/`, `data/`, contoh konfigurasi, dan placeholder modul sesuai rancangan. |           |      |
| TASK-002 | Definisikan `requirements.txt` dengan paket: yfinance, requests, python-telegram-bot, PyYAML, pandas, matplotlib, gspread, oauth2client, APScheduler.     |           |      |
| TASK-003 | Bangun `config.yaml` berisi kredensial placeholder, opsi strategi, pengaturan watchlist BSJP/BPJS/Swing, jadwal pemindaian, serta jalur logging lokal.    |           |      |

### Implementation Phase 2

- GOAL-002: Mengimplementasikan modul data dan strategi.

| Task     | Description                                                                                                                                 | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-004 | Kembangkan `utils/fetch_data.py` untuk mengambil data yfinance & goapi dengan caching, batching, dan fallback jika limit tercapai.           |           |      |
| TASK-005 | Implementasikan antarmuka strategi dasar dan modul `strategies/ma_crossover.py`, `rsi.py`, `support_resist.py`, `volume_spike.py`.           |           |      |
| TASK-006 | Tambahkan modul watchlist & screening (misal `utils/watchlist.py`) untuk men-generate simbol berdasarkan gaya trading plus filter likuiditas. |           |      |

### Implementation Phase 3

- GOAL-003: Integrasi notifikasi, logging, orkestrasi, dan deployment hooks.

| Task     | Description                                                                                                                                              | Completed | Date |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-007 | Implementasikan `utils/telegram.py` untuk format pesan template dan dukungan lampiran chart.                                                             |           |      |
| TASK-008 | Bangun `utils/gsheets.py` serta mekanisme logging CSV (`data/signal_log.csv`) dengan retry dan penanganan error kuota.                                    |           |      |
| TASK-009 | Lengkapi `main.py` dengan pipeline fetch->analysis->decision->notify, scheduler APScheduler/Cron, error handling, dan integrasi environment Coolify.     |           |      |
| TASK-010 | Siapkan skrip deployment (Dockerfile/Coolify config) plus dokumentasi README agar siap push & deploy otomatis.                                           |           |      |

## 3. Alternatives

- **ALT-001**: Mengembangkan aplikasi web/PWA sejak awal. Ditolak karena memperpanjang timeline dan fokus saat ini pada otomasi backend.
- **ALT-002**: Mengandalkan layanan pihak ketiga seperti TradingView alert. Ditolak karena ketergantungan eksternal dan keterbatasan kustomisasi.

## 4. Dependencies

- **DEP-001**: API yfinance untuk data historis global.
- **DEP-002**: API goapi dengan kunci untuk data real-time IDX (limit 30 request/hari).
- **DEP-003**: Telegram Bot API token & chat_id target.
- **DEP-004**: Google Sheets service account JSON untuk akses sheet logging.
- **DEP-005**: Coolify environment guna menyimpan secrets dan menjalankan container Python.

## 5. Files

- **FILE-001**: `trade-bot/main.py` - orkestrator utama pipeline.
- **FILE-002**: `trade-bot/config.yaml` - konfigurasi strategi, kredensial, jadwal.
- **FILE-003**: `trade-bot/strategies/*.py` - modul strategi individual.
- **FILE-004**: `trade-bot/utils/*.py` - utilitas (fetch data, telegram, charts, gsheets, watchlist).
- **FILE-005**: `trade-bot/data/signal_log.csv` - arsip sinyal lokal.

## 6. Testing

- **TEST-001**: Unit test strategi (MA/RSI/support/resist/volume) dengan data sintetis untuk memastikan sinyal konsisten.
- **TEST-002**: Integration test pipeline fetch->analysis->notify menggunakan dummy API/stub guna memastikan fallback berjalan.
- **TEST-003**: End-to-end dry run pada staging Coolify guna memastikan pesan Telegram & append Google Sheets berjalan tanpa rate limit.

## 7. Risks & Assumptions

- **RISK-001**: Limit API goapi tercapai sebelum jadwal selesai. Mitigasi: caching & penjadwalan ulang berdasar total simbol.
- **RISK-002**: Google Sheets quota atau autentikasi gagal. Mitigasi: retry exponential backoff dan logging lokal.
- **ASSUMPTION-001**: User menyediakan API key goapi, Telegram bot token, dan Google Sheets credential sebelum implementasi.
- **ASSUMPTION-002**: Lingkungan Coolify mendukung job terjadwal (cron) atau container APScheduler yang selalu aktif.

## 8. Related Specifications / Further Reading

- TBD - akan ditautkan jika tersedia dokumen desain tambahan atau panduan deployment Coolify spesifik.
