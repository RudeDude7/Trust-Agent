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
import re
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

    # 1. Cybersecurity & Data Integrity
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ("breach", "hack", "leak", "compromised", "ransomware", "unauthorized access", "exfiltration", "zero-day", "cyberattack", "data spill", "credential stuffing")): 
        return "breach_report"
    
    # 2. Regulatory & Compliance
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ("penalty", "gdpr", "ftc", "settlement", "regulatory", "sec probe", "investigation", "doj", "non-compliance", "subpoena", "consent decree", "cfpb", "fca violation")): 
        return "regulatory_filing"
    
    # 3. Legal & Judicial
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ("lawsuit", "sued", "litigation", "court", "class action", "plaintiff", "indictment", "injunction", "class-action", "ip theft", "patent infringement")): 
        return "legal_action"
    
    # 4. Privacy & Surveillance
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ("privacy", "tracking", "surveillance", "data collection", "unconsented", "selling data", "cookie tracking", "wiretap", "biometric", "ccpa violation")): 
        return "privacy_concern"

    # 5. Financial & Corporate Stability (NEW)
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ("bankruptcy", "chapter 11", "insolvent", "liquidation", "default", "restructuring", "layoffs", "downsizing", "going concern", "credit downgrade", "missed debt")): 
        return "financial_instability"

    # 6. Operational Resilience (NEW)
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ("outage", "downtime", "service disruption", "offline", "sla breach", "incident report", "degraded performance", "blackout", "network failure")): 
        return "operational_outage"

    # 7. ESG & Unethical Practices (NEW)
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ("child labor", "human rights", "environmental violation", "fraud", "embezzlement", "bribe", "corruption", "greenwashing", "toxic workplace", "money laundering", "fcpa")): 
        return "esg_unethical_practices"

    # 8. Geopolitical & State-Sponsored Risks (NEW)
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ("state-sponsored", "apt", "sanctions", "ofac", "embargo", "espionage", "nation-state", "foreign adversary", "export control", "ccp ties", "banned entity")): 
        return "state_sponsored_ties"

    return "news_article"


# ---------------------------------------------------------------------------
# Relevance scorer (simple keyword overlap)
# ---------------------------------------------------------------------------
def _score_relevance(title: str, snippet: str, vendor: str) -> float:
    """
    Scores 0.0 – 1.0 based on weighted risk keywords, negators, and proximity to the vendor name.
    Higher scores mean the finding is more directly relevant to security/compliance risk.
    """
    text: str = (title + " " + snippet).lower()
    vendor_lower: str = vendor.lower()
    
    # 1. Weighted Keyword Tiers
    HIGH_RISK = ["breach", "hack", "ransomware", "indicted", "sanctioned", "fraud", "embezzlement"]
    MED_RISK = ["fine", "penalty", "lawsuit", "investigation", "leak", "vulnerability", "subpoena"]
    LOW_RISK = ["gdpr", "privacy", "security", "incident", "compliance", "audit"]
    
    # 2. Negation/Mitigation Keywords
    NEGATORS = ["prevented", "awarded", "mitigated", "defended", "cleared", "dismissed", "protected", "blocks", "stops", "false"]

    score: float = 0.0
    
    # Find all vendor occurrences to calculate proximity
    vendor_matches = list(re.finditer(rf"\b{re.escape(vendor_lower)}\b", text))
    if not vendor_matches:
        vendor_matches = list(re.finditer(re.escape(vendor_lower), text))
        
    # Base Vendor Match
    if vendor_matches:
        score += 0.3
        
    # 3. Sliding Window Analysis
    for category, weight in [(HIGH_RISK, 0.3), (MED_RISK, 0.15), (LOW_RISK, 0.05)]:
        for kw in category:
            for match in re.finditer(rf"\b{re.escape(kw)}\b", text):
                kw_idx: int = match.start()
                
                # Create an 80-character window (~10 words) around the risk keyword
                start_window = max(0, kw_idx - 40)
                end_window = min(len(text), kw_idx + len(kw) + 40)
                context_window = text[start_window:end_window]
                
                # False Positive Reduction: Are there mitigating words nearby?
                is_negated = any(re.search(rf"\b{re.escape(neg)}\b", context_window) for neg in NEGATORS)
                
                if is_negated:
                    # Penalize the score slightly for false alarms (e.g., "attack prevented")
                    score -= (weight * 0.5) 
                else:
                    # Proximity Bonus: Is the vendor name right next to the risk word?
                    actual_weight = weight
                    vendor_in_window = any(
                        (start_window <= v_match.start() <= end_window) 
                        for v_match in vendor_matches
                    )
                    
                    if vendor_in_window:
                        actual_weight *= 1.5 # 50% boost if they share the same context window
                        
                    score += actual_weight
                    
    # Cap the final score strictly between 0.0 and 1.0
    return round(max(0.0, min(score, 1.0)), 2)


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
