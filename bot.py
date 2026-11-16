import os
import sys
import html
import time
import requests
from groq import Groq

# --- НАСТРОЙКИ И СЕКРЕТЫ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Список рабочих моделей от самой умной к самой быстрой
FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct"
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
        "disable_web_page_preview": True
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
            ctx = ctxs[i] if i < len(ctxs) else {}
            
            if name in ["USDC", "USDT", "DAI", "FDUSD"]:
                continue
                
            try:
                mark_px = float(ctx.get("markPx", 0))
                prev_day = float(ctx.get("prevDayPx", 0))
                vol_24h = float(ctx.get("dayNtlVlm", 0))
                funding = float(ctx.get("funding", 0))
                
                change_24h = 0.0
                if prev_day > 0:
                    change_24h = ((mark_px - prev_day) / prev_day) * 100
                
                if vol_24h > 100000: 
                    coins_data.append({
                        "name": name,
                        "price": mark_px,
                        "change_24h": round(change_24h, 2),
                        "volume": vol_24h,
                        "funding": funding * 100
                    })
            except (ValueError, TypeError):
                continue

        if not coins_data:
            return "Не удалось собрать данные по монетам."

        top_by_volume = sorted(coins_data, key=lambda x: x["volume"], reverse=True)[:5]
        top_movers = sorted(coins_data, key=lambda x: abs(x["change_24h"]), reverse=True)[:5]
        
        unique_coins = {}
        for c in top_by_volume + top_movers:
            unique_coins[c["name"]] = c

        result_lines = []
        for c in unique_coins.values():
            line = (f"{c['name']}: Цена {c['price']} | "
                    f"Изм. 24ч: {c['change_24h']}% | "
                    f"Объем: ${c['volume']:,.0f} | "
                    f"Фандинг: {c['funding']:.4f}%")
            result_lines.append(line)
            
        return "\n".join(result_lines)
        
    except Exception as e:
        print(f"❌ Hyperliquid Error: {e}")
        return f"⚠️ Ошибка получения данных: {e}"

def analyze_with_groq(market_data: str) -> str:
    if not GROQ_API_KEY:
        return "⚠️ Ошибка: Не задан GROQ_API_KEY"
        
    client = Groq(api_key=GROQ_API_KEY)
    
    prompt = f"""
    Ты профессиональный крипто-трейдер. Проанализируй данные по активным и волатильным монетам на Hyperliquid за последние 24 часа.
    
    Найди 2-3 монеты для потенциального трейдинга.
    Учти:
    - Высокий положительный фандинг (Funding > 0.01%) = много лонгистов, риск шорт-сквиза.
    - Сильное падение (Изм. 24ч < -10%) при большом объеме = возможен отскок.
    - Сильный рост (Изм. 24ч > 10%) = тренд, но риск коррекции.
    
    Напиши краткий отчет:
    1. 1-2 предложения об общем состоянии рынка.
    2. 2-3 монеты с конкретными цифрами и идеей (Лонг/Шорт/Пауза).
    3. Главный риск для этих идей.
    
    ПРАВИЛО: Пиши кратко, без воды. Максимум 800 символов. НЕ ИСПОЛЬЗУЙ Markdown, пиши обычным текстом.
    
    Данные:
    {market_data}
    """
    
    for model in FALLBACK_MODELS:
        try:
            print(f"⏳ Пробую модель: {model}...")
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            print(f"✅ Успех с моделью: {model}")
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"⚠️ Модель {model} не сработала. Ошибка: {e}")
            time.sleep(1)
            
    return "⚠️ Ошибка: Все доступные ИИ-модели временно недоступны."

def main():
    print("🚀 Запуск умного сканера...")
    
    market_data = get_profitable_market_data()
    print("✅ Данные собраны.")
    
    analysis = analyze_with_groq(market_data)
    print("✅ Анализ готов.")
    
    safe_market = html.escape(market_data)
    safe_analysis = html.escape(analysis).replace("*", "")
    
    msg = (
        f"<b>🔥 Hyperliquid Screener (Топ движения)</b>\n"
        f"<code>{safe_market}</code>\n\n"
        f"<b>🧠 Мнение ИИ:</b>\n{safe_analysis}"
    )
    
    if len(msg) > 4000:
        msg = msg[:3990] + "\n\n<i>...обрезано...</i>"
        
    success = send_telegram(msg)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
