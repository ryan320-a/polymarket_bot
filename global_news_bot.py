import os
import re
import json
import html
import time
import requests
import feedparser
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from openai import OpenAI

# ==========================================
# 1. API 與系統設定
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or "sk-517d8baa3a174590a5a8bedfe5b3b236"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or "9106778418:AAEDd0O_Wpwd7rAojcaOodlAVdDzjP1G0r8"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or "1290187511"

SENT_LOG_FILE = "sent_global_news.txt"
TOPIC_MEMORY_FILE = "covered_topics.json"
DAILY_POOL_FILE = "daily_digest_pool.json"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ==========================================
# 2. 全新 15 大領域 × 全球多語言資料來源矩陣
# ==========================================
TOPIC_SOURCES = {
    "政治新聞": [
        ("BBC Politics [英]", "http://feeds.bbci.co.uk/news/politics/rss.xml"),
        ("Politico [美]", "https://rss.politico.com/politics-news.xml"),
        ("NHK 政治 [日]", "https://www3.nhk.or.jp/rss/news/cat4.xml"),
        ("Yonhap 政治 [韓]", "https://www.yna.co.kr/rss/politics.xml"),
        ("Le Monde Politique [法]", "https://www.lemonde.fr/politique/rss_full.xml"),
        ("Tagesschau Politik [德]", "https://www.tagesschau.de/xml/rss/politik-inland/")
    ],
    "國際新聞": [
        ("BBC World [英]", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Al Jazeera [阿]", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f303/73d0e1b4-532f-45ef-b135-bfdff8b8cab9"),
        ("Le Monde International [法]", "https://www.lemonde.fr/international/rss_full.xml"),
        ("Der Spiegel International [德]", "https://www.spiegel.de/international/index.rss"),
        ("El País Internacional [西]", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
        ("TASS [俄]", "https://tass.ru/rss/v2.xml")
    ],
    "財經／經濟新聞": [
        ("CNBC Markets [英]", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
        ("Yahoo Finance [英]", "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US"),
        ("Financial Times [英]", "https://www.ft.com/rss/home"),
        ("WSJ Markets [英]", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
        ("Nikkei 經濟 [日]", "https://assets.wor.jp/rss/rdf/nikkei/news.rdf"),
        ("Handelsblatt [德]", "https://www.handelsblatt.com/contentexport/feed/top-themen")
    ],
    "社會新聞": [
        ("BBC Society [英]", "http://feeds.bbci.co.uk/news/education/rss.xml"),
        ("The Guardian Society [英]", "https://www.theguardian.com/society/rss"),
        ("Yonhap 社會 [韓]", "https://www.yna.co.kr/rss/society.xml"),
        ("NHK 社會 [日]", "https://www3.nhk.or.jp/rss/news/cat1.xml")
    ],
    "地方新聞": [
        ("BBC England [英]", "http://feeds.bbci.co.uk/news/england/rss.xml"),
        ("CBC Local [加]", "https://www.cbc.ca/cmlink/rss-canada"),
        ("ABC Local News [美]", "https://abcnews.go.com/abcnews/topstories")
    ],
    "科技新聞": [
        ("TechCrunch [英]", "https://techcrunch.com/feed/"),
        ("The Verge [英]", "https://www.theverge.com/rss/index.xml"),
        ("Wired [英]", "https://www.wired.com/feed/rss"),
        ("MIT Technology Review [英]", "https://www.technologyreview.com/feed/"),
        ("ITmedia 科技 [日]", "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
        ("Heise Online 科技 [德]", "https://www.heise.de/rss/heise-atom.xml")
    ],
    "健康醫療新聞": [
        ("STAT News [英]", "https://www.statnews.com/feed/"),
        ("Medical News Today [英]", "https://rss.medicalnewstoday.com/featurednews.xml"),
        ("WHO News [國際]", "https://www.who.int/rss-feeds/news-english.xml"),
        ("ScienceDaily Health [英]", "https://www.sciencedaily.com/rss/health_medicine.xml")
    ],
    "教育新聞": [
        ("BBC Education [英]", "http://feeds.bbci.co.uk/news/education/rss.xml"),
        ("The Guardian Education [英]", "https://www.theguardian.com/education/rss"),
        ("Yonhap 教育 [韓]", "https://www.yna.co.kr/rss/education.xml")
    ],
    "文化／娛樂新聞": [
        ("BBC Arts & Culture [英]", "http://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),
        ("The Guardian Culture [英]", "https://www.theguardian.com/culture/rss"),
        ("Variety 影視娛樂 [美]", "https://variety.com/feed/"),
        ("Hollywood Reporter [美]", "https://www.hollywoodreporter.com/feed/")
    ],
    "體育新聞": [
        ("BBC Sport [英]", "http://feeds.bbci.co.uk/news/10352335/rss.xml"),
        ("ESPN Top Stories [美]", "https://www.espn.com/espn/rss/news"),
        ("L'Équipe [法]", "https://www.lequipe.fr/rss/actu_rss.xml"),
        ("NHK 體育 [日]", "https://www3.nhk.or.jp/rss/news/cat3.xml")
    ],
    "環境／氣候新聞": [
        ("BBC Science & Environment [英]", "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("The Guardian Environment [英]", "https://www.theguardian.com/environment/rss"),
        ("ScienceDaily Earth [英]", "https://www.sciencedaily.com/rss/earth_climate.xml")
    ],
    "法律／治安新聞": [
        ("BBC Law [英]", "http://feeds.bbci.co.uk/news/uk-10834376/rss.xml"),
        ("The Guardian Law [英]", "https://www.theguardian.com/law/rss"),
        ("NHK 社會法庭 [日]", "https://www3.nhk.or.jp/rss/news/cat1.xml")
    ],
    "軍事新聞": [
        ("Defense News [美]", "https://www.defensenews.com/arc/outboundfeeds/rss/"),
        ("Janes 國防防務 [英]", "https://www.janes.com/rss"),
        ("TASS 軍事 [俄]", "https://tass.ru/rss/v2.xml")
    ],
    "生活／消費新聞": [
        ("BBC Lifestyle [英]", "http://feeds.bbci.co.uk/news/lifestyle-46487779/rss.xml"),
        ("The Guardian Life & Style [英]", "https://www.theguardian.com/lifeandstyle/rss"),
        ("CNET Consumer [美]", "https://www.cnet.com/rss/news/")
    ],
    "天氣／交通新聞": [
        ("BBC Weather/Transport [英]", "http://feeds.bbci.co.uk/news/uk-10738600/rss.xml"),
        ("NHK 災害氣象 [日]", "https://www3.nhk.or.jp/rss/news/cat6.xml")
    ]
}

# ==========================================
# 3. 記憶庫與 24 小時晨報素材池管理
# ==========================================
def load_history():
    if not os.path.exists(SENT_LOG_FILE):
        return set()
    with open(SENT_LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_history(text_hash):
    with open(SENT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{text_hash}\n")

def load_recent_topics():
    if not os.path.exists(TOPIC_MEMORY_FILE):
        return []
    try:
        with open(TOPIC_MEMORY_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        cutoff = time.time() - 24 * 3600
        return [r for r in records if r.get("timestamp", 0) > cutoff]
    except Exception:
        return []

def save_new_topics(new_topic_labels):
    records = load_recent_topics()
    now = time.time()
    for label in new_topic_labels:
        if label.strip():
            records.append({"topic": label.strip(), "timestamp": now})
    with open(TOPIC_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def append_to_daily_pool(hk_time_str, summary_text, items):
    pool = []
    if os.path.exists(DAILY_POOL_FILE):
        try:
            with open(DAILY_POOL_FILE, "r", encoding="utf-8") as f:
                pool = json.load(f)
        except Exception:
            pool = []
            
    cutoff = time.time() - 25 * 3600
    pool = [entry for entry in pool if entry.get("timestamp", 0) > cutoff]
    
    pool.append({
        "timestamp": time.time(),
        "hk_time": hk_time_str,
        "hourly_brief": summary_text[:900],
        "top_articles": [
            {
                "apa_intext": i["apa_intext"],
                "apa_ref": i["apa_ref"],
                "title": i["title"],
                "link": i["link"]
            } for i in items[:4]
        ]
    })
    with open(DAILY_POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)

def load_and_clear_daily_pool():
    if not os.path.exists(DAILY_POOL_FILE):
        return []
    try:
        with open(DAILY_POOL_FILE, "r", encoding="utf-8") as f:
            pool = json.load(f)
        with open(DAILY_POOL_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return pool
    except Exception:
        return []

# ==========================================
# 4. 即時全網熱搜雷達
# ==========================================
def fetch_realtime_hot_keywords():
    trend_feeds = [
        "https://trends.google.com/trending/rss?geo=US",
        "https://trends.google.com/trending/rss?geo=HK",
        "https://trends.google.com/trending/rss?geo=JP",
        "https://trends.google.com/trending/rss?geo=GB",
    ]
    hot_words = set()
    trend_list_ordered = []
    for url in trend_feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                word = entry.title.strip()
                if len(word) >= 2:
                    hot_words.add(word.lower())
                    if word not in trend_list_ordered:
                        trend_list_ordered.append(word)
        except Exception:
            pass
    core_boost = {"ai", "openai", "nvidia", "fed", "bitcoin", "btc", "rate", "tsmc", "trump", "china", "eu"}
    hot_words.update(core_boost)
    return hot_words, trend_list_ordered[:20]

# ==========================================
# 5. APA 7th 元數據生成器與多領域媒體掃描
# ==========================================
def format_apa_metadata(source_label, entry):
    clean_org = re.sub(r"\s*\[.*?\]", "", source_label).strip()
    raw_author = entry.get("author", "").strip()
    author_citation_name = clean_org
    author_ref_name = f"{clean_org}."
    
    if raw_author and len(raw_author) < 40 and "@" not in raw_author and "http" not in raw_author and raw_author.lower() != clean_org.lower():
        parts = [p for p in re.split(r"\s+", raw_author) if p]
        if len(parts) >= 2 and all(p.isascii() for p in parts):
            surname = parts[-1]
            initials = " ".join([f"{p[0].upper()}." for p in parts[:-1]])
            author_citation_name = surname
            author_ref_name = f"{surname}, {initials}"
        else:
            author_citation_name = raw_author
            author_ref_name = f"{raw_author}."

    year_str = "n.d."
    full_date_str = "n.d."
    published_ts = 0
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        published_ts = time.mktime(entry.published_parsed)
        dt = datetime(*entry.published_parsed[:6])
        year_str = str(dt.year)
        full_date_str = dt.strftime("%Y, %B %-d") if os.name != "nt" else dt.strftime("%Y, %B %d").replace(" 0", " ")

    apa_intext = f"({author_citation_name}, {year_str})"
    clean_title = entry.title.strip().rstrip(".")
    
    if author_ref_name.rstrip(".") == clean_org:
        apa_ref = f"{author_ref_name} ({full_date_str}). <i>{html.escape(clean_title)}</i>. <a href='{entry.link}'>{entry.link}</a>"
    else:
        apa_ref = f"{author_ref_name} ({full_date_str}). <i>{html.escape(clean_title)}</i>. {html.escape(clean_org)}. <a href='{entry.link}'>{entry.link}</a>"
        
    return published_ts, apa_intext, apa_ref

def fetch_single_rss(args):
    category, source_name, rss_url = args
    items = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:2]:
            published_ts, apa_intext, apa_ref = format_apa_metadata(source_name, entry)
            items.append({
                "category": category,
                "source": source_name,
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", ""),
                "published_ts": published_ts,
                "apa_intext": apa_intext,
                "apa_ref": apa_ref
            })
    except Exception:
        pass
    return items

def fetch_and_score_all_news(hot_keywords, history):
    tasks = []
    for category, sources in TOPIC_SOURCES.items():
        for source_name, rss_url in sources:
            tasks.append((category, source_name, rss_url))
            
    all_raw = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(fetch_single_rss, tasks)
        for res_list in results:
            all_raw.extend(res_list)
            
    now_utc = time.time()
    scored_items = []
    
    for item in all_raw:
        if str(hash(item['title'])) in history:
            continue
            
        score = 0
        title_lower = item['title'].lower()
        
        if item['published_ts'] > 0:
            age_hours = (now_utc - item['published_ts']) / 3600
            if age_hours <= 1.5:
                score += 10
            elif age_hours <= 4:
                score += 5
                
        matched_trends = [kw for kw in hot_keywords if kw in title_lower]
        if matched_trends:
            score += 8 * len(matched_trends)
            item['matched_trends'] = matched_trends
        else:
            item['matched_trends'] = []
            
        item['score'] = score
        scored_items.append(item)
        
    scored_items.sort(key=lambda x: x['score'], reverse=True)
    return scored_items

# ==========================================
# 6. 多語言網頁內文爬蟲
# ==========================================
def fetch_article_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=7)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 15])
        return full_text[:750] if full_text else ""
    except Exception:
        return ""

# ==========================================
# 7A. 每小時常規模式
# ==========================================
def analyze_hourly_news(combined_news, recent_topics):
    avoid_list_str = "、".join([r["topic"] for r in recent_topics]) if recent_topics else "無"
    
    prompt = f"""
你現在是一位精通 15 大新聞領域（政治、國際、財經、社會、地方、科技、健康、教育、文化、體育、環境、法律、軍事、生活、天氣）與學術引用規範（APA 第七版）的「全球趨勢首席情報官」。

【過去 24 小時已報導過的話題清單（語義去重避開區）】：
{avoid_list_str}
※ 嚴格規定：除非上述舊話題發生了重大新轉折，否則請絕對避開重複報導！

【過去 1 小時 15 大領域高熱度新聞池（每篇皆附 APA 文內引用標籤）】：
{combined_news}

【核心寫作與 APA 引用要求】：
1. 請從 15 大領域中挑選出「2 件最具全球或社會影響力的跨領域大事」（命名為【焦點一】與【焦點二】）。
2. 強制執行 APA 第七版文內引用：引述事實或觀點時，必須在句末加上對應的 APA 括號引用（例如：`(BBC News, 2026)`）。
3. 嚴格按照以下五段式結構輸出（不要在正文中加入網址、星號 `*` 或井字號 `#`）：

【焦點一：（填入 15 大領域中的對應分類名稱）】
1. 🔥 頭條焦點秒懂：用最簡單的 1-2 句話綜合點出核心全貌，並附上 APA 文內引用。
2. 💡 專家白話解說：將複雜概念用日常比喻解釋清楚。
3. 🗣️ 輿論與市場風向：綜合各方反應與輿論情緒。
4. 🔮 未來潛在影響：對未來發展或普通人生活的具體影響。
5. 📜 歷史借鏡與參考：歷史上是否有類似事件及啟示。

（空一行分隔）

【焦點二：（填入另一分類名稱）】
1. 🔥 頭條焦點秒懂：...
2. 💡 專家白話解說：...
3. 🗣️ 輿論與市場風向：...
4. 🔮 未來潛在影響：...
5. 📜 歷史借鏡與參考：...

---
COVERED_TOPICS: 焦點一核心關鍵詞(4-8字), 焦點二核心關鍵詞(4-8字)
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=2100
        ).choices[0].message.content.strip()
        return res
    except Exception as e:
        print(f"❌ DeepSeek 每小時分析失敗: {e}")
        return ""

# ==========================================
# 7B. 早上 07:00 晨間特別版：15 大領域 24 小時大整合
# ==========================================
def analyze_daily_24h_digest(daily_pool, current_trends, latest_news_text):
    pool_summary = []
    for entry in daily_pool:
        pool_summary.append(f"【時段 {entry['hk_time']}】\n{entry['hourly_brief']}\n---")
    accumulated_text = "\n".join(pool_summary) if pool_summary else "（請依據最新情報總結）"
    trends_str = "、".join(current_trends) if current_trends else "政策變革、科技突破、地緣政治"

    prompt = f"""
你現在是「全球情報總編輯」，現在是香港時間早上 07:00。
請為讀者撰寫一份涵蓋 15 大領域的【過去 24 小時全球 Hot Topic 深度大整合與晨間戰略簡報】，並嚴格遵循 APA 第七版文內引用規範。

【全網熱搜風向】：{trends_str}
【過去 24 小時累積重大事件紀錄】：{accumulated_text}
【最新補充情報】：{latest_news_text}

嚴格包含以下五大晨間板塊（不要使用星號 `*` 或井字號 `#`）：
🌅 一、 過去 24 小時 15 大領域核心主線（3 大最火熱 Hot Topic 總結）
🔗 二、 隱藏的蝴蝶效應（跨領域深度關聯分析）
🌡️ 三、 全球與社會輿論總體溫度計
📜 四、 大歷史週期對照
🎯 五、 今日重點關注與行動指南（未來 24 小時雷達）
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=2600
        ).choices[0].message.content.strip()
        return res
    except Exception as e:
        print(f"❌ DeepSeek 07:00 晨間大整合失敗: {e}")
        return ""

# ==========================================
# 8. Telegram 推播模組
# ==========================================
def send_telegram_html(briefing_text, reference_items, is_daily_morning=False):
    clean_body = briefing_text
    extracted_topics = []
    
    match = re.search(r"COVERED_TOPICS:\s*(.+)", briefing_text)
    if match:
        raw_topics = match.group(1)
        extracted_topics = [t.strip() for t in re.split(r"[,，、]", raw_topics) if t.strip()]
        clean_body = briefing_text[:match.start()].strip()

    safe_body = html.escape(clean_body)
    hk_time = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    
    if is_daily_morning:
        header = f"☀️ <b>【晨間 07:00 15大領域特別版】過去 24 小時全球 Hot Topic 深度大整合</b> ({hk_time} HKT)\n\n"
    else:
        header = f"🌐 <b>15大領域全球情報綜合簡報</b> ({hk_time} HKT)\n\n"
    
    unique_refs = {}
    for item in reference_items[:12]:
        ref_str = item['apa_ref']
        unique_refs[ref_str] = ref_str
    sorted_refs = sorted(unique_refs.values(), key=lambda s: re.sub(r"<.*?>", "", s).lower())
    
    ref_lines = ["\n\n━━━━━━━━━━━━━━━━━━\n📚 <b>References (APA 7th Edition)</b>\n"]
    for ref_entry in sorted_refs:
        ref_lines.append(f"• {ref_entry}")
        
    full_message = header + safe_body + "\n".join(ref_lines)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    if len(full_message) <= 4050:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": full_message, "parse_mode": "HTML", "disable_web_page_preview": True}
        res = requests.post(url, data=payload)
        if res.status_code == 200:
            print("📱 已成功發送 15 大領域簡報至 Telegram！")
        else:
            print(f"❌ Telegram 發送失敗: {res.text}")
    else:
        part1 = header + safe_body
        part2 = "📚 <b>References (APA 7th Edition)</b>\n\n" + "\n".join(ref_lines[1:])
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": part1[:4050], "parse_mode": "HTML", "disable_web_page_preview": True})
        time.sleep(1)
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": part2[:4050], "parse_mode": "HTML", "disable_web_page_preview": True})
        print("📱 已成功分段發送 15 大領域長篇報告與 APA 7th 參考文獻！")
        
    return extracted_topics, clean_body

# ==========================================
# 9. 主程式
# ==========================================
if __name__ == "__main__":
    hk_now = datetime.utcnow() + timedelta(hours=8)
    hk_hour = hk_now.hour
    hk_time_str = hk_now.strftime("%Y-%m-%d %H:%M")
    
    print(f"🚀 啟動 15 大領域全球情報引擎 | 當前香港時間：{hk_time_str}")
    history = load_history()
    recent_topics = load_recent_topics()
    hot_keywords, ordered_trends = fetch_realtime_hot_keywords()
    
    ranked_news = fetch_and_score_all_news(hot_keywords, history)
    
    if ranked_news:
        selected_updates = []
        seen_categories = {}
        for item in ranked_news:
            cat = item['category']
            if seen_categories.get(cat, 0) < 2:
                selected_updates.append(item)
                seen_categories[cat] = seen_categories.get(cat, 0) + 1
            if len(selected_updates) >= 15:
                break
                
        def enrich_article(item):
            content = fetch_article_content(item['link'])
            body = content if len(content) > 50 else item['summary']
            trend_tag = f" [熱搜命中: {','.join(item['matched_trends'])}]" if item['matched_trends'] else ""
            return (
                f"【領域：{item['category']} | 媒體：{item['source']}{trend_tag}】\n"
                f"【APA文內引用格式】：{item['apa_intext']}\n"
                f"原文標題：{item['title']}\n"
                f"原文內文：{body}\n---"
            )

        with ThreadPoolExecutor(max_workers=10) as executor:
            compiled_articles = list(executor.map(enrich_article, selected_updates))
        combined_news_text = "\n".join(compiled_articles)
        
        if hk_hour == 7:
            print("☀️ 偵測到香港時間 07:00！啟動【15大領域 24 小時晨間大整合模式】...")
            daily_pool = load_and_clear_daily_pool()
            
            pool_links = []
            for entry in daily_pool:
                pool_links.extend(entry.get("top_articles", []))
            all_morning_refs = selected_updates[:5] + pool_links[:5]
            
            morning_report = analyze_daily_24h_digest(daily_pool, ordered_trends, combined_news_text)
            if morning_report:
                send_telegram_html(morning_report, all_morning_refs, is_daily_morning=True)
                for item in selected_updates:
                    save_history(str(hash(item['title'])))
        else:
            print("⏱️ 執行 15 大領域常規【每小時跨媒體綜合快報】...")
            hourly_report = analyze_hourly_news(combined_news_text, recent_topics)
            if hourly_report:
                new_topics, clean_brief = send_telegram_html(hourly_report, selected_updates, is_daily_morning=False)
                if new_topics:
                    save_new_topics(new_topics)
                append_to_daily_pool(hk_time_str, clean_brief, selected_updates)
                for item in selected_updates:
                    save_history(str(hash(item['title'])))
    else:
        print("⏭️ 暫無新進新聞，本小時略過。")
