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

# ==========================================
# 3. 強制測試掃描 (無條件觸發)
# ==========================================
def run_force_test():
    print(f"🚀 啟動強制測試...")
    
    # 【測試 1】一啟動就發送打招呼訊息
    send_telegram_message("🤖 <b>系統測試</b>\n\n你的 GitHub Actions 機器人連線正常！如果你看到這則訊息，代表 Telegram 設定完全沒問題，API Token 與 Chat ID 都正確。")
    
    url = current_target["rss_url"]
    try:
        feed = feedparser.parse(url)
        print(f"✅ 成功獲取 RSS 列表，準備抓取最新一篇新聞...")
        
        # 只抓最新的第 1 篇，並且【跳過關鍵字檢查】，直接發送
        for entry in feed.entries[:1]:
            title = entry.title
            print(f"🔍 檢查新聞: {title}")
            print(f"🚨 [測試模式] 強制發送給 Telegram...")
            
            msg = (
                f"🚨 <b>Polymarket 抓取測試</b> 🚨\n\n"
                f"<b>這是最新的一篇新聞:</b> {title}\n\n"
                f"<a href='{entry.link}'>閱讀原文</a>"
            )
            send_telegram_message(msg)
                    
    except Exception as e:
        print(f"❌ 執行過程中發生錯誤: {e}")

if __name__ == "__main__":
    run_force_test()
    print("✅ 測試任務執行完畢。")
