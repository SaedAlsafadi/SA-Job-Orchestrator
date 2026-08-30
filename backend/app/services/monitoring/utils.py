"""Utilities for job monitoring."""

import hashlib
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Dict, Any


def get_canonical_url(url: str) -> str:
    """Normalize a URL by removing tracking parameters and fragments."""
    if not url:
        return ""
    
    parsed = urlparse(url)
    
    # Remove fragments
    fragment = ""
    
    # Filter query params
    qs = parse_qs(parsed.query)
    filtered_qs = {
        k: v for k, v in qs.items()
        if not k.startswith("utm_") and k not in ("ref", "source", "medium", "campaign")
    }
    
    new_query = urlencode(filtered_qs, doseq=True)
    
    # Reconstruct
    clean = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        fragment
    ))
    return clean


def compute_content_hash(job_data: Dict[str, Any]) -> str:
    """Compute a SHA-256 hash of meaningful job content to detect changes."""
    meaningful_fields = [
        str(job_data.get("title", "")).strip().lower(),
        str(job_data.get("company", "")).strip().lower(),
        str(job_data.get("description", "")).strip().lower(),
        str(job_data.get("responsibilities", "")).strip().lower(),
        str(job_data.get("requirements", "")).strip().lower(),
        str(job_data.get("location", "")).strip().lower(),
        str(job_data.get("employment_type", "")).strip().lower(),
        str(job_data.get("salary", "")).strip().lower(),
        str(job_data.get("salary_range", "")).strip().lower(),
    ]
    
    # Join with a delimiter that doesn't usually appear in text
    content_string = "|||".join(meaningful_fields)
    
    return hashlib.sha256(content_string.encode("utf-8")).hexdigest()
