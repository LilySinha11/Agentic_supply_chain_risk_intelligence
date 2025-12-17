import os
import json
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime, date
from neo4j.time import DateTime as Neo4jDateTime
from backend.utils.neo4j_utils import serialize_record
from backend.mcp.graph_mcp import GraphMCP


# Load environment variables
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)


# Create Groq key.
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_text(text):
    prompt = f"""
    You MUST respond ONLY in valid JSON. No extra text. No explanation.

    Extract the following from the news text:
    - summary (string)
    - sentiment (positive, neutral, negative)
    - sentiment_score (0 to 1)
    - entities (list of company or supplier names)
    - severity (0 to 1)

    Text:
    {text}
    """

    try:
        response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
        )

        raw = response.choices[0].message.content.strip()

        # 🔍 Debug print (optional)
        print("Raw LLM Output:", raw)

        # If model returned empty → avoid json error
        if not raw:
            raise ValueError("Empty response from model")

        # Try to parse JSON
        return json.loads(raw)

    except Exception as e:
        print("LLM error:", e)
        return {
            "summary": text[:100],
            "sentiment": "neutral",
            "sentiment_score": 0.5,
            "entities": [],
            "severity": 0.3
        }


def serialize_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Neo4jDateTime):
        return value.to_native().isoformat()

    return value

def serialize_record(obj):
    if isinstance(obj, dict):
        return {k: serialize_record(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_record(i) for i in obj]
    else:
        return serialize_value(obj)

def load_all_suppliers():
    """
    Fetch all suppliers dynamically from Neo4j.
    """
    g = GraphMCP()
    try:
        suppliers = g.get_all_suppliers()
        return suppliers
    finally:
        g.close()    


def extract_supplier_from_message(message: str):
    """
    Extract supplier name from user message using Neo4j-loaded suppliers
    """
    from backend.ai_utils import load_all_suppliers  # local import to avoid circular

    message_lower = message.lower()
    suppliers = load_all_suppliers()

    for supplier in suppliers:
        name = supplier["name"]
        aliases = supplier.get("aliases", [])

        # Match full name
        if name.lower() in message_lower:
            return name

        # Match aliases
        for alias in aliases:
            if alias.lower() in message_lower:
                return name

    return None
