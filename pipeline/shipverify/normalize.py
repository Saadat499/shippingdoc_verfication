"""
Normalize formatting, never spelling. Two documents should compare equal iff
a human would consider the values the same shipment fact — not the same
string. Container counts, weights and ports get numeric/code normalization;
company-name fields (shipper, consignee, notify_party) only get whitespace
and case folding, so an actual different company still shows as a mismatch.
"""
from __future__ import annotations

import re

PORT_CODE_RE = re.compile(r"\(([A-Z]{5})\)")


def normalize(field: str, value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if field == "container_count":
        m = re.match(r"\s*(\d+)", v)
        return m.group(1) if m else _fold(v)
    if field == "gross_weight_kg":
        digits = re.sub(r"[^\d.]", "", v)
        return digits or _fold(v)
    if field in ("port_of_loading", "port_of_discharge"):
        m = PORT_CODE_RE.search(v)
        if m:
            return m.group(1)
        return _fold(v)
    # shipper / consignee / notify_party: whitespace/case/punctuation only
    return _fold(v)


def _fold(v: str) -> str:
    v = v.upper()
    v = re.sub(r"[.,|;]", "", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip()
