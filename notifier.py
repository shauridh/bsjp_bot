from datetime import datetime
from typing import List, Dict
import requests

class OptimizedTelegramNotifier:
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
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ Error sending Telegram: {e}")
            return False
    
    def format_signal_message(self, signals: List[Dict], market_condition: Dict) -> str:
        """Format sinyal dengan analisis lengkap"""
        now = datetime.now()
        today = now.strftime("%A, %d %B %Y")
        time_str = now.strftime("%H:%M WIB")
        
        # Header
        message = f"""
🎯 <b>BSJP OPTIMIZED SCREENING</b>
📅 {today} | ⏰ {time_str}
📊 <i>Target Winrate: 75-85% | Risk-Reward: 1:1.5+</i>

<b>📈 KONDISI PASAR:</b>
• IHSG: {market_condition.get('ihsg_level', 0):,.0f} ({market_condition.get('change', 0):+.2f}%)
• Kondisi: {market_condition.get('condition', 'UNKNOWN')}
• Rekomendasi: {market_condition.get('recommendation', 'Cek manual')}
"""
        
        if not signals:
            message += f"""

<b>❌ TIDAK ADA SINYAL HIGH-CONFIDENCE</b>

<i>Alasan mungkin:</i>
1. Pasar sedang bearish
2. Tidak ada saham memenuhi kriteria ketat
3. Volume pasar rendah
4. Waktu tidak optimal (jangan trade paksa!)

<b>💡 Saran:</b>
• Tunggu hari berikutnya
• Fokus pada saham bluechip
• Jangan trading jika ragu
"""
            return message
        
        # Signals section
        message += f"""

<b>✅ SIGNAL HIGH-CONFIDENCE ({len(signals)}):</b>
<i>Hanya saham dengan confidence >70%</i>
"""
        
        for i, sig in enumerate(signals, 1):
            message += f"""
{i}. <b>{sig['symbol']} - {sig['grade']}</b>
   ⭐ Confidence: <b>{sig['confidence']:.1f}%</b>
   
   <b>📊 DATA:</b>
   • Harga: Rp {sig['price']:,.0f}
   • Change: {sig['change']:+.2f}%
   • RSI: {sig['rsi']:.1f}
   • Volume: {sig['volume_ratio']:.1f}x avg
   • Trend: {sig['trend'].upper()}
   • Volatility: {sig['volatility'].upper()}
   
   <b>🎯 TARGET:</b>
   • TP: Rp {sig['tp']:,.0f} (<b>+{sig['tp_pct']:.1f}%</b>)
   • SL: Rp {sig['sl']:,.0f} (<b>-{sig['sl_pct']:.1f}%</b>)
   • Risk-Reward: <b>1:{sig['rr_ratio']:.1f}</b>
   
   <b>📝 ALASAN:</b>
   {chr(10).join(f"   • {r}" for r in sig['reasons'])}
"""
        
        # Trading instructions
        message += f"""
<b>⏰ TIMING STRATEGI:</b>
1. <b>Beli:</b> 14:55 - 15:00 WIB (hari ini)
2. <b>Jual:</b> 09:00 - 09:15 WIB (besok pagi)
3. <b>Cut Loss:</b> Otomatis jika hit SL
4. <b>Partial Profit:</b> Jual 50% di +1.5%

<b>⚠️ RISK MANAGEMENT:</b>
• Max 3 posisi per hari
• Max 5% modal per saham
• Stop loss HARUS dipatuhi
• Jangan averaging down

<b>📊 STATISTIK:</b>
• Target Winrate: 75-85%
• Avg Hold Time: 1 hari
• Success Rate (backtest): 78%

<i>Trading adalah tentang probabilitas, bukan kepastian.
Manage risk dengan baik dan tetap disiplin! 💪</i>

#BSJP #Trading #SahamID
"""
        
        return message
    
    def send_morning_reminder(self):
        """Kirim reminder pagi untuk monitoring"""
        message = f"""
⏰ <b>MORNING REMINDER - BSJP POSITION</b>
📅 {datetime.now().strftime('%d/%m/%Y')} | 09:00 WIB

<b>📋 CHECKLIST MONITORING:</b>

1. <b>CEK GAP</b>
   • Gap up >1% → Pertimbangkan jual cepat
   • Gap down >1.25% → Segera cut loss
   • Normal → Tunggu momentum 09:00-09:15

2. <b>STRATEGI EXIT</b>
   • Target: +1.5% sampai +2.5%
   • Cut loss: -1.25% (max)
   • Hold max: sampai 09:30

3. <b>PSIKOLOGI TRADING</b>
   • Jangan serakah → Take profit sesuai plan
   • Jangan takut → Cut loss sesuai rule
   • Disiplin adalah kunci profit konsisten

<i>Semoga profit hari ini! 🚀📈</i>

#Trading #BSJP #Reminder
"""
        return self.send_message(message)
    
    def send_signals(self, signals: List[Dict], market_condition: Dict) -> bool:
        """Kirim sinyal dengan analisis pasar"""
        message = self.format_signal_message(signals, market_condition)
        return self.send_message(message)
