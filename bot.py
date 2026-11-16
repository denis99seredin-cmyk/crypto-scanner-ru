import os
import sys
import html
import time
from datetime import datetime, timezone
import requests
from groq import Groq

# --- СЕКРЕТЫ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Модели по приоритету
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Нет доступов к Telegram")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        print(f"TG Status: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ TG Error: {response.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ TG Exception: {e}")
        return False

def get_profitable_market_data() -> str:
    """Сканер под маленький депозит: мелкие и средние монеты с сильным движением"""
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "metaAndAssetCtxs"}

    try:
        response = requests.post(url, json=payload, timeout=12)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or len(data) < 2:
            return "Ошибка: Неверный формат данных"

        universe = data[0].get("universe", [])
        ctxs = data[1]

        coins_data = []

        for i, asset in enumerate(universe):
            name = asset.get("name")
            ctx = ctx
