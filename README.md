# ShipSentry — AI-Assisted Shipping Document Verification

**Team ShipSentry · Averis x Monash Hackathon 2026**

ShipSentry automatically checks whether a Shipping Instruction (SI) and a draft Bill of Lading (BL) describe the exact same shipment — catching real mismatches before they cause costly shipping errors, without burying a human reviewer in false alarms.

---

## Problem–Solution Alignment

**The problem:** When a shipment goes out, operations teams receive two documents by email — an SI and a draft BL — and must confirm both describe the same shipment across seven critical fields: shipper, consignee, notify party, port of loading, port of discharge, container count, and gross weight. A single missed mismatch can send the wrong cargo to the wrong place. This is made harder because documents arrive as PDFs, Word files, Excel sheets, or scanned images, with over 60 different ways of labeling the same field, and information is sometimes missing, mislabeled, or unreadable.

**Our solution:** A seven-stage pipeline (`Ingest → Classify → Read → Extract → Compare → Decide → Review`) that reads any of these formats through one shared interface, normalizes and extracts the 7 fields using a synonym table built from real observed label variants, and compares SI against BL deterministically wherever possible. Instead of forcing a reviewer to check every email, the system only escalates the genuinely uncertain cases to a Review Queue, each with the reasoning and both documents' evidence shown side by side. This directly targets the actual bottleneck — reviewer time — rather than just flagging everything.

---

## AI and Cloud Infrastructure Integration

**AI (Gemini API):** Deterministic rules handle the majority of the pipeline — this keeps the system fast, auditable, and cheap to run. Gemini is used only where rules genuinely can't do the job:
- Classifying the ~9% of emails that rule-based logic can't confidently categorize (batched, with cached responses, retried with backoff, and a safe fallback rather than crashing a run).
- Transcribing scanned or image-only PDFs via Gemini vision before falling back to human review if that fails.

**Cloud infrastructure (Firebase Realtime Database):** Review decisions are synced through Firebase so that reviewer input isn't trapped in a single browser's local storage — multiple people can review the same case queue and see each other's decisions. Setup:
1. Create a free Firebase project (Spark plan, no card) → Realtime Database → start in test mode.
2. Add the database URL to `FIREBASE_DB_URL` in both `frontend/index.html` and `frontend/upload_to_firebase.py`.
3. Run `python3 frontend/build_data.py` then `python3 frontend/upload_to_firebase.py` to push results to the cloud.

**Hosting:** The dashboard is a single-file React app (loaded from a CDN, no build step) deployed on GitHub Pages — free, and part of the same repo being submitted.

---

## User Feedback / Testing

- The frontend was built against three real fixture examples (`contracts/fixtures/`) — match, mismatch, and needs-review cases — so the UI was validated against actual data shapes before the backend even existed.
- An 8-test `pytest` suite runs before every merge to `main`; CI must pass before any pull request is accepted.
- The team ran two checkpoints a day (1 PM / 10 PM MYT) opening the live deployed URL and running the full pipeline end-to-end, rather than only testing in isolation.
- Every fix was validated against `eval/wrong_emails.py` — a tool that reports exactly which emails are wrong and why — turning bug-fixing into evidence-driven iteration instead of guesswork.

---

## Coding Challenges

Three real bugs were found through evidence (via `eval/wrong_emails.py`) and fixed one at a time:

1. **A PDF layout with no colons at all.** A layout that wrote `"Shipper APRIL FINE PAPER TRADING"` instead of `"Shipper: ..."` silently dropped 6 of 7 fields, since the extractor assumed a colon-based `label: value` format.
2. **Ports needed code *and* name logic, not one string match.** One document used a UN/LOCODE, the other only a city name — comparing them as plain text produced false mismatches even when the port was genuinely correct.
3. **An address-formatting mismatch across file types.** Excel wrote multi-line addresses using `|` and `;` separators; Word didn't. Identical addresses were being flagged as different purely because of formatting, not content.

---

## Success Metrics

To avoid reporting numbers that just reflect memorized training data, the system was scored on data it had never seen:

| Dataset | Result |
|---|---|
| Provided 520-email dataset | 100% |
| Freshly generated, unseen 520-email set (seed 7) | 100% |
| Second independent unseen set (seed 99) | 100% |

**1,560 emails scored across 3 independently generated datasets.** Every fix was re-checked on datasets generated *after* the fix was written, so these numbers reflect generalization rather than tuning to a known answer key.

For context, the early rules-only baseline (before Gemini was integrated) scored:
```json
{
  "final_score": 0.69,
  "stage1_macro_f1": 0.95,
  "stage3_defect_f1": 0.87,
  "end_to_end_rate": 0.46,
  "reliability_escalation_f1": 0.72
}
```
On the current, full pipeline, of the 520 provided emails, only 20 needed a human decision at all — the rest were resolved automatically.

---

## Scalability Plans

Three concrete changes separate this hackathon build from a production-ready system:

1. **Event-driven pipeline.** Replace the single batch script with a Pub/Sub queue and Cloud Run workers, enabling continuous, high-volume email intake instead of periodic batch runs.
2. **Shared cloud database.** Replace local/browser storage entirely with Firestore, so review decisions sync reliably across every reviewer and machine at production scale (the current Firebase Realtime Database integration is the first step toward this).
3. **Wider scanned-document coverage.** The Gemini-vision fallback already works for one scanned layout; the next step is broadening it across noisier scans and multi-page documents.

---

## Setup Instructions

### Backend / pipeline

```bash
git clone https://github.com/Saadat499/shippingdoc_verfication.git
cd shippingdoc_verfication
pip install -r requirements.txt
python3 -m pytest tests/ -v          # should say 8 passed
python3 cli/run.py data --score data/ground_truth.json
```

The last command prints a JSON scoreboard. If anything fails here, resolve it before writing new code.

### Frontend dashboard

```bash
python3 frontend/build_data.py       # regenerate results.json from pipeline output
cd frontend
python3 -m http.server 8000
```

Open `http://localhost:8000` in a browser. No `npm install` or build step — React and Babel load from a CDN and JSX compiles in-browser directly from `index.html`.

### Cloud sync (optional — Firebase)

See [AI and Cloud Infrastructure Integration](#ai-and-cloud-infrastructure-integration) above for the exact steps.

### Held-out scoring (regenerating fresh test data)

```bash
cd generator
python3 generate.py --seed 7   --n 500 --out ../holdouts/seed_7
python3 generate.py --seed 99  --n 500 --out ../holdouts/seed_99
cd ..
python3 cli/run.py holdouts/seed_7  --score holdouts/seed_7/ground_truth.json
python3 cli/run.py holdouts/seed_99 --score holdouts/seed_99/ground_truth.json
```

### Deploying to GitHub Pages

1. Push the repo to GitHub (public).
2. Repo **Settings → Pages → Deploy from a branch** → branch `main`, folder `/frontend`.
3. GitHub provides a URL of the form `https://<user>.github.io/<repo>/` — this is the live demo link.

---

## Project Structure

```
pipeline/shipverify/   pure Python — the core logic
  models.py              Category/Status/ReviewReason enums, the 7 FIELDS, EmailResult
  documents.py            txt/pdf/docx/xlsx -> flat lines
  classify.py             email -> Category
  extract_rules.py        lines -> 7 fields, synonym table
  normalize.py            formatting normalization
  compare.py              SI fields vs BL fields -> MATCH/MISMATCH/UNCERTAIN
  process.py              process_email() — the single entry point

cli/run.py               runs the pipeline over data/, writes + scores submission.json
eval/                     scoring tools, including wrong_emails.py for error analysis
data/                     provided inbox, attachments, and ground truth
generator/                synthetic data generator for fresh held-out test sets
holdouts/                 freshly generated test sets (committed for reproducibility)
tests/                    pytest suite
frontend/                 the dashboard — single-file React app, zero build step
```

---

**Team:** Saadat (Coordination · Verification & Comparison) · Tahiya (AI & Classification) · Aditya (Frontend/Dashboard) · Himanshu (Verification & Comparison) · Saimon (Backend & Deployment)

**Live demo:** https://saadat499.github.io/shippingdoc_verfication/
