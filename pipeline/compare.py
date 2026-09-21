from __future__ import annotations

import re

from .models import FIELDS, FieldComparison, FieldValue
from .normalize import normalize

PORT_FIELDS = {"port_of_loading", "port_of_discharge"}


def _port_parts(raw: str) -> tuple[str | None, str]:
    """Return (code, city). code = 5-letter UN/LOCODE in brackets (or a bare
    code), else None. city = lowercased text before the first comma."""
    raw = raw.strip()
    m = re.search(r"\(\s*([A-Za-z]{5})\s*\)", raw)
    if m:
        code, name_part = m.group(1).upper(), raw[: m.start()]
    elif re.fullmatch(r"[A-Za-z]{5}", raw):
        code, name_part = raw.upper(), ""
    else:
        code, name_part = None, raw
    city = re.sub(r"[^a-z0-9 ]", " ", name_part.split(",")[0].lower())
    return code, " ".join(city.split())


def _ports_match(a: str, b: str) -> bool | None:
    """True = same port, False = different, None = can't tell from these values."""
    ca, na = _port_parts(a)
    cb, nb = _port_parts(b)
    if ca and cb and ca != cb:
        return False
    if na and nb and na != nb:
        return False
    if (ca and cb) or (na and nb):
        return True
    return None  # e.g. only a code on one side and only a name on the other


def compare_documents(
    si_fields: dict[str, FieldValue], bl_fields: dict[str, FieldValue]
) -> list[FieldComparison]:
    results = []
    for field in FIELDS:
        si_val = si_fields.get(field, FieldValue(found=False))
        bl_val = bl_fields.get(field, FieldValue(found=False))

        if not si_val.found or not bl_val.found:
            outcome = "UNCERTAIN"
        else:
            outcome = None
            if field in PORT_FIELDS:
                same = _ports_match(si_val.value, bl_val.value)
                if same is not None:
                    outcome = "MATCH" if same else "MISMATCH"
            if outcome is None:  # not a port, or ports couldn't be judged
                si_norm = normalize(field, si_val.value)
                bl_norm = normalize(field, bl_val.value)
                outcome = "MATCH" if si_norm == bl_norm else "MISMATCH"

        results.append(FieldComparison(field=field, si=si_val, bl=bl_val, outcome=outcome))
    return results