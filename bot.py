import feedparser, telebot, os, requests, time, re, logging
from google import genai
from urllib.parse import urlparse, quote
from io import BytesIO

logging.basicConfig(level=logging.INFO)

# Ключи берутся из тех самых Secrets, что ты только что заполнил
T_TOKEN = os.environ.get("TELEGRAM_TOKEN")
G_KEY = os.environ.get("GEMINI_API_KEY")
GIT_T = os.environ.get("MY_GIT_TOKEN")
REPO = os.environ.get("MY_REPO")
CH_ID = "@cryptoteamko" # Твой канал

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
        # Принудительно v1, чтобы не было ошибки 404
        client = genai.Client(api_key=G_KEY, http_options={'api_version': 'v1'})
        prompt = (
            f"Напиши пост на РУССКОМ.\nЗАГОЛОВОК: {title}\nСУТЬ: {desc}\n"
            f"ПРАВИЛА: Без ссылок, без английского. В конце напиши 'Источник: {domain}'."
        )
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text.strip() if response.text else None
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return None

def run_bot():
    bot = telebot.TeleBot(T_TOKEN)
    all_news = []
    for url in SOURCES:
        try: all_news.extend(feedparser.parse(url).entries)
        except: continue
    
    all_news.sort(key=lambda x: x.get('published_parsed', (0,)), reverse=True)
    last_saved = get_last_link()
    
    for entry in all_news[:3]:
        link = entry.link.strip()
        if link == last_saved: break
        
        domain = urlparse(link).netloc.replace('www.', '').capitalize()
        text = generate_content(entry.title, entry.get('summary', ''), domain)
        
        if text:
            try:
                bot.send_message(CH_ID, text=text, parse_mode='Markdown')
                save_last_link(link)
                return # Публикуем по одной новости за раз
            except Exception as e:
                logging.error(f"Post error: {e}")

if __name__ == "__main__":
    run_bot()
