import feedparser
import telebot
import google.generativeai as genai
import os
import requests
import re
import time

# --- НАСТРОЙКИ ---
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
    # Используем стабильную модель flash
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    last_link = get_last_seen_link()
    all_entries = []

    # Собираем новости
    for url in SOURCES:
        try:
            feed = feedparser.parse(url)
            all_entries.extend(feed.entries)
        except: continue

    # Сортируем (самые свежие в начале)
    all_entries.sort(key=lambda x: x.get('published_parsed', (0,)), reverse=True)
    
    # Отбираем только НОВЫЕ новости (которых не было в базе)
    new_entries = []
    seen_titles = set()
    for e in all_entries:
        if e.link.strip() != last_link:
            if e.title not in seen_titles:
                new_entries.append(e)
                seen_titles.add(e.title)
        else:
            break # Дошли до старой новости, дальше не смотрим
    
    # Ограничим выборку пятью новостями для экономии запросов
    new_entries = new_entries[:5]

    if not new_entries:
        print("Новых новостей нет.")
        return

    # ШАГ 1: Один запрос к ИИ, чтобы выбрать лучшую новость
    titles_list = "\n".join([f"{i}. {e.title}" for i, e in enumerate(new_entries)])
    print(f"Новостей на проверку: {len(new_entries)}")
    
    try:
        prompt_select = (
            f"Из этого списка новостей выбери ОДНУ самую важную для криптоинвестора. "
            f"Напиши ТОЛЬКО цифру (номер в списке):\n{titles_list}"
        )
        
        time.sleep(10) # Безопасная пауза
        res_select = model.generate_content(prompt_select)
        
        # Ищем цифру в ответе
        match = re.search(r'\d+', res_select.text)
        if match:
            idx = int(match.group())
            # Проверка, что индекс не вылетает за границы списка
            if idx >= len(new_entries): idx = 0 
            
            best_entry = new_entries[idx]
            print(f"Выбрана лучшая новость: {best_entry.title}")
            
            # ШАГ 2: Генерация самого поста (второй запрос к ИИ)
            time.sleep(15) # Пауза перед постом
            
            prompt_post = (
                f"Напиши пост на РУССКОМ языке по новости: {best_entry.title}. "
                f"ПРАВИЛА: 1. Жирный заголовок. 2. Суть в 2 предложениях. 3. Без ссылок. 4. Без лишних фраз."
            )
            
            post_res = model.generate_content(prompt_post)
            final_text = re.sub(r'http\S+', '', post_res.text).strip()

            if final_text:
                bot.send_message(CHANNEL_ID, final_text, parse_mode='Markdown')
                save_last_link(best_entry.link)
                print("Успешно опубликовано в Telegram!")
        else:
            print("ИИ не смог выбрать номер новости.")

    except Exception as e:
        print(f"Ошибка лимитов или API: {e}")

if __name__ == "__main__":
    run_bot()
