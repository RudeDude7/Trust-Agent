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
import re
from typing import cast

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from risk_scoring import compute_overall_risk
from state import VendorDueDiligenceState
from sanitization import sanitize_osint_findings

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
Your job is to evaluate a vendor's risk profile by performing a Comparative Analysis. You must cross-reference their internal stated policies against our company's internal policies (provided in the Compliance Matrix and RAG Findings), and against external reality (OSINT Findings).

A deterministic risk score has already been computed independently from the raw evidence — treat it as ground truth. Your job is NOT to invent your own risk level. Set `overall_risk_level` to exactly the provided computed level, and set `confidence_score` to exactly the provided value. Your `summary`, `comparative_analysis`, `osint_inferences`, and `rag_inferences` must explain and justify this score using the evidence given — do not contradict it.

You must explicitly separate your findings into `osint_inferences` (from news/web) and `rag_inferences` (from policy text). Rely ONLY on the provided RAG and OSINT data."""),
    ("user", """Vendor Name: {vendor_name}

=== DETERMINISTIC RISK SCORE (COMPUTED INDEPENDENTLY — GROUND TRUTH) ===
Composite Score: {composite_score}/100
Risk Level: {computed_level}
Confidence: {computed_confidence}
OSINT Component: {osint_component_score}/100 ({osint_finding_count} findings, categories: {categories_involved})
Compliance Component: {compliance_component_score}/100 (method: {compliance_method})

=== INTERNAL POLICIES (COMPLIANCE MATRIX & FINDINGS) ===
{rag_text}

=== EXTERNAL NEWS (OSINT FINDINGS) ===
{osint_findings}

Evaluate the vendor and provide the final structured risk assessment, consistent with the computed score above.""")
])

VERIFIER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a strict QA Auditor for a Risk Assessment pipeline.
Your job is to review a proposed Risk Assessment against the provided source texts.
Ensure that every point in `osint_inferences` and `rag_inferences` is explicitly supported by the source texts.
If you find any hallucinations (claims not in the text), you MUST strip them out.
Adjust the `overall_risk_level`, `confidence_score`, `summary`, `comparative_analysis`, and `data_gaps` appropriately based ONLY on the remaining valid inferences.
If the original assessment is completely faithful, return it exactly as is, ensuring all fields of the structured output are provided."""),
    ("user", """=== SOURCE TEXTS ===
OSINT: {osint_findings}

RAG (Internal Policies): {rag_text}

=== PROPOSED ASSESSMENT ===
Risk Level: {risk_level}
Confidence: {confidence}
Summary: {summary}
OSINT Inferences: {osint_inferences}
RAG Inferences: {rag_inferences}
Comparative Analysis: {comparative_analysis}
Data Gaps: {data_gaps}

Return the corrected and verified Risk Assessment.""")
])

# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------
def judge_agent_node(state: VendorDueDiligenceState) -> dict:
    vendor: str = state.get("vendor_name", "unknown vendor")
    rag_findings = state.get("rag_findings", [])
    compliance_matrix = state.get("compliance_matrix", {})

    raw_osint = state.get("osint_findings", [])
    osint_findings = sanitize_osint_findings(raw_osint) if raw_osint else []

    log.info("=" * 50)
    log.info("Judge Agent activated for vendor: %s", vendor)
    log.info("=" * 50)

    # --- Deterministic scoring pass, computed BEFORE the LLM sees anything ---
    risk_calc = compute_overall_risk(osint_findings, compliance_matrix, rag_findings)
    log.info(
        "Deterministic risk score: %.1f/100 -> %s (confidence %.2f)",
        risk_calc["composite_score"], risk_calc["overall_risk_level"], risk_calc["confidence_score"]
    )

    rag_data = {"findings": rag_findings, "matrix": compliance_matrix}
    rag_text = json.dumps(rag_data, indent=2) if rag_findings or compliance_matrix else "No internal policies found."
    osint_text = json.dumps(osint_findings, indent=2) if osint_findings else "No external news found."
    log.info("OSINT payload sent to Judge (first 300 chars): %s", osint_text[:300])

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0, timeout=60, max_retries=2)
    structured_llm = llm.with_structured_output(RiskAssessmentModel)
    chain = JUDGE_PROMPT | structured_llm

    prompt_vars = {
        "vendor_name": vendor,
        "rag_text": rag_text,
        "osint_findings": osint_text,
        "composite_score": risk_calc["composite_score"],
        "computed_level": risk_calc["overall_risk_level"],
        "computed_confidence": risk_calc["confidence_score"],
        "osint_component_score": risk_calc["osint_component"]["score"],
        "osint_finding_count": risk_calc["osint_component"]["finding_count"],
        "categories_involved": ", ".join(risk_calc["osint_component"]["categories_involved"]) or "none",
        "compliance_component_score": risk_calc["compliance_component"]["score"],
        "compliance_method": risk_calc["compliance_component"]["method"],
    }

    try:
        result: RiskAssessmentModel = cast(RiskAssessmentModel, chain.invoke(prompt_vars))

        log.info("Judge Agent initial evaluation. Risk Level: %s (Confidence: %.2f)",
                  result.overall_risk_level, result.confidence_score)

        log.info("Running verification pass to check for hallucinations...")
        verifier_chain = VERIFIER_PROMPT | structured_llm

        verified_result: RiskAssessmentModel = cast(RiskAssessmentModel, verifier_chain.invoke({
            "osint_findings": osint_text,
            "rag_text": rag_text,
            "risk_level": result.overall_risk_level,
            "confidence": result.confidence_score,
            "summary": result.summary,
            "osint_inferences": json.dumps(result.osint_inferences),
            "rag_inferences": json.dumps(result.rag_inferences),
            "comparative_analysis": result.comparative_analysis,
            "data_gaps": json.dumps(result.data_gaps)
        }))

        # Deterministic values are authoritative — override whatever the LLM produced.
        verified_result.overall_risk_level = risk_calc["overall_risk_level"]
        verified_result.confidence_score = risk_calc["confidence_score"]

        result_dict = verified_result.model_dump()
        result_dict["risk_score_breakdown"] = risk_calc  # exposed for transparency/debugging in the UI later

        return {
            "risk_assessment": result_dict,
            "judge_reasoning": f"Deterministic composite score: {risk_calc['composite_score']}/100 "
                                f"(OSINT {risk_calc['osint_component']['score']}, "
                                f"Compliance {risk_calc['compliance_component']['score']})."
        }

    except Exception as exc:
        log.error("Failed to generate risk assessment: %s", exc)
        fallback = RiskAssessmentModel(
            overall_risk_level=risk_calc["overall_risk_level"],
            confidence_score=risk_calc["confidence_score"],
            summary=f"Narrative generation failed due to error: {exc}. Deterministic score was {risk_calc['composite_score']}/100.",
            osint_inferences=["LLM narrative generation failed — see deterministic score breakdown."],
            rag_inferences=["LLM narrative generation failed — see deterministic score breakdown."],
            comparative_analysis="Failed to generate comparative analysis due to an error.",
            data_gaps=["Narrative generation failure"]
        )
        result_dict = fallback.model_dump()
        result_dict["risk_score_breakdown"] = risk_calc
        return {"risk_assessment": result_dict, "judge_reasoning": f"Error: {exc}"}


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
        "rag_findings": [
            "Vendor encryption policy does not meet the AES-256 requirement."
        ],
        "compliance_matrix": {
            "Encryption": {
                "status": "Non-compliant",
                "details": "Vendor uses industry standard, but does not specify AES-256."
            }
        }
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



