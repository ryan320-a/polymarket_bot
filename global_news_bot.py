import os
import requests
import feedparser
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
    if not os.path.exists(SENT_LOG_FILE):
        return set()
    with open(SENT_LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_history(text_hash):
    with open(SENT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{text_hash}\n")

# ==========================================
# 3. 網頁內文爬蟲 (點進連結抓取正文)
# ==========================================
def fetch_article_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
        # 每篇截取前 1200 字元，確保多篇文章合在一起不會超過 DeepSeek 上下文限制
        return full_text[:1200] if full_text else ""
    except Exception as e:
        print(f"⚠️ 無法讀取網頁內文 ({url}): {e}")
        return ""

# ==========================================
# 4. 抓取全球權威與財經突發新聞
# ==========================================
def fetch_breaking_news():
    news_items = []
    sources = [
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("CNBC 財經", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
        ("CoinDesk 幣圈", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Yahoo 金融", "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US"),
        ("Google 全球頭條", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
    ]
    for source_name, rss_url in sources:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:2]:
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get("summary", ""),
                    "source": source_name
                })
        except Exception as e:
            print(f"⚠️ RSS 讀取失敗 ({source_name}): {e}")
    return news_items

# ==========================================
# 5. DeepSeek 全球趨勢首席分析師 (綜合白話解析版)
# ==========================================
def analyze_combined_news(combined_news):
    prompt = f"""
你現在是一位「全球趨勢首席分析師」。
你具備將艱澀概念「深入淺出 (Layman explanation)」的頂級能力，能夠將複雜的國際局勢、市場邏輯，轉化為完全沒有背景的外行人也能輕鬆秒懂的白話文。

以下是系統剛從全球權威媒體抓取到的「今日最火爆、最多人討論的頭條新聞」集合（包含標題與網頁內文摘要）：

{combined_news}

請你從中挑選出「1 到 2 件目前最具全球影響力的大事」進行高度整合，過濾掉不重要的雜訊。
拒絕生硬的機器翻譯感，使用極度流暢、接地氣且排版清晰的繁體中文寫出一份趨勢簡報。

簡報必須嚴格包含以下四個區塊，並使用 Emoji 作為標題：

1. 🔥 今日全球頭條秒懂：用最簡單的 1-2 句話，告訴外行人現在世界發生了什麼最火爆的大事。
2. 💡 專家白話解析：將這件大事背後的複雜概念、專有名詞或潛在原因，用日常生活的比喻解釋清楚，讓人一看就懂。
3. 🗣️ 輿論與市場風向：綜合分析目前大眾、媒體或投資者對這件事的看法與情緒。
4. 🔮 未來潛在影響：這件事接下來可能會對普通人的生活、經濟或國際局勢造成什麼影響？

請確保文字流暢，段落分明，適合在手機上快速閱讀。不要在文中加入任何網址連結或特殊 Markdown 符號（如星號或井字號），以免影響手機閱讀體驗。
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=1200
        ).choices[0].message.content.strip()
        return res
    except Exception as e:
        print(f"❌ DeepSeek 分析失敗: {e}")
        return ""

# ==========================================
# 6. Telegram 推播模組
# ==========================================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print("📱 已成功發送趨勢簡報至 Telegram！")
    else:
        print(f"❌ Telegram 發送失敗 ({response.status_code}): {response.text}")

# ==========================================
# 7. 主程式
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動全球趨勢雷達與深度分析引擎...")
    history = load_history()
    raw_news = fetch_breaking_news()
    
    # 過濾掉已經處理過的舊新聞
    new_updates = [item for item in raw_news if str(hash(item['title'])) not in history]
    
    # 門檻設定：至少累積 3 則新新聞才啟動整合分析（若要強制測試，可暫時將 3 改為 1）
    if len(new_updates) >= 3:
        print(f"✅ 發現 {len(new_updates)} 則全新頭條，正在爬取網頁內文...")
        
        compiled_articles = []
        for item in new_updates[:6]:  # 最多抽取 6 篇進行深度爬取，兼顧速度與廣度
            print(f"🔍 讀取內文: [{item['source']}] {item['title']}")
            content = fetch_article_content(item['link'])
            body = content if len(content) > 100 else item['summary']
            compiled_articles.append(f"【來源：{item['source']}】\n標題：{item['title']}\n內文：{body}\n---")
        
        combined_news_text = "\n".join(compiled_articles)
        
        print("🧠 正在交由 DeepSeek 進行深度整合與白話文解析...")
        final_briefing = analyze_combined_news(combined_news_text)
        
        if final_briefing:
            send_telegram(final_briefing)
            # 寫入歷史紀錄，避免重複分析同一批新聞
            for item in new_updates:
                save_history(str(hash(item['title'])))
    else:
        print(f"⏭️ 目前僅有 {len(new_updates)} 則零星新消息，尚未達到整合門檻，略過執行。")
