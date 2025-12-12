import os
from typing import Optional, Union, Dict, List
from typing_extensions import Literal
from pydantic import BaseModel
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from openai import OpenAI

# Import MCP modules
from .mcp.graph_mcp import GraphMCP
from .mcp.risk_mcp import RiskMCP
from .mcp.data_mcp import DataMCP

# ====================================================
# Load API Key
# ====================================================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
# Step 1 — Intent Classification
# ====================================================
def llm_route(state: AgentState) -> AgentState:
    prompt = f"""
Classify the user's intent into one of these:

- GRAPH_QUERY: General Neo4j graph questions
- RISK_REPORT: Ask for risk analysis or risk explanation
- DATA_UPDATE: Add/update supplier info
- NEWS_QUERY: Ask for latest events/news affecting FMCG suppliers
- SUPPLIER_RISK: Ask how risky a specific supplier is
- EVENT_SEVERITY: Ask for highest severity events globally

Return ONLY the label.

User Message: {state.message}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
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
        # Default: top risky suppliers
        state.result = g.top_risky_suppliers(limit=5)
    finally:
        g.close()
    return state


# ====================================================
# Step 2B — Supplier Risk Report (old)
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
# Step 2D — NEW: Latest Supplier News
# ====================================================
def handle_news(state: AgentState) -> AgentState:
    g = GraphMCP()
    try:
        supplier_name = state.message
        state.result = g.latest_supplier_events(supplier_name)
    finally:
        g.close()

    return state


# ====================================================
# Step 2E — NEW: Supplier Risk Summary
# ====================================================
def handle_supplier_risk(state: AgentState) -> AgentState:
    g = GraphMCP()
    try:
        supplier_name = state.message
        state.result = g.supplier_risk_summary(supplier_name)
    finally:
        g.close()

    return state


# ====================================================
# Step 2F — NEW: Highest Severity Events
# ====================================================
def handle_event_severity(state: AgentState) -> AgentState:
    g = GraphMCP()
    try:
        state.result = g.top_severe_events()
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
# Run Agent
# ====================================================
def run_agent(message: str):
    state = AgentState(message=message)
    out = graph.invoke(state)
    if isinstance(out, dict):
        return out.get("result", {})
    return getattr(out, "result", {})
