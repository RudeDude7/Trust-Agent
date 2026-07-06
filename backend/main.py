"""
main.py — Main Orchestration Script for the Vendor Due Diligence Pipeline

Wires together the OSINT, RAG, and Judge agents into a sequential LangGraph
pipeline. This is the main entry point to execute a full due diligence sweep.
"""

import json
import logging

from langgraph.graph import StateGraph, START, END

from state import VendorDueDiligenceState
from osint_agent import osint_agent_node
from rag_agent import rag_agent_node
from judge_agent import judge_agent_node

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------
def build_graph():
    """
    Constructs and compiles the LangGraph state machine.
    """
    log.info("Building StateGraph...")
    
    # 1. Initialize the graph with our shared state schema
    workflow = StateGraph(VendorDueDiligenceState)

    # 2. Add our agent nodes
    workflow.add_node("osint_agent", osint_agent_node)
    workflow.add_node("rag_agent", rag_agent_node)
    workflow.add_node("judge_agent", judge_agent_node)

    # 3. Define the sequential control flow
    workflow.add_edge(START, "osint_agent")
    workflow.add_edge("osint_agent", "rag_agent")
    workflow.add_edge("rag_agent", "judge_agent")
    workflow.add_edge("judge_agent", END)

    # 4. Compile into an executable application
    return workflow.compile()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = build_graph()

    # Define the initial state (inputs)
    initial_state: VendorDueDiligenceState = { # type: ignore[typeddict-item]
        "vendor_name": "TikTok",
        "vendor_url":  "https://tiktok.com",
    }

    log.info("Starting full due diligence pipeline for vendor: %s", initial_state["vendor_name"])
    
    # Execute the graph
    # LangGraph automatically handles passing the state dict from node to node,
    # applying our reducers (like operator.add) along the way.
    final_state = app.invoke(initial_state)

    # Pretty-print the final output
    print("\n" + "=" * 70)
    print("                     FINAL RISK ASSESSMENT")
    print("=" * 70)
    
    assessment = final_state.get("risk_assessment")
    if assessment:
        print(json.dumps(assessment, indent=2))
    else:
        print("Error: No risk assessment was generated.")
        
    print("=" * 70 + "\n")


# Compilation validates the graph, maps state reducers, and prepares the Runnable.
# Note: For lower latency, OSINT and RAG could run in parallel since they don't depend on each other.
