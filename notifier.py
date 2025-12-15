import requests
from typing import List, Dict
from datetime import datetime

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, text: str) -> bool:
        """Kirim pesan ke Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload)
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ Error sending Telegram: {e}")
            return False
    
    def format_signal_message(self, signals: List[Dict]) -> str:
        """Format sinyal untuk Telegram"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if not signals:
            return f"""
📊 <b>BSJP SCREENING - {now}</b>

❌ <i>Tidak ditemukan saham yang memenuhi kriteria hari ini.</i>

Coba lagi besok atau sesuaikan kriteria screening.
"""
        
        message = f"""
📊 <b>BSJP SCREENING - {now}</b>
⏰ Screening time: 14:50 WIB
🎯 Target: Jual besok pagi (09:00-09:15)

<b>📈 SIGNAL BELI ({len(signals)}):</b>
"""
        
        for i, sig in enumerate(signals, 1):
            message += f"""
{i}. <b>{sig['symbol']}</b>
   💰 Harga: Rp {sig['price']:,.0f}
   📈 Change: {sig['change']:+.2f}%
   📊 Volume: {sig['volume']:,.0f}
   🎯 TP: Rp {sig['tp']:,.0f} (+{sig['tp_pct']:.1f}%)
   🛑 SL: Rp {sig['sl']:,.0f} (-{sig['sl_pct']:.1f}%)
"""
        
        message += """

<b>⚠️ CATATAN:</b>
• Beli sebelum tutup (14:55-15:00)
• Jual besok pagi (09:00-09:15)
• Max 3 saham per hari
• Gunakan cut loss ketat

<i>Selamat trading! 🚀</i>
"""
        
        return message
    
    def send_signals(self, signals: List[Dict]) -> bool:
        """Kirim sinyal ke Telegram"""
        message = self.format_signal_message(signals)
        return self.send_message(message)
    
    def send_test_message(self):
        """Kirim test message"""
        test_msg = "🤖 <b>BSJP Bot Test</b>\n\nBot berjalan dengan baik!"
        return self.send_message(test_msg)
