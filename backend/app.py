import os
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from neo4j import GraphDatabase
import requests
from backend.langgraph_agent_reference import run_agent


# =========================
# Load .env
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(__file__)) 
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

app = Flask(__name__, template_folder="templates", static_folder="static")

# =========================
# Neo4j Driver
# =========================
def get_neo4j_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return "Supply Risk AI - Flask is running"

@app.route("/test-neo4j")
def test_neo4j():
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        return jsonify(ok=True, node_count=count)
    except Exception as e:
        return jsonify(ok=False, error=str(e))




# -------------------------
# AI INGESTION ENDPOINT
# -------------------------
@app.route("/api/ingest-news", methods=["GET", "POST"])
def ingest_news_api():
    from ingest_news import ingest_all
    from risk_engine import update_all_risks_and_alerts

    try:
        results = ingest_all()
        alerts = update_all_risks_and_alerts()
        return jsonify({"ingested": results, "alerts": alerts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# -------------------------
# ALERT LIST
# -------------------------
@app.route("/api/alerts")
def api_alerts():
    try:
        driver = get_neo4j_driver()
        query = """
        MATCH (a:Alert {open: true})
        RETURN a.supplier_id AS supplier_id,
               a.risk_value AS risk,
               a.created_at AS created_at
        """
        with driver.session() as session:
            results = session.run(query).data()
        return jsonify(results)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


# -------------------------
# INDIVIDUAL SUPPLIER DETAILS
# -------------------------
@app.route("/api/supplier/<sid>")
def api_supplier_detail(sid):
    driver = get_neo4j_driver()
    query = """
    MATCH (s:Supplier {id:$sid})
    OPTIONAL MATCH (s)-[:SUPPLIES]->(p:Product)
    OPTIONAL MATCH (e:RiskEvent)-[:AFFECTS]->(s)
    RETURN s{.*, 
            products: collect(DISTINCT p.name), 
            events: collect(DISTINCT e{.*})} AS supplier
    """
    with driver.session() as session:
        result = session.run(query, sid=sid).single()
    if not result:
        return jsonify({})
    return jsonify(result["supplier"])


@app.route("/agent-ui")
def agent_ui():
    return render_template("agent.html")    

@app.route("/api/agent", methods=["POST"])
def api_agent():
    data = request.get_json()
    message = data.get("message")

    if not message:
        return jsonify({"error": "Message is required"}), 400

    try:
        result = run_agent(message)
        return jsonify({
            "answer": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/supplier-dashboard")
def supplier_dashboard():
    from neo4j import GraphDatabase
    import os

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
    )

    query = """
    MATCH (s:Supplier)
    OPTIONAL MATCH (e:RiskEvent)-[:AFFECTS]->(s)
    WITH s,
         collect(DISTINCT e.type) AS risk_events,
         coalesce(avg(e.severity), 0.0) AS avg_risk
    RETURN
        s.name AS supplier,
        s.country AS country,
        avg_risk AS risk_score,
        risk_events
    ORDER BY risk_score DESC
    """

    with driver.session() as session:
        suppliers = session.run(query).data()

    driver.close()

    return render_template(
        "supplier_dashboard.html",
        suppliers=suppliers
    )



# =========================
if __name__ == "__main__":
    app.run(debug=True)
