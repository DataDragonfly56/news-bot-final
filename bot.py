import feedparser
import telebot
import google.generativeai as genai
import os
import requests
import re
import time

# Настройки
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("MY_GIT_TOKEN")
REPO = os.environ.get("MY_REPO")
CHANNEL_ID = "@cryptoteamko"

# СПИСОК ИСТОЧНИКОВ
SOURCES = [
    "https://news.google.com/rss/search?q=криптовалюта+биткоин&hl=ru&gl=RU&ceid=RU:ru",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]

genai.configure(api_key=GEMINI_API_KEY)

def get_last_seen_link():
    url = f"https://api.github.com/repos/{REPO}/issues?state=all&labels=last_news"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        res = requests.get(url, headers=headers).json()
        if isinstance(res, list) and len(res) > 0:
            return res[0].get('body', "").strip()
    except: pass
    return ""

def save_last_link(link):
    url = f"https://api.github.com/repos/{REPO}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    data = {"title": "Last Checked News", "body": link, "labels": ["last_news"]}
    requests.post(url, headers=headers, json=data)

def run_bot():
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    model = genai.GenerativeModel(available_models[0])
    
    last_link = get_last_seen_link()
    all_entries = []

    for url in SOURCES:
        try:
            feed = feedparser.parse(url)
            all_entries.extend(feed.entries)
        except: continue

    all_entries.sort(key=lambda x: x.get('published_parsed', (0,)), reverse=True)

    if not all_entries:
        print("Новостей нет.")
        return

    # Проверяем топ-10 свежих новостей
    for entry in all_entries[:10]:
        title, link = entry.title, entry.link
        
        if link.strip() == last_link:
            continue 

        try:
            # ПАУЗА ПЕРЕД ЗАПРОСОМ (чтобы не спамить)
            print(f"Анализирую: {title[:50]}...")
            time.sleep(12) 
            
            # 1. Запрос на оценку важности
            check_res = model.generate_content(f"Оцени важность для крипто-инвестора от 1 до 10: '{title}'. Ответь только цифрой.")
            score_text = ''.join(filter(str.isdigit, check_res.text))
            score = int(score_text) if score_text else 0
            
            if score >= 7:
                print(f"Важность {score}. Готовлю пост...")
                
                # Еще одна ПАУЗА перед генерацией текста
                time.sleep(12) 
                
                instr = (
                    f"Напиши пост по новости: {title}. "
                    f"ПРАВИЛА: 1. Только РУССКИЙ язык. 2. УДАЛИ любые ссылки. "
                    f"3. Формат: **Жирный заголовок**, суть в 2-3 предложениях. "
                    f"4. БЕЗ лишних фраз."
                )
                
                # 2. Запрос на создание текста
                post_res = model.generate_content(instr)
                text = post_res.text
                text = re.sub(r'http\S+', '', text).strip()

                if text:
                    bot.send_message(CHANNEL_ID, text, parse_mode='Markdown')
                    save_last_link(link)
                    print("Успешно опубликовано!")
                    return 
            else:
                print(f"Пропуск: важность {score}")
                
        except Exception as e:
            if "429" in str(e):
                print("Google просит подождать. Отдыхаем 20 секунд...")
                time.sleep(20)
            else:
                print(f"Ошибка: {e}")
            continue

if __name__ == "__main__":
    run_bot()
