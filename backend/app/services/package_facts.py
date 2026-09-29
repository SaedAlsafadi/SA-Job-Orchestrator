"""Deterministic facts used before probabilistic package QA.

The LLM may comment on prose quality, but it is not allowed to overrule dates or
canonical candidate entities that the application can validate itself.
"""

from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from typing import TypedDict

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_DATE_TOKEN = (
    r"(?:present|current|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)\s+\d{4}|\d{4})"
)
_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE_TOKEN})\s*(?:-|\u2013|\u2014|to)\s*(?P<end>{_DATE_TOKEN})",
    re.I,
)
_ENTITY_WORD_RE = re.compile(r"[A-Za-z]+(?:[.&'-][A-Za-z]+)*")


class ProtectedEntity(TypedDict):
    """Canonical entity plus the evidence that authorizes it."""

    category: str
    canonical: str
    source: str
    evidence_ref: str | None


class ProtectedEntityViolation(TypedDict):
    """Structured, non-reasoning explanation of one entity mismatch."""

    category: str
    canonical: str
    generated: str
    difference: str
    source: str
    evidence_ref: str | None
    confidence: float
    safe_to_restore: bool


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


def _prefer_resume_spelling(value: str, resume_text: str) -> tuple[str, bool]:
    match = re.search(re.escape(value), resume_text or "", re.I)
    return (match.group(0), True) if match else (value, False)


def build_protected_entity_map(
    candidate: dict,
    resume_text: str,
    *,
    job_company: str | None = None,
    job_title: str | None = None,
) -> list[ProtectedEntity]:
    """Build the canonical generation contract with provenance references."""
    entities: list[ProtectedEntity] = []

    def add(
        category: str, value: object, source: str, evidence_ref: str | None = None
    ) -> None:
        cleaned = str(value or "").strip()
        if not cleaned:
            return
        canonical, found_in_resume = _prefer_resume_spelling(cleaned, resume_text)
        entities.append(
            {
                "category": category,
                "canonical": canonical,
                "source": "Resume.content_text" if found_in_resume else source,
                "evidence_ref": evidence_ref,
            }
        )

    identity = candidate.get("identity") or {}
    full_name = " ".join(
        part
        for part in [identity.get("first_name", ""), identity.get("last_name", "")]
        if part
    ).strip()
    add(
        "candidate_name",
        full_name,
        "CandidateProfile.identity",
        "candidate_profile.identity",
    )
    for index, item in enumerate(candidate.get("experience") or []):
        add(
            "employer",
            item.get("company"),
            "CandidateProfile.experience",
            item.get("evidence_id") or f"experience[{index}]",
        )
    for index, item in enumerate(candidate.get("education") or []):
        ref = item.get("evidence_id") or f"education[{index}]"
        add("degree_name", item.get("degree"), "CandidateProfile.education", ref)
        add("institution", item.get("institution"), "CandidateProfile.education", ref)
    for index, item in enumerate(candidate.get("certifications") or []):
        add(
            "certification",
            item.get("name"),
            "CandidateProfile.certifications",
            item.get("evidence_id") or f"certification[{index}]",
        )
    for index, item in enumerate(candidate.get("projects") or []):
        add(
            "project_name",
            item.get("name"),
            "CandidateProfile.projects",
            item.get("evidence_id") or f"project[{index}]",
        )
    add("job_company", job_company, "Job.company", "job.company")
    add("job_title", job_title, "Job.title", "job.title")
    return entities


_FACT_KEYS = {
    "candidate_name": "candidate_names",
    "employer": "employers",
    "degree_name": "degrees",
    "institution": "institutions",
    "certification": "certifications",
    "project_name": "projects",
    "job_company": "job_companies",
    "job_title": "job_titles",
}


def build_protected_facts(candidate: dict, resume_text: str) -> dict[str, list[str]]:
    """Collect authoritative entity strings, preferring their résumé spelling."""
    facts: dict[str, list[str]] = {value: [] for value in _FACT_KEYS.values()}
    for entity in build_protected_entity_map(candidate, resume_text):
        facts[_FACT_KEYS[entity["category"]]].append(entity["canonical"])
    return {key: values for key, values in facts.items() if values}


def format_protected_entity_contract(entities: list[ProtectedEntity]) -> str:
    """Render an explicit immutable-data contract for generation prompts."""
    lines = [
        "PROTECTED FACTS — COPY EXACTLY.",
        "Do not translate, normalize, respell, expand, abbreviate, or improve these strings.",
        "If you reference one, copy its CANONICAL value verbatim:",
    ]
    for entity in entities:
        evidence = (
            f"; evidence={entity['evidence_ref']}" if entity["evidence_ref"] else ""
        )
        lines.append(
            f"- {entity['category'].upper()}: {entity['canonical']} "
            f"(source={entity['source']}{evidence})"
        )
    return "\n".join(lines)


def _entity_variant(
    text: str,
    canonical: str,
    all_canonicals: list[str],
) -> tuple[int, int, str, str, float, bool] | None:
    """Find the strongest sliding-token variant and classify restoration safety."""
    exact_casefold = re.search(
        rf"(?<![A-Za-z0-9]){re.escape(canonical)}(?![A-Za-z0-9])",
        text,
        re.I,
    )
    if exact_casefold:
        generated = exact_casefold.group(0)
        if generated == canonical:
            return None
        if len(canonical.strip()) < 4:
            # Short case-only strings (for example "IT" vs the pronoun "It") are
            # too ambiguous to rewrite without surrounding structured context.
            return None
        return (
            exact_casefold.start(),
            exact_casefold.end(),
            generated,
            "CASING",
            1.0,
            True,
        )

    canonical_words = _ENTITY_WORD_RE.findall(canonical)
    word_matches = list(_ENTITY_WORD_RE.finditer(text))
    width = len(canonical_words)
    if not width or len(word_matches) < width:
        return None
    canonical_normalized = " ".join(canonical_words)
    if len(canonical_normalized) < 6:
        return None
    candidates: list[tuple[float, int, int, str]] = []
    for index in range(len(word_matches) - width + 1):
        first, last = word_matches[index], word_matches[index + width - 1]
        generated = text[first.start() : last.end()]
        normalized = " ".join(
            match.group(0) for match in word_matches[index : index + width]
        )
        ratio = SequenceMatcher(
            None, normalized.casefold(), canonical_normalized.casefold()
        ).ratio()
        if ratio >= 0.86:
            candidates.append((ratio, first.start(), last.end(), generated))
    if not candidates:
        return None
    ratio, start, end, generated = max(candidates, key=lambda item: item[0])
    normalized_generated = " ".join(_ENTITY_WORD_RE.findall(generated))
    difference = (
        "SPACING"
        if normalized_generated.casefold() == canonical_normalized.casefold()
        else "TYPO"
    )

    plausible = 0
    for other in all_canonicals:
        other_words = _ENTITY_WORD_RE.findall(other)
        if len(other_words) != width:
            continue
        other_ratio = SequenceMatcher(
            None,
            normalized_generated.casefold(),
            " ".join(other_words).casefold(),
        ).ratio()
        if other_ratio >= 0.86 and other_ratio >= ratio - 0.05:
            plausible += 1
    safe = plausible == 1 and difference in {"CASING", "SPACING", "TYPO"}
    return start, end, generated, difference, ratio, safe


def protected_entity_violations(
    texts: list[str],
    entities: list[ProtectedEntity],
) -> list[ProtectedEntityViolation]:
    """Return structured mismatches including provenance and correction safety."""
    combined = "\n".join(text for text in texts if text)
    canonicals = list(dict.fromkeys(entity["canonical"] for entity in entities))
    violations: list[ProtectedEntityViolation] = []
    for entity in entities:
        if entity["canonical"] in combined:
            continue
        variant = _entity_variant(combined, entity["canonical"], canonicals)
        if not variant:
            continue
        _, _, generated, difference, confidence, safe = variant
        violations.append(
            {
                "category": entity["category"],
                "canonical": entity["canonical"],
                "generated": generated,
                "difference": difference,
                "source": entity["source"],
                "evidence_ref": entity["evidence_ref"],
                "confidence": round(confidence, 3),
                "safe_to_restore": safe,
            }
        )
    return violations


def protected_entity_issues(
    texts: list[str], facts: dict[str, list[str]]
) -> list[dict[str, str]]:
    """Flag likely renamed protected entities without requiring exact-string matching."""
    reverse_categories = {value: key for key, value in _FACT_KEYS.items()}
    entities: list[ProtectedEntity] = [
        {
            "category": reverse_categories.get(category, category.rstrip("s")),
            "canonical": canonical,
            "source": "canonical candidate evidence",
            "evidence_ref": None,
        }
        for category, values in facts.items()
        for canonical in values
    ]
    return [
        {
            "kind": "protected_entity_changed",
            "detail": (
                f'Preserve canonical {violation["category"]} spelling: '
                f'"{violation["canonical"]}" (found "{violation["generated"]}").'
            ),
            "severity": "warning",
        }
        for violation in protected_entity_violations(texts, entities)
    ]


def restore_protected_entities(text: str, facts: dict[str, list[str]]) -> str:
    """Restore a referenced near-match name to its canonical spelling.

    Only same-width word spans with high similarity are replaced, and an absent
    entity is never inserted. This keeps model spelling drift out of persisted
    documents without inventing candidate facts.
    """
    restored = text
    canonicals = list(
        dict.fromkeys(
            canonical for values in facts.values() for canonical in values if canonical
        )
    )
    for canonical in canonicals:
        if canonical in restored:
            continue
        variant = _entity_variant(restored, canonical, canonicals)
        if variant and variant[-1]:
            start, end = variant[0], variant[1]
            restored = restored[:start] + canonical + restored[end:]
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
        "degree" in lowered
        or "b.sc" in lowered
        or "bsc" in lowered
        or "bachelor" in lowered
    ):
        return bool(facts.get("degrees"))
    return False
