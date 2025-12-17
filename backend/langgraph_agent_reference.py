import os
from typing import Optional, Union, Dict, List
from typing_extensions import Literal
from pydantic import BaseModel
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from groq import Groq 

# Import MCP modules
from .mcp.graph_mcp import GraphMCP
from .mcp.risk_mcp import RiskMCP
from .mcp.data_mcp import DataMCP

from backend.ai_utils import extract_supplier_from_message



# ====================================================
# Load API Key
# ====================================================
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ====================================================
# Agent State
# ====================================================
class AgentState(BaseModel):
    message: str
    intent: Literal[
        "GRAPH_QUERY",
        "RISK_REPORT",
        "DATA_UPDATE",
        "NEWS_QUERY",
        "SUPPLIER_RISK",
        "EVENT_SEVERITY",
        "UNKNOWN"
    ] = "UNKNOWN"

    result: Optional[Union[Dict, List]] = None


# ====================================================
# Step 1 — Intent Classification (FIXED)
# ====================================================
def llm_route(state: AgentState) -> AgentState:
    prompt = f"""
You are an intent classifier for a supply chain risk AI agent.

Classify the user's intent into ONE of the following labels:

- SUPPLIER_RISK:
  Use ONLY if the question clearly mentions a specific supplier name
  (e.g. "How risky is ITC Limited?", "Risk score for Hindustan Unilever").

- EVENT_SEVERITY:
  Use for country-level or general risk severity questions
  (e.g. "What is the risk severity in India?",
        "Show highest severity risks in India").

- NEWS_QUERY:
  Questions about recent news or events affecting suppliers or countries.

- GRAPH_QUERY:
  General Neo4j graph or relationship questions.

- RISK_REPORT:
  Requests for explanation or summaries of risk.

- DATA_UPDATE:
  Requests to add or update supplier or risk data.

Return ONLY the label name.

User message:
{state.message}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    label = (response.choices[0].message.content or "UNKNOWN").strip().upper()

    valid_labels = {
        "GRAPH_QUERY",
        "RISK_REPORT",
        "DATA_UPDATE",
        "NEWS_QUERY",
        "SUPPLIER_RISK",
        "EVENT_SEVERITY"
    }

    if label not in valid_labels:
        label = "UNKNOWN"

    state.intent = label
    return state


# ====================================================
# Step 2A — Handle Graph Query
# ====================================================
def handle_graph(state: AgentState) -> AgentState:
    g = GraphMCP()
    try:
        state.result = g.top_risky_suppliers(limit=5)
    finally:
        g.close()
    return state


# ====================================================
# Step 2B — Supplier Risk Report (legacy)
# ====================================================
def handle_risk(state: AgentState) -> AgentState:
    r = RiskMCP()
    try:
        state.result = r.supplier_risk_report("S1")
    finally:
        r.close()
    return state


# ====================================================
# Step 2C — Handle Data Updates
# ====================================================
def handle_data(state: AgentState) -> AgentState:
    d = DataMCP()
    try:
        example = {
            "id": "S99",
            "name": "New Supplier GmbH",
            "esg": 70,
            "fin": 0.8,
            "ld": 20,
            "country": "DE"
        }
        state.result = d.add_supplier(example)
    finally:
        d.close()
    return state




# ====================================================
# Step 2D — Latest Supplier News
# ====================================================
def handle_news(state: AgentState) -> AgentState:
    from backend.ai_utils import extract_supplier_from_message
    g = GraphMCP()

    try:
        supplier_name = extract_supplier_from_message(state.message)

        if not supplier_name:
            state.result = {
                "error": "Please specify a supplier name for news lookup."
            }
            return state

        state.result = g.latest_supplier_events(supplier_name)

    finally:
        g.close()

    return state



# ====================================================
# Step 2E — Supplier Risk Summary (GUARDED)
# ====================================================
def handle_supplier_risk(state: AgentState) -> AgentState:
    from backend.ai_utils import extract_supplier_from_message
    g = GraphMCP()

    try:
        supplier_name = extract_supplier_from_message(state.message)

        if not supplier_name:
            state.result = {
                "error": "Could not identify supplier. Please mention a supplier name."
            }
            return state

        state.result = g.supplier_risk_summary(supplier_name)

    finally:
        g.close()

    return state



# ====================================================
# Step 2F — Highest Severity Events (Country-level)
# ====================================================
def handle_event_severity(state: AgentState) -> AgentState:
    g = GraphMCP()
    try:
        state.result = g.top_severe_events(country="India")
    finally:
        g.close()
    return state


# ====================================================
# LangGraph Workflow
# ====================================================
builder = StateGraph(AgentState)

builder.add_node("route", llm_route)
builder.add_node("graph", handle_graph)
builder.add_node("risk", handle_risk)
builder.add_node("data", handle_data)
builder.add_node("news", handle_news)
builder.add_node("supplier_risk", handle_supplier_risk)
builder.add_node("event_severity", handle_event_severity)


def edge_router(state: AgentState):
    return {
        "GRAPH_QUERY": "graph",
        "RISK_REPORT": "risk",
        "DATA_UPDATE": "data",
        "NEWS_QUERY": "news",
        "SUPPLIER_RISK": "supplier_risk",
        "EVENT_SEVERITY": "event_severity"
    }.get(state.intent, END)


builder.add_edge(START, "route")
builder.add_conditional_edges(
    "route",
    edge_router,
    {
        "graph": "graph",
        "risk": "risk",
        "data": "data",
        "news": "news",
        "supplier_risk": "supplier_risk",
        "event_severity": "event_severity",
        END: END
    }
)

builder.add_edge("graph", END)
builder.add_edge("risk", END)
builder.add_edge("data", END)
builder.add_edge("news", END)
builder.add_edge("supplier_risk", END)
builder.add_edge("event_severity", END)

graph = builder.compile()


# ====================================================
# Run Agent (GUARDED)
# ====================================================
def run_agent(message: str):
    state = AgentState(message=message)
    out = graph.invoke(state)

    result = out.get("result", {}) if isinstance(out, dict) else out.result

    # ---- Guard: empty or error ----
    if not result or (isinstance(result, dict) and "error" in result):
        return {
            "data": result,
            "explanation": (
                result.get("error")
                if isinstance(result, dict)
                else "No risk data found for the given criteria."
            )
        }

    # ---- LLM Explanation ----
    prompt = f"""
You are a supply chain risk analyst.

User question:
{message}

Agent data:
{result}

Explain the risk clearly in 3–4 lines.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    explanation = response.choices[0].message.content

    return {
        "data": result,
        "explanation": explanation
    }
