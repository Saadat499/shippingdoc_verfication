from __future__ import annotations

from .models import FIELDS, FieldComparison, FieldValue
from .normalize import normalize


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
            si_norm = normalize(field, si_val.value)
            bl_norm = normalize(field, bl_val.value)
            outcome = "MATCH" if si_norm == bl_norm else "MISMATCH"

        results.append(FieldComparison(field=field, si=si_val, bl=bl_val, outcome=outcome))
    return results
