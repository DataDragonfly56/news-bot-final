import feedparser, telebot, os, requests, time, re, logging
from google import genai
from urllib.parse import urlparse, quote
from io import BytesIO

logging.basicConfig(level=logging.INFO)

# --- НАСТРОЙКИ (Берутся из твоих Secrets) ---
T_TOKEN = os.environ.get("TELEGRAM_TOKEN")
G_KEY = os.environ.get("GEMINI_API_KEY")
GIT_T = os.environ.get("MY_GIT_TOKEN")
REPO = os.environ.get("MY_REPO")
CH_ID = "@cryptoteamko"

SOURCES = [
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed"
]

def get_last_link():
    url = f"https://api.github.com/repos/{REPO}/issues?state=all&labels=last_news&per_page=1"
    try:
        res = requests.get(url, headers={"Authorization": f"token {GIT_T}"}, timeout=10).json()
        return res[0].get('body', "").strip() if res else ""
    except: return ""

def save_last_link(link):
    url = f"https://api.github.com/repos/{REPO}/issues"
    try:
        payload = {"title": f"Log {time.strftime('%H:%M')}", "body": link, "labels": ["last_news"]}
        requests.post(url, headers={"Authorization": f"token {GIT_T}"}, json=payload, timeout=10)
    except: pass

def generate_content(title, desc, domain):
    try:
        # Используем v1beta — она самая стабильная для новых ключей
        client = genai.Client(api_key=G_KEY, http_options={'api_version': 'v1beta'})
        
        prompt = (
            f"Ты — профессиональный крипто-блогер. Напиши краткий пост.\n"
            f"НОВОСТЬ: {title}\nСУТЬ: {desc}\n\n"
            f"ПРАВИЛА:\n"
            f"1. Только РУССКИЙ язык.\n"
            f"2. УДАЛИ все ссылки.\n"
            f"3. ЗАПРЕЩЕНЫ фразы: 'Актуальная новость', 'Вот подробности', 'Читать далее'.\n"
            f"4. СТРУКТУРА: **Жирный заголовок**, 2 предложения сути. В конце 'Источник: {domain}' (текстом, не ссылкой)."
        )
        
        # Используем модель flash-001 (она самая быстрая и безотказная)
        response = client.models.generate_content(model="gemini-1.5-flash-001", contents=prompt)
        
        if not response.text: return None
        
        # Финальная чистка текста от остатков ссылок
        clean_text = re.sub(r'http\S+', '', response.text).strip()
        return clean_text
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return None

def run_bot():
    bot = telebot.TeleBot(T_TOKEN)
    all_news = []
    for url in SOURCES:
        try:
            feed = feedparser.parse(url)
            all_news.extend(feed.entries)
        except: continue
    
    all_news.sort(key=lambda x: x.get('published_parsed', (0,)), reverse=True)
    last_saved = get_last_link()
    
    for entry in all_news[:5]:
        link = entry.link.strip()
        if link == last_saved: break
        
        domain = urlparse(link).netloc.replace('www.', '').capitalize()
        text = generate_content(entry.title, entry.get('summary', ''), domain)
        
        if text:
            try:
                # Отправляем сообщение без лишних кнопок и ссылок
                bot.send_message(CH_ID, text=text, parse_mode='Markdown')
                save_last_link(link)
                logging.info("Успешно опубликовано")
                return # За один запуск постим одну новость
            except Exception as e:
                logging.error(f"TG Error: {e}")

if __name__ == "__main__":
    run_bot()
