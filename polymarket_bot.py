import feedparser
import requests
from openai import OpenAI

# ==========================================
# 1. 系統設定區 (已包含你的專屬 Key)
# ==========================================
# DeepSeek API
DEEPSEEK_API_KEY = "sk-517d8baa3a174590a5a8bedfe5b3b236"
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# Telegram Bot
TELEGRAM_TOKEN = "9106778418:AAEDd0O_Wpwd7rAojcaOodlAVdDzjP1G0r8"
TELEGRAM_CHAT_ID = "1290187511" 

# 監控目標
current_target = {
    "title": "聯準會 (Fed) 降息預測",
    "rss_url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    "keywords": ["Fed", "rate", "powell", "inflation", "cut"]
}

# ==========================================
# 2. 核心功能模組
# ==========================================
def send_telegram_message(text):
    """發送訊息到你的 Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("📱 已成功發送 Telegram 警報！")
        else:
            print(f"❌ Telegram 發送失敗，錯誤碼: {response.status_code}")
    except Exception as e:
        print(f"❌ Telegram 請求發生例外錯誤: {e}")

def ask_deepseek_probability(news_title):
    """要求 DeepSeek 評估新聞對賭盤的影響機率"""
    prompt = f"""
    目前 Polymarket 賭盤主題：{current_target['title']}
    突發新聞標題：{news_title}
    
    請判斷這則新聞發生後，該賭盤事件發生的「機率」。
    請只輸出 0 到 100 之間的單一數字。不要有任何解釋。
    """
    try:
         response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.0
        )
         return int(response.choices[0].message.content.strip())
    except Exception as e:
         print(f"❌ DeepSeek 分析失敗: {e}")
         return 50 # 失敗則給出中立機率 50%

# ==========================================
# 3. 單次掃描主程式 (給 GitHub Actions 執行)
# ==========================================
def run_single_scan():
    print(f"🚀 啟動 GitHub Actions 單次掃描...")
    print(f"🎯 鎖定目標: {current_target['title']}")
    print(f"📡 讀取來源: {current_target['rss_url']}")
    
    url = current_target["rss_url"]
    keywords = current_target["keywords"]
    
    try:
        feed = feedparser.parse(url)
        print(f"✅ 成功獲取 RSS 列表，共有 {len(feed.entries)} 篇文章。")
        
        # 為了避免 API 消耗過大，每次只檢查最新的 5 篇文章
        for entry in feed.entries[:5]:
            title = entry.title
            print(f"🔍 檢查新聞: {title}")
            
            # 檢查新聞標題是否包含任何一個關鍵字 (不分大小寫)
            if any(kw.lower() in title.lower() for kw in keywords):
                print(f"🚨 觸發關鍵字！準備交由 DeepSeek 分析...")
                
                probability = ask_deepseek_probability(title)
                print(f"🧠 DeepSeek 判定發生機率: {probability}%")
                
                # 判斷是否值得發送警報
                # 這裡設定機率 >= 0 只是為了方便你立刻測試。
                # 測試成功收到訊息後，建議改為：if probability >= 70 or probability <= 30:
                if probability >= 0: 
                    msg = (
                        f"🚨 <b>Polymarket 雲端掃描警報</b> 🚨\n\n"
                        f"<b>賭盤:</b> {current_target['title']}\n"
                        f"<b>新聞:</b> {title}\n"
                        f"<b>AI 勝率預估:</b> {probability}%\n\n"
                        f"<a href='{entry.link}'>閱讀原文</a>"
                    )
                    send_telegram_message(msg)
                    
    except Exception as e:
        print(f"❌ 執行過程中發生錯誤: {e}")

# ==========================================
# 4. 執行與結束
# ==========================================
if __name__ == "__main__":
    run_single_scan()
    print("✅ 掃描任務執行完畢，程式安全關閉。")
