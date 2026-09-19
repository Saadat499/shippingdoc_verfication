#!/usr/bin/env python3
"""
Run the pipeline over a local data folder and write submission.json.

    python3 cli/run.py data
    python3 cli/run.py data --score data/ground_truth.json
    python3 cli/run.py holdouts/seed_7 --score holdouts/seed_7/ground_truth.json

This is the same process_email() the backend calls — nothing pipeline-related
should ever be written twice.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from loader import Inbox  # noqa: E402
from shipverify.export import build_submission  # noqa: E402
from shipverify.process import process_email  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", help="folder with inbox/ + attachments/, or a server URL")
    ap.add_argument("--out", default="submission.json")
    ap.add_argument("--score", help="path to ground_truth.json to score against locally")
    args = ap.parse_args()

    inbox = Inbox(args.data_dir)
    emails = inbox.emails()
    print(f"{len(emails)} emails loaded from {args.data_dir}", file=sys.stderr)

    results = [process_email(e, inbox.read_bytes) for e in emails]
    submission = build_submission(results)

    Path(args.out).write_text(json.dumps(submission, indent=2))
    print(f"wrote {args.out}", file=sys.stderr)

    if args.score:
        sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))
        import scoring  # noqa: E402

        truth = json.loads(Path(args.score).read_text())
        result = scoring.score_all(truth, submission)
        print(json.dumps({
            "final_score": result["final_score"],
            "stage1_macro_f1": result["stage1"]["macro_f1"],
            "stage3_defect_f1": result["stage3"]["defect_f1"],
            "end_to_end_rate": result["end_to_end"]["rate"],
            "reliability_escalation_f1": result["reliability"]["escalation_f1"],
            "rule_pct": result["stage1"]["rule_pct"],
        }, indent=2))


if __name__ == "__main__":
    main()
