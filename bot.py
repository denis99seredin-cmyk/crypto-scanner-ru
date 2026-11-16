import os
import sys
import html
import time
from datetime import datetime, timezone
import requests
from groq import Groq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("No Telegram credentials")
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
            print(f"TG Error: {response.text}")
            return False
        return True
    except Exception as e:
        print(f"TG Exception: {e}")
        return False

def get_profitable_market_data() -> str:
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "metaAndAssetCtxs"}

    try:
        response = requests.post(url, json=payload, timeout=12)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list) or len(data) < 2:
            return "Bad data format"

        universe = data[0].get("universe", [])
        ctxs = data[1]
        coins_data = []

        for i, asset in enumerate(universe):
            name = asset.get("name")
            ctx = ctxs[i] if i < len(ctxs) else {}

            if name in ["USDC", "USDT", "DAI", "FDUSD", "USDE", "USD1"]:
                continue

            try:
                mark_px = float(ctx.get("markPx", 0))
                prev_day = float(ctx.get("prevDayPx", 0))
                vol_24h = float(ctx.get("dayNtlVlm", 0))
                funding = float(ctx.get("funding", 0))

                change_24h = 0.0
                if prev_day > 0:
                    change_24h = ((mark_px - prev_day) / prev_day) * 100

                if vol_24h > 15000:
                    coins_data.append({
                        "name": name,
                        "price": mark_px,
                        "change_24h": round(change_24h, 2),
                        "volume": vol_24h,
                        "funding": funding * 100,
                    })
            except (ValueError, TypeError):
                continue

        if not coins_data:
            return "No coins found"

        top_by_volume = sorted(coins_data, key=lambda x: x["volume"], reverse=True)[:4]
        top_movers = sorted(coins_data, key=lambda x: abs(x["change_24h"]), reverse=True)[:7]
        strong_movers = [c for c in coins_data if abs(c["change_24h"]) >= 8]
        strong_movers = sorted(strong_movers, key=lambda x: abs(x["change_24h"]), reverse=True)[:5]

        unique_coins = {}
        for c in top_by_volume + top_movers + strong_movers:
            unique_coins[c["name"]] = c

        sorted_coins = sorted(unique_coins.values(), key=lambda x: abs(x["change_24h"]), reverse=True)

        lines = []
        for c in sorted_coins[:10]:
            lines.append(
                f"{c['name']}: Цена {c['price']} | "
                f"Изм. 24ч: {c['change_24h']}% | "
                f"Объем: ${c['volume']:,.0f} | "
                f"Фандинг: {c['funding']:.4f}%"
            )
        return "\n".join(lines)

    except Exception as e:
        print(f"Hyperliquid Error: {e}")
        return f"Error getting data: {e}"

def analyze_with_groq(market_data: str) -> str:
    if not GROQ_API_KEY:
        return "No GROQ_API_KEY"

    client = Groq(api_key=GROQ_API_KEY)

    prompt = (
        "Ты профессиональный крипто-трейдер с маленьким депозитом ($100-500). "
        "Ищешь возможности на мелких и средних монетах Hyperliquid.\n\n"
        "Приоритеты: сильные движения от 8%, объём от $15k, возможность отскока.\n\n"
        "Напиши кратко:\n"
        "1. Общее состояние рынка (1-2 предложения)\n"
        "2. 2-3 монеты с цифрами и идеей (Лонг/Шорт/Пауза)\n"
        "3. Главный риск\n\n"
        "Максимум 800 символов. Без Markdown.\n\n"
        f"Данные:\n{market_data}"
    )

    for model in FALLBACK_MODELS:
        try:
            print(f"Trying model: {model}")
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            print(f"Success with {model}")
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Model {model} failed: {e}")
            time.sleep(1)

    return "All models failed"

def write_status(market: str, analysis: str, success: bool):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    status = "OK" if success else "FAILED"

    content = (
        "# Crypto Scanner Status\n\n"
