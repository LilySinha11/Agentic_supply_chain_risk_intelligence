import os
import datetime
from dotenv import load_dotenv
from neo4j import GraphDatabase


# ====================================
# Load .env
# ====================================
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, ".env")

print("Loading .env from:", env_path)
load_dotenv(env_path)
from ai_utils import analyze_text

print("OPENAI_API_KEY =", os.getenv("OPENAI_API_KEY"))  # Debug check

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
# Sample News (mocked)
# ====================================
def sample_news():
    return [
        {
            "title": "Strike at Foxconn plant",
            "text": "A major strike hit Foxconn’s Zhengzhou factory disrupting smartphone production.",
            "source": "SampleNews"
        },
        {
            "title": "Earthquake affects Bosch China supplier",
            "text": "A strong earthquake near Bosch China EV battery facility halted production.",
            "source": "SampleNews"
        }
    ]


# ====================================
# Create relationships
# ====================================
def link_entities(tx, event_id, entities):
    for ent in entities:
        tx.run("""
            MATCH (s:Supplier)
            WHERE toLower(s.name) CONTAINS toLower($ent)
            MATCH (e:RiskEvent {id:$event_id})
            MERGE (e)-[:AFFECTS]->(s)
        """, ent=ent, event_id=event_id)


# ====================================
# Ingest all articles
# ====================================
def ingest_all():
    articles = sample_news()
    events_created = []

    for art in articles:
        print(f"\n🔍 Processing article: {art['title']}")

        # Run AI analysis
        analysis = analyze_text(art["text"])
        print("AI Analysis Result:", analysis)

        entities = analysis.get("entities", [])
        severity = analysis.get("severity", 0.3)

        event_id = f"EVT_{int(datetime.datetime.utcnow().timestamp())}"

        # Save RiskEvent node
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

            # FIXED: Use execute_write instead of invalid lambda
            session.execute_write(link_entities, event_id, entities)

        events_created.append({
            "id": event_id,
            "entities": entities,
            "severity": severity
        })

        print(f"✔ Event {event_id} created with entities: {entities}")

    return events_created


# ====================================
# Run script manually
# ====================================
if __name__ == "__main__":
    print("\n🚀 Starting News Ingestion...")
    results = ingest_all()
    print("\n🎉 Finished! Ingested events:")
    for r in results:
        print(r)
