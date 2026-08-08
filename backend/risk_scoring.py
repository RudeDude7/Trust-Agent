"""
risk_scoring.py — Deterministic Risk Scoring Engine

Computes a numeric, explainable risk score (0-100) from OSINT findings and
compliance/RAG data, using real-world weighting logic:
  - Severity varies by finding type (a breach matters more than a passing
    news mention).
  - Older incidents are discounted via exponential recency decay (half-life
    ~1 year — a remediated 5-year-old fine shouldn't score like an active
    breach from last week).
  - Findings are combined via noisy-OR aggregation, not a simple sum, so a
    pile of low-relevance search hits doesn't mechanically inflate the score.
  - A "systemic pattern" bonus applies when risk spans multiple distinct
    categories (breach + regulatory + legal) — a genuine signal of a
    troubled vendor vs. one isolated incident.

This score feeds the Judge agent as a hard anchor so the LLM narrates and
explains the verdict instead of inventing it from vibes.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Tunable constants — adjust these to recalibrate the model
# ---------------------------------------------------------------------------

FINDING_TYPE_SEVERITY: dict[str, float] = {
    "breach_report": 9.0,
    "state_sponsored_ties": 9.0,
    "financial_instability": 8.0,
    "esg_unethical_practices": 7.0,
    "legal_action": 6.0,
    "regulatory_filing": 6.0,
    "operational_outage": 4.0,
    "privacy_concern": 4.0,
    "news_article": 2.0,
}

RECENCY_HALF_LIFE_DAYS: float = 365.0

SYSTEMIC_PATTERN_BONUS: float = 10.0
SYSTEMIC_PATTERN_MIN_CATEGORIES: int = 3

OSINT_WEIGHT: float = 0.45
COMPLIANCE_WEIGHT: float = 0.55

RISK_THRESHOLDS: list[tuple[float, str]] = [
    (75.0, "CRITICAL"),
    (50.0, "HIGH"),
    (25.0, "MEDIUM"),
    (0.0, "LOW"),
]


def _age_factor(date_str: str) -> float:
    """0-1 recency multiplier. Missing/unparseable dates default to 1.0 (no discount)."""
    if not date_str:
        return 1.0
    try:
        pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        days_old = max(0.0, (datetime.now(timezone.utc) - pub_date).days)
        return math.exp(-math.log(2) * days_old / RECENCY_HALF_LIFE_DAYS)
    except Exception:
        return 1.0


def score_osint_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic 0-100 OSINT risk score via severity * recency * relevance, noisy-OR combined."""
    if not findings:
        return {"score": 0.0, "categories_involved": [], "top_contributors": [], "finding_count": 0}

    contributions: list[tuple[float, dict[str, Any]]] = []
    categories: set[str] = set()

    for f in findings:
        finding_type = f.get("finding_type", "news_article")
        severity = FINDING_TYPE_SEVERITY.get(finding_type, 2.0)
        relevance = float(f.get("relevance_score", 0.0))
        age_mult = _age_factor(f.get("date", ""))

        raw_contribution = severity * relevance * age_mult
        p = max(0.0, min(raw_contribution / 10.0, 1.0))

        contributions.append((p, f))
        if relevance > 0.15:
            categories.add(finding_type)

    combined_p = 1.0
    for p, _ in contributions:
        combined_p *= (1.0 - p)
    combined_p = 1.0 - combined_p

    score = combined_p * 100.0

    if len(categories) >= SYSTEMIC_PATTERN_MIN_CATEGORIES:
        score += SYSTEMIC_PATTERN_BONUS

    score = round(max(0.0, min(score, 100.0)), 1)
    top_contributors = sorted(contributions, key=lambda x: x[0], reverse=True)[:5]

    return {
        "score": score,
        "categories_involved": sorted(categories),
        "top_contributors": [
            {"title": f.get("title", ""), "finding_type": f.get("finding_type", ""), "weight": round(p, 2)}
            for p, f in top_contributors
        ],
        "finding_count": len(findings),
    }


def score_compliance(compliance_matrix: dict, rag_findings: list[str]) -> dict[str, Any]:
    """Deterministic 0-100 compliance risk score. Prefers structured compliance_matrix; falls back to raw counts."""
    if compliance_matrix:
        total = len(compliance_matrix)
        non_compliant = sum(
            1 for v in compliance_matrix.values()
            if isinstance(v, dict) and str(v.get("status", "")).lower().startswith("non")
        )
        partial = sum(
            1 for v in compliance_matrix.values()
            if isinstance(v, dict) and "partial" in str(v.get("status", "")).lower()
        )
        if total > 0:
            score = 100.0 * (non_compliant + 0.5 * partial) / total
            return {
                "score": round(min(score, 100.0), 1),
                "method": "compliance_matrix",
                "non_compliant_count": non_compliant,
                "partial_count": partial,
                "total_categories": total,
            }

    if rag_findings:
        score = min(len(rag_findings) * 15.0, 100.0)
        return {"score": round(score, 1), "method": "rag_findings_fallback", "discrepancy_count": len(rag_findings)}

    return {"score": 0.0, "method": "no_data", "discrepancy_count": 0}


def _level_from_score(score: float) -> str:
    for threshold, level in RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return "LOW"


def compute_overall_risk(
    osint_findings: list[dict[str, Any]],
    compliance_matrix: dict,
    rag_findings: list[str],
) -> dict[str, Any]:
    """Combines OSINT + compliance scores into a composite score, level, and data-driven confidence."""
    osint_result = score_osint_findings(osint_findings)
    compliance_result = score_compliance(compliance_matrix, rag_findings)

    composite = OSINT_WEIGHT * osint_result["score"] + COMPLIANCE_WEIGHT * compliance_result["score"]
    composite = round(min(composite, 100.0), 1)
    level = _level_from_score(composite)

    meaningful_findings = sum(1 for f in osint_findings if float(f.get("relevance_score", 0.0)) > 0.3)
    confidence = 0.3
    confidence += 0.07 * min(meaningful_findings, 5)
    confidence += 0.2 if compliance_result["method"] == "compliance_matrix" else 0.0
    confidence = round(max(0.0, min(confidence, 1.0)), 2)

    return {
        "composite_score": composite,
        "overall_risk_level": level,
        "confidence_score": confidence,
        "osint_component": osint_result,
        "compliance_component": compliance_result,
    }