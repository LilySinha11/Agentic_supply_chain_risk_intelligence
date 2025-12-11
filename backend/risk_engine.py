import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
ALERT_THRESHOLD = 0.5

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def compute_supplier_risk(tx, sid):
    q = """
    MATCH (s:Supplier {id:$sid})
    OPTIONAL MATCH (s)<-[:AFFECTS]-(e:RiskEvent)
    RETURN s.risk AS base_risk, collect(e.severity) AS sev
    """
    data = tx.run(q, sid=sid).single()
    if not data:
        return 0

    base = data["base_risk"] or 0
    sev_list = data["sev"] or []

    event_impact = sum(sev_list)/len(sev_list) if sev_list else 0
    score = base * 0.6 + event_impact * 0.4

    tx.run("MATCH (s:Supplier {id:$sid}) SET s.last_computed_risk=$r", sid=sid, r=score)
    return score


def update_all_risks_and_alerts():
    alerts_created = []
    with driver.session() as session:
        suppliers = session.run("MATCH (s:Supplier) RETURN s.id AS id").data()

        for row in suppliers:
            sid = row["id"]

            with session.begin_transaction() as tx:
                risk = compute_supplier_risk(tx, sid)

                if risk >= ALERT_THRESHOLD:
                    tx.run("""
                        MERGE (a:Alert {supplier_id:$sid, open:true})
                        SET a.risk_value=$risk, a.created_at=datetime()
                    """, sid=sid, risk=risk)
                    alerts_created.append({"supplier": sid, "risk": risk})

    return alerts_created
