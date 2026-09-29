"""Posting-quality signal (Phase 19).

A lightweight, DETERMINISTIC heuristic signal about how trustworthy a job posting looks:
``LIKELY_LEGITIMATE`` / ``NEEDS_REVIEW`` / ``SUSPICIOUS``.

This is a *signal*, never a definitive scam determination — the UI must present it as
such. All external job text is untrusted data: patterns here only DESCRIBE the posting,
they never execute or follow anything found in it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog
from sqlalchemy import inspect as sa_inspect

from app.models.enums import PostingQualitySignal
from app.models.job import Job

logger = structlog.get_logger(__name__)

# Instructions that ask the candidate for money, sensitive data, or off-platform contact.
_SUSPICIOUS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "asks for payment/fees",
        re.compile(
            r"\b(pay|payment|fee|fees|deposit|transfer)\b[^.]{0,40}\b(application|registration|training|processing)\b",
            re.I,
        ),
    ),
    (
        "asks for financial details",
        re.compile(r"\b(bank account|credit card|iban|wire transfer)\b", re.I),
    ),
    (
        "recruits via personal chat app for money",
        re.compile(
            r"\b(whatsapp|telegram)\b[^.]{0,60}\b(pay|fee|transfer|send money)\b", re.I
        ),
    ),
    (
        "asks for identity documents upfront",
        re.compile(
            r"\b(send|provide|upload)\b[^.]{0,40}\b(passport|national id|bank details)\b",
            re.I,
        ),
    ),
    (
        "too-good-to-be-true earnings claim",
        re.compile(
            r"\b(earn|make)\b\s+\$?\d[\d,.]*\s*(per day|daily|per week|weekly|a day)",
            re.I,
        ),
    ),
]

_PLACEHOLDER_COMPANY = re.compile(r"^\s*(company|employer|unknown|n/?a|test)\s*$", re.I)
_FREE_MAIL = re.compile(r"@(gmail|hotmail|yahoo|outlook|mail\.ru)\.\w+", re.I)
_EMAIL_ADDR = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


@dataclass
class PostingQualityResult:
    """Result of the deterministic posting-quality assessment."""

    signal: PostingQualitySignal
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"signal": self.signal.value, "reasons": self.reasons}


def assess_posting_quality(job: Job) -> PostingQualityResult:
    """Assess posting quality from deterministic heuristics on untrusted posting text."""
    reasons: list[str] = []
    suspicious: list[str] = []
    review: list[str] = []

    description = job.description or ""
    requirements = job.requirements or ""
    blob = f"{description}\n{requirements}"

    # 1. Missing employer / placeholder company
    if not job.company or _PLACEHOLDER_COMPANY.match(job.company):
        review.append("missing or placeholder employer name")
        reasons.append("missing employer")

    # 2. Malformed posting — extremely thin content
    if len(blob.strip()) < 120:
        review.append("posting text is unusually short")
        reasons.append("malformed or truncated posting")

    # 3. Inconsistent source data (intake already flagged low extraction confidence)
    if job.extraction_confidence is not None and job.extraction_confidence < 0.5:
        review.append("low extraction confidence from source")
        reasons.append("inconsistent source data")

    # 4. Suspicious instructions inside the posting (data, never followed)
    for label, pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(blob):
            suspicious.append(label)
            reasons.append(f"suspicious instruction: {label}")

    # 5. Unusual application destination — recruiting via free personal mail
    emails = _EMAIL_ADDR.findall(blob)
    route_email = None
    # Only read the routes relationship if it is already loaded — triggering a lazy
    # load here would raise MissingGreenlet in async (non-await) context.
    routes = [] if "routes" in sa_inspect(job).unloaded else (job.routes or [])
    for route in routes:
        if route.email:
            route_email = route.email
            break
    destination = route_email or (emails[0] if emails else "")
    if destination and _FREE_MAIL.search(destination):
        review.append("application destination is a free personal mail provider")
        reasons.append("unusual application destination")

    # 6. Inconsistent contact details — multiple unrelated recipient addresses
    if len({e.lower() for e in emails}) > 1:
        review.append("multiple different contact addresses in posting")
        reasons.append("inconsistent contact details")

    if suspicious:
        return PostingQualityResult(PostingQualitySignal.SUSPICIOUS, reasons)
    if review:
        return PostingQualityResult(PostingQualitySignal.NEEDS_REVIEW, reasons)
    return PostingQualityResult(PostingQualitySignal.LIKELY_LEGITIMATE, reasons)
