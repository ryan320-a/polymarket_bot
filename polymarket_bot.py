import feedparser
import requests
from openai import OpenAI

# ==========================================
# 1. 系統設定區
# ==========================================
DEEPSEEK_API_KEY = "sk-517d8baa3a174590a5a8bedfe5b3b236"
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

TELEGRAM_TOKEN = "9106778418:AAEDd0O_Wpwd7rAojcaOodlAVdDzjP1G0r8"
TELEGRAM_CHAT_ID = "1290187511" 

current_target = {
    "title": "聯準會 (Fed) 降息預測",
    "rss_url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    "keywords": ["Fed", "rate", "powell", "inflation", "cut"]
}

# ==========================================
# 2. 核心功能模組
# ==========================================
def send_telegram_message(text):
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
            print(f"❌ Telegram 發送失敗，錯誤碼: {response.status_code}, 原因: {response.text}")
    except Exception as e:
        print(f"❌ Telegram 請求發生例外錯誤: {e}")

def ask_deepseek_probability(news_title):
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
         return 50

# ==========================================
# 3. 實戰掃描主程式
# ==========================================
def run_production_scan():
    print(f"🚀 啟動正式版掃描...")
    print(f"🎯 鎖定目標: {current_target['title']}")
    
    url = current_target["rss_url"]
    keywords = current_target["keywords"]
    
    try:
        feed = feedparser.parse(url)
        print(f"✅ 成功獲取 RSS 列表，正在比對關鍵字...")
        
        for entry in feed.entries[:5]:
            title = entry.title
            
            # 只有當標題包含關鍵字時，才花費 API 額度請 DeepSeek 分析
            if any(kw.lower() in title.lower() for kw in keywords):
                print(f"🚨 觸發關鍵字: {title}")
                
                probability = ask_deepseek_probability(title)
                print(f"🧠 DeepSeek 判定發生機率: {probability}%")
                
                # 實戰門檻：機率高於 70% 或低於 30% 才發送警報
                if probability >= 70 or probability <= 30: 
                    msg = (
                        f"🚨 <b>Polymarket 實戰警報</b> 🚨\n\n"
                        f"<b>賭盤:</b> {current_target['title']}\n"
                        f"<b>新聞:</b> {title}\n"
                        f"<b>AI 勝率預估:</b> {probability}%\n\n"
                        f"<a href='{entry.link}'>閱讀原文</a>"
                    )
                    send_telegram_message(msg)
                    print(f"✅ 已發送高價值情報。")
                else:
                    print(f"⚠️ 機率 ({probability}%) 未達發送門檻，略過。")
                    
    except Exception as e:
        print(f"❌ 執行過程中發生錯誤: {e}")

if __name__ == "__main__":
    run_production_scan()
    print("✅ 掃描任務執行完畢，程式安全關閉。")
