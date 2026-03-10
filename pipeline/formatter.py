from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def standardize(records: list[dict[str, Any]], rules: dict[str, str] | None = None) -> dict[str, Any]:
    """Standardize formats across records — dates, phones, emails, currencies.

    Args:
        records: List of dicts to standardize.
        rules: Optional field→type mapping. Auto-detected if not provided.
               Types: "date", "phone", "email", "currency", "text_lower", "text_upper"

    Returns:
        {"records_in": int, "records_out": int, "nulls_filled": int,
         "formats_standardized": int, "cleaned_data": [...]}
    """
    nulls_filled = 0
    formats_standardized = 0
    cleaned: list[dict] = []

    # Auto-detect field types if not provided
    if not rules and records:
        rules = _auto_detect_types(records[0])

    rules = rules or {}

    for record in records:
        row = dict(record)
        for field, fmt in rules.items():
            if field not in row:
                continue
            val = row[field]

            if val is None or val == "":
                nulls_filled += 1
                row[field] = _default_for_type(fmt)
                continue

            original = str(val)
            row[field] = _format_value(val, fmt)
            if str(row[field]) != original:
                formats_standardized += 1

        cleaned.append(row)

    return {
        "records_in": len(records),
        "records_out": len(cleaned),
        "nulls_filled": nulls_filled,
        "formats_standardized": formats_standardized,
        "cleaned_data": cleaned,
    }


def _auto_detect_types(sample: dict) -> dict[str, str]:
    """Guess field types from a sample record."""
    types: dict[str, str] = {}
    for key, val in sample.items():
        val_str = str(val).lower() if val else ""
        if any(d in key.lower() for d in ("date", "created", "updated", "timestamp")):
            types[key] = "date"
        elif any(p in key.lower() for p in ("phone", "tel", "mobile")):
            types[key] = "phone"
        elif any(e in key.lower() for e in ("email", "mail")):
            types[key] = "email"
        elif any(c in key.lower() for c in ("price", "amount", "revenue", "value", "cost")):
            types[key] = "currency"
    return types


def _format_value(val: Any, fmt: str) -> Any:
    """Format a value according to its type."""
    if fmt == "date":
        return _standardize_date(val)
    elif fmt == "phone":
        return _standardize_phone(val)
    elif fmt == "email":
        return str(val).strip().lower()
    elif fmt == "currency":
        return _standardize_currency(val)
    elif fmt == "text_lower":
        return str(val).strip().lower()
    elif fmt == "text_upper":
        return str(val).strip().upper()
    return val


def _standardize_date(val: Any) -> str:
    """Try to parse and standardize to ISO 8601."""
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def _standardize_phone(val: Any) -> str:
    """Strip to digits + leading +."""
    s = str(val).strip()
    digits = re.sub(r"[^\d+]", "", s)
    return digits if digits else s


def _standardize_currency(val: Any) -> float:
    """Parse currency string to float."""
    s = str(val).strip().replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def _default_for_type(fmt: str) -> Any:
    defaults = {"date": "", "phone": "", "email": "", "currency": 0.0, "text_lower": "", "text_upper": ""}
    return defaults.get(fmt, "")
