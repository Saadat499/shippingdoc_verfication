"""
Classify one email into a Category. Rules catch the clear cases cheaply and
deterministically (and mark decided_by=rule, which the scorer reports back
to us as rule_pct). Everything else falls through to `llm_classify`, which
the AI engineer should replace with a real Gemini call.

IMPORTANT: classify on the body + attachments, not the subject. Subjects are
reused across categories in this dataset (e.g. shipment-reference subjects
appear on both comparison requests and invoice emails).
"""
from __future__ import annotations

import re

from .models import Category, DecidedBy

SPAM_DOMAINS = [
    "secure-mailbox.org", "webmail-verify.co", "logistics-deals.biz",
    "parcel-track.co", "prize-claims.info", "crypto-invest.net",
]

SPAM_PHRASES = [
    "congratulations", "gift card", "claim now", "won a", "urgent business proposal",
    "one weird trick", "limited time offer", "unpaid customs fee",
]

# "please send me the SI/BL details in the body" — no attachment, still BL_COMPARISON
SI_REQUEST_PHRASES = [
    "please find shipping instruction", "shipping instruction for",
]

BL_REQUEST_PHRASES = [
    "please assist to send the draft bl", "send the draft bl for",
    "compare the si and draft bl", "compare the si and bl",
]

INVOICE_PHRASES = [
    "invoice", "local charges", "detention charges", "d&d", "gr is still missing",
    "freight", "billing",
]

BOILERPLATE_RE = re.compile(
    r"warning: this email originated outside.*?(?=\n\n|\Z)", re.I | re.S
)


def strip_boilerplate(body: str) -> str:
    return BOILERPLATE_RE.sub("", body).strip()


def classify_email(email: dict) -> tuple[Category, DecidedBy | None]:
    sender = email.get("from", "").lower()
    domain = sender.split("@")[-1] if "@" in sender else ""
    body = strip_boilerplate(email.get("body", "")).lower()
    n_attachments = len(email.get("attachments", []))

    if domain in SPAM_DOMAINS or any(p in body for p in SPAM_PHRASES):
        return Category.SPAM, DecidedBy.RULE

    if n_attachments == 2:
        # two attachments in a shipping-doc context is almost always a
        # comparison request; let extract/compare confirm downstream.
        return Category.BL_COMPARISON, DecidedBy.RULE

    if any(p in body for p in BL_REQUEST_PHRASES):
        return Category.BL_COMPARISON, DecidedBy.RULE

    if n_attachments == 1 and "draft bl is still missing" in body:
        return Category.BL_COMPARISON, DecidedBy.RULE  # -> NEEDS_REVIEW downstream

    if any(p in body for p in SI_REQUEST_PHRASES):
        return Category.SI_REQUEST, DecidedBy.RULE

    if any(p in body for p in INVOICE_PHRASES):
        return Category.INVOICE_QUERY, DecidedBy.RULE

    # not confident -> let the LLM decide
    return llm_classify(email)


def llm_classify(email: dict) -> tuple[Category, DecidedBy | None]:
    """
    TODO(AI engineer): replace with a real Gemini call using structured
    output (response_schema=Category). Batch 10-20 emails per call to save
    quota. For now, default to GENERAL so the pipeline always produces a
    valid submission end to end.
    """
    return Category.GENERAL, None
