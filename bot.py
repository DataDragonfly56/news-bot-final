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
    
    # Автоматический выбор доступной модели (чтобы не было 404)
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    if not available_models:
        print("Модели не найдены.")
        return
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

    # Проверяем 3 новости
    for entry in all_entries[:3]:
        title, link = entry.title, entry.link
        
        if link.strip() == last_link:
            continue 

        try:
            print(f"Анализирую: {title[:50]}...")
            time.sleep(20) # Пауза против ошибки 429
            
            check_res = model.generate_content(f"Оцени важность для крипто-инвестора от 1 до 10: '{title}'. Ответь только цифрой.")
            score_text = ''.join(filter(str.isdigit, check_res.text))
            score = int(score_text) if score_text else 0
            
            if score >= 7:
                print(f"Важность {score}. Ждем лимит для текста...")
                time.sleep(25) 
                
                instr = (
                    f"Напиши пост по новости: {title}. "
                    f"ПРАВИЛА: 1. Только РУССКИЙ. 2. БЕЗ ссылок. "
                    f"3. Формат: **Жирный заголовок**, суть в 2 предложениях."
                )
                
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
                print("Лимит исчерпан. Остановка до следующего запуска.")
                return 
            else:
                print(f"Ошибка: {e}")
            continue

if __name__ == "__main__":
    run_bot()
