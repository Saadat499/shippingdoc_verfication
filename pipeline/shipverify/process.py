"""
process_email() is the ONLY entry point into the pipeline. The CLI runner
and the FastAPI backend worker both call this and nothing else — that's
what keeps them in sync. If you need to change pipeline behavior, change it
here (or in the stage modules this calls), not in the CLI or backend.
"""
from __future__ import annotations

from .classify import classify_email
from .compare import compare_documents
from .documents import read_document
from .extract_rules import classify_document_title, extract_fields
from .models import Category, DecidedBy, EmailResult, ReviewReason, Status


def process_email(email: dict, read_bytes) -> EmailResult:
    """
    email: one record from inbox/email_XXX.json
        {email_id, from, subject, body, attachments: [path, ...]}
    read_bytes: callable(path) -> bytes, e.g. loader.Inbox(...).read_bytes
    """
    email_id = email["email_id"]
    category, decided_by = classify_email(email)

    if category != Category.BL_COMPARISON:
        return EmailResult(email_id=email_id, category=category, status=Status.OK,
                            decided_by=decided_by)

    attachments = email.get("attachments", [])

    if len(attachments) == 0:
        # e.g. "please send the draft BL for checking" with nothing attached
        # yet, OR an SI written entirely in the body. Treated as OK unless the
        # body explicitly says something is missing (handled in classify.py
        # by routing those to here with 1 attachment case below).
        return EmailResult(email_id=email_id, category=category, status=Status.OK,
                            decided_by=decided_by,
                            notes="No attachments; nothing to compare.")

    if len(attachments) == 1:
        return EmailResult(email_id=email_id, category=category, status=Status.NEEDS_REVIEW,
                            review_reason=ReviewReason.MISSING_ATTACHMENT,
                            decided_by=decided_by, si_path=attachments[0])

    # exactly 2 attachments: figure out which is SI and which is BL
    docs = {}
    for path in attachments:
        raw = read_bytes(path)
        lines, title, readable = read_document(path, raw)
        docs[path] = (lines, title, readable)

    si_path = next((p for p, (_, t, _) in docs.items()
                     if classify_document_title(t) == "SI"), None)
    bl_path = next((p for p, (_, t, _) in docs.items()
                     if classify_document_title(t) == "BL"), None)

    # fall back on filename hints if title sniffing failed
    if si_path is None:
        si_path = next((p for p in attachments if "_si" in p.lower()), None)
    if bl_path is None:
        bl_path = next((p for p in attachments if "_bl" in p.lower()), None)

    if si_path is None or bl_path is None:
        return EmailResult(email_id=email_id, category=category, status=Status.NEEDS_REVIEW,
                            review_reason=ReviewReason.WRONG_DOC_TYPE,
                            decided_by=decided_by, si_path=si_path, bl_path=bl_path)

    si_lines, si_title, si_readable = docs[si_path]
    bl_lines, bl_title, bl_readable = docs[bl_path]

    if not si_readable or not bl_readable:
        return EmailResult(email_id=email_id, category=category, status=Status.NEEDS_REVIEW,
                            review_reason=ReviewReason.UNREADABLE,
                            decided_by=decided_by, si_path=si_path, bl_path=bl_path)

    if (classify_document_title(bl_title) not in ("BL", "UNKNOWN")
            or classify_document_title(si_title) not in ("SI", "UNKNOWN")):
        return EmailResult(email_id=email_id, category=category, status=Status.NEEDS_REVIEW,
                            review_reason=ReviewReason.WRONG_DOC_TYPE,
                            decided_by=decided_by, si_path=si_path, bl_path=bl_path)

    si_fields = extract_fields(si_lines)
    bl_fields = extract_fields(bl_lines)
    comparisons = compare_documents(si_fields, bl_fields)

    if any(c.outcome == "UNCERTAIN" for c in comparisons):
        return EmailResult(email_id=email_id, category=category, status=Status.NEEDS_REVIEW,
                            review_reason=ReviewReason.MISSING_VALUE,
                            decided_by=decided_by, si_path=si_path, bl_path=bl_path,
                            fields=comparisons)

    mismatched = [c.field for c in comparisons if c.outcome == "MISMATCH"]
    status = Status.MISMATCH if mismatched else Status.OK
    return EmailResult(email_id=email_id, category=category, status=status,
                        decided_by=decided_by, si_path=si_path, bl_path=bl_path,
                        fields=comparisons, defect_fields=mismatched)
