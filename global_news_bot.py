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
# 1. API 與系統設定 (優先讀取 GitHub Secrets)
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or "sk-517d8baa3a174590a5a8bedfe5b3b236"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or "9106778418:AAEDd0O_Wpwd7rAojcaOodlAVdDzjP1G0r8"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or "1290187511"

SENT_LOG_FILE = "sent_global_news.txt"
TOPIC_MEMORY_FILE = "covered_topics.json"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ==========================================
# 2. 五大領域 × 20 個全球多語言資料來源 (共 100 源)
# ==========================================
TOPIC_SOURCES = {
    "國際政經與突發": [
        ("BBC World [英]", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("NHK 日本放送協會 [日]", "https://www3.nhk.or.jp/rss/news/cat0.xml"),
        ("Yonhap 韓聯社 [韓]", "https://www.yna.co.kr/rss/news.xml"),
        ("Le Monde 世界報 [法]", "https://www.lemonde.fr/rss/une.xml"),
        ("Der Spiegel 明鏡周刊 [德]", "https://www.spiegel.de/international/index.rss"),
        ("El País 國家報 [西]", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
        ("Al Jazeera 半島電視台 [阿]", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f303/73d0e1b4-532f-45ef-b135-bfdff8b8cab9"),
        ("Folha de S.Paulo 聖保羅頁報 [葡]", "https://feeds.folha.uol.com.br/mundo/rss091.xml"),
        ("TASS 塔斯社 [俄]", "https://tass.ru/rss/v2.xml"),
        ("CNA 中央社 [繁中]", "https://feeds.feedburner.com/rsscna/intworld"),
        ("NYT 紐約時報國際 [英]", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
        ("Asahi 朝日新聞 [日]", "https://www.asahi.com/rss/asahi/newsheadlines.rdf"),
        ("Chosun 朝鮮日報 [韓]", "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
        ("France 24 法蘭西24 [法]", "https://www.france24.com/fr/rss"),
        ("Tagesschau 德國每日新聞 [德]", "https://www.tagesschau.de/infoservices/alle-meldungen-100~rss2.xml"),
        ("BBC Mundo 拉美新聞 [西]", "https://feeds.bbci.co.uk/mundo/rss.xml"),
        ("Sky News Arabia 天空新聞 [阿]", "https://www.skynewsarabia.com/web/rss"),
        ("ANSA 義大利安莎社 [義]", "https://www.ansa.it/sito/ansait_rss.xml"),
        ("The Guardian 衛報國際 [英]", "https://www.theguardian.com/world/rss"),
        ("SCMP 南華早報 [英/亞太]", "https://www.scmp.com/rss/91/feed")
    ],
    "華爾街與全球財經": [
        ("CNBC 財經 [英]", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
        ("Nikkei 日經新聞 [日]", "https://assets.wor.jp/rss/rdf/nikkei/news.rdf"),
        ("Maeil 每日經濟 [韓]", "https://www.mk.co.kr/rss/30000001/"),
        ("Les Echos 回聲報 [法]", "https://services.lesechos.fr/rss/les-echos-finance-marches.xml"),
        ("Handelsblatt 德國商報 [德]", "https://www.handelsblatt.com/contentexport/feed/top-themen"),
        ("Expansión 經濟人報 [西]", "https://e00-expansion.uecdn.es/rss/portada.xml"),
        ("Al Arabiya 阿拉比亞財經 [阿]", "https://www.alarabiya.net/.mrss/ar/aswaq.xml"),
        ("Valor Econômico 經濟價值報 [葡]", "https://pox.globo.com/rss/valor"),
        ("Kommersant 生意人報 [俄]", "https://www.kommersant.ru/RSS/news.xml"),
        ("經濟日報 [繁中]", "https://money.udn.com/rssfeed/news/1001/5591/5612?ch=fb_share"),
        ("Yahoo Finance 金融 [英]", "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US"),
        ("Toyo Keizai 東洋經濟 [日]", "https://toyokeizai.net/list/feed/rss"),
        ("Hankyung 韓國經濟 [韓]", "https://www.hankyung.com/feed/all-news"),
        ("La Tribune 論壇報 [法]", "https://www.latribune.fr/feed.xml"),
        ("WirtschaftsWoche 經濟周刊 [德]", "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen"),
        ("Cinco Días 財經日報 [西]", "https://feeds.elpais.com/mrss-s/pages/ep/site/cincodias.elpais.com/portada"),
        ("WSJ 華爾街日報 [英]", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
        ("Financial Times 金融時報 [英]", "https://www.ft.com/rss/home"),
        ("Il Sole 24 Ore 24小時太陽報 [義]", "https://www.ilsole24ore.com/rss/economia.xml"),
        ("MarketWatch 市場觀察 [英]", "http://feeds.marketwatch.com/marketwatch/topstories/")
    ],
    "前沿科技與 AI 動態": [
        ("TechCrunch 科技 [英]", "https://techcrunch.com/feed/"),
        ("ITmedia 科技新聞 [日]", "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
        ("ZDNet Korea 科技 [韓]", "https://zdnet.co.kr/news_rss.asp"),
        ("Frandroid 數碼科技 [法]", "https://www.frandroid.com/feed"),
        ("Heise Online 德國科技 [德]", "https://www.heise.de/rss/heise-atom.xml"),
        ("Xataka 科技前線 [西]", "https://www.xataka.com/feedburner.xml"),
        ("AITNews 阿拉伯科技 [阿]", "https://aitnews.com/feed/"),
        ("Tecnoblog 巴西科技 [葡]", "https://tecnoblog.net/feed/"),
        ("Habr 俄語極客社區 [俄]", "https://habr.com/ru/rss/articles/all/"),
        ("科技新報 TechNews [繁中]", "https://technews.tw/feed/"),
        ("The Verge 數碼趨勢 [英]", "https://www.theverge.com/rss/index.xml"),
        ("Gigazine 科技新知 [日]", "https://gigazine.net/news/rss_2.0/"),
        ("Bloter 韓國數位媒體 [韓]", "https://www.bloter.net/rss/allArticle.xml"),
        ("Numerama 數位文化 [法]", "https://www.numerama.com/feed/"),
        ("Golem.de 德國IT新聞 [德]", "https://rss.golem.de/rss.php?feed=RSS2.0"),
        ("Genbeta 軟體與AI [西]", "https://www.genbeta.com/feedburner.xml"),
        ("MIT Technology Review [英]", "https://www.technologyreview.com/feed/"),
        ("Wired 連線雜誌 [英]", "https://www.wired.com/feed/rss"),
        ("Ars Technica 硬核科技 [英]", "https://feeds.arstechnica.com/arstechnica/index"),
        ("Hacker News 熱門科技 [英]", "https://hnrss.org/frontpage")
    ],
    "科學探索與健康醫療": [
        ("ScienceDaily 科學新知 [英]", "https://www.sciencedaily.com/rss/all.xml"),
        ("Nature Asia 自然亞太 [日]", "https://www.natureasia.com/ja-jp/rss/nature"),
        ("Science Times 韓國科學 [韓]", "https://www.sciencetimes.co.kr/feed/"),
        ("Futura Sciences 未來科學 [法]", "https://www.futura-sciences.com/rss/actualites.xml"),
        ("Spektrum 德國科學人 [德]", "https://www.spektrum.de/alias/rss/spektrum-de-rss-feed/996406"),
        ("Agencia SINC 西班牙科學 [西]", "https://www.agenciasinc.es/feed/noticias"),
        ("Nature Arabic 自然阿拉伯版 [阿]", "https://arabicedition.nature.com/rss"),
        ("Superinteressante 科學雜誌 [葡]", "https://super.abril.com.br/feed/"),
        ("N+1 俄語科學媒體 [俄]", "https://nplus1.ru/rss"),
        ("泛科學 PanSci [繁中]", "https://pansci.asia/feed"),
        ("Nature 自然期刊 [英]", "https://www.nature.com/nature.rss"),
        ("New Scientist 新科學家 [英]", "https://www.newscientist.com/feed/home/"),
        ("NASA 太空總署 [英]", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
        ("Sciences et Avenir 科學與未來 [法]", "https://www.sciencesetavenir.fr/rss.xml"),
        ("Scinexx 德國科學網 [德]", "https://www.scinexx.de/feed/"),
        ("Muy Interesante 科學探索 [西]", "https://www.muyinteresante.es/feed"),
        ("STAT News 生物醫藥 [英]", "https://www.statnews.com/feed/"),
        ("WHO 世界衛生組織 [英]", "https://www.who.int/rss-feeds/news-english.xml"),
        ("Phys.org 物理與科學 [英]", "https://phys.org/rss-feed/"),
        ("Space.com 太空探索 [英]", "https://www.space.com/feeds/all")
    ],
    "加密貨幣與 Web3": [
        ("CoinDesk 幣圈權威 [英]", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinPost 日本最大幣媒 [日]", "https://coinpost.jp/?feed=rss2"),
        ("TokenPost 韓國區塊鏈 [韓]", "https://www.tokenpost.kr/rss"),
        ("Journal du Coin 法語幣媒 [法]", "https://journalducoin.com/feed/"),
        ("BTC-ECHO 德語區塊鏈 [德]", "https://www.btc-echo.de/feed/"),
        ("CriptoNoticias 西語幣訊 [西]", "https://www.criptonoticias.com/feed/"),
        ("Arabian Crypto 阿拉伯幣圈 [阿]", "https://arabiancrypto.com/feed/"),
        ("Portal do Bitcoin 巴西幣媒 [葡]", "https://portaldobitcoin.uol.com.br/feed/"),
        ("ForkLog 俄語區塊鏈權威 [俄]", "https://forklog.com/feed"),
        ("動區動趨 BlockTempo [繁中]", "https://www.blocktempo.com/feed/"),
        ("Cointelegraph 幣電訊 [英]", "https://cointelegraph.com/rss"),
        ("CoinTelegraph Japan [日]", "https://jp.cointelegraph.com/rss"),
        ("BlockMedia 韓國區塊鏈 [韓]", "https://www.blockmedia.co.kr/feed"),
        ("Cryptoast 法語加密新聞 [法]", "https://cryptoast.fr/feed/"),
        ("Blocktrainer 德語比特幣 [德]", "https://www.blocktrainer.de/feed/"),
        ("DiarioBitcoin 西語比特幣 [西]", "https://www.diariobitcoin.com/feed/"),
        ("Decrypt Web3 媒體 [英]", "https://decrypt.co/feed"),
        ("The Block 區塊鏈研究 [英]", "https://www.theblock.co/rss.xml"),
        ("Cointelegraph Brasil [葡]", "https://br.cointelegraph.com/rss"),
        ("Bits.media 俄語加密媒體 [俄]", "https://bits.media/rss2/")
    ]
}

# ==========================================
# 3. 24小時語義話題記憶 & 網址去重模組
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
    """讀取過去 24 小時內已經報導過的核心事件標籤"""
    if not os.path.exists(TOPIC_MEMORY_FILE):
        return []
    try:
        with open(TOPIC_MEMORY_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        cutoff = time.time() - 24 * 3600
        valid_records = [r for r in records if r.get("timestamp", 0) > cutoff]
        return valid_records
    except Exception:
        return []

def save_new_topics(new_topic_labels):
    """將本次已報導的事件寫入 24 小時語義記憶庫"""
    records = load_recent_topics()
    now = time.time()
    for label in new_topic_labels:
        if label.strip():
            records.append({"topic": label.strip(), "timestamp": now})
    with open(TOPIC_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

# ==========================================
# 4. 即時全網熱搜雷達 (Google Trends 多國熱搜 + 科技熱詞)
# ==========================================
def fetch_realtime_hot_keywords():
    """自動抓取全球多國過去 1 小時飆升搜尋關鍵字，作為動態加權依據"""
    trend_feeds = [
        "https://trends.google.com/trending/rss?geo=US", # 美國熱搜
        "https://trends.google.com/trending/rss?geo=HK", # 香港熱搜
        "https://trends.google.com/trending/rss?geo=JP", # 日本熱搜
        "https://trends.google.com/trending/rss?geo=GB", # 英國熱搜
    ]
    hot_words = set()
    for url in trend_feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                word = entry.title.strip().lower()
                if len(word) >= 2:
                    hot_words.add(word)
        except Exception:
            pass
    # 額外加入固定高價值核心追蹤詞
    core_boost = {"ai", "openai", "nvidia", "fed", "bitcoin", "btc", "rate", "tsmc", "trump", "china", "eu"}
    hot_words.update(core_boost)
    print(f"🔥 本小時全網熱搜加權關鍵字庫已載入 ({len(hot_words)} 個熱詞)")
    return hot_words

# ==========================================
# 5. 全量掃描 100 大多語言媒體 & 過去 1 小時熱度篩選
# ==========================================
def fetch_single_rss(args):
    category, source_name, rss_url = args
    items = []
    try:
        feed = feedparser.parse(rss_url)
        # 每個媒體抓取最新 2 則，以捕捉過去 1 小時內的多源交叉報導
        for entry in feed.entries[:2]:
            published_ts = 0
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_ts = time.mktime(entry.published_parsed)
            items.append({
                "category": category,
                "source": source_name,
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", ""),
                "published_ts": published_ts
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
    # 25 線程並行掃描全部 100 個全球來源，約 6-8 秒完成
    with ThreadPoolExecutor(max_workers=25) as executor:
        results = executor.map(fetch_single_rss, tasks)
        for res_list in results:
            all_raw.extend(res_list)
            
    now_utc = time.time()
    scored_items = []
    
    for item in all_raw:
        # 排除已經抓過的完全相同網址/標題
        if str(hash(item['title'])) in history:
            continue
            
        score = 0
        title_lower = item['title'].lower()
        
        # 1. 時效性加分：過去 2 小時內發布的新聞給予高權重
        if item['published_ts'] > 0:
            age_hours = (now_utc - item['published_ts']) / 3600
            if age_hours <= 1.5:
                score += 10
            elif age_hours <= 4:
                score += 5
                
        # 2. 熱搜關鍵字加權：命中 Google Trends 當下熱搜詞大幅加分
        matched_trends = [kw for kw in hot_keywords if kw in title_lower]
        if matched_trends:
            score += 8 * len(matched_trends)
            item['matched_trends'] = matched_trends
        else:
            item['matched_trends'] = []
            
        item['score'] = score
        scored_items.append(item)
        
    # 依熱度與時效總分由高至低排序
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
# 7. DeepSeek 跨媒體綜合研判與語義去重引擎
# ==========================================
def analyze_and_synthesize(combined_news, recent_topics):
    avoid_list_str = "、".join([r["topic"] for r in recent_topics]) if recent_topics else "無（這是今日首次播報）"
    
    prompt = f"""
你現在是一位精通全球 10 國語言與世界歷史的「全球趨勢首席情報官」。
你的核心任務是進行「跨媒體情報聚類與深度綜合」——將多家不同國家、不同語言媒體對同一事件的報導融會貫通，轉化為外行人也能輕鬆秒懂的繁體中文白話簡報。

【重要：過去 24 小時已報導過的話題清單（語義去重避開區）】：
{avoid_list_str}
※ 嚴格規定：除非上述舊話題在過去 1 小時發生了「顛覆性的重大新轉折」，否則請**絕對避開**重複報導上述事件！請從下方新聞池中挖掘**全新的焦點事件**。

【過去 1 小時全球 100 大多語言媒體高熱度新聞池（已按全網熱搜關鍵字加權排序）】：
{combined_news}

【核心寫作要求】：
1. 請自動掃描上述各國語言情報，找出「目前最多家媒體同時報導、或熱搜權重最高的 2 件全新跨領域大事」（命名為【焦點一】與【焦點二】）。如果有多家不同媒體（例如同時有美媒、日媒、德媒）報導同一件事，請將這幾家媒體的觀點與細節**高度綜合**在一起寫！
2. 拒絕生硬機翻感，使用極度流暢、接地氣的繁體中文撰寫。
3. 嚴格按照以下獨立單元五段式結構輸出（不要在正文中加入任何網址、星號 `*` 或井字號 `#`）：

【焦點一：（填入領域名稱，並列出本次綜合參考的幾家媒體名稱）】
1. 🔥 頭條焦點秒懂：用最簡單的 1-2 句話，綜合多家媒體報導，點出這件事的核心全貌。
2. 💡 專家白話解說：將這件事背後的複雜概念、專有名詞或科學/商業原理，用日常生活的比喻解釋清楚。
3. 🗣️ 輿論與市場風向：綜合比較各國媒體（如歐美與亞洲視角）及市場投資者對這件事的看法與情緒。
4. 🔮 未來潛在影響：這件事接下來可能會對普通人的日常生活、工作型態、健康或經濟造成什麼具體影響？
5. 📜 歷史借鏡與參考：在人類歷史或過去幾十年的商業/金融/科技史上，有沒有類似的事件？當時的結局能給我們什麼啟示？

（空一行分隔）

【焦點二：（填入另一領域名稱，並列出本次綜合參考的幾家媒體名稱）】
1. 🔥 頭條焦點秒懂：...
2. 💡 專家白話解說：...
3. 🗣️ 輿論與市場風向：...
4. 🔮 未來潛在影響：...
5. 📜 歷史借鏡與參考：...

---
【系統記憶標籤】（此行非常重要，請務必在最底部輸出這一行，供程式寫入 24 小時防重複記憶庫，格式嚴格如下）：
COVERED_TOPICS: 焦點一核心關鍵詞(4-8字), 焦點二核心關鍵詞(4-8字)
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=2000
        ).choices[0].message.content.strip()
        return res
    except Exception as e:
        print(f"❌ DeepSeek 分析失敗: {e}")
        return ""

# ==========================================
# 8. Telegram HTML 安全推播 (附底部原文超連結清單)
# ==========================================
def send_telegram_html(briefing_text, reference_items):
    # 1. 分離出 AI 生成的記憶標籤，不顯示給使用者看
    clean_body = briefing_text
    extracted_topics = []
    
    match = re.search(r"COVERED_TOPICS:\s*(.+)", briefing_text)
    if match:
        raw_topics = match.group(1)
        extracted_topics = [t.strip() for t in re.split(r"[,，、]", raw_topics) if t.strip()]
        clean_body = briefing_text[:match.start()].strip()

    # 2. 對正文進行 HTML 特殊字元轉義，防止 < > & 導致發送失敗
    safe_body = html.escape(clean_body)
    
    # 3. 組合頂部時間標記與底部原文超連結清單
    hk_time = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    header = f"🌐 <b>全球多語言情報綜合簡報</b> ({hk_time} HKT)\n\n"
    
    ref_lines = ["\n\n━━━━━━━━━━━━━━━━━━\n📎 <b>本期綜合分析原文超連結清單：</b>"]
    for idx, item in enumerate(reference_items, 1):
        safe_title = html.escape(item['title'])
        safe_source = html.escape(item['source'])
        ref_lines.append(f"{idx}. [{safe_source}] <a href='{item['link']}'>{safe_title}</a>")
        
    full_message = header + safe_body + "\n".join(ref_lines)
    
    # 若超過 Telegram 4096 字元上限則安全截斷參考清單
    if len(full_message) > 4050:
        full_message = full_message[:4000] + "\n...(部分連結已省略)"

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": full_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print("📱 已成功發送綜合趨勢簡報與原文連結至 Telegram！")
        return extracted_topics
    else:
        print(f"❌ Telegram 發送失敗 ({response.status_code}): {response.text}")
        return []

# ==========================================
# 9. 主程式
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動全球熱搜加權 + 100 大多語言媒體跨源綜合雷達...")
    history = load_history()
    recent_topics = load_recent_topics()
    print(f"🧠 已載入過去 24 小時語義防重複記憶：{len(recent_topics)} 個已報導事件")
    
    # 1. 獲取即時熱搜關鍵字
    hot_keywords = fetch_realtime_hot_keywords()
    
    # 2. 全量掃描 100 個多語言媒體並按熱度/時效評分
    ranked_news = fetch_and_score_all_news(hot_keywords, history)
    
    if ranked_news:
        # 挑選分數最高的前 14 篇跨領域新聞（讓同一事件的多家媒體報導有機會同時入選以便綜合）
        selected_updates = []
        seen_categories = {}
        for item in ranked_news:
            cat = item['category']
            if seen_categories.get(cat, 0) < 4:
                selected_updates.append(item)
                seen_categories[cat] = seen_categories.get(cat, 0) + 1
            if len(selected_updates) >= 14:
                break
                
        print(f"✅ 鎖定 {len(selected_updates)} 篇高熱度多國報導，正在並行爬取內文...")
        
        # 並行爬取這 14 篇文章的網頁正文
        def enrich_article(item):
            content = fetch_article_content(item['link'])
            body = content if len(content) > 50 else item['summary']
            trend_tag = f" [命中熱搜: {','.join(item['matched_trends'])}]" if item['matched_trends'] else ""
            return f"【主題：{item['category']} | 媒體：{item['source']}{trend_tag}】\n原文標題：{item['title']}\n原文內文：{body}\n---"

        with ThreadPoolExecutor(max_workers=10) as executor:
            compiled_articles = list(executor.map(enrich_article, selected_updates))
            
        combined_news_text = "\n".join(compiled_articles)
        
        print("🧠 正在交由 DeepSeek 進行跨媒體綜合、語義去重與五段式白話解析...")
        final_briefing = analyze_and_synthesize(combined_news_text, recent_topics)
        
        if final_briefing:
            new_covered_topics = send_telegram_html(final_briefing, selected_updates)
            if new_covered_topics:
                save_new_topics(new_covered_topics)
                print(f"💾 已將新事件寫入 24 小時語義記憶庫：{new_covered_topics}")
            for item in selected_updates:
                save_history(str(hash(item['title'])))
    else:
        print("⏭️ 暫無新進新聞，本小時略過。")
