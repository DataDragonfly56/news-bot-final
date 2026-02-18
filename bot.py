import feedparser
import telebot
import google.generativeai as genai
import os
import requests
import re

# Настройки
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("MY_GIT_TOKEN")
REPO = os.environ.get("MY_REPO") # Используем твой секрет
CHANNEL_ID = "@cryptoteamko"
RSS_URL = "https://news.google.com/rss/search?q=криптовалюта+биткоин&hl=ru&gl=RU&ceid=RU:ru"

genai.configure(api_key=GEMINI_API_KEY)

def get_last_seen_link():
    url = f"https://api.github.com/repos/{REPO}/issues?state=all&labels=last_news"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        res = requests.get(url, headers=headers).json()
        if isinstance(res, list) and len(res) > 0:
            return res[0].get('body', "").strip()
    except:
        pass
    return ""

def save_last_link(link):
    url = f"https://api.github.com/repos/{REPO}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    data = {"title": "Last Checked News", "body": link, "labels": ["last_news"]}
    requests.post(url, headers=headers, json=data)

def run_bot():
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    # Используем проверенный метод выбора модели
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    model = genai.GenerativeModel(available_models[0])
    
    feed = feedparser.parse(RSS_URL)
    
    if feed.entries:
        entry = feed.entries[0]
        title, link = entry.title, entry.link
        
        if link.strip() == get_last_seen_link():
            print("Эта новость уже была.")
            return

        try:
            # СТРОГАЯ ИНСТРУКЦИЯ: Текст на русском, без ссылок, без мусора
            instr = (
                f"Напиши профессиональный пост по новости: {title}. "
                f"ПРАВИЛА: 1. Только РУССКИЙ язык. 2. УДАЛИ любые ссылки. "
                f"3. Формат: **Жирный заголовок**, затем коротко суть (2 предложения). "
                f"4. НЕ пиши 'Актуальная новость' или 'Вот текст'."
            )
            
            post_res = model.generate_content(instr)
            text = post_res.text
            
            # Дополнительная очистка от ссылок (на всякий случай)
            text = re.sub(r'http\S+', '', text).strip()

            if text:
                bot.send_message(CHANNEL_ID, text, parse_mode='Markdown')
                print("Пост отправлен!")
                save_last_link(link)
            
        except Exception as e:
            print(f"Ошибка: {e}")
    else:
        print("Новостей нет.")

if __name__ == "__main__":
    run_bot()
