"""Work-authorization requirement detection (Phase 19).

DETERMINISTIC detection of EXPLICIT work-authorization requirements stated in a posting.
Only explicit statements are detected; UNKNOWN remains UNKNOWN. Nationality, ethnicity,
religion, or sensitive characteristics are NEVER inferred from indirect signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class WorkAuthorizationResult:
    """Explicit work-authorization requirements detected in a posting."""

    status: str  # RESTRICTED | UNKNOWN | NONE
    requirements: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "requirements": self.requirements,
            "evidence": self.evidence,
        }


# Each pattern maps to a canonical requirement label. Only explicit phrasings match.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "sponsorship_unavailable",
        re.compile(
            r"\b(no|not|unavailable|cannot|can'?t|does not|doesn'?t)\b[^.]{0,30}\b(sponsorship|visa sponsorship|provide sponsorship)\b",
            re.I,
        ),
    ),
    (
        "sponsorship_unavailable",
        re.compile(
            r"\b(sponsorship|visa)\b[^.]{0,20}\b(not|is not)\b[^.]{0,20}\b(available|provided|offered)\b",
            re.I,
        ),
    ),
    (
        "work_authorization_required",
        re.compile(
            r"\b(must|only|required|candidates? (must|should))\b[^.]{0,40}\b(work authorization|authorised to work|authorized to work|right to work)\b",
            re.I,
        ),
    ),
    (
        "saudi_citizen_required",
        re.compile(
            r"\b(saudi (citizens?|nationals?)|saudization)\b[^.]{0,30}\b(only|must|required)\b",
            re.I,
        ),
    ),
    (
        "saudi_citizen_required",
        re.compile(
            r"\b(only|open (only|to))\b[^.]{0,20}\bsaudi (citizens?|nationals?)\b", re.I
        ),
    ),
    (
        "gcc_restriction",
        re.compile(
            r"\bgcc (citizens?|nationals?)\b[^.]{0,30}\b(only|must|required)\b", re.I
        ),
    ),
    (
        "local_residency_required",
        re.compile(
            r"\b(transferable (iqama|residency)|valid (iqama|residency permit))\b[^.]{0,30}\b(required|must|only)\b",
            re.I,
        ),
    ),
]

# Explicit statements that authorization is available (status NONE).
_AVAILABLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "sponsorship_available",
        re.compile(
            r"\b(visa )?sponsorship\b[^.]{0,30}\b(available|provided|offered|supported)\b",
            re.I,
        ),
    ),
]


def detect_work_requirements(job_text: str) -> WorkAuthorizationResult:
    """Detect explicit work-authorization requirements in untrusted posting text."""
    requirements: list[str] = []
    evidence: list[str] = []

    for label, pattern in _PATTERNS:
        match = pattern.search(job_text or "")
        if match and label not in requirements:
            requirements.append(label)
            # Keep a short verbatim snippet as evidence for the review UI.
            start = max(0, match.start() - 30)
            snippet = (job_text[start : match.end() + 30]).strip().replace("\n", " ")
            evidence.append(snippet)

    if requirements:
        return WorkAuthorizationResult("RESTRICTED", requirements, evidence)

    for label, pattern in _AVAILABLE_PATTERNS:
        if pattern.search(job_text or ""):
            return WorkAuthorizationResult("NONE", [], [label])

    # Nothing explicit stated — UNKNOWN stays UNKNOWN. Never inferred.
    return WorkAuthorizationResult("UNKNOWN", [], [])
