# Trade Bot Scheduler

Bot trading modular berbahasa Python yang menjadwalkan pengambilan data pasar, menjalankan beberapa strategi (MA crossover, RSI, Support/Resistance, Volume Spike), dan mengirim pemberitahuan ke Telegram sambil mencatat log ke Google Sheets.

## Fitur Utama
- Watchlist dinamis via gaya trading atau daftar manual.
- Integrasi data harga melalui yfinance dan GoAPI dengan cache & fallback mock.
- Strategi teknikal modular dengan konfigurasi di `config.yaml`.
- Notifikasi Telegram + pencatatan CSV/Google Sheets + lampiran chart PNG.
- Siap dijalankan terus-menerus (APScheduler) atau dijalankan sekali untuk pengujian.
- Artefak deployment: `.env.example`, `Dockerfile`, dan panduan Coolify.

## Prasyarat Lokal
- Python 3.10+ (disarankan 3.11).
- Pip + virtual environment (opsional namun direkomendasikan).
- `git`, `make`, atau tooling lain bersifat opsional.

## Setup
1. Salin file contoh env:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Isi variabel rahasia di `.env` (lihat daftar di bawah).
3. Pasang ketergantungan:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. Jalankan bot:
   ```powershell
   python main.py
   ```

## Variabel Lingkungan
| Variabel | Deskripsi |
| --- | --- |
| `LOG_LEVEL` | Level logging Python (`INFO`, `DEBUG`, dst). |
| `MOCK_DATA` | `true` untuk memakai data dummy (berguna saat pengujian/offline). |
| `TELEGRAM_TOKEN` / `TELEGRAM_BOT_TOKEN` | Token Bot Telegram. Salah satu cukup. |
| `TELEGRAM_CHAT_ID` / `TELEGRAM_CHANNEL_ID` | ID chat/channel tujuan. |
| `GOAPI_TOKEN` | API key GoAPI IDX. |
| `GOAPI_BASE_URL` | Opsional, override base URL GoAPI. |
| `GSHEETS_SPREADSHEET_ID` | Spreadsheet target untuk logging sinyal. |
| `GSHEETS_CREDENTIALS_FILE` | Path file JSON service-account. |
| `GSHEETS_CREDENTIALS_JSON` | Alternatif langsung dalam bentuk JSON satu baris. |

> Rahasiakan `.env` Anda dan jangan commit ke repo publik.

## Konfigurasi Strategi & Watchlist
- Semua parameter dapat diedit di [`config.yaml`](config.yaml).
- Atur gaya watchlist (`watchlist.style`) atau masukkan simbol manual.
- Parameter strategi berada di `strategy_params`.

## Pengujian Cepat
Jalankan satu siklus tanpa scheduler dengan data mock:
```powershell
$env:MOCK_DATA = "true"
python -c "import main; main.job()"
Remove-Item Env:MOCK_DATA
```
Scheduler utama akan tetap berjalan normal dengan `python main.py`.

## Deploy ke Coolify
1. Buat aplikasi tipe **Python** atau **Dockerfile**.
2. Tambah repo ini dan pilih cabang yang sesuai.
3. Pada tab **Environment Variables**, isi seluruh variabel dari `.env.example`.
4. Jika memakai Dockerfile (disarankan), pastikan Coolify menjalankan perintah default `python main.py`.
5. Aktifkan opsi "Always On" agar APScheduler tetap hidup. Gunakan monitor log Coolify untuk memastikan job berjalan setiap interval.

### Volume & Persistent Data
- Direktori `data/` menyimpan `signal_log.csv` dan `charts/`. Jika ingin menyimpannya lintas deploy, pasang volume pada path tersebut.

## Operasional
- Log ringkas tersedia di stdout; gunakan `LOG_LEVEL=DEBUG` untuk investigasi lebih detail.
- Chart PNG disimpan di `data/charts`. Kirim secara manual melalui Telegram bila diperlukan.
- Google Sheets bersifat best-effort: jika kredensial kosong, bot hanya menulis CSV lokal.

## Troubleshooting
- Set `MOCK_DATA=true` jika jaringan GoAPI/yfinance bermasalah selama debugging.
- Gunakan `pip list --outdated` secara berkala untuk memperbarui dependensi.
- Pastikan jam server sinkron agar jadwal tidak meleset.
