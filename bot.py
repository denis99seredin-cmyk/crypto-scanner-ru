import os
import sys
import requests
from groq import Groq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

TOP = ["BTC", "ETH", "SOL", "HYPE", "BNB", "XRP", "DOGE", "AVAX"]

def send_tg(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("No Telegram credentials")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=15)
        print("TG:", r.status_code)
        return r.status_code == 200
    except Exception as e:
        print("TG error:", e)
        return False

def get_market() -> str:
    try:
        r = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            timeout=12
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Hyperliquid error: {e}"

    if not isinstance(data, list) or len(data) < 2:
        return "Bad response shape"

    universe = data[0].get("universe", [])
    ctxs = data[1]
    lines = []

    for i, asset in enumerate(universe):
        name = asset.get("name")
        if name not in TOP:
            continue
        ctx = ctxs[i] if i < len(ctxs) else {}
        mark = ctx.get("markPx") or ctx.get("midPx") or "?"
        funding = ctx.get("funding") or "?"
        prev = ctx.get("prevDayPx") or "?"
        vol = ctx.get("dayNtlVlm") or "?"
        lines.append(f"{name}: {mark} | prev {prev} | fund {funding} | vol {vol}")

    return "\n".join(lines) if lines else "No data"

def analyze(market: str) -> str:
    if not GROQ_API_KEY:
        return "Нет GROQ_API_KEY"

    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"""Ты крипто-аналитик. По данным Hyperliquid дай короткий ответ на русском:

1. Общее настроение рынка (1-2 предложения)
2. 2-3 самых интересных монеты с цифрами
3. Один риск / на что смотреть ближайшие часы

Максимум 900 символов, без воды.

Данные:
{market}"""

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=700,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Groq error: {e}"

def main():
    print("Start")
    market = get_market()
    print(market[:400])

    analysis = analyze(market)

    msg = (
        f"<b>📊 Hyperliquid Scanner</b>\n"
        f"<code>{market[:850]}</code>\n\n"
        f"<b>🤖 Анализ (Groq):</b>\n{analysis}"
    )
    if len(msg) > 4000:
        msg = msg[:3990] + "…"

    ok = send_tg(msg)
    print("Done, sent:", ok)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
