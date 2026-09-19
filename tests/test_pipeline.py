import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from loader import Inbox  # noqa: E402
from shipverify.normalize import normalize  # noqa: E402
from shipverify.process import process_email  # noqa: E402

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
FIXTURES = ROOT / "contracts" / "fixtures"


def _run(email_id: str):
    inbox = Inbox(str(DATA))
    email = inbox.get(email_id)
    return process_email(email, inbox.read_bytes)


def test_match_fixture():
    expected = json.loads((FIXTURES / "match.json").read_text())
    r = _run(expected["email_id"])
    assert r.status.value == expected["status"]
    assert r.defect_fields == expected["defect_fields"]


def test_mismatch_fixture():
    expected = json.loads((FIXTURES / "mismatch.json").read_text())
    r = _run(expected["email_id"])
    assert r.status.value == expected["status"]
    assert set(r.defect_fields) == set(expected["defect_fields"])


def test_needs_review_fixture():
    expected = json.loads((FIXTURES / "needs_review.json").read_text())
    r = _run(expected["email_id"])
    assert r.status.value == expected["status"]
    assert r.review_reason.value == expected["review_reason"]


def test_container_count_normalizes_unit_and_case():
    assert normalize("container_count", "6 x 40'HC") == normalize("container_count", "6 x 40'hc")


def test_gross_weight_normalizes_commas_and_unit():
    assert normalize("gross_weight_kg", "131,058 KG") == normalize("gross_weight_kg", "131058")


def test_port_prefers_un_code_when_present():
    a = normalize("port_of_loading", "NANTONG, CHINA (CNNTG)")
    b = normalize("port_of_loading", "Nantong (CNNTG), China")
    assert a == b == "CNNTG"


def test_company_name_typo_is_a_real_mismatch():
    # normalize() must NOT fuzzy-match company names -- a typo/substitution
    # in shipper/consignee/notify_party is exactly the defect we're meant
    # to catch, not something to normalize away.
    a = normalize("shipper", "ABC Trading Sdn Bhd")
    b = normalize("shipper", "ABD Trading Sdn Bhd")
    assert a != b


def test_every_email_gets_a_result():
    inbox = Inbox(str(DATA))
    emails = inbox.emails()
    assert len(emails) == 520
    for e in emails[:20]:  # smoke-test a slice; CI runs the full CLI separately
        r = process_email(e, inbox.read_bytes)
        assert r.email_id == e["email_id"]
