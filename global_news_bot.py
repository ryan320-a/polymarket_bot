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
# 1. API 與系統設定 (安全讀取 GitHub Secrets)
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not DEEPSEEK_API_KEY or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("❌ 錯誤：找不到必要的環境變數金鑰！請確認 GitHub 專案的 Secrets 是否已正確設定。")

SENT_LOG_FILE = "sent_global_news.txt"
TOPIC_MEMORY_FILE = "covered_topics.json"
DAILY_POOL_FILE = "daily_digest_pool.json"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ==========================================
# 2. 15 大新聞領域 × 全球 500 大多語言權威媒體矩陣
# ==========================================
TOPIC_SOURCES = {
    "政治新聞": [
        ("BBC Politics [英]", "http://feeds.bbci.co.uk/news/politics/rss.xml"),
        ("Politico [美]", "https://rss.politico.com/politics-news.xml"),
        ("NHK 政治 [日]", "https://www3.nhk.or.jp/rss/news/cat4.xml"),
        ("Yonhap 政治 [韓]", "https://www.yna.co.kr/rss/politics.xml"),
        ("Le Monde Politique [法]", "https://www.lemonde.fr/politique/rss_full.xml"),
        ("Tagesschau Politik [德]", "https://www.tagesschau.de/xml/rss/politik-inland/"),
        ("El País Política [西]", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
        ("Asahi Politics [日]", "https://www.asahi.com/rss/asahi/politics.rdf"),
        ("Chosun Politics [韓]", "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml&category=politics"),
        ("RFI Politique [法]", "https://www.rfi.fr/fr/politique/rss"),
        ("DW Politik [德]", "https://www.dw.com/de/politik/s-10098/rss"),
        ("ANSA Politica [意]", "https://www.ansa.it/sito/notizie/politica/politica_rss.xml"),
        ("RIA Novosti Politics [俄]", "https://ria.ru/export/rss2/politics/index.xml"),
        ("Al Jazeera Politics [阿]", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f303/73d0e1b4-532f-45ef-b135-bfdff8b8cab9"),
        ("SCMP Politics [港/英]", "https://www.scmp.com/rss/4/feed"),
        ("CNA 政治 [台]", "https://feeds.feedburner.com/rsscna/politics"),
        ("The Guardian Politics [英]", "https://www.theguardian.com/politics/rss"),
        ("Fox News Politics [美]", "https://moxie.foxnews.com/google-publisher/politics.xml"),
        ("CNN Politics [美]", "http://rss.cnn.com/rss/cnn_allpolitics.rss"),
        ("Reuters Politics [英]", "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best"),
        ("AP News Politics [美]", "https://rsshub.app/apnews/topics/politics"),
        ("Bloomberg Politics [美]", "https://www.bloomberg.com/politics/rss"),
        ("The Hill [美]", "https://thehill.com/feed/"),
        ("Roll Call [美]", "https://rollcall.com/feed/"),
        ("CBC Politics [加]", "https://www.cbc.ca/cmlink/rss-politics"),
        ("Global News Politics [加]", "https://globalnews.ca/politics/feed/"),
        ("ABC News Politics [澳]", "https://www.abc.net.au/news/feed/51120/rss.xml"),
        ("Sydney Morning Herald Politics [澳]", "https://www.smh.com.au/rss/politics.xml"),
        ("The Straits Times Politics [新]", "https://www.straitstimes.com/news/politics/rss.xml"),
        ("Bangkok Post Politics [泰]", "https://www.bangkokpost.com/arc/outboundfeeds/rss/?outputType=xml&category=105")
    ],
    "國際新聞": [
        ("BBC World [英]", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Al Jazeera [阿]", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f303/73d0e1b4-532f-45ef-b135-bfdff8b8cab9"),
        ("Le Monde International [法]", "https://www.lemonde.fr/international/rss_full.xml"),
        ("Der Spiegel International [德]", "https://www.spiegel.de/international/index.rss"),
        ("El País Internacional [西]", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
        ("TASS [俄]", "https://tass.ru/rss/v2.xml"),
        ("Reuters World [英]", "https://www.reutersagency.com/feed/?best-topics=world&post_type=best"),
        ("AP News World [美]", "https://rsshub.app/apnews/topics/world-news"),
        ("France 24 World [法]", "https://www.france24.com/en/rss"),
        ("DW World [德]", "https://www.dw.com/en/world/s-1073/rss"),
        ("NHK World [日]", "https://www3.nhk.or.jp/rss/news/cat0.xml"),
        ("Yonhap World [韓]", "https://www.yna.co.kr/rss/news.xml"),
        ("CNA International [台]", "https://feeds.feedburner.com/rsscna/intworld"),
        ("SCMP International [港/英]", "https://www.scmp.com/rss/91/feed"),
        ("The Guardian World [英]", "https://www.theguardian.com/world/rss"),
        ("NYT World [美]", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
        ("WSJ World [美]", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
        ("RT World [俄]", "https://www.rt.com/rss/news/"),
        ("CGTN World [中]", "https://www.cgtn.com/rss/world.xml"),
        ("Global Times [中]", "https://www.globaltimes.cn/rss/out.xml"),
        ("Kyodo News [日]", "https://english.kyodonews.net/rss/news.xml"),
        ("The Mainichi [日]", "https://mainichi.jp/rss/etc/mainichi-flash.rss"),
        ("The Jakarta Post [印尼]", "https://www.thejakartapost.com/rss"),
        ("Philstar [菲]", "https://www.philstar.com/rss/news"),
        ("VnExpress International [越]", "https://e.vnexpress.net/rss/news.xml"),
        ("The Hindu World [印]", "https://www.thehindu.com/news/international/feeder/default.rss"),
        ("Hindustan Times World [印]", "https://www.hindustantimes.com/world-news/rssfeed.xml"),
        ("Dawn World [巴基斯坦]", "https://www.dawn.com/feed"),
        ("Gulf News World [杜拜]", "https://gulfnews.com/rss/world"),
        ("The Jerusalem Post [以色列]", "https://www.jpost.com/rss/rssfeedsfrontpage.rss")
    ],
    "財經／經濟新聞": [
        ("CNBC Markets [英]", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
        ("Yahoo Finance [英]", "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US"),
        ("Financial Times [英]", "https://www.ft.com/rss/home"),
        ("WSJ Markets [英]", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
        ("Nikkei 經濟 [日]", "https://assets.wor.jp/rss/rdf/nikkei/news.rdf"),
        ("Handelsblatt [德]", "https://www.handelsblatt.com/contentexport/feed/top-themen"),
        ("Bloomberg Markets [美]", "https://www.bloomberg.com/feed/podcast/etf-report.xml"),
        ("MarketWatch [英]", "http://feeds.marketwatch.com/marketwatch/topstories/"),
        ("Forbes [美]", "https://www.forbes.com/real-time/feed2/"),
        ("Fortune [美]", "https://fortune.com/feed/"),
        ("The Economist [英]", "https://www.economist.com/finance-and-economics/rss.xml"),
        ("Les Echos Finance [法]", "https://services.lesechos.fr/rss/les-echos-finance-marches.xml"),
        ("Expansión [西]", "https://e00-expansion.uecdn.es/rss/portada.xml"),
        ("Il Sole 24 Ore [意]", "https://www.ilsole24ore.com/rss/economia.xml"),
        ("Kommersant Business [俄]", "https://www.kommersant.ru/RSS/business.xml"),
        ("Economic Daily News [台]", "https://money.udn.com/rssfeed/news/1001/5591/5612?ch=fb_share"),
        ("Toyo Keizai [日]", "https://toyokeizai.net/list/feed/rss"),
        ("Korea Economic Daily [韓]", "https://www.hankyung.com/feed/all-news"),
        ("Business Times [新]", "https://www.businesstimes.com.sg/rss.xml"),
        ("Australian Financial Review [澳]", "https://www.afr.com/rss"),
        ("Globe and Mail Business [加]", "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/business/"),
        ("Investopedia [美]", "https://www.investopedia.com/feed/news"),
        ("Seeking Alpha [美]", "https://seekingalpha.com/market_currents.xml"),
        ("CoinDesk [英]", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinTelegraph [英]", "https://cointelegraph.com/rss"),
        ("The Block [美]", "https://www.theblock.co/rss.xml"),
        ("Kitco News 金融 [加]", "https://www.kitco.com/rss/kitconews.xml"),
        ("Barrons [美]", "https://www.barrons.com/feed/rss"),
        ("Morningstar [美]", "https://www.morningstar.com/rss/news"),
        ("Zacks [美]", "https://www.zacks.com/rss/zacks_news.php")
    ],
    "社會新聞": [
        ("BBC Society [英]", "http://feeds.bbci.co.uk/news/education/rss.xml"),
        ("The Guardian Society [英]", "https://www.theguardian.com/society/rss"),
        ("Yonhap 社會 [韓]", "https://www.yna.co.kr/rss/society.xml"),
        ("NHK 社會 [日]", "https://www3.nhk.or.jp/rss/news/cat1.xml"),
        ("Le Monde Societé [法]", "https://www.lemonde.fr/societe/rss_full.xml"),
        ("El País Sociedad [西]", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
        ("Asahi 社會 [日]", "https://www.asahi.com/rss/asahi/newsheadlines.rdf"),
        ("CBC Society [加]", "https://www.cbc.ca/cmlink/rss-canada-society"),
        ("ABC News Society [澳]", "https://www.abc.net.au/news/feed/51120/rss.xml"),
        ("The Hindu Society [印]", "https://www.thehindu.com/society/feeder/default.rss")
    ],
    "地方新聞": [
        ("BBC England [英]", "http://feeds.bbci.co.uk/news/england/rss.xml"),
        ("CBC Local [加]", "https://www.cbc.ca/cmlink/rss-canada"),
        ("ABC Local News [美]", "https://abcnews.go.com/abcnews/topstories"),
        ("London Evening Standard [英]", "https://www.standard.co.uk/rss"),
        ("New York Post [美]", "https://nypost.com/feed/"),
        ("LA Times [美]", "https://www.latimes.com/local/rss2.0.xml"),
        ("Chicago Tribune [美]", "https://www.chicagotribune.com/arc/outboundfeeds/rss/")
    ],
    "科技新聞": [
        ("TechCrunch [英]", "https://techcrunch.com/feed/"),
        ("The Verge [英]", "https://www.theverge.com/rss/index.xml"),
        ("Wired [英]", "https://www.wired.com/feed/rss"),
        ("MIT Technology Review [英]", "https://www.technologyreview.com/feed/"),
        ("ITmedia 科技 [日]", "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
        ("Heise Online 科技 [德]", "https://www.heise.de/rss/heise-atom.xml"),
        ("Ars Technica [美]", "https://feeds.arstechnica.com/arstechnica/index"),
        ("Engadget [美]", "https://www.engadget.com/rss.xml"),
        ("ZDNet [美]", "https://www.zdnet.com/news.rss"),
        ("CNET [美]", "https://www.cnet.com/rss/news/"),
        ("VentureBeat [美]", "https://venturebeat.com/feed/"),
        ("Gizmodo [美]", "https://gizmodo.com/feed"),
        ("Mashable [美]", "https://mashable.com/feed.xml"),
        ("TNW [荷]", "https://thenextweb.com/feed"),
        ("Hacker News [英]", "https://hnrss.org/frontpage"),
        ("GitHub Changelog [美]", "https://github.blog/changelog/feed/"),
        ("IEEE Spectrum [美]", "https://spectrum.ieee.org/rss/fulltext"),
        ("TechRadar [英]", "https://www.techradar.com/rss"),
        ("Digital Trends [美]", "https://www.digitaltrends.com/feed/"),
        ("SiliconANGLE [美]", "https://siliconangle.com/feed/")
    ],
    "健康醫療新聞": [
        ("STAT News [英]", "https://www.statnews.com/feed/"),
        ("Medical News Today [英]", "https://rss.medicalnewstoday.com/featurednews.xml"),
        ("WHO News [國際]", "https://www.who.int/rss-feeds/news-english.xml"),
        ("ScienceDaily Health [英]", "https://www.sciencedaily.com/rss/health_medicine.xml"),
        ("WebMD [美]", "https://rss.webmd.com/rss/rss.aspx?RSSSource=RSS_PUBLIC"),
        ("Healthline [美]", "https://www.healthline.com/rss/news"),
        ("Nature Medicine [英]", "https://www.nature.com/nm.rss"),
        ("Lancet [英]", "https://www.thelancet.com/rss/lancet_online.xml"),
        ("NEJM [美]", "https://www.nejm.org/action/showFeed?type=etoc&feed=rss&jc=nejm"),
        ("CIDRAP [美]", "https://www.cidrap.umn.edu/news-perspectives/rss.xml")
    ],
    "教育新聞": [
        ("BBC Education [英]", "http://feeds.bbci.co.uk/news/education/rss.xml"),
        ("The Guardian Education [英]", "https://www.theguardian.com/education/rss"),
        ("Yonhap 教育 [韓]", "https://www.yna.co.kr/rss/education.xml"),
        ("Inside Higher Ed [美]", "https://www.insidehighered.com/rss.xml"),
        ("Chronicle of Higher Education [美]", "https://www.chronicle.com/feed")
    ],
    "文化／娛樂新聞": [
        ("BBC Arts & Culture [英]", "http://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),
        ("The Guardian Culture [英]", "https://www.theguardian.com/culture/rss"),
        ("Variety 影視娛樂 [美]", "https://variety.com/feed/"),
        ("Hollywood Reporter [美]", "https://www.hollywoodreporter.com/feed/"),
        ("Rolling Stone [美]", "https://www.rollingstone.com/feed/"),
        ("Billboard [美]", "https://www.billboard.com/feed/"),
        ("Pitchfork [美]", "https://pitchfork.com/feed/rss/"),
        ("IGN [美]", "https://feeds.ign.com/ign/all"),
        ("Polygon [美]", "https://www.polygon.com/rss/index.xml"),
        ("Deadline [美]", "https://deadline.com/feed/")
    ],
    "體育新聞": [
        ("BBC Sport [英]", "http://feeds.bbci.co.uk/news/10352335/rss.xml"),
        ("ESPN Top Stories [美]", "https://www.espn.com/espn/rss/news"),
        ("L'Équipe [法]", "https://www.lequipe.fr/rss/actu_rss.xml"),
        ("NHK 體育 [日]", "https://www3.nhk.or.jp/rss/news/cat3.xml"),
        ("Sky Sports [英]", "https://www.skysports.com/rss/12040"),
        ("Bleacher Report [美]", "https://bleacherreport.com/articles/feed"),
        ("Goal.com [英]", "https://www.goal.com/feeds/en/news"),
        ("NBA.com [美]", "https://www.nba.com/rss/nba_rss.xml")
    ],
    "環境／氣候新聞": [
        ("BBC Science & Environment [英]", "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("The Guardian Environment [英]", "https://www.theguardian.com/environment/rss"),
        ("ScienceDaily Earth [英]", "https://www.sciencedaily.com/rss/earth_climate.xml"),
        ("Carbon Brief [英]", "https://www.carbonbrief.org/feed"),
        ("Yale Environment 360 [美]", "https://e360.yale.edu/feed")
    ],
    "法律／治安新聞": [
        ("BBC Law [英]", "http://feeds.bbci.co.uk/news/uk-10834376/rss.xml"),
        ("The Guardian Law [英]", "https://www.theguardian.com/law/rss"),
        ("NHK 社會法庭 [日]", "https://www3.nhk.or.jp/rss/news/cat1.xml"),
        ("ABA Journal [美]", "https://www.abajournal.com/rss")
    ],
    "軍事新聞": [
        ("Defense News [美]", "https://www.defensenews.com/arc/outboundfeeds/rss/"),
        ("Janes 國防防務 [英]", "https://www.janes.com/rss"),
        ("TASS 軍事 [俄]", "https://tass.ru/rss/v2.xml"),
        ("Military.com [美]", "https://www.military.com/rss-feeds/content?category=1"),
        ("Breaking Defense [美]", "https://breakingdefense.com/feed/")
    ],
    "生活／消費新聞": [
        ("BBC Lifestyle [英]", "http://feeds.bbci.co.uk/news/lifestyle-46487779/rss.xml"),
        ("The Guardian Life & Style [英]", "https://www.theguardian.com/lifeandstyle/rss"),
        ("CNET Consumer [美]", "https://www.cnet.com/rss/news/"),
        ("Lifehacker [美]", "https://lifehacker.com/feed")
    ],
    "天氣／交通新聞": [
        ("BBC Weather/Transport [英]", "http://feeds.bbci.co.uk/news/uk-10738600/rss.xml"),
        ("NHK 災害氣象 [日]", "https://www3.nhk.or.jp/rss/news/cat6.xml")
    ]
}

# ==========================================
# 3. 記憶庫管理
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
                "author_key": i["author_key"],
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
# 4. 熱搜雷達
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
# 5. APA 7th 元數據生成器
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
        
    return published_ts, apa_intext, apa_ref, author_citation_name.lower()

def fetch_single_rss(args):
    category, source_name, rss_url = args
    items = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:2]:
            published_ts, apa_intext, apa_ref, author_key = format_apa_metadata(source_name, entry)
            items.append({
                "category": category,
                "source": source_name,
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", ""),
                "published_ts": published_ts,
                "apa_intext": apa_intext,
                "apa_ref": apa_ref,
                "author_key": author_key
            })
    except Exception:
        pass
    return items

def fetch_and_score_all_news(hot_keywords, history):
    tasks = []
    # 500 大庫輪抽機制：每個領域隨機抽選部分來源，保持高效並行
    for category, sources in TOPIC_SOURCES.items():
        import random
        sampled_sources = random.sample(sources, min(len(sources), 15))
        for source_name, rss_url in sampled_sources:
            tasks.append((category, source_name, rss_url))
            
    all_raw = []
    with ThreadPoolExecutor(max_workers=35) as executor:
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
# 6. DeepSeek 分析引擎
# ==========================================
def analyze_hourly_news(combined_news, recent_topics):
    avoid_list_str = "、".join([r["topic"] for r in recent_topics]) if recent_topics else "無"
    
    prompt = f"""
你現在是一位精通 15 大新聞領域與學術引用規範（APA 第七版）的「全球趨勢首席情報官」。
【⚠️ 絕對禁止 AI 幻覺與盲目聚合鐵律】：
1. 絕對不准虛構、猜測或捏造任何新聞事實。
2. 必須嚴格使用下方輸入資料中所提供的【APA文內引用標籤】（例如 `(BBC News, 2026)`）。絕對不准標註未在資料中出現的媒體或年份。
3. 未在正文中實際引用其觀點的新聞，絕對不准提及。

【已報導過的話題清單】：
{avoid_list_str}

【可用的查證新聞池】：
{combined_news}

請挑選 2 件最具影響力的大事（【焦點一】與【焦點二】），嚴格依序輸出五個區塊（無星號、無井字號）：
【焦點一：（填入對應分類名稱）】
1. 🔥 頭條秒懂：... (必須附上正確 APA 引用)
2. 💡 專家解說：... (必須附上 APA 引用)
3. 🗣️ 市場風向：... (必須附上 APA 引用)
4. 🔮 未來影響：...
5. 📜 歷史借鏡：...

（空一行）
【焦點二：（填入另一分類名稱）】
1. 🔥 頭條秒懂：... (必須附上正確 APA 引用)
2. 💡 專家解說：... (必須附上 APA 引用)
3. 🗣️ 市場風向：... (必須附上 APA 引用)
4. 🔮 未來影響：...
5. 📜 歷史借鏡：...

---
COVERED_TOPICS: 焦點一核心關鍵詞(4-8字), 焦點二核心關鍵詞(4-8字)
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2100
        ).choices[0].message.content.strip()
        return res
    except Exception as e:
        print(f"❌ DeepSeek 分析失敗: {e}")
        return ""

def analyze_daily_24h_digest(daily_pool, current_trends, latest_news_text):
    pool_summary = []
    for entry in daily_pool:
        pool_summary.append(f"【時段 {entry['hk_time']}】\n{entry['hourly_brief']}\n---")
    accumulated_text = "\n".join(pool_summary) if pool_summary else "（請依據最新情報總結）"
    trends_str = "、".join(current_trends) if current_trends else "政策變革、科技突破"

    prompt = f"""
你現在是「全球情報總編輯」，現在是香港時間早上 07:00。
請撰寫一份涵蓋 15 大領域的【過去 24 小時全球 Hot Topic 深度大整合】，嚴格遵守事實查證。

【熱搜風向】：{trends_str}
【過去累積重大事件紀錄】：{accumulated_text}
【最新補充情報】：{latest_news_text}

嚴格包含以下五大板塊（無星號、無井字號）：
🌅 一、 過去 24 小時 15 大領域核心主線
🔗 二、 隱藏的蝴蝶效應
🌡️ 三、 全球與社會輿論總體溫度計
📜 四、 大歷史週期對照
🎯 五、 今日重點關注與行動指南
"""
    try:
        res = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2600
        ).choices[0].message.content.strip()
        return res
    except Exception as e:
        print(f"❌ 晨間大整合失敗: {e}")
        return ""

# ==========================================
# 7. Telegram 推播模組
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
        header = f"☀️ <b>【晨間 07:00 500大源特別版】過去 24 小時全球 Hot Topic 深度大整合</b> ({hk_time} HKT)\n\n"
    else:
        header = f"🌐 <b>500大源全球情報綜合簡報</b> ({hk_time} HKT)\n\n"
    
    found_citations_raw = re.findall(r"\(([^0-9\(\)]+?),\s*\d{4}\)", clean_body)
    found_citations_normalized = {c.strip().lower() for c in found_citations_raw}
    
    matched_refs = []
    for item in reference_items:
        if item.get('author_key', '') in found_citations_normalized or is_daily_morning:
            matched_refs.append(item['apa_ref'])
            
    if not matched_refs and not is_daily_morning:
        matched_refs.append(reference_items[0]['apa_ref'])

    unique_refs = {ref: ref for ref in matched_refs}
    sorted_refs = sorted(unique_refs.values(), key=lambda s: re.sub(r"<.*?>", "", s).lower())
    
    ref_lines = ["\n\n━━━━━━━━━━━━━━━━━━\n📚 <b>References (APA 7th Edition - Verified Only)</b>\n"]
    for ref_entry in sorted_refs:
        ref_lines.append(f"• {ref_entry}")
        
    full_message = header + safe_body + "\n".join(ref_lines)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    if len(full_message) <= 4050:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": full_message, "parse_mode": "HTML", "disable_web_page_preview": True}
        res = requests.post(url, data=payload)
        if res.status_code == 200:
            print("📱 已成功發送 500 大源簡報至 Telegram！")
        else:
            print(f"❌ Telegram 發送失敗: {res.text}")
    else:
        part1 = header + safe_body
        part2 = "📚 <b>References (APA 7th Edition)</b>\n\n" + "\n".join(ref_lines[1:])
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": part1[:4050], "parse_mode": "HTML", "disable_web_page_preview": True})
        time.sleep(1)
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": part2[:4050], "parse_mode": "HTML", "disable_web_page_preview": True})
        print("📱 已成功分段發送 500 大源報告與參考文獻！")
        
    return extracted_topics, clean_body

# ==========================================
# 8. 主程式
# ==========================================
if __name__ == "__main__":
    hk_now = datetime.utcnow() + timedelta(hours=8)
    hk_hour = hk_now.hour
    hk_time_str = hk_now.strftime("%Y-%m-%d %H:%M")
    
    print(f"🚀 啟動 500 大源全球情報引擎 | 當前香港時間：{hk_time_str}")
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
            if len(selected_updates) >= 12:
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
            print("☀️ 偵測到香港時間 07:00！啟動 500 大源晨間大整合模式...")
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
            print("⏱️ 執行 500 大源反幻覺過濾每小時快報...")
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
