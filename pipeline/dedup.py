from __future__ import annotations

import hashlib
import json
from typing import Any


def deduplicate(records: list[dict[str, Any]], keys: list[str] | None = None) -> dict[str, Any]:
    """Remove duplicate records based on specified keys or full record hash.

    Args:
        records: List of dicts to deduplicate.
        keys: Optional list of field names to use for dedup key.
              If None, uses a hash of the entire record.

    Returns:
        {"records_in": int, "records_out": int, "duplicates_removed": int, "deduplicated_data": [...]}
    """
    seen: set[str] = set()
    unique: list[dict] = []

    for record in records:
        if keys:
            key_vals = tuple(str(record.get(k, "")) for k in keys)
            fingerprint = "|".join(key_vals)
        else:
            fingerprint = hashlib.md5(
                json.dumps(record, sort_keys=True, default=str).encode()
            ).hexdigest()

        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(record)

    return {
        "records_in": len(records),
        "records_out": len(unique),
        "duplicates_removed": len(records) - len(unique),
        "deduplicated_data": unique,
    }
