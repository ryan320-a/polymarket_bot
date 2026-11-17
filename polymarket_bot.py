import os
import requests
import feedparser
from openai import OpenAI

# ==========================================
# 1. 系統變數與 API 設置
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "你的_DEEPSEEK_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "你的_TG_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "你的_CHAT_ID")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
SENT_LOG_FILE = "sent_news.txt"

TARGETS = [
    {
        "title": "聯準會 (Fed) 降息預測",
        "keywords": ["Federal Reserve", "rate cut", "powell", "inflation"],
        "stock_ticker": "SPY", 
        "world_query": "US Economy Interest Rate"
    }
]

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
# 3. 模組化搜集器
# ==========================================
def fetch_world_news(query):
    try:
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        return [f"[全球宏觀] {entry.title}" for entry in feed.entries[:3]]
    except:
        return []

def fetch_stock_market_news(ticker):
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        feed = feedparser.parse(url)
        return [f"[股市財經] {entry.title}" for entry in feed.entries[:3]]
    except:
        return []

def fetch_media_manager(keywords):
    try:
        url = "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"
        feed = feedparser.parse(url)
        return [f"[主流媒體] {entry.title}" for entry in feed.entries[:3] 
                if any(kw.lower() in entry.title.lower() for kw in keywords)]
    except:
        return []

# ==========================================
# 4. DeepSeek 資深分析師大腦 (白話文解說版)
# ==========================================
def analyze_and_synthesize_with_deepseek(news_list, target_title):
    combined_news = "\n".join(news_list)
    
    prompt = f"""
    你現在是一位「華爾街資深情報分析師」。
    你具備將艱澀金融概念「深入淺出 (Layman explanation)」的頂級能力，能夠將複雜的市場邏輯、經濟數據，轉化為完全沒有金融背景的外行人也能輕鬆秒懂的白話文。
    
    以下是系統剛從全球宏觀新聞、股市 API 以及主流媒體抓取到的即時雜亂情報：
    
    {combined_news}
    
    你正在針對 Polymarket 賭盤主題：「{target_title}」進行研究。
    請將上述零散資料進行高度整合，拒絕生硬的機器翻譯感，使用極度流暢、接地氣且排版清晰的繁體中文寫出一份情報簡報。
    
    簡報必須嚴格包含以下四個區塊，並使用 Emoji 作為標題：
    
    1. 🎯 核心事件秒懂：用最簡單的 1-2 句話，告訴外行人現在世界發生了什麼大事。
    2. 💡 專家白話解析：將新聞背後的複雜概念、專有名詞或潛在影響，用日常生活的比喻或極度白話的方式解釋清楚，讓人一看就懂。
    3. 🔍 市場交叉比對：綜合不同情報來源，分析市場情緒是否有矛盾或共識。
    4. 🎲 預估勝率與決策：針對該賭盤，給出 0-100 的精確機率數字，並說明給出這個數字的最關鍵理由。
    
    請確保文字流暢，段落分明，適合在手機上快速閱讀。
    """
    
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        ).choices[0].message.content.strip()
        
        import re
        numbers = re.findall(r'\b(?:100|[1-9]?[0-9])\b', res)
        prob = int(numbers[-1]) if numbers else 50 
        
        return prob, res
    except Exception as e:
        return 50, f"分析失敗: {e}"

# ==========================================
# 5. Telegram 排版推播
# ==========================================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# ==========================================
# 6. 主程式 (測試模式)
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動 Polymarket 終極情報分析中心 (測試模式)")
    history = load_history()
    
    for target in TARGETS:
        print(f"\n🎯 正在搜集並分析: {target['title']}")
        
        raw_pool = []
        raw_pool.extend(fetch_world_news(target["world_query"]))
        raw_pool.extend(fetch_stock_market_news(target["stock_ticker"]))
        raw_pool.extend(fetch_media_manager(target["keywords"]))
        
        new_intel = [news for news in raw_pool if str(hash(news)) not in history]
        
        if not new_intel:
            print("⏭️ 暫無新情報，略過。")
            continue
            
        print(f"✅ 搜集到 {len(new_intel)} 筆新數據，正在交由 DeepSeek 撰寫中文報告...")
        
        prob, final_report = analyze_and_synthesize_with_deepseek(new_intel, target["title"])
        print(f"🧠 分析完成。預估勝率: {prob}%")
        
        # 【測試模式】無條件大於等於 0 就發送
        if prob >= 0: 
            send_telegram(final_report)
            print("📱 已發送情報簡報至 Telegram。")
            
            # 【測試模式】暫停寫入歷史紀錄，方便重複測試
            # for intel in new_intel:
            #     save_history(str(hash(intel)))
