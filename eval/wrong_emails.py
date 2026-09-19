#!/usr/bin/env python3
"""
Daily error-analysis loop. Shows exactly which emails are wrong and why.

    python3 eval/wrong_emails.py submission.json data/ground_truth.json
    python3 eval/wrong_emails.py submission.json data/ground_truth.json --category BL_COMPARISON
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("submission")
    ap.add_argument("ground_truth")
    ap.add_argument("--category", help="only show mistakes in this category")
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    sub = json.loads(Path(args.submission).read_text())
    truth = json.loads(Path(args.ground_truth).read_text())

    wrong = []
    for eid, t in truth.items():
        s = sub.get(eid, {})
        if args.category and t["category"] != args.category:
            continue
        reasons = []
        if s.get("category") != t["category"]:
            reasons.append(f"category: pred={s.get('category')} true={t['category']}")
        if t["category"] == "BL_COMPARISON":
            if s.get("status") != t.get("status"):
                reasons.append(f"status: pred={s.get('status')} true={t.get('status')}")
            pred_fields = set(s.get("defect_fields", []))
            true_fields = set(t.get("defect_fields", []))
            if pred_fields != true_fields:
                reasons.append(f"defect_fields: pred={sorted(pred_fields)} true={sorted(true_fields)}")
        if reasons:
            wrong.append((eid, reasons))

    print(f"{len(wrong)} / {len(truth)} emails wrong"
          + (f" (within category={args.category})" if args.category else ""))
    for eid, reasons in wrong[: args.limit]:
        print(f"\n{eid}")
        for r in reasons:
            print(f"  - {r}")


if __name__ == "__main__":
    main()
