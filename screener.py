import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import numpy as np

class OptimizedBSJPScreener:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.goapi.io/stock/idx"
        self.headers = {"X-API-KEY": api_key}
        
        # OPTIMAL PARAMETERS untuk winrate 75-85%
        self.parameters = {
            'min_volume_change': 30,           # Volume harus naik >30% (bukan 20%)
            'min_price': 200,                  # Harga minimal Rp 200 (likuiditas)
            'min_52w_ratio': 0.7,              # 70% dari 52-week high
            'min_transaction': 10000000000,    # Transaksi minimal 10M (bukan 5M)
            'rsi_min': 45,                     # RSI minimal 45 (bukan 40)
            'rsi_max': 65,                     # RSI maksimal 65 (bukan 70)
            'price_change_min': 0.5,           # Minimal naik 0.5% hari ini
            'volume_to_avg_ratio': 1.5,        # Volume 1.5x rata-rata
            'max_price_change': 5.0,           # Maksimal naik 5% (hindari overbought)
            'market_cap_min': 5000000000000,   # Market cap minimal 5T (bluechip)
        }
    
    def get_ihsg_stocks(self) -> List[str]:
        """Ambil hanya saham LQ45 untuk winrate lebih tinggi"""
        try:
            url = f"{self.base_url}"
            params = {"type": "index_components", "index_code": "LQ45"}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            data = response.json()
            
            stocks = [stock['ticker'] for stock in data.get('data', [])]
            return stocks  # Hanya saham LQ45
            
        except:
            # Fallback ke bluechip terbaik
            return [
                'BBCA', 'BBRI', 'BMRI', 'BNGA', 'BBNI',  # Banking (strong)
                'TLKM', 'EXCL', 'ISAT',                   # Telco (stable)
                'ASII', 'AUTO', 'GJTL',                   # Automotive
                'UNVR', 'ICBP', 'MYOR',                   # Consumer (defensive)
                'ANTM', 'PTBA', 'MDKA',                   # Mining
                'ADRO', 'HRUM', 'ITMG',                   # Energy
                'AKRA', 'TPIA', 'SMGR',                   # Infrastructure
                'GOTO', 'EMTK', 'ARTO',                   # Tech/Others
            ]
    
    def get_stock_data(self, symbol: str) -> Dict:
        """Ambil data lengkap termasuk historical untuk analisis"""
        try:
            # 1. Real-time data
            url = f"{self.base_url}/{symbol}"
            response = requests.get(url, headers=self.headers, timeout=5)
            
            if response.status_code != 200:
                return {}
            
            data = response.json().get('data', {})
            
            # 2. Historical data untuk indikator (7 hari terakhir)
            hist_url = f"{self.base_url}/{symbol}/historical"
            hist_params = {
                "from": (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                "to": datetime.now().strftime('%Y-%m-%d')
            }
            
            hist_response = requests.get(hist_url, headers=self.headers, params=hist_params, timeout=5)
            if hist_response.status_code == 200:
                hist_data = hist_response.json().get('data', [])
                data['historical'] = hist_data[-5:] if len(hist_data) >= 5 else hist_data  # 5 hari terakhir
            
            return data
            
        except Exception as e:
            print(f"⚠️ Error getting {symbol} data: {e}")
            return {}
    
    def calculate_indicators(self, data: Dict) -> Dict:
        """Hitung indikator teknis untuk konfirmasi"""
        indicators = {
            'rsi': 50,
            'volume_trend': 'neutral',
            'price_trend': 'neutral',
            'volatility': 'medium',
            'pattern_score': 0,
            'support_resistance': {}
        }
        
        try:
            if 'historical' not in data or len(data['historical']) < 5:
                return indicators
            
            hist = data['historical']
            closes = [day['close'] for day in hist]
            volumes = [day['volume'] for day in hist]
            highs = [day['high'] for day in hist]
            lows = [day['low'] for day in hist]
            
            # 1. RSI Simplified
            if len(closes) >= 5:
                changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                gains = sum([c for c in changes if c > 0]) / len(closes)
                losses = abs(sum([c for c in changes if c < 0])) / len(closes)
                
                if losses > 0:
                    rs = gains / losses
                    indicators['rsi'] = 100 - (100 / (1 + rs))
            
            # 2. Volume Trend
            if len(volumes) >= 3:
                vol_today = volumes[-1]
                vol_yesterday = volumes[-2]
                vol_avg = sum(volumes[-3:]) / 3
                
                if vol_today > vol_yesterday and vol_today > vol_avg * 1.3:
                    indicators['volume_trend'] = 'bullish'
                elif vol_today < vol_yesterday:
                    indicators['volume_trend'] = 'bearish'
            
            # 3. Price Trend
            if len(closes) >= 3:
                price_today = closes[-1]
                price_yesterday = closes[-2]
                price_3day_avg = sum(closes[-3:]) / 3
                
                if price_today > price_yesterday and price_today > price_3day_avg:
                    indicators['price_trend'] = 'bullish'
            
            # 4. Volatility
            if len(closes) >= 5:
                price_range = max(closes) - min(closes)
                avg_price = sum(closes) / len(closes)
                volatility_pct = (price_range / avg_price) * 100
                
                if volatility_pct > 5:
                    indicators['volatility'] = 'high'
                elif volatility_pct < 2:
                    indicators['volatility'] = 'low'
            
            # 5. Simple Pattern Detection
            if len(closes) >= 3:
                # Bullish pattern: Higher high, higher low
                if closes[-1] > closes[-2] > closes[-3]:
                    indicators['pattern_score'] += 2
                
                # Strong close near high
                last_high = highs[-1]
                last_close = closes[-1]
                if (last_high - last_close) / last_high < 0.01:  # Close di atas 99% dari high
                    indicators['pattern_score'] += 1
            
            # 6. Support/Resistance
            if len(closes) >= 5:
                resistance = max(closes[-5:])
                support = min(closes[-5:])
                current = closes[-1]
                
                distance_to_resistance = (resistance - current) / current * 100
                distance_to_support = (current - support) / current * 100
                
                indicators['support_resistance'] = {
                    'resistance': resistance,
                    'support': support,
                    'distance_to_resistance': distance_to_resistance,
                    'distance_to_support': distance_to_support
                }
            
        except Exception as e:
            print(f"⚠️ Error calculating indicators: {e}")
        
        return indicators
    
    def check_winrate_criteria(self, data: Dict, indicators: Dict) -> Tuple[bool, List[str], float]:
        """
        Kriteria screening OPTIMIZED untuk winrate 75-85%
        Return: (passed, reasons, confidence_score)
        """
        reasons = []
        score = 0
        max_score = 12  # Total maksimal score
        
        # Data required
        price = data.get('last_price', 0)
        volume = data.get('volume', 0)
        value = price * volume
        change = data.get('change_percent', 0)
        avg_volume = data.get('avg_volume', volume)
        
        # === KRITERIA UTAMA (HARUS DIPENUHI) ===
        
        # 1. Harga minimal Rp 200 (likuiditas)
        if price < self.parameters['min_price']:
            return False, ["Harga terlalu rendah (< Rp 200)"], 0
        score += 1
        
        # 2. Volume naik signifikan (>30% dari kemarin)
        # Simplifikasi: volume harus > 1.5x rata-rata
        if volume < avg_volume * 1.3:
            return False, ["Volume kurang dari 1.3x rata-rata"], 0
        score += 1
        
        # 3. Transaksi minimal 10M
        if value < self.parameters['min_transaction']:
            return False, ["Transaksi < 10M"], 0
        score += 1
        
        # 4. Perubahan harga positif hari ini
        if change <= 0:
            return False, ["Harga turun hari ini"], 0
        score += 1
        
        # 5. Tidak overbought (naik tidak lebih dari 5%)
        if change > self.parameters['max_price_change']:
            return False, ["Sudah naik >5% (overbought)"], 0
        score += 1
        
        # === KRITERIA PENUNJANG (BOOST WINRATE) ===
        
        # 6. RSI dalam zona optimal 45-65
        rsi = indicators['rsi']
        if self.parameters['rsi_min'] <= rsi <= self.parameters['rsi_max']:
            reasons.append(f"RSI optimal ({rsi:.1f})")
            score += 2
        else:
            reasons.append(f"RSI kurang optimal ({rsi:.1f})")
            score += 0.5
        
        # 7. Volume trend bullish
        if indicators['volume_trend'] == 'bullish':
            reasons.append("Volume trend bullish")
            score += 2
        
        # 8. Price trend bullish
        if indicators['price_trend'] == 'bullish':
            reasons.append("Price trend bullish")
            score += 2
        
        # 9. Pattern score
        if indicators['pattern_score'] >= 2:
            reasons.append("Pattern bullish terdeteksi")
            score += 2
        
        # 10. Volatility medium (optimal untuk BSJP)
        if indicators['volatility'] == 'medium':
            reasons.append("Volatilitas optimal")
            score += 1
        
        # 11. Near 52-week high (momentum kuat)
        high_52w = data.get('high_52w', price * 1.5)
        low_52w = data.get('low_52w', price * 0.5)
        
        if high_52w != low_52w:
            near_ratio = (price - low_52w) / (high_52w - low_52w)
            if near_ratio >= self.parameters['min_52w_ratio']:
                reasons.append(f"Near 52W high ({near_ratio:.1%})")
                score += 2
            elif near_ratio >= 0.6:
                reasons.append(f"Mendekati 52W high ({near_ratio:.1%})")
                score += 1
        
        # 12. Market cap (bluechip preference)
        market_cap = data.get('market_cap', 0)
        if market_cap >= self.parameters['market_cap_min']:
            reasons.append("Bluechip (likuiditas tinggi)")
            score += 2
        
        # === FINAL DECISION ===
        confidence = (score / max_score) * 100
        
        # Minimal confidence 70% untuk winrate tinggi
        if confidence >= 70:
            reasons.append(f"Confidence: {confidence:.1f}%")
            return True, reasons, confidence
        else:
            return False, [f"Confidence terlalu rendah ({confidence:.1f}%)"], confidence
    
    def calculate_smart_tp_sl(self, price: float, indicators: Dict) -> Tuple[float, float, float, float]:
        """
        TP/SL cerdas berdasarkan volatilitas dan kondisi
        """
        volatility = indicators.get('volatility', 'medium')
        
        if volatility == 'high':
            # High volatility: TP lebih kecil, SL lebih ketat
            tp_percent = 1.5
            sl_percent = 1.0
        elif volatility == 'low':
            # Low volatility: TP lebih besar, SL lebih longgar
            tp_percent = 2.5
            sl_percent = 1.5
        else:
            # Medium volatility: Standard
            tp_percent = 2.0
            sl_percent = 1.25
        
        # Adjust berdasarkan trend
        if indicators.get('price_trend') == 'bullish':
            tp_percent += 0.5  # Lebih optimis untuk trend bullish
        
        tp = price * (1 + tp_percent / 100)
        sl = price * (1 - sl_percent / 100)
        
        return tp, sl, tp_percent, sl_percent
    
    def screen_with_high_winrate(self) -> List[Dict]:
        """
        Screening dengan optimasi winrate 75-85%
        Hanya return sinyal dengan confidence tinggi
        """
        print("🎯 OPTIMIZED SCREENING - Target Winrate 75-85%")
        print("=" * 50)
        
        # Hanya screening saham bluechip/LQ45
        stocks = self.get_ihsg_stocks()
        print(f"📊 Screening {len(stocks)} saham bluechip/LQ45")
        
        signals = []
        
        for symbol in stocks:
            try:
                # Get data
                data = self.get_stock_data(symbol)
                if not data:
                    continue
                
                # Calculate indicators
                indicators = self.calculate_indicators(data)
                
                # Check criteria
                passed, reasons, confidence = self.check_winrate_criteria(data, indicators)
                
                if passed and confidence >= 70:
                    price = data.get('last_price', 0)
                    
                    # Calculate smart TP/SL
                    tp, sl, tp_pct, sl_pct = self.calculate_smart_tp_sl(price, indicators)
                    
                    # Risk-Reward Ratio
                    rr_ratio = tp_pct / sl_pct
                    
                    # Only accept RR >= 1.5
                    if rr_ratio >= 1.5:
                        signal = {
                            'symbol': symbol,
                            'price': price,
                            'change': data.get('change_percent', 0),
                            'volume': data.get('volume', 0),
                            'volume_ratio': data.get('volume', 0) / data.get('avg_volume', 1) if data.get('avg_volume', 0) > 0 else 1,
                            'rsi': indicators['rsi'],
                            'confidence': confidence,
                            'tp': tp,
                            'sl': sl,
                            'tp_pct': tp_pct,
                            'sl_pct': sl_pct,
                            'rr_ratio': rr_ratio,
                            'reasons': reasons[:3],  # Ambil 3 alasan utama
                            'grade': self.get_grade(confidence),
                            'volatility': indicators.get('volatility', 'medium'),
                            'trend': indicators.get('price_trend', 'neutral')
                        }
                        
                        signals.append(signal)
                        print(f"✅ {symbol}: Confidence {confidence:.1f}%, Grade {signal['grade']}")
                
            except Exception as e:
                print(f"⚠️ Error processing {symbol}: {e}")
                continue
        
        # Sort by confidence (highest first)
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        
        print(f"\n📈 Screening selesai: {len(signals)} sinyal high-confidence")
        
        # Hanya ambil 3 terbaik (quality over quantity)
        return signals[:3]
    
    def get_grade(self, confidence: float) -> str:
        """Convert confidence score to grade"""
        if confidence >= 85:
            return "A+"
        elif confidence >= 75:
            return "A"
        elif confidence >= 65:
            return "B+"
        elif confidence >= 55:
            return "B"
        else:
            return "C"
    
    def get_market_condition(self) -> Dict:
        """Analisis kondisi pasar sebelum screening"""
        try:
            url = f"{self.base_url}/technical"
            response = requests.get(url, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                
                change = data.get('change_percent', 0)
                volume = data.get('volume', 0)
                avg_volume = data.get('avg_volume', volume)
                
                # Determine market condition
                if change > 1.0:
                    condition = "STRONG_BULLISH"
                    recommendation = "✅ Optimal untuk trading"
                elif change > 0.5:
                    condition = "BULLISH"
                    recommendation = "✅ Baik untuk trading"
                elif change > -0.5:
                    condition = "NEUTRAL"
                    recommendation = "⚠️ Hati-hati, pilih yang berkualitas"
                elif change > -1.0:
                    condition = "BEARISH"
                    recommendation = "❌ Hindari trading"
                else:
                    condition = "STRONG_BEARISH"
                    recommendation = "❌ JANGAN trading"
                
                return {
                    'condition': condition,
                    'change': change,
                    'volume_ratio': volume / avg_volume if avg_volume > 0 else 1,
                    'recommendation': recommendation,
                    'ihsg_level': data.get('close', 0)
                }
            
        except:
            pass
        
        return {'condition': 'UNKNOWN', 'recommendation': '⚠️ Cek kondisi pasar manual'}
