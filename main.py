import os
import requests
import sys

# Ambil env vars
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print("--- MULAI DIAGNOSA ---")

# 1. Cek apakah Variable terbaca
if not TOKEN:
    print("❌ ERROR: Variable TELEGRAM_TOKEN tidak terbaca/kosong!")
else:
    # Tampilkan 5 huruf awal saja untuk verifikasi (keamanan)
    print(f"✅ Token terbaca: {TOKEN[:5]}... (panjang: {len(TOKEN)})")

if not CHAT_ID:
    print("❌ ERROR: Variable TELEGRAM_CHAT_ID tidak terbaca/kosong!")
else:
    print(f"✅ Chat ID terbaca: {CHAT_ID}")

# 2. Cek Koneksi ke Telegram
if TOKEN and CHAT_ID:
    print("\n--- MENCOBA KIRIM PESAN ---")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": "✅ <b>TEST DARI COOLIFY BERHASIL!</b>\nJika ini masuk, berarti bot Anda sehat.",
        "parse_mode": "HTML"
    }
    
    try:
        resp = requests.post(url, data=data, timeout=15)
        print(f"Status Code: {resp.status_code}")
        print(f"Response API: {resp.text}")
        
        if resp.status_code == 200:
            print("✅ SUKSES: Pesan terkirim! Cek HP Anda.")
        else:
            print("❌ GAGAL: Token/ID mungkin salah, atau bot di-block.")
    except Exception as e:
        print(f"❌ KONEKSI ERROR: {e}")
        print("Saran: Cek DNS server atau Firewall di VPS Anda.")

print("--- DIAGNOSA SELESAI ---")
# Biarkan script mati agar logs berhenti dan mudah dibaca
sys.exit()
