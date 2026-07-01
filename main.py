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


# ============================================================
# 🧠 Mentor Notes: Graph Compilation
# ============================================================
#
# WHAT IS workflow.compile()?
# ───────────────────────────
# When we build our graph using `workflow.add_node()` and
# `workflow.add_edge()`, we are just building a blueprint. We
# are telling LangGraph how the nodes connect, but we aren't
# creating an executable program yet.
#
# `app = workflow.compile()` takes that blueprint and "freezes" it
# into a Runnable. Under the hood, compilation does several things:
#
# 1. Validation: It checks that the graph has no dead ends. It ensures
#    every path eventually leads to the special `END` node, and that
#    the `START` node is properly connected.
# 2. State Mapping: It injects the state management machinery. It ensures
#    that when Node A returns `{"rag_clauses": [x]}`, the state reducers
#    (like `operator.add`) are triggered to correctly merge the data.
# 3. Checkpointing (Optional): If we pass a `checkpointer` to compile
#    (e.g., `workflow.compile(checkpointer=memory)`), this is where
#    LangGraph hooks into SQLite/Postgres to save the state snapshot
#    after EVERY single node executes. This allows "time-travel"
#    debugging and human-in-the-loop approvals.
#
#
# SEQUENTIAL VS PARALLEL
# ──────────────────────
# Right now, our flow is:
#     START → OSINT → RAG → JUDGE → END
#
# This is simple and easy to debug. But notice that OSINT and RAG don't
# actually depend on each other — they only depend on `vendor_name` from
# the initial state.
#
# LangGraph natively supports parallel execution. If we simply changed
# our edges to:
#     workflow.add_edge(START, "osint_agent")
#     workflow.add_edge(START, "rag_agent")
#     workflow.add_edge(["osint_agent", "rag_agent"], "judge_agent")
#
# LangGraph would run the OSINT web searches AND the RAG vector searches
# at the exact same time, cutting our pipeline latency in half, before
# waiting for both to finish and passing the merged state to the Judge.
# ============================================================
