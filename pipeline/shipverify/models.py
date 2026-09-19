"""
The shared contract. Every piece of the pipeline (rules, LLM, backend, CLI)
imports these types instead of passing raw dicts around. If you need a new
field, add it here first and tell the team — this file is the one thing
nobody edits without saying so in the group chat.

FIELDS is the single source of truth for the 7 compared fields. Import it
instead of typing field names as string literals anywhere else.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    BL_COMPARISON = "BL_COMPARISON"
    SI_REQUEST = "SI_REQUEST"
    INVOICE_QUERY = "INVOICE_QUERY"
    GENERAL = "GENERAL"
    SPAM = "SPAM"


class Status(str, Enum):
    OK = "OK"
    MISMATCH = "MISMATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ReviewReason(str, Enum):
    WRONG_DOC_TYPE = "wrong_doc_type"
    MISSING_ATTACHMENT = "missing_attachment"
    UNREADABLE = "unreadable"
    MISSING_VALUE = "missing_value"


class DecidedBy(str, Enum):
    RULE = "rule"
    LLM = "llm"


FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]


class FieldValue(BaseModel):
    """One field, as read from one document."""
    raw: Optional[str] = None          # exact text as found (or None if absent)
    value: Optional[str] = None        # normalized value used for comparison
    evidence: Optional[str] = None     # verbatim snippet the value came from
    found: bool = False                # False if the field/label wasn't present at all


class FieldComparison(BaseModel):
    field: str
    si: FieldValue
    bl: FieldValue
    outcome: str  # "MATCH" | "MISMATCH" | "UNCERTAIN"


class EmailResult(BaseModel):
    """The full internal result for one email. export.py turns this into the
    flat submission.json shape the scorer expects."""
    email_id: str
    category: Category
    status: Status
    review_reason: Optional[ReviewReason] = None
    decided_by: Optional[DecidedBy] = None

    si_path: Optional[str] = None
    bl_path: Optional[str] = None
    fields: list[FieldComparison] = Field(default_factory=list)
    defect_fields: list[str] = Field(default_factory=list)
    notes: Optional[str] = None  # free-text reason, for the UI / debugging only

    def has_defect(self) -> bool:
        return self.status == Status.MISMATCH


class SubmissionRecord(BaseModel):
    """Exact shape score_cli.py / the server expect, per email_id."""
    category: Category
    status: Status
    review_reason: Optional[ReviewReason] = None
    has_defect: bool
    defect_fields: list[str] = Field(default_factory=list)
    decided_by: Optional[DecidedBy] = None
