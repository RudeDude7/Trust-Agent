"""
sanitization.py — Shared Prompt Injection Detection

Heuristic regex scanner to detect and strip potential indirect prompt injections
from untrusted content (web-scraped OSINT, vendor PDFs, VLM-captioned images)
before they reach any LLM prompt.
"""

import logging
import re
from typing import Any

log = logging.getLogger("sanitization")

# Common jailbreak and prompt injection attack vectors
_INJECTION_PATTERNS = re.compile(
    r"|".join([
        r"ignore (all )?previous instructions",
        r"system prompt",
        r"you are now",
        r"forget all",
        r"bypass (the|all)? rules",
        r"print out your",
        r"disregard",
        r"override (your|all) instructions",
        r"new instructions",
        r"act as if",
        r"pretend you",
        r"reveal your",
        r"output your (system|initial)",
    ]),
    re.IGNORECASE,
)


def sanitize_osint_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Scans OSINT findings (dicts with 'title' and 'snippet' keys) for
    prompt injection patterns. Returns only clean findings.
    """
    safe = []
    for finding in findings:
        text = str(finding.get("title", "")) + " " + str(finding.get("snippet", ""))
        if _INJECTION_PATTERNS.search(text):
            log.warning(
                "PROMPT INJECTION DETECTED & BLOCKED in OSINT finding from %s",
                finding.get("source_url", "unknown"),
            )
            continue
        safe.append(finding)
    return safe


def sanitize_text(text: str, source_label: str = "unknown") -> str:
    """
    Scans a plain text string (e.g. a retrieved policy chunk) for prompt
    injection patterns. Returns the original text if clean, or an empty
    string if injection is detected.
    """
    if _INJECTION_PATTERNS.search(text):
        log.warning(
            "PROMPT INJECTION DETECTED & BLOCKED in RAG chunk from %s (first 80 chars: '%s')",
            source_label,
            text[:80],
        )
        return ""
    return text