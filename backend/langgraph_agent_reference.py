import os
from typing import Optional, Union, Dict, List
from typing_extensions import Literal
from pydantic import BaseModel
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from openai import OpenAI

# MCP modules
from .mcp.graph_mcp import GraphMCP
from .mcp.risk_mcp import RiskMCP
from .mcp.data_mcp import DataMCP

# ✅ Load environment vars
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Agent State
class AgentState(BaseModel):
    message: str
    intent: Literal["GRAPH_QUERY", "RISK_REPORT", "DATA_UPDATE", "UNKNOWN"] = "UNKNOWN"
    result: Optional[Union[Dict, List]] = None

# ✅ Step 1: Classify intent using OpenAI
def llm_route(state: AgentState) -> AgentState:
    prompt = f"""Classify the user's intent into one of:
    - GRAPH_QUERY = Neo4j query about suppliers, countries, risks, relationships.
    - RISK_REPORT = Ask for supplier-specific risk evaluation.
    - DATA_UPDATE = Add or update supplier data in Neo4j.
    Return ONLY the label.

    User message: {state.message}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    label = (response.choices[0].message.content or "UNKNOWN").strip().upper()

    if label not in {"GRAPH_QUERY", "RISK_REPORT", "DATA_UPDATE"}:
        label = "UNKNOWN"

    state.intent = label
    return state

# ✅ Step 2A: Handle Graph Query
def handle_graph(state: AgentState) -> AgentState:
    g = GraphMCP()
    try:
        # Example: return top 5 risky suppliers
        rows = g.top_risky_suppliers(limit=5)
        state.result = rows
    finally:
        g.close()
    return state

# ✅ Step 2B: Handle Risk Report
def handle_risk(state: AgentState) -> AgentState:
    r = RiskMCP()
    try:
        # For now, use a static supplier ID
        state.result = r.supplier_risk_report("S1")
    finally:
        r.close()
    return state

# ✅ Step 2C: Handle Data Update
def handle_data(state: AgentState) -> AgentState:
    d = DataMCP()
    try:
        # Example static supplier update
        new_supplier = {
            "id": "S99",
            "name": "New Supplier GmbH",
            "esg": 70,
            "fin": 0.8,
            "ld": 20,
            "country": "DE"
        }
        state.result = d.add_supplier(new_supplier)
    finally:
        d.close()
    return state

# ✅ Build LangGraph Workflow
builder = StateGraph(AgentState)

builder.add_node("route", llm_route)
builder.add_node("graph", handle_graph)
builder.add_node("risk", handle_risk)
builder.add_node("data", handle_data)

def edge_router(state: AgentState):
    if state.intent == "GRAPH_QUERY":
        return "graph"
    if state.intent == "RISK_REPORT":
        return "risk"
    if state.intent == "DATA_UPDATE":
        return "data"
    return END

builder.add_edge(START, "route")
builder.add_conditional_edges(
    "route", 
    edge_router,
    {"graph": "graph", "risk": "risk", "data": "data", END: END}
)
builder.add_edge("graph", END)
builder.add_edge("risk", END)
builder.add_edge("data", END)

graph = builder.compile()

# ✅ Main function to run agent
def run_agent(message: str):
    state = AgentState(message=message)
    out = graph.invoke(state)

    if isinstance(out, dict):
        return out.get("result", {})
    return getattr(out, "result", {})