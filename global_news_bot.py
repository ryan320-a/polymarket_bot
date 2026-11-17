import os
import requests
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from openai import OpenAI

# ==========================================
# 1. API 與系統設定
# ==========================================
DEEPSEEK_API_KEY = "sk-517d8baa3a174590a5a8bedfe5b3b236"
TELEGRAM_TOKEN = "9106778418:AAEDd0O_Wpwd7rAojcaOodlAVdDzjP1G0r8"
TELEGRAM_CHAT_ID = "1290187511"
SENT_LOG_FILE = "sent_global_news.txt"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ==========================================
# 2. 歷史紀錄防重複
# ==========================================
def load_history():
    if not os.path.exists(SENT_LOG_FILE): return set()
    with open(SENT_LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_history(text_hash):
    with open(SENT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{text_hash}\n")

# ==========================================
# 3. 網頁內文爬蟲 (點進連結抓正文)
# ==========================================
def fetch_article_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        # 提取所有段落文字
        paragraphs = soup.find_all('p')
        full_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
        # 截取前 2500 個字元送給 AI，避免超出 token 限制或包含底部廣告
        return full_text[:2500] if full_text else ""
    except Exception as e:
        print(f"⚠️ 無法讀取網頁內文 ({url}): {e}")
        return ""

# ==========================================
# 4. 抓取全球金融與權威突發新聞
# ==========================================
def fetch_breaking_news():
    news_items = []
    sources = [
        ("BBC", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("CNBC", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Yahoo", "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US")
    ]
    for source_name, rss_url in sources:
        try:
            feed = feedparser.parse(rss_url)
            # 每個來源抓最新 1 篇，確保每次總共最多處理 4 篇深度文章，避免執行超時
            for entry in feed.entries[:1]:
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get("summary", ""),
                    "source": source_name
                })
        except:
            pass
    return news_items

# ==========================================
# 5. DeepSeek 深度內文整理 (嚴格限制 200 字內)
# ==========================================
def summarize_article_with_deepseek(item, article_text):
    # 如果網頁有擋爬蟲抓不到內文，就退回使用 RSS 自帶的摘要與標題
    source_material = article_text if len(article_text) > 100 else f"標題：{item['title']}\n摘要：{item['summary']}"
    
    prompt = f"""
    你是一位專業的財經與國際新聞主編。請閱讀以下新聞內容，並為忙碌的讀者整理出一份高質素、容易理解的繁體中文精華摘要。
    
    【新聞來源】：{item['source']}
    【原始資料】：
    {source_material}
    
    【寫作要求】：
    1. 內容必須包含：事件核心經過、背後的關鍵原因，以及對市場或大眾的潛在影響。
    2. 語氣流暢自然，將複雜的財經或政治概念轉化為白話文，拒絕生硬的機翻感。
    3. 嚴格控制總字數在「150 到 200 個繁體中文字」之間，絕對不可超過 200 字。
    4. 直接輸出整理後的段落內容，不要加上「摘要：」、「字數統計」或任何開場白。
    """
    
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400
        ).choices[0].message.content.strip()
        return res
    except Exception as e:
        print(f"❌ DeepSeek 摘要失敗: {e}")
        return item['title']

# ==========================================
# 6. Telegram 獨立卡片推播
# ==========================================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, data=payload)

# ==========================================
# 7. 主程式
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動全球新聞深度爬蟲與 200 字精華整理...")
    history = load_history()
    raw_news = fetch_breaking_news()
    
    new_updates = [item for item in raw_news if str(hash(item['title'])) not in history]
    
    if new_updates:
        print(f"✅ 發現 {len(new_updates)} 則新文章，開始爬取內文並進行分析...")
        
        for item in new_updates:
            print(f"🔍 正在讀取 [{item['source']}] {item['title']}...")
            article_text = fetch_article_content(item['link'])
            
            # 交由 DeepSeek 整理成 200 字以內精華
            digest_zh = summarize_article_with_deepseek(item, article_text)
            
            # 組合單篇新聞卡片
            msg = (
                f"📰 <b>[{item['source']}] 深度快訊</b>\n\n"
                f"{digest_zh}\n\n"
                f"🔗 <a href='{item['link']}'>查看原始報導</a>"
            )
            
            send_telegram(msg)
            print(f"📱 已發送 [{item['source']}] 精華摘要。")
            save_history(str(hash(item['title'])))
    else:
        print("⏭️ 暫無最新報導，略過執行。")
