import os
import datetime
import requests
import feedparser
from dotenv import load_dotenv
from neo4j import GraphDatabase



# ====================================
# Load .env
# ====================================
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, ".env")

print("Loading .env from:", env_path)
load_dotenv(env_path)


from backend.ai_utils import analyze_text


# ====================================
# Neo4j Connection
# ====================================
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)


# ====================================
# FMCG Keywords
# ====================================
FMCG_KEYWORDS = [
    "Hindustan Unilever", "HUL",
    "ITC", "ITC Limited",
    "Nestle India",
    "Britannia Industries",
    "Dabur India",
    "Marico",
    "FMCG India supply chain"
]


# ====================================
# 1️⃣ Fetch from NewsAPI
# ====================================
def fetch_news_from_newsapi():
    print("\n📰 Fetching NewsAPI articles...")
    url = "https://newsapi.org/v2/everything"
    NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

    articles = []

    if not NEWSAPI_KEY:
        print("⚠ NEWSAPI_KEY missing in .env — skipping NewsAPI.")
        return articles

    for keyword in FMCG_KEYWORDS:
        params = {
            "q": keyword,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": NEWSAPI_KEY
        }

        response = requests.get(url, params=params)
        data = response.json()

        if "articles" in data:
            for art in data["articles"]:
                articles.append({
                    "title": art["title"],
                    "text": art["description"] or art["content"] or "",
                    "source": art["source"]["name"]
                })

    print(f"✔ NewsAPI returned {len(articles)} articles.")
    return articles


# ====================================
# 2️⃣ Fetch from Google News RSS
# ====================================
def fetch_google_news_rss():
    print("\n📰 Fetching Google News RSS articles...")
    rss_urls = [
        "https://news.google.com/rss/search?q=FMCG+India",
        "https://news.google.com/rss/search?q=Hindustan+Unilever",
        "https://news.google.com/rss/search?q=ITC+Limited",
        "https://news.google.com/rss/search?q=Nestle+India",
        "https://news.google.com/rss/search?q=Britannia",
        "https://news.google.com/rss/search?q=Dabur",
        "https://news.google.com/rss/search?q=Marico"
    ]

    articles = []

    for url in rss_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            articles.append({
                "title": entry.title,
                "text": entry.summary,
                "source": "GoogleNewsRSS"
            })

    print(f"✔ Google RSS returned {len(articles)} articles.")
    return articles


# ====================================
# 3️⃣ Fetch from GDELT
# ====================================
def fetch_gdelt_news():
    print("\n📰 Fetching GDELT articles...")
    
    url = "https://api.gdeltproject.org/api/v2/doc/doc"

    params = {
        "query": " OR ".join(FMCG_KEYWORDS),
        "mode": "ArtList",
        "format": "json"
    }

    articles = []

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if "articles" in data:
            for art in data["articles"][:10]:
                articles.append({
                    "title": art.get("title"),
                    "text": art.get("documentidentifier", ""),
                    "source": "GDELT"
                })

    except Exception as e:
        print("⚠ GDELT error:", e)

    print(f"✔ GDELT returned {len(articles)} articles.")
    return articles


# ====================================
# Combine All Real News
# ====================================
def get_all_real_news():
    news = []
    news.extend(fetch_news_from_newsapi())
    news.extend(fetch_google_news_rss())
    news.extend(fetch_gdelt_news())

    print(f"\n🔎 Total collected articles: {len(news)}")
    return news


# ====================================
# Create Supplier Relationships
# ====================================
def link_entities(tx, event_id, entities):
    for ent in entities:
        tx.run("""
            MATCH (s:Supplier)
            WHERE toLower(s.name) CONTAINS toLower($ent)
               OR any(alias IN s.aliases WHERE toLower(alias) CONTAINS toLower($ent))
            MATCH (e:RiskEvent {id:$event_id})
            MERGE (e)-[:AFFECTS]->(s)
        """, ent=ent, event_id=event_id)


# ====================================
# Ingest Pipeline
# ====================================
def ingest_all():
    articles = get_all_real_news()
    events_created = []

    for art in articles:
        print(f"\n🔍 Processing article: {art['title']}")

        # Run LLM
        analysis = analyze_text(art["text"])
        print("Raw LLM Output:", analysis)

        entities = analysis.get("entities", [])
        severity = analysis.get("severity", 0.3)

        # Generate event ID
        event_id = f"EVT_{int(datetime.datetime.utcnow().timestamp())}"

        # Store in Neo4j
        with driver.session() as session:
            session.run("""
                MERGE (e:RiskEvent {id:$id})
                SET e.summary=$summary,
                    e.sentiment=$sentiment,
                    e.sentiment_score=$sentiment_score,
                    e.severity=$severity,
                    e.source=$source,
                    e.ingested_at=datetime()
            """,
            id=event_id,
            summary=analysis["summary"],
            sentiment=analysis["sentiment"],
            sentiment_score=analysis["sentiment_score"],
            severity=severity,
            source=art["source"])

            session.execute_write(link_entities, event_id, entities)

        events_created.append({"id": event_id, "entities": entities})
        print(f"✔ Event {event_id} created with entities: {entities}")

    return events_created


# ====================================
# Run manually
# ====================================
if __name__ == "__main__":
    print("\n🚀 Starting FMCG News Ingestion...")
    results = ingest_all()

    print("\n🎉 Finished! Total Events Created:", len(results))
    for r in results:
        print(r)
