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

    # 1. Отбираем до 15 НОВЫХ новостей
    new_entries = []
    for entry in all_entries:
        if entry.link.strip() == last_link:
            break
        new_entries.append(entry)
        if len(new_entries) >= 15:
            break

    if not new_entries:
        print("Новых новостей нет.")
        return

    # 2. Формируем список заголовков для ИИ
    titles_block = ""
    for i, entry in enumerate(new_entries):
        titles_block += f"{i}. {entry.title}\n"

    try:
        print(f"Отправляю на анализ {len(new_entries)} новостей...")
        
        # ШАГ 3: Обновленный промт с аналитикой и запретом на выдумки
        prompt = (
            f"Вот список новостей:\n{titles_block}\n"
            f"ЗАДАНИЕ:\n"
            f"1. Выбери ОДНУ самую важную и актуальную новость для крипто-инвестора.\n"
            f"2. Напиши в первой строке ответа только её НОМЕР из списка.\n"
            f"3. Со следующей строки напиши сам пост.\n\n"
            f"ПРАВИЛА ПОСТА:\n"
            f"- Только РУССКИЙ язык. НЕ ВЫДУМЫВАЙ факты, используй только данные из заголовка.\n"
            f"- Перефразируй новость своими словами (не копируй заголовок вчистую).\n"
            f"- Добавь краткую аналитику от себя (почему это важно для рынка или инвесторов).\n"
            f"- БЕЗ каких-либо ссылок.\n"
            f"- Формат: **Жирный заголовок**, суть и аналитика в 2-3 предложениях.\n"
            f"- БЕЗ лишних фраз (не пиши 'я выбрал новость №...')."
        )

        # Делаем паузу перед запросом для страховки
        time.sleep(10)
        response = model.generate_content(prompt)
        full_text = response.text.strip()

        # Разделяем номер и текст поста
        lines = full_text.split('\n', 1)
        index_match = re.search(r'\d+', lines[0])
        
        if index_match and len(lines) > 1:
            idx = int(index_match.group())
            post_content = lines[1].strip()
            
            if 0 <= idx < len(new_entries):
                best_entry = new_entries[idx]
                
                # Отправляем в ТГ
                bot.send_message(CHANNEL_ID, post_content, parse_mode='Markdown')
                save_last_link(best_entry.link)
                print(f"Опубликовано: {best_entry.title}")
            else:
                print("ИИ указал неверный номер новости.")
        else:
            print("ИИ вернул ответ в неправильном формате.")

    except Exception as e:
        if "429" in str(e):
            print("Лимит исчерпан. Ждем следующего запуска.")
        else:
            print(f"Ошибка: {e}")

if __name__ == "__main__":
    run_bot()
