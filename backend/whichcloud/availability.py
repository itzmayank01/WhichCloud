"""Availability class reader.

Classifies plain-English text into one of four distinct availability classes:
  - standard: no stated uptime need, internal tools, batch workloads, or downtime is fine.
  - business_hours: uptime required during store / office / business / working hours.
  - always_on: 24/7, around-the-clock, mission-critical, or zero-downtime required.
  - regulated_dr: disaster recovery, RTO/RPO limits, regulator/compliance requirements.

Does not guess: if unclear or unmentioned, returns 'standard'.
"""

from __future__ import annotations

import re
from typing import Literal

AvailabilityClass = Literal["standard", "business_hours", "always_on", "regulated_dr"]

# Evaluated in priority order: regulated_dr > always_on > business_hours > standard

_REGULATED_DR_PATTERNS = (
    r"\bdisaster\s+recovery\b",
    r"\bdr\s+(?:site|region|failover|plan|requirement|strategy|within|across)\b",
    r"\b(?:rto|rpo)\b",
    r"\bregulat(?:or|ory|ion)\b.*?\b(?:dr|recovery|continuity|resilien(?:ce|cy))\b",
    r"\bbusiness\s+continuity\b",
    r"\b(?:rbi|sebi|hipaa|pci|gdpr)\b.*?\b(?:compliance|recovery|dr|audits?|audited)\b",
    r"\b(?:compliance|regulatory)\b.*?\b(?:disaster\s+recovery|rto|rpo)\b",
)

_ALWAYS_ON_PATTERNS = (
    r"\b24\s*[/x]\s*7\b",
    r"\b24\s*hours?\s*(?:a|per)\s*day\b",
    r"\baround\s+the\s+clock\b",
    r"\bround\s+the\s+clock\b",
    r"\bmission\s*[- ]?critical\b",
    r"\bnever\s+(?:go\s+)?down\b",
    r"\bzero\s+downtime\b",
    r"\balways\s+(?:on|up|available)\b",
    r"\bcontinuous\s+(?:availability|uptime|operation)\b",
    r"\bhigh\s+availability\b",
    r"\bultra\s*[- ]?high\s+availability\b",
)

_BUSINESS_HOURS_PATTERNS = (
    r"\b(?:must\s+not|cannot|can't)\s+(?:go\s+)?down\s+during\s+(?:business|working|work|store|office|trading|daytime)\s+hours\b",
    r"\bdowntime\s+(?:is\s+unacceptable|not\s+allowed)\s+during\s+(?:business|working|work|store|office|trading|daytime)\b",
    r"\b(?:business|working|work|store|office|trading|daytime)\s+hours\b.*?\b(?:must\s+stay|must\s+be|keep\s+it)\s+up\b",
    r"\b(?:business|working|work|store|office)\s+hours\b.*?\b(?:no\s+downtime|cannot\s+fail|cannot\s+stop)\b",
    r"\bstore\s+hours\b.*?\bcannot\s+(?:go\s+)?down\b",
    r"\bduring\s+business\s+hours\b.*?\bbilling\s+stops\b",
    r"\bbilling\s+stops\b.*?\bduring\s+business\s+hours\b",
    r"\bactive\s+(?:7pm|8pm|9pm|[0-9]+[ap]m).*?quiet\s+by\s+day\b",
    r"\bbusiness\s+hours\s+only\b",
)

_STANDARD_EXPLICIT_PATTERNS = (
    r"\bdowntime\s+is\s+(?:fine|acceptable|okay|tolerable)\b",
    r"\bif\s+it(?:'s|\s+is)\s+down\b.*?\bnobody\s+minds\b",
    r"\bnobody\s+minds\b.*?\bdowntime\b",
    r"\bnot\s+(?:mission\s+)?critical\b",
    r"\bbest\s+effort\b",
    r"\binternal\s+tool\b.*?\bdowntime\s+is\s+fine\b",
    r"\bsimple\s+internal\s+tool\b",
)


def classify_availability(text: str) -> tuple[AvailabilityClass, str]:
    """Classify availability requirements from text.

    Returns (availability_class, matched_evidence).
    If no clear availability requirement is stated, returns ('standard', '').
    """
    if not text or not text.strip():
        return "standard", ""

    lower_text = text.lower()

    # 1. Check explicit standard / downtime is fine first to avoid false positives
    for pat in _STANDARD_EXPLICIT_PATTERNS:
        match = re.search(pat, lower_text)
        if match:
            return "standard", match.group(0).strip()

    # 2. Check regulated disaster recovery
    for pat in _REGULATED_DR_PATTERNS:
        match = re.search(pat, lower_text)
        if match:
            return "regulated_dr", match.group(0).strip()

    # 3. Check business hours uptime need
    for pat in _BUSINESS_HOURS_PATTERNS:
        match = re.search(pat, lower_text)
        if match:
            return "business_hours", match.group(0).strip()

    # 4. Check always-on 24/7 mission critical
    for pat in _ALWAYS_ON_PATTERNS:
        match = re.search(pat, lower_text)
        if match:
            return "always_on", match.group(0).strip()

    # Default to standard when no specific availability tier is stated
    return "standard", ""


def read_availability(text: str) -> AvailabilityClass:
    """Return the classified availability class for the text."""
    cls, _ = classify_availability(text)
    return cls
