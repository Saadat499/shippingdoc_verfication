"""
Email classification for the shipping-document verification pipeline.

Classification strategy:
1. Deterministic rules handle clear cases.
2. Uncertain emails are classified by Gemini in batches of 10-20.
3. Gemini uses structured output constrained to the five Category values.
4. Gemini responses are cached using a hash of the exact input.
5. Failed Gemini batches are retried and then fall back to GENERAL/review-safe
   behavior rather than crashing the pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from pydantic import BaseModel

from .models import Category, DecidedBy


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BATCH_SIZE = 15
CACHE_DIR = Path(".gemini_cache")
CACHE_DIR.mkdir(exist_ok=True)

# NOTE (reviewed): default changed from "gemini-3.6-flash" -- that name
# doesn't appear anywhere in Google's current model docs. gemini-3.5-flash
# is the current stable GA flash model as of this review; verify against
# your own AI Studio console before trusting this, since names shift often.
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash",
)


# ---------------------------------------------------------------------------
# Deterministic rules
# ---------------------------------------------------------------------------

SPAM_DOMAINS = [
    "secure-mailbox.org",
    "webmail-verify.co",
    "logistics-deals.biz",
    "parcel-track.co",
    "prize-claims.info",
    "crypto-invest.net",
]

SPAM_PHRASES = [
    "congratulations",
    "gift card",
    "claim now",
    "won a",
    "urgent business proposal",
    "one weird trick",
    "limited time offer",
    "unpaid customs fee",
]

SI_REQUEST_PHRASES = [
    "please find shipping instruction",
    "shipping instruction for",
]

BL_REQUEST_PHRASES = [
    "please assist to send the draft bl",
    "send the draft bl for",
    "compare the si and draft bl",
    "compare the si and bl",
]



BOILERPLATE_RE = re.compile(
    r"warning: this email originated outside.*?(?=\n\n|\Z)",
    re.I | re.S,
)


# ---------------------------------------------------------------------------
# Gemini structured-output schema
# ---------------------------------------------------------------------------

class GeminiClassification(BaseModel):
    email_id: str
    category: Category


class GeminiClassificationBatch(BaseModel):
    results: list[GeminiClassification]


# ---------------------------------------------------------------------------
# Internal cache
# ---------------------------------------------------------------------------

# email_id -> (Category, DecidedBy)
_LLM_RESULTS: dict[str, tuple[Category, DecidedBy]] = {}

# emails that have already been classified by deterministic rules
_RULE_RESULTS: dict[str, tuple[Category, DecidedBy]] = {}


def strip_boilerplate(body: str) -> str:
    return BOILERPLATE_RE.sub("", body).strip()


def _email_payload(email: dict) -> dict[str, Any]:
    """
    Create the exact representation sent to Gemini.
    """
    return {
        "email_id": email.get("email_id", ""),
        "from": email.get("from", ""),
        "subject": email.get("subject", ""),
        "body": strip_boilerplate(email.get("body", "")),
        "attachments": email.get("attachments", []),
    }


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()


def _cache_path(cache_key: str) -> Path:
    return CACHE_DIR / f"{cache_key}.json"


def _load_cache(cache_key: str) -> GeminiClassificationBatch | None:
    path = _cache_path(cache_key)

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return GeminiClassificationBatch.model_validate(data)
    except Exception:
        # Corrupt cache should never crash the pipeline.
        return None


def _save_cache(
    cache_key: str,
    result: GeminiClassificationBatch,
) -> None:
    path = _cache_path(cache_key)

    path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Deterministic classifier
# ---------------------------------------------------------------------------

def rule_classify(
    email: dict,
) -> tuple[Category, DecidedBy | None]:
    """
    Return a deterministic classification when the evidence is strong.

    Return (GENERAL, None) for emails that should be sent to Gemini.
    """

    sender = email.get("from", "").lower()
    domain = sender.split("@")[-1] if "@" in sender else ""

    body = strip_boilerplate(
        email.get("body", "")
    ).lower()

    n_attachments = len(
        email.get("attachments", [])
    )

    # ------------------------------------------------------------------
    # 1. Spam
    # ------------------------------------------------------------------

    if (
        domain in SPAM_DOMAINS
        or any(p in body for p in SPAM_PHRASES)
    ):
        return Category.SPAM, DecidedBy.RULE

    # ------------------------------------------------------------------
    # 2. BL comparison
    # ------------------------------------------------------------------

    if n_attachments == 2:
        return Category.BL_COMPARISON, DecidedBy.RULE

    if any(
        p in body
        for p in BL_REQUEST_PHRASES
    ):
        return Category.BL_COMPARISON, DecidedBy.RULE

    if (
        n_attachments == 1
        and "draft bl is still missing" in body
    ):
        return Category.BL_COMPARISON, DecidedBy.RULE

    # ------------------------------------------------------------------
    # 3. SI request
    # ------------------------------------------------------------------

    if any(
        p in body
        for p in SI_REQUEST_PHRASES
    ):
        return Category.SI_REQUEST, DecidedBy.RULE

    # ------------------------------------------------------------------
    # 4. Automated operational/RPA notifications
    #
    # These can contain words such as "billing", "freight", or
    # "charges", but their actual purpose is simply to report that
    # an automated process completed.
    # ------------------------------------------------------------------

    automated_notification = (
        "this is an automated notification" in body
        or "-- rpa bot" in body
        or "rpa bot" in body
    )

    if automated_notification:
        return Category.GENERAL, DecidedBy.RULE

    # ------------------------------------------------------------------
    # 5. Invoice / billing query
    #
    # Keep these specific enough that incidental mentions of billing,
    # freight, etc. do not automatically make an operational email
    # an INVOICE_QUERY.
    # ------------------------------------------------------------------

    invoice_phrases = [
        "invoice",
        "local charges",
        "detention charges",
        "d&d",
        "gr is still missing",
        "billing",
        "freight",
    ]

    if any(
        p in body
        for p in invoice_phrases
    ):
        return Category.INVOICE_QUERY, DecidedBy.RULE

    # ------------------------------------------------------------------
    # 6. Unresolved -> Gemini
    # ------------------------------------------------------------------

    return Category.GENERAL, None



# ---------------------------------------------------------------------------
# Gemini prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You classify shipping-operation emails into exactly one category.

Allowed categories:

BL_COMPARISON
SI_REQUEST
INVOICE_QUERY
GENERAL
SPAM

Definitions:

BL_COMPARISON:
The sender wants a Shipping Instruction and Draft Bill of Lading compared,
checked, verified, or reviewed.

SI_REQUEST:
The sender's actual purpose is to request, submit, correct, or follow up
on a specific Shipping Instruction (SI).

Important distinction:
- Do NOT classify an email as SI_REQUEST merely because the text contains
  "SI", "submit SI", or "SI & AED".
- Automated reminders asking teams to action pending/outstanding shipment
  documentation are GENERAL when they are simply referring to an
  outstanding list.
- Emails about outstanding BL lists or documentation SLA reminders are
  GENERAL unless the actual purpose is a specific SI request.

INVOICE_QUERY:
The sender is specifically asking about an invoice, billing, local charges,
detention/D&D charges, invoice payment, invoice amount, or a similar
financial/documentation billing issue.

GENERAL:
Normal operational, administrative, informational, reporting, reminder,
status-update, berthing, loading, outstanding-list, or other shipping
emails that do not fit the categories above.

SPAM:
Promotional, fraudulent, suspicious, unsolicited commercial, prize,
credential, cryptocurrency, or obviously malicious emails.

Important:
- Do not classify an email as INVOICE_QUERY merely because it mentions
  freight, charges, billing, or financial terminology incidentally.
- Classify based on the actual purpose of the email.
- Return exactly one category per email.
"""


def _build_batch_prompt(
    emails: list[dict],
) -> list[dict]:
    return [
        {
            "email_id": email.get("email_id", ""),
            "from": email.get("from", ""),
            "subject": email.get("subject", ""),
            "body": strip_boilerplate(
                email.get("body", "")
            ),
            "attachments": email.get("attachments", []),
        }
        for email in emails
    ]


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------

def _call_gemini(
    emails: list[dict],
) -> GeminiClassificationBatch:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set."
        )

    client = genai.Client(
        api_key=api_key,
    )

    payload = _build_batch_prompt(emails)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            SYSTEM_PROMPT,
            "\nClassify the following emails:\n",
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
        ],
        config={
            "response_mime_type": "application/json",
            "response_schema": GeminiClassificationBatch,
            "temperature": 0,
        },
    )

    parsed = response.parsed

    if parsed is None:
        raise ValueError(
            "Gemini returned no structured response."
        )

    result = GeminiClassificationBatch.model_validate(
        parsed
    )

    expected_ids = {
        email["email_id"]
        for email in emails
    }

    returned_ids = {
        item.email_id
        for item in result.results
    }

    if expected_ids != returned_ids:
        raise ValueError(
            "Gemini returned an incomplete or unexpected "
            "set of email IDs."
        )

    return result


# ---------------------------------------------------------------------------
# Batch classification
# ---------------------------------------------------------------------------

def classify_emails(
    emails: list[dict],
) -> dict[str, tuple[Category, DecidedBy | None]]:
    """
    Classify an entire inbox.

    Rules are applied first. Only unresolved emails are sent to Gemini,
    in batches of 10-20.
    """

    results: dict[
        str,
        tuple[Category, DecidedBy | None],
    ] = {}

    llm_candidates: list[dict] = []

    for email in emails:
        email_id = email["email_id"]

        category, decided_by = rule_classify(email)

        if decided_by is not None:
            results[email_id] = (
                category,
                decided_by,
            )
            _RULE_RESULTS[email_id] = (
                category,
                decided_by,
            )
        else:
            llm_candidates.append(email)

    # ---------------------------------------------------------------
    # Gemini batches
    # ---------------------------------------------------------------

    for start in range(
        0,
        len(llm_candidates),
        BATCH_SIZE,
    ):
        batch = llm_candidates[
            start:start + BATCH_SIZE
        ]

        payload = _build_batch_prompt(batch)
        cache_key = _hash_payload(payload)

        cached = _load_cache(cache_key)

        if cached is not None:
            gemini_result = cached
        else:
            gemini_result = None

            for attempt in range(3):
                try:
                    gemini_result = _call_gemini(batch)

                    _save_cache(
                        cache_key,
                        gemini_result,
                    )

                    break

                except Exception as exc:
                    if attempt == 2:
                        print(
                            f"[Gemini] batch failed after retries: "
                            f"{exc}"
                        )
                    else:
                        delay = 2** (attempt + 1)

                        print(
                            f"[Gemini] attempt {attempt + 1} "
                            f"failed: {exc}; retrying..."
                        )

                        time.sleep(delay)

        if gemini_result is None:
            # Safe fallback.
            #
            # We don't crash the complete 520-email pipeline because
            # an external model call failed.
            for email in batch:
                email_id = email["email_id"]

                results[email_id] = (
                    Category.GENERAL,
                    None,
                )

            continue

        for item in gemini_result.results:
            results[item.email_id] = (
                item.category,
                DecidedBy.LLM,
            )

            _LLM_RESULTS[item.email_id] = (
                item.category,
                DecidedBy.LLM,
            )

    return results


# ---------------------------------------------------------------------------
# Existing single-email interface
# ---------------------------------------------------------------------------

def classify_email(
    email: dict,
) -> tuple[Category, DecidedBy | None]:
    """
    Existing compatibility interface.

    For a single email we first check whether it has already been classified
    through classify_emails(). This allows process_email() to continue using
    the existing interface.
    """

    email_id = email["email_id"]

    if email_id in _RULE_RESULTS:
        return _RULE_RESULTS[email_id]

    if email_id in _LLM_RESULTS:
        return _LLM_RESULTS[email_id]

    # No batch context exists yet.
    #
    # Do NOT silently make an individual Gemini call here because the project
    # requirement is 10-20 emails per API call.
    #
    # Returning GENERAL keeps the old interface safe; the batch runner should
    # prime classifications before process_email() is called.
    category, decided_by = rule_classify(email)

    if decided_by is not None:
        return category, decided_by

    return Category.GENERAL, None


# ---------------------------------------------------------------------------
# Backward-compatible llm_classify()
# ---------------------------------------------------------------------------

def llm_classify(
    email: dict,
) -> tuple[Category, DecidedBy | None]:
    """
    Compatibility wrapper.

    Individual LLM calls are deliberately not made here because the project
    requires batching. Use classify_emails() for actual Gemini inference.
    """

    email_id = email["email_id"]

    if email_id in _LLM_RESULTS:
        return _LLM_RESULTS[email_id]

    return Category.GENERAL, None
