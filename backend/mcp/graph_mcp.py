from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

class GraphMCP:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USER")
        self.password = os.getenv("NEO4J_PASSWORD")

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )

    def close(self):
        self.driver.close()

    # -----------------------------------
    # Helper: Run Cypher Query
    # -----------------------------------
    def run_query(self, query, params=None):
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    # -----------------------------------
    # 1) Top Risky Suppliers
    # -----------------------------------
    def top_risky_suppliers(self, limit: int = 5):
        query = """
        MATCH (e:RiskEvent)-[:AFFECTS]->(s:Supplier)
        WITH s,
             count(e) AS event_count,
             avg(e.severity) AS avg_severity,
             sum(e.severity) AS total_severity
        RETURN
            s.name AS supplier,
            s.country AS country,
            event_count,
            round(avg_severity, 2) AS avg_severity,
            round(total_severity, 2) AS total_severity
        ORDER BY total_severity DESC
        LIMIT $limit
        """
        return self.run_query(query, {"limit": limit})

    # -----------------------------------
    # 2) Latest Supplier Events
    # -----------------------------------
    def latest_supplier_events(self, supplier, limit=5):
        query = """
        MATCH (e:RiskEvent)-[:AFFECTS]->(s:Supplier)
        WHERE toLower(s.name) CONTAINS toLower($supplier)
        RETURN e.summary AS summary,
               e.severity AS severity,
               e.ingested_at AS time
        ORDER BY time DESC
        LIMIT $limit
        """
        return self.run_query(query, {"supplier": supplier, "limit": limit})

    # -----------------------------------
    # 3) Supplier Risk Summary
    # -----------------------------------
    def supplier_risk_summary(self, supplier):
        query = """
        MATCH (e:RiskEvent)-[:AFFECTS]->(s:Supplier)
        WHERE toLower(s.name) CONTAINS toLower($supplier)
        RETURN
            s.name AS supplier,
            count(e) AS total_events,
            round(avg(e.severity), 2) AS avg_severity,
            max(e.severity) AS max_severity
        """
        return self.run_query(query, {"supplier": supplier})

    # -----------------------------------
    # 4) Top Severe Events (Global)
    # -----------------------------------
    def top_severe_events(self, country="India", limit=5):
        query = """
        MATCH (e:RiskEvent)-[:AFFECTS]->(s:Supplier)
        WHERE s.country = $country
        RETURN
            s.name AS supplier,
            s.country AS country,
            e.type AS event_type,
            e.severity AS severity
        ORDER BY e.severity DESC
        LIMIT $limit
        """
        return self.run_query(query, {
            "country": country,
            "limit": limit
        })
