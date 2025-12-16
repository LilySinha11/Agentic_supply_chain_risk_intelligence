import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

class DataMCP:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        )

    def close(self):
        self.driver.close()

    # -----------------------------
    # Add / Update Supplier
    # -----------------------------
    def add_supplier(self, supplier: dict):
        """
        supplier = {
            id, name, country, aliases (list)
        }
        """
        query = """
        MERGE (s:Supplier {id:$id})
        SET s.name = $name,
            s.country = $country,
            s.aliases = $aliases
        RETURN s
        """

        with self.driver.session() as session:
            record = session.run(
                query,
                id=supplier["id"],
                name=supplier["name"],
                country=supplier.get("country"),
                aliases=supplier.get("aliases", [])
            ).single()

        return dict(record["s"])

    # -----------------------------
    # Attach supplier to product
    # -----------------------------
    def link_supplier_product(self, supplier_id, product_name):
        query = """
        MATCH (s:Supplier {id:$sid})
        MERGE (p:Product {name:$pname})
        MERGE (s)-[:SUPPLIES]->(p)
        """

        with self.driver.session() as session:
            session.run(query, sid=supplier_id, pname=product_name)

        return {"ok": True}
