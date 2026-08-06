"""
state.py — LangGraph State Definition for the Vendor Due Diligence Pipeline

This module defines the shared state object that flows between all three
agents in the orchestration graph:

    OSINT Agent  →  RAG Agent  →  Judge Agent

Every field uses strict type hints.  List fields use LangGraph's reducer
annotation (operator.add) so agents APPEND to the state instead of
overwriting it.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


# ---------------------------------------------------------------------------
# Sub-types — structured payloads produced by each agent
# ---------------------------------------------------------------------------

class OSINTFinding(TypedDict):
    """A single finding surfaced by the OSINT (web search) agent."""
    source_url: str                 # where the information was found
    title: str                      # headline or page title
    snippet: str                    # relevant excerpt from the source
    relevance_score: float          # 0.0 – 1.0, how relevant to the query
    finding_type: str               # e.g. "news_article", "regulatory_filing", "breach_report"


class RiskAssessment(TypedDict):
    """The structured verdict produced by the Judge agent."""
    overall_risk_level: str         # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    confidence_score: float         # 0.0 – 1.0
    summary: str                    # 2–3 sentence executive summary
    osint_inferences: list[str]     # identified risks from OSINT
    rag_inferences: list[str]       # identified risks from RAG
    comparative_analysis: str       # internal vs vendor policy comparison
    data_gaps: list[str]            # areas where evidence was insufficient


# ---------------------------------------------------------------------------
# Graph State — the single object passed through every node
# ---------------------------------------------------------------------------

class VendorDueDiligenceState(TypedDict):
    """
    Shared state for the LangGraph vendor due diligence pipeline.

    Fields fall into four groups:

    1. INPUTS        — set once at graph invocation, never mutated.
    2. OSINT STAGE   — populated by the OSINT agent.
    3. RAG STAGE     — populated by the RAG agent.
    4. JUDGE STAGE   — populated by the Judge agent.

    List fields use ``Annotated[list[T], operator.add]`` so that each
    agent node can return a partial dict like ``{"osint_findings": [new_item]}``
    and LangGraph will *append* rather than *replace*.
    """

    # ── 1. Inputs ──────────────────────────────────────────────
    user_id: str                                                # authenticated user id
    vendor_name: str                                            # e.g. "TikTok"
    vendor_url: str                                             # e.g. "https://tiktok.com"

    # ── 2. OSINT Stage ─────────────────────────────────────────
    osint_findings: Annotated[list[OSINTFinding], operator.add]
    osint_summary: str                                          # plain-language digest

    # ── 3. Comparator Stage (formerly RAG) ─────────────────────
    rag_findings: Annotated[list[str], operator.add]            # Identified discrepancies and policy gaps
    compliance_matrix: dict                                     # Structured mapping of internal vs vendor policies
    raw_rag_clauses: Annotated[list[dict], operator.add]        # Raw chunks for Sandbox What-If simulation

    # ── 4. Judge Stage ─────────────────────────────────────────
    risk_assessment: RiskAssessment | None                      # final structured verdict
    judge_reasoning: str                                        # chain-of-thought trace


# Note: LangGraph uses reducers (e.g., operator.add) on list fields
# so that agent nodes append to the state instead of overwriting each other's outputs.
