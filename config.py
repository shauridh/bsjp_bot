import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
GOAPI_KEY = os.getenv("GOAPI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Screening Rules (dari PDF Anda)
MIN_VOLUME_CHANGE = 20  # Minimal 20%
MIN_PRICE = 50
MIN_52W_RATIO = 0.7  # 70% dari 52-week high
MIN_VALUE = 5000000000  # 5M
