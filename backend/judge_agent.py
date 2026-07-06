# pip install langchain-google-genai pydantic python-dotenv
"""
judge_agent.py — Judge Agent Node for the Vendor Due Diligence Pipeline

Consumes the OSINT findings and internal RAG clauses from the state and
uses the Gemini 2.5 Flash LLM to cross-reference the data and produce
a final, structured risk assessment.
"""

from __future__ import annotations

import json
import logging
from typing import cast

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from state import VendorDueDiligenceState

# Load API keys (e.g. GOOGLE_API_KEY)
load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("judge_agent")


# ---------------------------------------------------------------------------
# Pydantic Schema
# ---------------------------------------------------------------------------
class RiskAssessmentModel(BaseModel):
    """The structured verdict produced by the Judge agent."""
    overall_risk_level: str = Field(
        description="The final risk level. Must be exactly one of: LOW, MEDIUM, HIGH, CRITICAL."
    )
    confidence_score: float = Field(
        description="Confidence in the assessment from 0.0 to 1.0."
    )
    summary: str = Field(
        description="A 2–3 sentence executive summary of the vendor's risk profile."
    )
    osint_inferences: list[str] = Field(
        description="Identified risks and inferences derived strictly from the external OSINT findings."
    )
    rag_inferences: list[str] = Field(
        description="Identified risks and inferences derived strictly from the vendor's policy (RAG clauses)."
    )
    comparative_analysis: str = Field(
        description="A paragraph comparing the vendor's policy against the internal company policy, highlighting gaps or discrepancies."
    )
    data_gaps: list[str] = Field(
        description="Areas where evidence was insufficient to make a firm determination."
    )


# ---------------------------------------------------------------------------
# Prompt Engineering
# ---------------------------------------------------------------------------
JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a Senior Risk and Compliance Officer performing vendor due diligence.
Your job is to evaluate a vendor's risk profile by performing a Comparative Analysis. You must cross-reference their internal stated policies against our company's internal policies (provided in the RAG Clauses, labeled with their respective roles), and against external reality (OSINT Findings).

Analyze the provided inputs and determine the risk level:
- LOW: No major breaches or regulatory actions, strong policies aligned with ours.
- MEDIUM: Minor incidents or vague policies, minor misalignment.
- HIGH: Significant past breaches, regulatory fines, or alarming discrepancies between our policy and the vendor's policy.
- CRITICAL: Active existential risks, bankruptcy, massive unmitigated breaches.

You must explicitly separate your findings into `osint_inferences` (from news/web) and `rag_inferences` (from policy text). In your `comparative_analysis`, explicitly state how the vendor's policy compares to the internal policy. Rely ONLY on the provided RAG and OSINT data."""),
    ("user", """Vendor Name: {vendor_name}

=== INTERNAL POLICIES (RAG CLAUSES) ===
{rag_clauses}

=== EXTERNAL NEWS (OSINT FINDINGS) ===
{osint_findings}

Evaluate the vendor and provide the final structured risk assessment.""")
])


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------
def judge_agent_node(state: VendorDueDiligenceState) -> dict:
    """
    Judge agent node for the LangGraph pipeline.

    1. Formats RAG clauses and OSINT findings into text.
    2. Constructs the prompt for the LLM.
    3. Calls Gemini using structured output to enforce the schema.
    4. Returns the validated JSON payload to the state.
    """
    vendor: str = state.get("vendor_name", "unknown vendor")
    rag_clauses = state.get("rag_clauses", [])
    osint_findings = state.get("osint_findings", [])

    log.info("=" * 50)
    log.info("Judge Agent activated for vendor: %s", vendor)
    log.info("=" * 50)

    # Format inputs for the prompt
    rag_text = json.dumps(rag_clauses, indent=2) if rag_clauses else "No internal policies found."
    osint_text = json.dumps(osint_findings, indent=2) if osint_findings else "No external news found."

    log.info("Analyzing %d RAG clauses and %d OSINT findings...", len(rag_clauses), len(osint_findings))

    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.0,
    )

    # Enforce Pydantic schema
    structured_llm = llm.with_structured_output(RiskAssessmentModel)

    # Create the chain
    chain = JUDGE_PROMPT | structured_llm

    try:
        # Execute the chain
        result: RiskAssessmentModel = cast(RiskAssessmentModel, chain.invoke({
            "vendor_name": vendor,
            "rag_clauses": rag_text,
            "osint_findings": osint_text
        }))
        
        log.info("Judge Agent completed evaluation. Risk Level: %s (Confidence: %.2f)", 
                 result.overall_risk_level, result.confidence_score)
                 
        return {
            "risk_assessment": result.model_dump(),
            "judge_reasoning": "Assessment generated successfully."
        }
        
    except Exception as exc:
        log.error("Failed to generate risk assessment: %s", exc)
        # Fallback payload to keep the graph running
        fallback = RiskAssessmentModel(
            overall_risk_level="CRITICAL",
            confidence_score=0.0,
            summary=f"Analysis failed due to error: {exc}",
            osint_inferences=["LLM Failure"],
            rag_inferences=["LLM Failure"],
            comparative_analysis="Failed to generate comparative analysis due to an error.",
            data_gaps=["Complete assessment failure"]
        )
        return {
            "risk_assessment": fallback.model_dump(),
            "judge_reasoning": f"Error: {exc}"
        }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_state: VendorDueDiligenceState = {  # type: ignore[typeddict-item]
        "vendor_name": "TikTok",
        "vendor_url":  "https://tiktok.com",
        "osint_findings": [
            {
                "source_url": "https://example.com/fine",
                "title": "TikTok fined €530M",
                "snippet": "Massive GDPR violation.",
                "relevance_score": 1.0,
                "finding_type": "regulatory_filing"
            }
        ],
        "rag_clauses": [
            {
                "clause_text": "We protect user data using industry standard encryption.",
                "source_document": "privacy_policy.pdf",
                "similarity_score": 0.85,
                "parent_context": "We take privacy seriously. We protect user data using industry standard encryption.",
                "role": "vendor"
            },
            {
                "clause_text": "All vendors must use AES-256 encryption at rest.",
                "source_document": "internal_policy.pdf",
                "similarity_score": 0.90,
                "parent_context": "All vendors must use AES-256 encryption at rest.",
                "role": "internal"
            }
        ]
    }

    print("Running Judge Agent Standalone Test...\n")
    result: dict = judge_agent_node(test_state)

    print("\n" + "=" * 56)
    print("       JUDGE AGENT — STANDALONE TEST RESULTS")
    print("=" * 56)
    
    assessment = result.get("risk_assessment", {})
    print(f"  Risk Level   : {assessment.get('overall_risk_level')}")
    print(f"  Confidence   : {assessment.get('confidence_score')}")
    print(f"  Summary      : {assessment.get('summary')}")
    print(f"\n  Comparative Analysis:\n    {assessment.get('comparative_analysis')}")
    
    print("\n  OSINT Inferences:")
    for f in assessment.get("osint_inferences", []):
        print(f"    - {f}")
        
    print("\n  RAG Inferences:")
    for r in assessment.get("rag_inferences", []):
        print(f"    - {r}")
        
    print("=" * 56 + "\n")


# ============================================================
# 🧠 Mentor Notes: Enforcing Structured Outputs
# ============================================================
#
# THE CHALLENGE WITH LLMs
# ───────────────────────
# LLMs are trained to be helpful chatbots. By default, if you ask
# them for JSON, they will wrap it in markdown code blocks:
#
#    Here is the JSON you requested:
#    ```json
#    { "risk_level": "HIGH" }
#    ```
#
# This breaks downstream code (like `json.loads()`) that expects
# raw, valid JSON. Parsing it manually with regex is brittle and
# error-prone.
#
#
# THE SOLUTION: PYDANTIC + STRUCTURED OUTPUT
# ──────────────────────────────────────────
# We use LangChain's `.with_structured_output(RiskAssessmentModel)`
# alongside a Pydantic schema to solve this permanently.
#
# 1. Pydantic defines the exact shape, types, and descriptions of
#    the data we want.
# 2. Under the hood, LangChain translates this Pydantic schema into
#    a JSON Schema and passes it to the LLM (for Gemini, via the
#    `response_schema` parameter).
# 3. The LLM's decoding process is constrained at the API level to
#    ONLY output tokens that conform to that exact schema. No markdown,
#    no conversational filler.
# 4. LangChain automatically parses the raw JSON string back into a
#    fully validated Python object (`RiskAssessmentModel`).
#
#
# WHY IT MATTERS FOR BACKEND ENGINEERING
# ──────────────────────────────────────
# In a production AI application, the LLM is just another API
# endpoint. You wouldn't tolerate a database that sometimes returns
# SQL results wrapped in conversational text. You shouldn't tolerate
# it from your LLMs either.
#
# Structured outputs turn non-deterministic text generators into
# reliable, typed function calls that integrate seamlessly into
# strict frontend interfaces and databases.
# ============================================================
