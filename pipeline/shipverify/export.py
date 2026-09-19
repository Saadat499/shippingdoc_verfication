from __future__ import annotations

from .models import EmailResult


def to_submission_record(result: EmailResult) -> dict:
    return {
        "category": result.category.value,
        "status": result.status.value,
        "review_reason": result.review_reason.value if result.review_reason else None,
        "has_defect": result.status.value == "MISMATCH",
        "defect_fields": result.defect_fields,
        "decided_by": result.decided_by.value if result.decided_by else None,
    }


def build_submission(results: list[EmailResult]) -> dict:
    return {r.email_id: to_submission_record(r) for r in results}
