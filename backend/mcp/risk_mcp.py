import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

class RiskMCP:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        )

    def close(self):
        self.driver.close()

    # -----------------------------
    # Supplier Risk Report
    # -----------------------------
    def supplier_risk_report(self, supplier_name: str):
        """
        Returns risk events affecting a supplier + aggregated severity
        """
        query = """
        MATCH (s:Supplier)
        WHERE toLower(s.name) CONTAINS toLower($name)
        OPTIONAL MATCH (e:RiskEvent)-[:AFFECTS]->(s)
        RETURN
            s.name AS supplier,
            collect(e.summary) AS events,
            avg(e.severity) AS avg_severity,
            max(e.severity) AS max_severity,
            count(e) AS event_count
        """

        with self.driver.session() as session:
            record = session.run(query, name=supplier_name).single()

        if not record:
            return {"error": "Supplier not found"}

        return {
            "supplier": record["supplier"],
            "event_count": record["event_count"],
            "average_severity": round(record["avg_severity"] or 0, 2),
            "max_severity": record["max_severity"],
            "events": record["events"]
        }

    # -----------------------------
    # Top risky suppliers
    # -----------------------------
    def top_risky_suppliers(self, limit=5):
        query = """
        MATCH (s:Supplier)<-[:AFFECTS]-(e:RiskEvent)
        RETURN
            s.name AS supplier,
            avg(e.severity) AS risk_score,
            count(e) AS events
        ORDER BY risk_score DESC
        LIMIT $limit
        """

        with self.driver.session() as session:
            return session.run(query, limit=limit).data()
