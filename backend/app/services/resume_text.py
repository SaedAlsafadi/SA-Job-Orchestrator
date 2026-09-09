"""Resume text normalization and structured parsing (Phase 19.5).

Uploaded base CV PDFs often extract as POSITIONAL text: headings rendered with
letter spacing come out as "W O R K  E X P E R I E N C E", adjacent text boxes
glue onto one line ("...lifecycle.Technology Operations...WORK EXPERIENCE"),
header letters fuse with neighboring words ("InstitutesP ROJECTS :", "SKILL SAI"),
and bullet glyphs mangle into mojibake. The previous builder matched section
headers EXACTLY, so none of these forms ever matched and nearly the whole
resume collapsed into whichever plain header happened to appear, while
projects were never extracted at all.

This module normalizes that text BEFORE structuring:
1. bullet mojibake is converted to a real bullet
2. letter-spaced runs are collapsed back into words
3. glued ALL-CAPS section headers are split onto their own lines (matched
   letter-by-letter so fused/partially-spaced forms are recovered too)

Then it builds the structured document with ALL base sections preserved.
"""

from __future__ import annotations

import re

# Real bullet character used everywhere after normalization.
BULLET = "\u2022"

# Mojibake / variant bullet forms observed in extracted PDF text.
_BULLET_FORMS = [
    "\u00b7",                # middle dot
    "\u2023", "\u25aa",      # triangle / small square bullets
    "\u00f2",                # PDF-extraction mangling of the bullet glyph
    "\u00e2\u20ac\u00a2",    # UTF-8 bullet read as CP1252
    "\u00c3\u00a2\u20ac\u00a2",
    "\u0393\u00c7\u00a2",    # UTF-8 bullet read as CP1251-style
    "\u252c\u00a7",          # middle-dot mojibake variant
    "\u00c2\u2022", "\u00c2\u00b7",
]

# Characters that can introduce a bullet line after normalization.
_BULLET_PREFIXES = BULLET + "\u00b7-*"

# Section headers (single source of truth lives in the document parser).
_SECTION_HEADERS: list[str] | None = None


def _section_headers() -> list[str]:
    """Lazily import the canonical header list from the document parser."""
    global _SECTION_HEADERS
    if _SECTION_HEADERS is None:
        from app.core.documents.parser import _SECTION_HEADERS as headers

        _SECTION_HEADERS = list(headers)
    return _SECTION_HEADERS


def _normalize_bullets(text: str) -> str:
    """Convert every mojibake bullet form to a real bullet character."""
    for form in _BULLET_FORMS:
        if form and form != BULLET:
            text = text.replace(form, BULLET)
    return text


def _join_dotted_runs(segment: str) -> str:
    """Tighten "B . Sc ." style abbreviations left by letter collapse."""
    return re.sub(r"(?<=[A-Za-z0-9]) \. (?=[A-Za-z0-9])", ".", segment)


def _collapse_letter_spaced(segment: str) -> str:
    """Collapse letter-spaced runs inside one segment.

    "S A E D" becomes "SAED" and "e c h n o l o g y" becomes "technology",
    while normal multi-character words pass through untouched. Single "."
    tokens inside a letter run (as in "B . Sc .") stay joined, and a lone
    uppercase letter glued after a period ("lifecycle.T echnology") is
    re-attached to the following word.
    """
    tokens = segment.split(" ")
    if len(tokens) < 2:
        return segment
    fixed: list[str] = []
    for tok in tokens:
        if (
            fixed
            and re.match(r"^.*\.[A-Z]$", fixed[-1])
            and tok
            and tok[0].islower()
        ):
            # "lifecycle.T" + "echnology" -> "lifecycle." + "Technology"
            moved = fixed[-1][-1]
            fixed[-1] = fixed[-1][:-1]
            tok = moved + tok
        fixed.append(tok)
    tokens = fixed

    out: list[str] = []
    run: list[str] = []
    for tok in tokens:
        if len(tok) == 1 and (tok.isalnum() or tok == "."):
            run.append(tok)
        else:
            if run:
                out.append("".join(run))
                run = []
            out.append(tok)
    if run:
        out.append("".join(run))
    return _join_dotted_runs(" ".join(out))


def _header_pattern(upper_header: str) -> re.Pattern[str]:
    """Build a letter-tolerant pattern for an ALL-CAPS section header.

    Letters inside a word may be separated by any amount of space (covering
    "W O R K", "SKILL S", "P ROJECTS"); words must be separated by at least
    one space. An optional trailing colon is consumed. The match is blocked
    when an uppercase letter immediately precedes it ("MYEXPERIENCE") or a
    lowercase word follows it ("...of EXPERIENCE in...").
    """
    words = [r"\s*".join(re.escape(ch) for ch in word) for word in upper_header.split()]
    body = r"\s+".join(words)
    return re.compile(r"(?<![A-Z])" + body + r"\s*:?(?![a-z])")


def _preceded_by_lowercase_word(seg: str, start: int) -> bool:
    """True when the match is preceded by an all-lowercase prose word.

    Blocks false splits like "...years of EXPERIENCE" while still allowing
    "...Present WORK EXPERIENCE" ("Present" is capitalized).
    """
    pre = seg[:start].rstrip()
    if not pre or not (pre[-1].isalpha() and pre[-1].islower()):
        return False
    m = re.search(r"[A-Za-z]+$", pre)
    return bool(m) and m.group().islower()


def _split_glued_headers(line: str) -> list[str]:
    """Break a line around ALL-CAPS section headers glued to other content."""
    results = [line]
    # Longest headers first so "WORK EXPERIENCE" splits before "EXPERIENCE".
    headers = sorted(_section_headers(), key=len, reverse=True)
    for header in headers:
        upper = header.upper()
        if len(upper) < 5:
            continue
        pattern = _header_pattern(upper)
        pieces: list[str] = []
        for seg in results:
            matches = [
                m for m in pattern.finditer(seg)
                if not _preceded_by_lowercase_word(seg, m.start())
            ]
            if not matches:
                pieces.append(seg)
                continue
            cursor = 0
            for m in matches:
                pre = seg[cursor:m.start()].strip()
                if pre:
                    pieces.append(pre)
                pieces.append(seg[m.start():m.end()].strip().rstrip(":").strip())
                cursor = m.end()
            post = seg[cursor:].strip()
            if post:
                pieces.append(post)
        results = pieces
    return [r for r in results if r]


def _merge_header_fragments(lines: list[str]) -> list[str]:
    """Join section-header fragments that were split across raw lines.

    Positional extraction often breaks a letter-spaced header across lines
    ("W O R K" / "E X P E R I E N C E" or "P ROFESSIONAL" / "SUMMARY"). After
    collapse these become short uppercase fragments; joining the window and
    matching space-stripped header names reassembles them.
    """
    header_nospace = set(_nospace_keys())
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        matched = False
        if line and line.lower().replace(" ", "") not in header_nospace:
            joined = line
            for w in range(1, 4):
                if i + w >= len(lines):
                    break
                frag = lines[i + w]
                if not frag or len(frag) > 20 or frag.upper() != frag:
                    break
                joined = joined + " " + frag
                if joined.lower().replace(" ", "") in header_nospace:
                    merged.append(joined)
                    i += w + 1
                    matched = True
                    break
        if not matched:
            merged.append(line)
            i += 1
    return merged


def normalize_resume_text(text: str) -> str:
    """Normalize positionally-extracted resume text so structure can be recovered.

    Steps: bullet mojibake repair, letter-spacing collapse (double spaces act
    as word boundaries), splitting glued ALL-CAPS section headers onto their
    own lines, and re-joining header fragments broken across raw lines.
    """
    if not text:
        return text
    text = _normalize_bullets(text)
    out_lines: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line.strip():
            out_lines.append("")
            continue
        segments = re.split(r"\s{2,}", raw_line.strip())
        collapsed = " ".join(_collapse_letter_spaced(seg) for seg in segments)
        # Positional extractors also drop whitespace between a sentence and
        # the next capitalized word ("demand.React"). Preserve dotted tech
        # names such as Node.js and ASP.NET by requiring lower-to-Titlecase.
        collapsed = re.sub(r"(?<=[a-z])([.!?])(?=[A-Z][a-z])", r"\1 ", collapsed)
        out_lines.extend(_split_glued_headers(collapsed))
    out_lines = _merge_header_fragments(out_lines)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out_lines))


# ---------------------------------------------------------------------------
# Structured document building (replaces the lossy builder in services.resume)
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_INSTITUTION_HINTS = (
    "university", "institute", "college", "school", "academy", "polytechnic",
)
_PHONE_FALLBACK_RE = re.compile(r"\+\d{1,3}[\s\-]\d{2,3}[\s\-]\d{3,4}(?:[\s\-]\d{2,4})?")


def _is_bullet_line(stripped: str) -> bool:
    """True when the line starts with a bullet marker."""
    return stripped[:1] in (BULLET, "\u00b7", "-", "*") and len(stripped) > 1


def _nospace_keys() -> dict[str, str]:
    """Map space-stripped header names to canonical header names."""
    return {h.replace(" ", ""): h for h in _section_headers()}


def _split_sections(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Split normalized lines into sections; return (sections, pre-header lines).

    A line counts as a header when it equals a known header (ignoring spaces
    inside the name, so the collapsed "SKILL S" still matches "skills") or
    starts with "Header:" followed by content.
    """
    nospace = _nospace_keys()
    sections: dict[str, str] = {}
    pre: list[str] = []
    current = ""
    buf: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        key = stripped.lower().rstrip(":").strip()
        canonical = nospace.get(key.replace(" ", ""), "")
        if not canonical and ":" in stripped:
            label = stripped.split(":", 1)[0].strip().lower()
            canonical = nospace.get(label.replace(" ", ""), "")
            if canonical:
                # "Languages: Arabic..." -> header + first content line.
                rest = stripped.split(":", 1)[1].strip()
                if current:
                    sections[current] = "\n".join(buf).strip()
                current = canonical
                buf = [rest] if rest else []
                continue
        if canonical:
            if current:
                sections[current] = "\n".join(buf).strip()
            current = canonical
            buf = []
        elif current:
            buf.append(stripped)
        else:
            pre.append(stripped)
    if current:
        sections[current] = "\n".join(buf).strip()
    return sections, [p for p in pre if p]


def _first(sections: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = sections.get(key, "")
        if value:
            return value
    return ""


def _append_description(entry: dict, line: str) -> None:
    """Append a line to an entry description, joining wrapped prose."""
    desc = entry.get("description", "")
    if desc and not desc.rstrip().endswith((".", "!", "?", ":")):
        entry["description"] = desc.rstrip() + " " + line + "\n"
    else:
        entry["description"] = desc + line + "\n"


def parse_experience_section(text: str) -> list[dict]:
    """Parse an experience section into entries.

    Non-bullet lines start a new entry unless they are a wrapped continuation
    of the previous sentence. "Title | Company | Duration" lines are split
    into their fields; bullet lines append to the entry description.
    """
    entries: list[dict] = []
    current: dict | None = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_bullet_line(stripped):
            if current is not None:
                _append_description(current, stripped.lstrip(_BULLET_PREFIXES + " "))
            continue
        desc_open = (
            current is not None
            and current["description"]
            and not current["description"].rstrip().endswith((".", "!", "?"))
        )
        looks_like_title = "|" in stripped or (
            len(stripped) <= 60 and not stripped.endswith((".", "!", "?"))
        )
        if current is not None and (
            not looks_like_title or stripped[0].islower() or (desc_open and "|" not in stripped)
        ):
            _append_description(current, stripped)
            continue
        if current is not None:
            entries.append(current)
        title, company, duration = stripped, "", ""
        if "|" in stripped:
            parts = [p.strip() for p in stripped.split("|") if p.strip()]
            if len(parts) >= 2:
                title = parts[0]
                company = parts[1]
                if len(parts) >= 3:
                    duration = parts[2]
        current = {"title": title, "company": company, "duration": duration, "description": ""}
    if current is not None:
        entries.append(current)
    return entries


def parse_education_section(text: str) -> list[dict]:
    """Parse an education section into entries.

    "Degree | Institution" lines map directly; bare year-range lines attach
    to the previous entry; other lines start a new degree entry unless they
    look like an institution for the previous one.
    """
    entries: list[dict] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or _is_bullet_line(stripped):
            continue
        if "|" in stripped:
            parts = [p.strip() for p in stripped.split("|") if p.strip()]
            entry = {"degree": parts[0], "institution": "", "year": ""}
            if len(parts) >= 2:
                entry["institution"] = parts[1]
            if len(parts) >= 3:
                entry["year"] = parts[2]
            entries.append(entry)
            continue
        is_year_line = bool(_YEAR_RE.search(stripped)) and len(stripped) <= 40
        if is_year_line and entries:
            entries[-1]["year"] = stripped
            continue
        if entries and not entries[-1]["institution"] and any(
            hint in stripped.lower() for hint in _INSTITUTION_HINTS
        ):
            entries[-1]["institution"] = stripped
            continue
        entries.append({"degree": stripped, "institution": "", "year": ""})
    return entries


def parse_projects_section(text: str) -> list[dict]:
    """Parse a projects section into entries (name + description).

    Non-bullet lines start a project; bullet lines and tech-stack lines
    (several bullet separators on one line) append to the description, with
    wrapped prose joined onto the previous sentence.
    """
    projects: list[dict] = []
    current: dict | None = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_bullet_line(stripped):
            if current is not None:
                _append_description(current, stripped.lstrip(_BULLET_PREFIXES + " "))
            continue
        if current is not None and stripped.count(BULLET) >= 2:
            _append_description(current, stripped)
            continue
        # A bare year-range line is a stray date (often the previous education
        # entry's dates landing after the header), never a project name.
        if _YEAR_RE.search(stripped) and len(stripped) <= 40:
            continue
        looks_like_name = len(stripped) <= 60 and not stripped.endswith((".", "!", "?", ","))
        if current is not None and (
            not looks_like_name or not current["description"]
        ):
            # Long prose / comma-ending lines are description text, not names -
            # including the FIRST description line of a fresh project.
            if not looks_like_name:
                _append_description(current, stripped)
                continue
            if not current["description"]:
                _append_description(current, stripped)
                continue
            projects.append(current)
            current = {"name": stripped, "description": ""}
            continue
        if current is not None:
            projects.append(current)
        current = {"name": stripped, "description": ""}
    if current is not None:
        projects.append(current)
    return projects


def _parse_contact_line(line: str) -> str:
    """Extract a location from a labeled contact line ("Address: X | ...")."""
    for part in line.split("|"):
        part = part.strip()
        if part.lower().startswith("address:"):
            return part.split(":", 1)[1].strip()
    return ""


def build_resume_data_from_text(content_text: str) -> dict:
    """Build the structured template context from raw resume text.

    Normalizes positional PDF-extraction artifacts first, then extracts every
    base section (including projects, which the previous builder dropped) and
    preserves pre-header prose as the summary fallback.
    """
    from app.core.documents.parser import _EMAIL_RE, _GITHUB_RE, _LINKEDIN_RE, _PHONE_RE

    text = normalize_resume_text(content_text)
    lines = text.split("\n")
    name = lines[0].strip() if lines else ""

    email_m = _EMAIL_RE.search(text)
    phone_m = _PHONE_RE.search(text) or _PHONE_FALLBACK_RE.search(text)
    linkedin_m = _LINKEDIN_RE.search(text)
    github_m = _GITHUB_RE.search(text)

    sections, pre_header = _split_sections(lines[1:])

    location = ""
    title = ""
    prose: list[str] = []
    for line in pre_header[:6]:
        if "@" in line or _PHONE_RE.search(line) or _PHONE_FALLBACK_RE.search(line):
            if not location:
                location = _parse_contact_line(line)
            continue
        if not title and len(line) <= 60 and not line.endswith("."):
            title = line
            continue
        prose.append(line)
    prose.extend(pre_header[6:])

    skills_text = _first(
        sections, "skills", "technical skills", "core competencies", "competencies",
    )
    skills = [
        s.strip()
        for s in re.split(r"[,\n" + BULLET + "\u00b7|]", skills_text)
        if s.strip()
    ]

    exp_text = _first(
        sections, "experience", "work experience", "professional experience", "employment",
    )
    experience = parse_experience_section(exp_text) if exp_text else []

    # Salvage: bare single-word "entries" (no company, dates, or description)
    # are skill/category lines the extractor emitted inside the experience
    # region - move them to skills instead of dropping them.
    kept_experience: list[dict] = []
    for entry in experience:
        is_orphan_skill = (
            not entry["company"]
            and not entry["duration"]
            and not entry["description"].strip()
            and len(entry["title"]) <= 30
            and len(entry["title"].split()) <= 3
            and not any(ch.isdigit() for ch in entry["title"])
        )
        if is_orphan_skill:
            skills.append(entry["title"])
        else:
            kept_experience.append(entry)
    experience = kept_experience

    # Split prose fragments out of the skills list: long, sentence-like tokens
    # are summary text the extractor glued after a header. They become the
    # summary fallback when no explicit summary section exists.
    def _is_prose(token: str) -> bool:
        first = token.split()[0].lower() if token.split() else ""
        return (
            len(token) > 45
            or ". " in token
            or token.endswith(".")
            or first in ("and", "with", "or", "that", "experience")
        )

    prose_from_skills = [t for t in skills if _is_prose(t)]
    skills = [t for t in skills if not _is_prose(t)]

    # Salvage: a pre-header "Title | Company | Dates" line is a job entry the
    # extractor emitted before the first section header; the long prose lines
    # right before it are that job's bullets.
    pre_experience: list[dict] = []
    title_idx = next(
        (i for i, line in enumerate(pre_header) if "|" in line and _YEAR_RE.search(line)),
        None,
    )
    if title_idx is not None:
        raw_title_line = pre_header[title_idx]
        parts = [p.strip() for p in raw_title_line.split("|") if p.strip()]
        # The glued line may carry the previous bullet before the real title:
        # "...lifecycle. Technology Operations Specialist | MINNHA IT | ..." -
        # split at the last sentence boundary; the prefix joins the bullets.
        if ". " in parts[0]:
            prefix, parts[0] = parts[0].rsplit(". ", 1)
            parts[0] = parts[0].strip()
        else:
            prefix = ""
        def _is_contact(l: str) -> bool:
            low = l.lower()
            return "@" in l or low.startswith("address:") or "phone:" in low or "linkedin" in low or "github:" in low
        bullets = [l for l in pre_header[:title_idx] if len(l) > 40 and not _is_contact(l)]
        if prefix:
            bullets.append(prefix + ".")
        pre_experience.append({
            "title": parts[0],
            "company": parts[1] if len(parts) > 1 else "",
            "duration": parts[2] if len(parts) > 2 else "",
            "description": "\n".join(bullets) + ("\n" if bullets else ""),
        })
        pre_header = [
            l for i, l in enumerate(pre_header)
            if i > title_idx or (i < title_idx and len(l) <= 40)
        ]
    experience = pre_experience + experience

    edu_text = _first(sections, "education", "academic background")
    education = parse_education_section(edu_text) if edu_text else []

    cert_text = _first(sections, "certifications", "certificates", "licenses")
    certifications = (
        [
            c.strip().lstrip(_BULLET_PREFIXES + " ")
            for c in cert_text.split("\n")
            if c.strip().lstrip(_BULLET_PREFIXES + " ")
        ]
        if cert_text
        else []
    )

    proj_text = _first(sections, "projects", "personal projects", "key projects")
    projects = parse_projects_section(proj_text) if proj_text else []

    # Salvage: when the PDF never extracted a SKILLS header, the skill
    # categories follow the projects as short "name -> single skill" entries
    # ("AI & Machine Learning" -> "TensorFlow"). Real projects have long,
    # sentence-like descriptions; these pairs do not - move them to skills.
    kept_projects: list[dict] = []
    for proj in projects:
        desc_lines = [d.strip() for d in proj["description"].split("\n") if d.strip()]
        is_skill_pair = (
            len(proj["name"]) <= 40
            and len(desc_lines) <= 2
            and all(len(d) <= 40 and not d.endswith((".", "!", "?")) for d in desc_lines)
            and not _YEAR_RE.search(proj["name"])
        )
        if is_skill_pair and skills:
            skills.append(proj["name"])
            skills.extend(desc_lines)
        elif is_skill_pair and not kept_projects:
            # No real skills seen yet - keep the entry (do not drop content).
            kept_projects.append(proj)
        else:
            kept_projects.append(proj)
    projects = kept_projects

    # Readability: un-glue concatenated category phrases. Only tokens that
    # already contain a space are split, so single CamelCase tech terms
    # ("JavaScript", "TensorFlow") stay intact.
    skills = [
        re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s) if " " in s else s
        for s in skills
    ]

    summary = _first(
        sections, "summary", "professional summary", "objective", "profile",
    )
    if not summary:
        # Recompute from pre-header lines that survived the job salvage.
        prose = [l for l in pre_header if len(l) > 40]
    if not summary and prose:
        summary = " ".join(prose)
    if not summary and prose_from_skills:
        # Summary text the extractor glued after a header (e.g. into skills).
        summary = " ".join(prose_from_skills)

    return {
        "name": name,
        "email": email_m.group() if email_m else "",
        "phone": phone_m.group() if phone_m else "",
        "location": location,
        "linkedin": linkedin_m.group() if linkedin_m else "",
        "github": github_m.group() if github_m else "",
        "title": title,
        "summary": summary,
        "skills": skills,
        "experience": experience,
        "education": education,
        "certifications": certifications,
        "projects": projects,
    }
