import requests
import json
from datetime import datetime
from typing import List, Dict

class SimpleBSJPScreener:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.goapi.io/stock/idx"
        self.headers = {"X-API-KEY": api_key}
    
    def get_ihsg_stocks(self) -> List[str]:
        """Ambil daftar saham IHSG"""
        try:
            url = f"{self.base_url}"
            params = {"type": "index_components", "index_code": "IHSG"}
            
            response = requests.get(url, headers=self.headers, params=params)
            data = response.json()
            
            stocks = [stock['ticker'] for stock in data.get('data', [])]
            return stocks[:30]  # Ambil 30 saham pertama saja
            
        except Exception as e:
            print(f"Error getting stocks: {e}")
            # Fallback ke saham liquid
            return ['BBCA', 'BBRI', 'TLKM', 'ASII', 'UNVR', 'ICBP', 'BMRI']
    
    def get_stock_data(self, symbol: str) -> Dict:
        """Ambil data saham dari GoAPI"""
        try:
            url = f"{self.base_url}/{symbol}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return response.json().get('data', {})
            return {}
            
        except Exception as e:
            print(f"Error getting {symbol}: {e}")
            return {}
    
    def check_bsjp_criteria(self, stock_data: Dict) -> bool:
        """Cek apakah saham memenuhi kriteria BSJP dari PDF"""
        
        # Data required
        price = stock_data.get('last_price', 0)
        volume = stock_data.get('volume', 0)
        value = price * volume
        
        # 1. Price > 50
        if price < 50:
            return False
        
        # 2. Volume change (simplified)
        # Karena API mungkin tidak memberikan volume kemarin,
        # kita skip dulu atau cari cara lain
        # Untuk sini, kita anggap volume cukup besar
        if volume < 1000000:  # Minimal 1 juta lembar
            return False
        
        # 3. Transaction value > 5M
        if value < 5000000000:
            return False
        
        # 4. Near 52-week high > 70%
        high_52w = stock_data.get('high_52w', price * 2)
        low_52w = stock_data.get('low_52w', price / 2)
        
        if high_52w != low_52w:
            near_ratio = (price - low_52w) / (high_52w - low_52w)
            if near_ratio < 0.7:
                return False
        
        # 5. Price change today positive
        change = stock_data.get('change_percent', 0)
        if change <= 0:
            return False
        
        # 6. Volume decent (lagi)
        avg_volume = stock_data.get('avg_volume', volume)
        if volume < avg_volume * 1.2:  # Minimal 20% di atas rata-rata
            return False
        
        return True
    
    def calculate_tp_sl(self, price: float) -> tuple:
        """Hitung Target Price dan Stop Loss sederhana"""
        # TP: +2%, SL: -1.25%
        tp = price * 1.02
        sl = price * 0.9875
        
        return tp, sl
    
    def screen_all_stocks(self) -> List[Dict]:
        """Screening semua saham IHSG"""
        print("🔍 Memulai screening BSJP...")
        
        stocks = self.get_ihsg_stocks()
        signals = []
        
        for symbol in stocks:
            try:
                data = self.get_stock_data(symbol)
                if not data:
                    continue
                
                if self.check_bsjp_criteria(data):
                    price = data.get('last_price', 0)
                    tp, sl = self.calculate_tp_sl(price)
                    
                    signal = {
                        'symbol': symbol,
                        'price': price,
                        'change': data.get('change_percent', 0),
                        'volume': data.get('volume', 0),
                        'value': price * data.get('volume', 0),
                        'tp': tp,
                        'sl': sl,
                        'tp_pct': 2.0,
                        'sl_pct': 1.25
                    }
                    
                    signals.append(signal)
                    print(f"✅ {symbol}: Rp {price:,.0f}")
                    
            except Exception as e:
                print(f"❌ Error processing {symbol}: {e}")
                continue
        
        # Urutkan berdasarkan volume terbesar
        signals.sort(key=lambda x: x['volume'], reverse=True)
        
        print(f"📊 Screening selesai. Ditemukan {len(signals)} sinyal.")
        return signals[:5]  # Ambil 5 terbaik saja
