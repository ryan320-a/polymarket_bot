import os
import requests
import feedparser
from openai import OpenAI

# ==========================================
# 1. 系統變數與 API 設置
# ==========================================
DEEPSEEK_API_KEY = "sk-517d8baa3a174590a5a8bedfe5b3b236"
TELEGRAM_TOKEN = "9106778418:AAEDd0O_Wpwd7rAojcaOodlAVdDzjP1G0r8"
TELEGRAM_CHAT_ID = "1290187511"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
SENT_LOG_FILE = "sent_news.txt"

# ==========================================
# 2. 歷史紀錄防重複 (這次改記當天的重點標題 Hash)
# ==========================================
def load_history():
    if not os.path.exists(SENT_LOG_FILE): return set()
    with open(SENT_LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_history(text_hash):
    with open(SENT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{text_hash}\n")

# ==========================================
# 3. 抓取全球「最火爆」頭條 (無需關鍵字)
# ==========================================
def fetch_trending_news():
    pool = []
    # 1. Google News 全球英文版 Top Stories
    try:
        feed = feedparser.parse("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
        pool.extend([f"[全球頭條] {entry.title}" for entry in feed.entries[:8]])
    except: pass
    
    # 2. Yahoo Finance 全球財經 Top Stories
    try:
        feed = feedparser.parse("https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US")
        pool.extend([f"[財經熱點] {entry.title}" for entry in feed.entries[:5]])
    except: pass
    
    return pool

# ==========================================
# 4. DeepSeek 趨勢分析師大腦
# ==========================================
def analyze_trending_news(news_list):
    combined_news = "\n".join(news_list)
    
    prompt = f"""
    你現在是一位「全球趨勢首席分析師」。
    你具備將艱澀概念「深入淺出 (Layman explanation)」的頂級能力，能夠將複雜的國際局勢、市場邏輯，轉化為完全沒有背景的外行人也能輕鬆秒懂的白話文。
    
    以下是系統剛從全球權威媒體抓取到的「今日最火爆、最多人討論的頭條新聞」集合：
    
    {combined_news}
    
    請你從中挑選出「1 到 2 件目前最具全球影響力的大事」進行高度整合，過濾掉不重要的雜訊。
    拒絕生硬的機器翻譯感，使用極度流暢、接地氣且排版清晰的繁體中文寫出一份趨勢簡報。
    
    簡報必須嚴格包含以下四個區塊，並使用 Emoji 作為標題：
    
    1. 🔥 今日全球頭條秒懂：用最簡單的 1-2 句話，告訴外行人現在世界發生了什麼最火爆的大事。
    2. 💡 專家白話解析：將這件大事背後的複雜概念、專有名詞或潛在原因，用日常生活的比喻解釋清楚，讓人一看就懂。
    3. 🗣️ 輿論與市場風向：綜合分析目前大眾、媒體或投資者對這件事的看法與情緒。
    4. 🔮 未來潛在影響：這件事接下來可能會對普通人的生活、經濟或國際局勢造成什麼影響？
    
    請確保文字流暢，段落分明，適合在手機上快速閱讀。不要給我任何網址連結。
    """
    
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4, # 稍微調高一點溫度，讓解析的比喻更生動
            max_tokens=1000
        ).choices[0].message.content.strip()
        
        return res
    except Exception as e:
        return f"分析失敗: {e}"

# ==========================================
# 5. Telegram 排版推播
# ==========================================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# ==========================================
# 6. 主程式
# ==========================================
# 【測試模式】：為了讓你馬上看到成果，這裡把門檻設為 0。
    if len(new_intel) >= 0:
        print(f"✅ 搜集到 {len(new_intel)} 筆全新熱點數據，交由 DeepSeek 撰寫中文報告...")
        
        final_report = analyze_trending_news(new_intel)
        
        send_telegram(final_report)
        print("📱 已發送熱點簡報至 Telegram。")
        
        # 【測試模式】：暫時註解掉歷史紀錄，方便你重複按 Run 測試
        # for intel in new_intel:
        #     save_history(str(hash(intel)))
    else:
        print("⏭️ 目前熱點新聞尚未大幅更新，略過發送。")
