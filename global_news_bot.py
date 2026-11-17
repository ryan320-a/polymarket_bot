import os
import random
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor
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
# 2. 五大領域 × 20 個全球多語言資料來源 (涵蓋英/日/韓/法/德/西/阿/葡/俄/中)
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
# 3. 歷史紀錄防重複
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
# 4. 多語言網頁內文爬蟲 (點進連結抓取正文)
# ==========================================
def fetch_article_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=8)
        # 自動偵測多國語言網頁編碼 (避免日文、韓文、俄文、阿文出現亂碼)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        # 針對中日韓等無空格語言，放寬段落長度過濾條件至 15 字元
        full_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 15])
        return full_text[:800] if full_text else ""
    except Exception:
        return ""

# ==========================================
# 5. 多線程並發抓取全球多語言來源
# ==========================================
def fetch_single_rss(args):
    category, source_name, rss_url = args
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            entry = feed.entries[0]
            return {
                "category": category,
                "source": source_name,
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", "")
            }
    except Exception:
        pass
    return None

def fetch_all_topics_news():
    tasks = []
    for category, sources in TOPIC_SOURCES.items():
        # 每次從每個主題的 20 個多語言來源中隨機抽取 6 個，確保涵蓋歐美、日韓、中東、拉美等不同語言新聞
        sampled_sources = random.sample(sources, min(6, len(sources)))
        for source_name, rss_url in sampled_sources:
            tasks.append((category, source_name, rss_url))
            
    news_items = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(fetch_single_rss, tasks)
        for res in results:
            if res:
                news_items.append(res)
    return news_items

# ==========================================
# 6. DeepSeek 多語言情報破譯與首席分析師 (獨立事件五段式深度結構)
# ==========================================
def analyze_combined_news(combined_news):
    prompt = f"""
你現在是一位精通全球多國語言與世界歷史的「全球趨勢首席分析師」。
你具備將艱澀概念「深入淺出 (Layman explanation)」的頂級能力，能夠直接閱讀並翻譯日文、韓文、法文、德文、西班牙文、阿拉伯文、俄文、葡萄牙文及英文等各國第一手媒體情報，轉化為完全沒有背景的外行人也能輕鬆秒懂的繁體中文白話文。

以下是系統剛從五大領域（國際政經、華爾街與全球財經、前沿科技AI、科學醫療、加密貨幣Web3）全球各國權威媒體抓取到的「多語言最新頭條與內文摘要」集合：

{combined_news}

【核心任務要求】：
1. 請自動翻譯並破譯上述各國語言的原始資料，從中挑選出「2 件不同領域、且最具全球影響力或獨特地區視角的大事」（分別命名為【焦點一】與【焦點二】，務必跨領域平衡，並優先挖掘非英語系國家媒體報導的重要趨勢）。
2. 拒絕生硬的機器翻譯感，使用極度流暢、接地氣且排版清晰的繁體中文撰寫。
3. 必須嚴格按照「先完整解析完第一件大事（1至5點），再完整解析第二件大事（1至5點）」的獨立單元順序輸出，嚴格包含以下五個區塊與 Emoji 標題：

【焦點一：（請填入該領域名稱與情報來源媒體）】
1. 🔥 頭條焦點秒懂：用最簡單的 1-2 句話，直接點出這件事的核心內容。
2. 💡 專家白話解說：將這件事背後的複雜概念、專有名詞或科學/商業原理，用日常生活的比喻解釋清楚，讓人一看就懂。
3. 🗣️ 輿論與市場風向：綜合分析目前各國大眾、科技界、媒體或投資者對這件事的看法與情緒。
4. 🔮 未來潛在影響：這件事接下來可能會對普通人的日常生活、工作型態、健康或經濟造成什麼具體影響？
5. 📜 歷史借鏡與參考：在人類歷史或過去幾十年的商業/金融/科技史上，有沒有發生過類似的事件？當時的發展軌跡與最終結局是什麼，能給我們什麼啟示？

（請空一行分隔）

【焦點二：（請填入另一領域名稱與情報來源媒體）】
1. 🔥 頭條焦點秒懂：...
2. 💡 專家白話解說：...
3. 🗣️ 輿論與市場風向：...
4. 🔮 未來潛在影響：...
5. 📜 歷史借鏡與參考：...

請確保文字流暢，段落分明，適合在手機上快速閱讀。不要在文中加入任何網址連結或特殊 Markdown 符號（如星號或井字號），以免影響手機閱讀體驗。
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1800
        ).choices[0].message.content.strip()
        return res
    except Exception as e:
        print(f"❌ DeepSeek 分析失敗: {e}")
        return ""

# ==========================================
# 7. Telegram 推播模組
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
        print("📱 已成功發送全球多語言趨勢簡報至 Telegram！")
    else:
        print(f"❌ Telegram 發送失敗 ({response.status_code}): {response.text}")

# ==========================================
# 8. 主程式
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動全球多語言（10國語言×100大媒體）趨勢雷達...")
    history = load_history()
    raw_news = fetch_all_topics_news()
    
    new_updates = [item for item in raw_news if str(hash(item['title'])) not in history]
    
    if len(new_updates) >= 4:
        print(f"✅ 發現 {len(new_updates)} 則來自世界各地的新頭條，正在挑選並破譯網頁內文...")
        
        # 確保每個領域至少挑選 1-2 篇最新文章，且盡量保留不同語言來源
        selected_updates = []
        seen_categories = {}
        for item in new_updates:
            cat = item['category']
            if seen_categories.get(cat, 0) < 2:
                selected_updates.append(item)
                seen_categories[cat] = seen_categories.get(cat, 0) + 1
            if len(selected_updates) >= 10:
                break
                
        compiled_articles = []
        for item in selected_updates:
            print(f"🔍 讀取多語言內文: [{item['category']} - {item['source']}] {item['title']}")
            content = fetch_article_content(item['link'])
            body = content if len(content) > 50 else item['summary']
            compiled_articles.append(f"【主題：{item['category']} | 媒體與語種：{item['source']}】\n原文標題：{item['title']}\n原文內文：{body}\n---")
        
        combined_news_text = "\n".join(compiled_articles)
        
        print("🧠 正在交由 DeepSeek 進行多語言翻譯、跨領域整合與白話文解析...")
        final_briefing = analyze_combined_news(combined_news_text)
        
        if final_briefing:
            send_telegram(final_briefing)
            for item in selected_updates:
                save_history(str(hash(item['title'])))
    else:
        print(f"⏭️ 目前僅有 {len(new_updates)} 則零星新消息，尚未達到整合門檻，略過執行。")
