import os
import requests
import feedparser
import re
from datetime import datetime
from openai import OpenAI

# ==========================================
# 1. 系統變數與 API 設置
# ==========================================
# 請確保這裡的 Key 有填上，或是 GitHub Secrets 有正確設定
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "你的_DEEPSEEK_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "你的_TG_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "你的_CHAT_ID")
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
# 3. 抓取全球金融與權威突發新聞
# ==========================================
def fetch_breaking_news():
    news_items = []
    try:
        feed = feedparser.parse("http://feeds.bbci.co.uk/news/world/rss.xml")
        for entry in feed.entries[:2]:
            news_items.append({"title": entry.title, "link": entry.link, "source": "BBC"})
    except: pass
    
    try:
        feed = feedparser.parse("https://www.cnbc.com/id/10000664/device/rss/rss.html")
        for entry in feed.entries[:2]:
            news_items.append({"title": entry.title, "link": entry.link, "source": "CNBC"})
    except: pass

    try:
        feed = feedparser.parse("https://www.coindesk.com/arc/outboundfeeds/rss/")
        for entry in feed.entries[:2]:
            news_items.append({"title": entry.title, "link": entry.link, "source": "CoinDesk"})
    except: pass

    try:
        feed = feedparser.parse("https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US")
        for entry in feed.entries[:2]:
            news_items.append({"title": entry.title, "link": entry.link, "source": "Yahoo"})
    except: pass
    
    return news_items

# ==========================================
# 4. DeepSeek 批次翻譯大腦
# ==========================================
def translate_to_zh(news_list):
    print("🧠 正在呼叫 DeepSeek 進行繁體中文翻譯...")
    
    # 將標題組合成帶有編號的清單
    titles_text = "\n".join([f"{i+1}. {item['title']}" for i, item in enumerate(news_list)])
    
    prompt = f"""
    你是一位專業的財經新聞編譯。請將以下 {len(news_list)} 則英文新聞標題，翻譯成流暢、專業的繁體中文。
    請嚴格保留原本的數字編號，每行一個翻譯結果，絕對不要加上任何多餘的解釋或廢話：
    
    {titles_text}
    """
    
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500
        ).choices[0].message.content.strip()
        
        # 解析 AI 回傳的翻譯結果
        translated_lines = res.split('\n')
        
        for i, item in enumerate(news_list):
            if i < len(translated_lines):
                # 用正則表達式移除前方的 "1. " 編號，只保留翻譯文字
                clean_zh = re.sub(r'^\d+\.\s*', '', translated_lines[i]).strip()
                item['title_zh'] = clean_zh
            else:
                item['title_zh'] = item['title'] # 翻譯失敗時的備用方案
        return news_list
    except Exception as e:
        print(f"❌ 翻譯失敗: {e}")
        for item in news_list: item['title_zh'] = item['title']
        return news_list

# ==========================================
# 5. Telegram 訊息發送
# ==========================================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, data=payload)

# ==========================================
# 6. 主程式
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動全球突發新聞中文化雷達...")
    history = load_history()
    
    raw_news = fetch_breaking_news()
    
    # 過濾舊新聞
    new_updates = [item for item in raw_news if str(hash(item['title'])) not in history]
    
    if new_updates:
        print(f"✅ 抓到 {len(new_updates)} 則最新突發新聞，準備翻譯...")
        
        # 進行翻譯
        translated_updates = translate_to_zh(new_updates)
        
        # 組合推播訊息
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg_lines = [f"🌍 <b>全球突發新聞快訊</b> ({current_time})\n"]
        
        for item in translated_updates:
            # 訊息格式：[來源] 中文翻譯標題 (閱讀原文)
            msg_lines.append(f"▪️ <b>[{item['source']}]</b> {item['title_zh']} <a href='{item['link']}'>[原文]</a>")
            
            # 記錄原文 Hash 避免重複發送
            save_history(str(hash(item['title'])))
            
        final_message = "\n\n".join(msg_lines)
        send_telegram(final_message)
        print("📱 已成功發送中文快訊至 Telegram。")
    else:
        print("⏭️ 暫無最新突發新聞，略過發送。")
