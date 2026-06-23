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


class RAGClause(TypedDict):
    """A policy clause retrieved from Supabase by the RAG agent."""
    clause_text: str                # the raw text of the matched chunk
    source_document: str            # filename or document title it came from
    similarity_score: float         # cosine similarity from the vector search
    parent_context: str             # the larger parent chunk for grounding


class RiskAssessment(TypedDict):
    """The structured verdict produced by the Judge agent."""
    overall_risk_level: str         # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    confidence_score: float         # 0.0 – 1.0
    summary: str                    # 2–3 sentence executive summary
    risk_factors: list[str]         # bullet-point list of identified risks
    recommendations: list[str]      # actionable next steps
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
    vendor_name: str                                            # e.g. "TikTok"
    vendor_url: str                                             # e.g. "https://tiktok.com"

    # ── 2. OSINT Stage ─────────────────────────────────────────
    osint_findings: Annotated[list[OSINTFinding], operator.add]
    osint_summary: str                                          # plain-language digest

    # ── 3. RAG Stage ───────────────────────────────────────────
    rag_clauses: Annotated[list[RAGClause], operator.add]
    rag_query: str                                              # the search query used
    rag_summary: str                                            # plain-language digest

    # ── 4. Judge Stage ─────────────────────────────────────────
    risk_assessment: RiskAssessment | None                      # final structured verdict
    judge_reasoning: str                                        # chain-of-thought trace


# ============================================================
# 🧠 Mentor Notes: How LangGraph Reducers Work
# ============================================================
#
# THE PROBLEM THEY SOLVE
# ──────────────────────
# In a multi-agent graph, several nodes write to the same state dict.
# Without reducers, each node's return value REPLACES the field:
#
#   OSINT agent returns:  {"osint_findings": [finding_A]}     → state has [A]
#   RAG agent returns:    {"osint_findings": [finding_B]}     → state has [B]  ← A is GONE
#
# That's catastrophic — agents erase each other's work.
#
#
# HOW REDUCERS FIX IT
# ───────────────────
# When you annotate a field with:
#
#     osint_findings: Annotated[list[OSINTFinding], operator.add]
#                                                   ^^^^^^^^^^^^
#                                                   this is the reducer
#
# LangGraph intercepts every state update and applies the reducer
# function INSTEAD of a raw assignment.  Under the hood:
#
#     new_value = operator.add(current_state["osint_findings"], node_return["osint_findings"])
#     #           operator.add( [finding_A],                    [finding_B] )
#     #           → [finding_A, finding_B]                                    ← both preserved
#
# So ``operator.add`` for lists is just list concatenation.  Each agent
# returns ONLY its new items, and LangGraph merges them into the
# running state automatically.
#
#
# WHICH FIELDS GET REDUCERS?
# ──────────────────────────
# Rule of thumb:
#
#   • Lists that MULTIPLE agents (or the same agent across retries)
#     might append to  →  USE a reducer.
#     Examples: osint_findings, rag_clauses
#
#   • Scalar values that only ONE agent ever writes (or that should
#     be fully replaced each time)  →  NO reducer needed.
#     Examples: vendor_name, risk_assessment, osint_summary
#
#
# CUSTOM REDUCERS
# ───────────────
# operator.add is the most common, but you can supply any
# (old, new) → merged function.  Useful examples:
#
#   • Deduplication:
#         def dedupe(old: list, new: list) -> list:
#             seen = {item["source_url"] for item in old}
#             return old + [i for i in new if i["source_url"] not in seen]
#
#   • Latest-wins with history:
#         def keep_latest(old: str, new: str) -> str:
#             return new  # same as no reducer, but explicit
#
# You can drop any of these into the Annotated[] wrapper later
# without changing your agent code.
# ============================================================
