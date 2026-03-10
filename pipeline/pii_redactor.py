from __future__ import annotations

import re
from typing import Any


# PII patterns
_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}

_FIELD_PATTERNS = {
    "email": ["email", "mail", "e_mail"],
    "phone": ["phone", "tel", "mobile", "fax"],
    "name": ["name", "first_name", "last_name", "full_name", "contact_name"],
    "address": ["address", "street", "city", "zip", "postal"],
    "ssn": ["ssn", "social_security", "tax_id", "national_id"],
}


def redact_pii(
    records: list[dict[str, Any]],
    fields_to_redact: list[str] | None = None,
    replacement: str = "[REDACTED]",
) -> dict[str, Any]:
    """Redact PII from records.

    Args:
        records: List of dicts to redact.
        fields_to_redact: Specific fields to redact. If None, auto-detects PII fields.
        replacement: String to replace PII with.

    Returns:
        {"records_in": int, "fields_redacted": int, "pii_types_found": [...], "redacted_data": [...]}
    """
    fields_redacted = 0
    pii_types: set[str] = set()
    redacted: list[dict] = []

    # Auto-detect fields if not specified
    if fields_to_redact is None and records:
        fields_to_redact = _auto_detect_pii_fields(records[0])

    fields_to_redact = fields_to_redact or []

    for record in records:
        row = dict(record)
        for field in fields_to_redact:
            if field in row and row[field] is not None:
                original = str(row[field])
                pii_type = _classify_field(field)
                if pii_type:
                    pii_types.add(pii_type)

                row[field] = replacement
                if original != replacement:
                    fields_redacted += 1

        # Also scan all string values for regex-based PII
        for field, val in list(row.items()):
            if field in fields_to_redact:
                continue
            if isinstance(val, str):
                for pii_name, pattern in _PATTERNS.items():
                    if pattern.search(val):
                        row[field] = pattern.sub(replacement, val)
                        pii_types.add(pii_name)
                        fields_redacted += 1
                        break

        redacted.append(row)

    return {
        "records_in": len(records),
        "fields_redacted": fields_redacted,
        "pii_types_found": sorted(pii_types),
        "redacted_data": redacted,
    }


def _auto_detect_pii_fields(sample: dict) -> list[str]:
    """Detect which fields likely contain PII based on field names."""
    pii_fields: list[str] = []
    for field in sample.keys():
        field_lower = field.lower()
        for pii_type, keywords in _FIELD_PATTERNS.items():
            if any(kw in field_lower for kw in keywords):
                pii_fields.append(field)
                break
    return pii_fields


def _classify_field(field: str) -> str | None:
    field_lower = field.lower()
    for pii_type, keywords in _FIELD_PATTERNS.items():
        if any(kw in field_lower for kw in keywords):
            return pii_type
    return None
