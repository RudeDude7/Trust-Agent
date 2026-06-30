# pip install ddgs langchain-community
"""
osint_agent.py — OSINT Agent Node for the Vendor Due Diligence Pipeline

Performs open-source intelligence gathering via DuckDuckGo web search.
Searches for data breaches, regulatory fines, and security incidents
associated with a vendor, then maps the results into the OSINTFinding
format defined in state.py.

Zero-cost: DuckDuckGo requires no API key and no paid subscription.
"""

from __future__ import annotations

import logging
from typing import Any

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException

from state import OSINTFinding, VendorDueDiligenceState

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("osint_agent")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_RESULTS: int = 5              # cap per search query (keep it fast)
SEARCH_REGION: str = "wt-wt"     # worldwide, no region bias

# Multiple search angles to maximise coverage.
QUERY_TEMPLATES: list[str] = [
    "{vendor} data breach security incident",
    "{vendor} regulatory fine GDPR penalty",
    "{vendor} privacy policy controversy news",
]


# ---------------------------------------------------------------------------
# Finding-type classifier (simple keyword heuristic)
# ---------------------------------------------------------------------------
def _classify_finding(title: str, snippet: str) -> str:
    """
    Assigns a finding_type based on keyword presence in the title/snippet.
    A production system would use an LLM or NER model here; this heuristic
    is good enough for the MVP and costs $0.
    """
    text: str = (title + " " + snippet).lower()

    if any(w in text for w in ("breach", "hack", "leak", "compromised", "ransomware")):
        return "breach_report"
    if any(w in text for w in ("fine", "penalty", "gdpr", "ftc", "settlement", "regulatory")):
        return "regulatory_filing"
    if any(w in text for w in ("lawsuit", "sued", "litigation", "court")):
        return "legal_action"
    if any(w in text for w in ("privacy", "tracking", "surveillance", "data collection")):
        return "privacy_concern"

    return "news_article"


# ---------------------------------------------------------------------------
# Relevance scorer (simple keyword overlap)
# ---------------------------------------------------------------------------
def _score_relevance(title: str, snippet: str, vendor: str) -> float:
    """
    Scores 0.0–1.0 based on how many risk-related keywords appear.
    Higher scores mean the finding is more directly relevant to
    security/compliance risk.
    """
    text: str = (title + " " + snippet).lower()
    vendor_lower: str = vendor.lower()

    risk_keywords: list[str] = [
        "breach", "hack", "fine", "penalty", "gdpr", "privacy",
        "security", "vulnerability", "incident", "compliance",
        "lawsuit", "leak", "ransomware", "ban", "investigation",
    ]

    score: float = 0.0

    # Vendor name mentioned → strong signal.
    if vendor_lower in text:
        score += 0.3

    # Count risk keyword hits (diminishing returns).
    hits: int = sum(1 for kw in risk_keywords if kw in text)
    score += min(hits * 0.1, 0.7)  # cap keyword contribution at 0.7

    return round(min(score, 1.0), 2)


# ---------------------------------------------------------------------------
# Core search logic
# ---------------------------------------------------------------------------
def _search_duckduckgo(query: str) -> list[dict[str, Any]]:
    """
    Executes a DuckDuckGo text search and returns raw result dicts.

    Each result has keys: 'title', 'href', 'body'.
    Returns an empty list on failure (network errors, rate limits, etc.).
    """
    try:
        ddgs = DDGS()
        results: list[dict[str, Any]] = ddgs.text(
            query,
            region=SEARCH_REGION,
            max_results=MAX_RESULTS,
        )
        log.info("  ↳ Query \"%s\" → %d results", query[:60], len(results))
        return results

    except RatelimitException:
        log.warning("DuckDuckGo rate limit hit for \"%s\". Skipping.", query[:60])
        return []

    except DDGSException as exc:
        log.warning("DuckDuckGo search failed for \"%s\": %s", query[:60], exc)
        return []

    except Exception as exc:
        log.error("Unexpected error during search: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Deduplication helper
# ---------------------------------------------------------------------------
def _deduplicate(findings: list[OSINTFinding]) -> list[OSINTFinding]:
    """Removes duplicate findings based on source_url."""
    seen: set[str] = set()
    unique: list[OSINTFinding] = []

    for finding in findings:
        if finding["source_url"] not in seen:
            seen.add(finding["source_url"])
            unique.append(finding)

    return unique


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------
def osint_agent_node(state: VendorDueDiligenceState) -> dict:
    """
    OSINT agent node for the LangGraph vendor due diligence pipeline.

    1. Extracts the vendor name from the graph state.
    2. Runs multiple DuckDuckGo searches with different risk angles.
    3. Deduplicates results across queries.
    4. Maps raw results into OSINTFinding TypedDict format.
    5. Returns findings + summary for state accumulation.
    """
    vendor: str = state.get("vendor_name", "unknown vendor")

    log.info("=" * 50)
    log.info("OSINT Agent activated for vendor: %s", vendor)
    log.info("=" * 50)

    # Run searches across multiple query templates.
    all_findings: list[OSINTFinding] = []

    for template in QUERY_TEMPLATES:
        query: str = template.format(vendor=vendor)
        log.info("Searching: \"%s\"", query)

        raw_results: list[dict[str, Any]] = _search_duckduckgo(query)

        for result in raw_results:
            title: str = str(result.get("title", ""))
            snippet: str = str(result.get("body", ""))
            url: str = str(result.get("href", ""))

            if not url:
                continue

            finding: OSINTFinding = {
                "source_url":      url,
                "title":           title,
                "snippet":         snippet[:500],  # cap length for the LLM context window
                "relevance_score": _score_relevance(title, snippet, vendor),
                "finding_type":    _classify_finding(title, snippet),
            }
            all_findings.append(finding)

    # Deduplicate across query batches (same URL from different queries).
    unique_findings: list[OSINTFinding] = _deduplicate(all_findings)

    # Sort by relevance so the Judge sees the most important findings first.
    unique_findings.sort(key=lambda f: f["relevance_score"], reverse=True)

    # Build summary.
    if unique_findings:
        top_types: list[str] = list({f["finding_type"] for f in unique_findings[:5]})
        summary: str = (
            f"OSINT scan for '{vendor}' found {len(unique_findings)} unique "
            f"findings across {len(QUERY_TEMPLATES)} search angles. "
            f"Top finding types: {', '.join(top_types)}."
        )
    else:
        summary = (
            f"OSINT scan for '{vendor}' returned 0 results. "
            f"This may indicate a low public profile or search rate-limiting."
        )

    log.info(summary)

    for i, f in enumerate(unique_findings[:3], 1):
        log.info(
            "  ↳ Top %d: [%.2f] %s — \"%s\"",
            i, f["relevance_score"], f["finding_type"], f["title"][:60],
        )

    return {
        "osint_findings": unique_findings,
        "osint_summary":  summary,
    }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_state: VendorDueDiligenceState = {  # type: ignore[typeddict-item]
        "vendor_name": "TikTok",
        "vendor_url":  "https://tiktok.com",
    }

    result: dict = osint_agent_node(test_state)

    print("\n" + "=" * 56)
    print("       OSINT AGENT — STANDALONE TEST RESULTS")
    print("=" * 56)
    print(f"  Vendor           : {test_state['vendor_name']}")
    print(f"  Findings returned: {len(result.get('osint_findings', []))}")
    print(f"  Summary          : {result.get('osint_summary', '')}")

    for i, finding in enumerate(result.get("osint_findings", [])[:5], 1):
        print(f"\n  --- Finding {i} ---")
        print(f"  Type  : {finding['finding_type']}")
        print(f"  Score : {finding['relevance_score']}")
        print(f"  Title : {finding['title'][:80]}")
        print(f"  URL   : {finding['source_url'][:80]}")
        print(f"  Snippet: {finding['snippet'][:120]}…")

    print("=" * 56 + "\n")


# ============================================================
# 🧠 Mentor Notes: Why OSINT Matters Alongside RAG
# ============================================================
#
# THE GAP IN STATIC POLICY ANALYSIS
# ──────────────────────────────────
# The RAG agent searches your INTERNAL policy documents — the
# vendor's published privacy policy, security whitepaper, etc.
# But these documents are:
#
#   1. Self-reported — the vendor wrote them to look good.
#   2. Point-in-time — they reflect policy at publication date.
#   3. Aspirational — they describe what the vendor SAYS it does,
#      not what it ACTUALLY does.
#
# A vendor's privacy policy might say "we encrypt all data at rest"
# while a news article reveals they suffered a breach because
# encryption wasn't actually implemented.
#
#
# WHAT OSINT ADDS
# ───────────────
# The OSINT agent provides the EXTERNAL perspective:
#
#   • Data breaches:     Has this vendor been hacked?
#   • Regulatory fines:  Has the FTC/GDPR/CCPA penalized them?
#   • Lawsuits:          Are they being sued for data practices?
#   • News coverage:     What does independent journalism say?
#   • Public sentiment:  Are users/employees raising red flags?
#
# This creates a trust-but-verify dynamic:
#
#     RAG says:   "Policy states AES-256 encryption is used."
#     OSINT says: "Company fined €50M for storing passwords in
#                  plaintext (GDPR Article 32 violation)."
#
# The Judge agent can now weigh the internal claim against the
# external evidence and assign a meaningful risk score.
#
#
# WHY DUCKDUCKGO?
# ───────────────
# DuckDuckGo's search API is:
#   • Free — no API key, no credit card, no rate-limit billing.
#   • Privacy-preserving — no user tracking, appropriate for a
#     compliance tool.
#   • Good enough — for due diligence we need breadth (news,
#     regulatory filings, breach databases), not perfect ranking.
#
# For production, you'd upgrade to Google Custom Search ($5/1000
# queries) or a dedicated OSINT API like Shodan/GreyNoise, but
# DuckDuckGo is perfect for a $0 budget MVP.
#
#
# THE MULTI-QUERY STRATEGY
# ────────────────────────
# We run 3 separate searches per vendor instead of one because:
#
#   1. Search engines optimize for user intent — a single broad
#      query returns general results (Wikipedia, company homepage).
#   2. Targeted queries ("TikTok GDPR fine") surface specific risk
#      signals that a broad query would bury on page 5.
#   3. Different query angles cover different risk categories:
#      breaches, regulatory actions, and privacy controversies.
#
# The deduplication step ensures the same URL found by multiple
# queries is only passed to the Judge once.
# ============================================================
