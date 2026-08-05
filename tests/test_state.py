"""
test_state.py — LangGraph State & Reducer Verification

Simulates the full vendor due diligence pipeline with mock nodes to prove:
  1. The StateGraph compiles and executes with our VendorDueDiligenceState.
  2. The operator.add reducer on rag_clauses correctly ACCUMULATES items
     from two separate RAG nodes instead of overwriting.

Usage:
    python test_state.py
"""

import logging
from typing import Any, cast

from langgraph.graph import StateGraph, START, END
from state import VendorDueDiligenceState

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_state")


# ---------------------------------------------------------------------------
# Mock agent nodes — return hardcoded partial state updates
# ---------------------------------------------------------------------------
def mock_osint_node(state: VendorDueDiligenceState) -> dict:
    """Simulates OSINT agent finding one news article."""
    log.info("Executing Mock OSINT Agent …")
    return {
        "osint_findings": [{
            "source_url": "https://news.com/tiktok-data",
            "title": "Data Privacy Audit",
            "snippet": "Data routing analysis completed.",
            "relevance_score": 0.95,
            "finding_type": "news_article",
        }],
        "osint_summary": "OSINT sweep complete. Found 1 relevant article.",
    }


def mock_comparator_node_part_one(state: VendorDueDiligenceState) -> dict:
    """Simulates Comparator agent finding a discrepancy."""
    log.info("Executing Mock Comparator Agent (Step 1) …")
    return {
        "rag_findings": ["Vendor encryption policy does not meet internal standard."],
        "compliance_matrix": {"Encryption": {"status": "Non-compliant"}}
    }


def mock_comparator_node_part_two(state: VendorDueDiligenceState) -> dict:
    """Simulates a second Comparator retrieval — tests that operator.add APPENDS."""
    log.info("Executing Mock Comparator Agent (Step 2 — testing list accumulation) …")
    return {
        "rag_findings": ["Vendor lacks multi-factor authentication."],
    }


def mock_judge_node(state: VendorDueDiligenceState) -> dict:
    """Simulates the Judge agent issuing a final risk verdict."""
    log.info("Executing Mock Judge Agent …")
    return {
        "risk_assessment": {
            "overall_risk_level": "LOW",
            "confidence_score": 0.9,
            "summary": "Vendor meets standard encryption and identity baseline requirements.",
            "risk_factors": ["Third-party logging infrastructure lacks explicit retention bounds."],
            "recommendations": ["Request data retention logs during onboarding."],
            "data_gaps": [],
        },
        "judge_reasoning": (
            "Reasoning trace: Evaluated OSINT inputs against 2 matching "
            "internal policy rules."
        ),
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
workflow = StateGraph(VendorDueDiligenceState)  # type: ignore[arg-type]

workflow.add_node("osint_agent", mock_osint_node)
workflow.add_node("comparator_agent_1", mock_comparator_node_part_one)
workflow.add_node("comparator_agent_2", mock_comparator_node_part_two)
workflow.add_node("judge_agent", mock_judge_node)

workflow.add_edge(START, "osint_agent")
workflow.add_edge("osint_agent", "comparator_agent_1")
workflow.add_edge("comparator_agent_1", "comparator_agent_2")
workflow.add_edge("comparator_agent_2", "judge_agent")
workflow.add_edge("judge_agent", END)

app = workflow.compile()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    initial_input: dict[str, Any] = {
        "vendor_name": "TikTok",
        "vendor_url": "https://tiktok.com",
    }

    log.info("Invoking graph with vendor: %s", initial_input["vendor_name"])
    final_state: dict[str, Any] = cast(
        dict[str, Any],
        app.invoke(cast(VendorDueDiligenceState, initial_input)),
    )

    # --- Validation report ---
    osint_count: int = len(final_state.get("osint_findings", []))
    rag_count: int = len(final_state.get("rag_findings", []))
    risk_level: str = str(final_state.get("risk_assessment", {}).get("overall_risk_level", "N/A"))

    print("\n" + "=" * 56)
    print("       GRAPH VERIFICATION METRICS")
    print("=" * 56)
    print(f"  Target Vendor       : {final_state.get('vendor_name')}")
    print(f"  OSINT Findings      : {osint_count}")
    print(f"  RAG Findings Found  : {rag_count}  (expected: 2)")
    print(f"  Reducer Test        : {'✅ PASS' if rag_count == 2 else '❌ FAIL'}")
    print(f"  Verdict Risk Level  : {risk_level}")
    print(f"  Judge Confidence    : {final_state.get('risk_assessment', {}).get('confidence_score', 'N/A')}")
    print("=" * 56 + "\n")
