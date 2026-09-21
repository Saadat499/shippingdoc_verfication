#!/usr/bin/env python3
"""
Exports one static JSON file the frontend fetches directly — no backend,
no API, no cloud service. Regenerate any time the pipeline changes:

    python3 frontend/build_data.py

Commit the resulting frontend/results.json so GitHub Pages can serve it as
a plain static file alongside index.html.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from loader import Inbox  # noqa: E402
from shipverify.process import process_email  # noqa: E402


def main():
    root = Path(__file__).parent.parent
    inbox = Inbox(str(root / "data"))
    emails = inbox.emails()

    out = {}
    for e in emails:
        r = process_email(e, inbox.read_bytes)
        out[e["email_id"]] = {
            "email": {
                "from": e["from"],
                "subject": e["subject"],
                "body": e["body"],
            },
            "result": json.loads(r.model_dump_json()),
        }

    dest = Path(__file__).parent / "results.json"
    dest.write_text(json.dumps(out))
    print(f"wrote {dest} — {len(out)} emails, {dest.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
