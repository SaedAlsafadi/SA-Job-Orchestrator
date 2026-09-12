"""Deterministic facts used before probabilistic package QA.

The LLM may comment on prose quality, but it is not allowed to overrule dates or
canonical candidate entities that the application can validate itself.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_DATE_TOKEN = r"(?:present|current|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4}|\d{4})"
_RANGE_RE = re.compile(rf"(?P<start>{_DATE_TOKEN})\s*(?:-|–|—|to)\s*(?P<end>{_DATE_TOKEN})", re.I)


def parse_end_date(value: str, *, today: date | None = None) -> tuple[date | None, str]:
    """Parse a résumé end date and return (value, precision).

    PRESENT/CURRENT resolve to today. A year-only value is deliberately marked
    ``year`` so callers can avoid claiming that the current year is in the future.
    """
    now = today or date.today()
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    if cleaned in {"present", "current"}:
        return now, "current"
    if re.fullmatch(r"\d{4}", cleaned):
        year = int(cleaned)
        return date(year, 12, 31), "year"
    match = re.fullmatch(r"([a-z]+)\s+(\d{4})", cleaned)
    if not match or match.group(1) not in _MONTHS:
        return None, "unknown"
    month, year = _MONTHS[match.group(1)], int(match.group(2))
    # First day is enough for the only decision made here: is this month future?
    return date(year, month, 1), "month"


def date_future_status(value: str, *, today: date | None = None) -> str:
    """Return FUTURE, NOT_FUTURE, or UNKNOWN for a résumé end-date token."""
    now = today or date.today()
    parsed, precision = parse_end_date(value, today=now)
    if parsed is None:
        return "UNKNOWN"
    if precision == "year" and parsed.year == now.year:
        return "UNKNOWN"
    return "FUTURE" if parsed > now else "NOT_FUTURE"


def date_ranges(text: str) -> list[dict[str, str]]:
    """Extract deterministic date-range verdicts from package text."""
    return [
        {
            "range": match.group(0),
            "start": match.group("start"),
            "end": match.group("end"),
            "end_status": date_future_status(match.group("end")),
        }
        for match in _RANGE_RE.finditer(text or "")
    ]


def _prefer_resume_spelling(value: str, resume_text: str) -> str:
    match = re.search(re.escape(value), resume_text or "", re.I)
    return match.group(0) if match else value


def build_protected_facts(candidate: dict, resume_text: str) -> dict[str, list[str]]:
    """Collect authoritative entity strings, preferring their résumé spelling."""
    identity = candidate.get("identity") or {}
    full_name = " ".join(
        part for part in [identity.get("first_name", ""), identity.get("last_name", "")] if part
    ).strip()
    facts: dict[str, list[str]] = {
        "candidate_names": [full_name] if full_name else [],
        "employers": [e.get("company", "") for e in candidate.get("experience") or []],
        "degrees": [e.get("degree", "") for e in candidate.get("education") or []],
        "institutions": [e.get("institution", "") for e in candidate.get("education") or []],
        "certifications": [e.get("name", "") for e in candidate.get("certifications") or []],
        "projects": [e.get("name", "") for e in candidate.get("projects") or []],
    }
    return {
        key: [_prefer_resume_spelling(str(value).strip(), resume_text) for value in values if value]
        for key, values in facts.items()
    }


def protected_entity_issues(texts: list[str], facts: dict[str, list[str]]) -> list[dict[str, str]]:
    """Flag likely renamed protected entities without requiring exact-string matching."""
    combined = "\n".join(t for t in texts if t)
    words = re.findall(r"[A-Za-z][A-Za-z.&'-]*", combined)
    issues: list[dict[str, str]] = []
    for category, values in facts.items():
        for canonical in values:
            if canonical in combined:
                continue
            canonical_words = re.findall(r"[A-Za-z][A-Za-z.&'-]*", canonical)
            if not canonical_words:
                continue
            width = len(canonical_words)
            for idx in range(max(0, len(words) - width + 1)):
                candidate = " ".join(words[idx:idx + width])
                if candidate.casefold() == canonical.casefold() or (
                    len(canonical) >= 6 and SequenceMatcher(None, candidate.casefold(), canonical.casefold()).ratio() >= .86
                ):
                    issues.append({
                        "kind": "protected_entity_changed",
                        "detail": f'Preserve canonical {category[:-1]} spelling: "{canonical}" (found "{candidate}").',
                        "severity": "warning",
                    })
                    break
    return issues


def restore_protected_entities(text: str, facts: dict[str, list[str]]) -> str:
    """Restore a referenced near-match name to its canonical spelling.

    Only same-width word spans with high similarity are replaced, and an absent
    entity is never inserted. This keeps model spelling drift out of persisted
    documents without inventing candidate facts.
    """
    restored = text
    for values in facts.values():
        for canonical in values:
            if not canonical or canonical.casefold() in restored.casefold():
                continue
            canonical_words = re.findall(r"[A-Za-z][A-Za-z.&'-]*", canonical)
            if not canonical_words:
                continue
            pattern = re.compile(
                r"(?<![A-Za-z])"
                + r"\s+".join(r"([A-Za-z][A-Za-z.&'-]*)" for _ in canonical_words)
                + r"(?![A-Za-z])"
            )
            for match in pattern.finditer(restored):
                raw_candidate = " ".join(match.groups())
                candidate = raw_candidate.rstrip(".,;:!?")
                trailing = raw_candidate[len(candidate):]
                if (
                    len(canonical) >= 6
                    and SequenceMatcher(None, candidate.casefold(), canonical.casefold()).ratio() >= .86
                ):
                    restored = restored[:match.start()] + canonical + trailing + restored[match.end():]
                    break
    return restored


def llm_issue_overruled(issue: object, facts: dict[str, list[str]]) -> bool:
    """Return true only when deterministic evidence disproves an LLM warning."""
    detail = str(getattr(issue, "detail", ""))
    lowered = detail.casefold()
    if "future" in lowered:
        ranges = date_ranges(detail)
        if ranges and all(item["end_status"] == "NOT_FUTURE" for item in ranges):
            return True
    if ("unsupported" in lowered or "not supported" in lowered) and (
        "degree" in lowered or "b.sc" in lowered or "bsc" in lowered or "bachelor" in lowered
    ):
        return bool(facts.get("degrees"))
    return False
