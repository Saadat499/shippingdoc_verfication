"""
Deterministic field extraction: "label: value" lines -> our 7 canonical
fields. Built from every label variant actually observed in the provided
dataset (data/attachments/*.txt, *.docx, *.xlsx).

Verification engineer: this is your file. Add new synonyms here as you find
them in PDFs/edge cases. Keep it data-driven (the SYNONYMS dict) rather than
scattering if/elif chains — that keeps it testable.
"""
from __future__ import annotations

import re

from .models import FieldValue

# canonical_field -> list of label variants seen in the data (lowercased,
# punctuation-insensitive match is applied at lookup time).
SYNONYMS: dict[str, list[str]] = {
    "shipper": [
        "shipper", "shipper (principal or seller)", "shipper/exporter", "exporter",
    ],
    "consignee": [
        "consignee", "consignee (non-negotiable)", "to the order of",
    ],
    "notify_party": [
        "notify", "notify party", "notify party/intermediate consignee",
    ],
    "port_of_loading": [
        "port of loading", "port of loading (pol)", "pol", "load port",
    ],
    "port_of_discharge": [
        "port of discharge", "port of discharge (pod)", "pod", "discharge port",
    ],
    "container_count": [
        "no. of containers", "no. of containers or packages", "total containers",
        "container count",
    ],
    "gross_weight_kg": [
        "gross weight", "gross weight (kg)", "gross wt (kgs)",
        "gross weight毛重(kgs)",
    ],
}

# document-title -> whether it's an SI or a BL (for wrong_doc_type detection)
SI_TITLES = ["shipping instruction", "s.i.", "bl instruction", "bill of lading instruction"]
BL_TITLES = ["bill of lading"]
OTHER_DOC_TITLES = [
    "certificate of origin", "packing list", "commercial invoice", "invoice",
]

_LABEL_RE = re.compile(r"^([A-Za-z][^:]{1,60}):\s*(.*)$")

MISSING_MARKERS = {"n/a", "na", "____", "___mt", "_______ mts", "???", "??? mts", ""}


_CJK_PAREN_RE = re.compile(r"\([^)]*[\u4e00-\u9fff][^)]*\)")


def _clean_label(label: str) -> str:
    label = _CJK_PAREN_RE.sub("", label)  # drop bilingual suffixes e.g. "(发货人)"
    return re.sub(r"\s+", " ", label).strip().lower()


def _label_to_field(label: str) -> str | None:
    label = _clean_label(label)
    for field, variants in SYNONYMS.items():
        if label in variants:
            return field
    return None


def classify_document_title(title: str) -> str:
    """Returns 'SI', 'BL', or 'OTHER' based on the first line of the document."""
    t = title.strip().lower()
    if any(t.startswith(x) for x in SI_TITLES):
        return "SI"
    if any(t.startswith(x) for x in BL_TITLES):
        return "BL"
    if any(x in t for x in OTHER_DOC_TITLES):
        return "OTHER"
    return "UNKNOWN"


# Some PDF layouts print a label with no colon at all, e.g.
# "Shipper APRIL FINE PAPER TRADING" instead of "Shipper: APRIL FINE...".
# Sorted longest-variant-first so "consignee (non-negotiable)" is tried
# before the shorter "consignee", or the parenthetical would leak into value.
_COLONLESS_CANDIDATES = sorted(
    ((variant, field) for field, variants in SYNONYMS.items() for variant in variants),
    key=lambda x: -len(x[0]),
)


def _match_colonless(line: str) -> tuple[str, str] | None:
    cleaned = _CJK_PAREN_RE.sub("", line)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    lower = cleaned.lower()
    for variant, field in _COLONLESS_CANDIDATES:
        if lower.startswith(variant + " "):
            return field, cleaned[len(variant):].strip()
    return None


def is_missing_value(raw: str) -> bool:
    v = raw.strip().lower().replace(" ", "")
    if v in MISSING_MARKERS:
        return True
    if re.fullmatch(r"_+m?t?s?", v):
        return True
    if re.fullmatch(r"\?+m?t?s?", v):
        return True
    return False


def extract_fields(lines: list[str]) -> dict[str, FieldValue]:
    """Scan document lines for our 7 fields. Handles the 'TOTAL Gross Weight'
    fallback used by table-style BLs (see attachments with per-container rows)."""
    out: dict[str, FieldValue] = {}
    fallback_total_weight: str | None = None

    for line in lines:
        # Check the total-weight fallback on EVERY line, not just ones that
        # fail the normal label match -- "TOTAL Gross Wt (kgs): 131,322 KG"
        # has a colon (so it matches _LABEL_RE below), but "TOTAL Gross Wt
        # (kgs)" isn't itself a recognized label, so it would otherwise be
        # silently dropped before this fallback ever got a chance to run.
        if fallback_total_weight is None:
            tm = re.search(r"total\s+gross\s+w\w*[^:]*:\s*([\d,.]+\s*kg)", line, re.I)
            if tm:
                fallback_total_weight = tm.group(1)

        m = _LABEL_RE.match(line)
        if not m:
            # no colon at all -- some PDF layouts print "Label Value" directly
            cm = _match_colonless(line)
            if cm is None:
                continue
            field, value = cm
            if field in out and out[field].found:
                continue
            if is_missing_value(value):
                out[field] = FieldValue(raw=value, value=None, evidence=line, found=False)
            else:
                out[field] = FieldValue(raw=value, value=value, evidence=line, found=True)
            continue

        label, value = m.group(1), m.group(2).strip()
        field = _label_to_field(label)
        if field is None:
            continue
        if field in out and out[field].found:
            continue  # keep first occurrence
        if is_missing_value(value):
            out[field] = FieldValue(raw=value, value=None, evidence=line, found=False)
        else:
            out[field] = FieldValue(raw=value, value=value, evidence=line, found=True)

    if "gross_weight_kg" not in out and fallback_total_weight:
        out["gross_weight_kg"] = FieldValue(
            raw=fallback_total_weight, value=fallback_total_weight,
            evidence=f"TOTAL Gross Weight: {fallback_total_weight}", found=True,
        )

    return out
