# SDOC — Shipping Document Verification

Averis x Monash Hackathon 2026. Reads an inbox of 520 emails, classifies each
into `BL_COMPARISON | SI_REQUEST | INVOICE_QUERY | GENERAL | SPAM`, and for
`BL_COMPARISON` emails compares the Shipping Instruction (SI) against the
draft Bill of Lading (BL) on 7 fields.

## Setup (everyone, tonight)

```bash
git clone <this repo>
cd shipverify
pip install -r requirements.txt
python3 -m pytest tests/ -v          # should say 8 passed
python3 cli/run.py data --score data/ground_truth.json
```

The last command should print a JSON scoreboard ending in something like
`"final_score": 0.69`. If it doesn't, something's wrong with your setup —
ask in the group chat before writing any new code.

## How it's organized

```
pipeline/shipverify/   pure Python, no web/cloud code — the actual logic
  models.py              THE CONTRACT. Category/Status/ReviewReason enums,
                          the 7 FIELDS, EmailResult. Import from here, don't
                          redefine these anywhere else.
  documents.py            txt/pdf/docx/xlsx -> flat lines  (AI engineer)
  classify.py             email -> Category                (AI engineer)
  extract_rules.py        lines -> 7 fields, synonym table  (Verification)
  normalize.py            formatting normalization          (Verification)
  compare.py              SI fields vs BL fields -> MATCH/MISMATCH/UNCERTAIN
  process.py              process_email() — THE ONLY ENTRY POINT. Backend
                          and CLI both call this and nothing else.
  export.py               EmailResult -> submission.json record shape

cli/run.py               loads data/, runs process_email on every email,
                          writes submission.json, scores it locally
eval/
  scoring.py, score_cli.py   organizer-provided scorer (don't edit)
  wrong_emails.py             YOUR daily loop: which emails are wrong & why
contracts/fixtures/       3 real example EmailResult JSON — match, mismatch,
                          needs_review. Frontend builds screens against
                          these before the backend even exists.
data/                     the provided inbox + attachments + ground_truth
generator/                organizer's synthetic data generator (for making
                          fresh, unseen test sets — see "Held-out scoring")
holdouts/                 put freshly generated test sets here (gitignored
                          is NOT set for this — we want these in the repo
                          for the final numbers slide)
tests/                    pytest — run before every PR
frontend/                 THE DASHBOARD. Real React, zero build step —
                          loaded straight from a CDN in one HTML file.
  index.html                Inbox, Case Detail, Review Queue — all in one
                             file. Open it in any editor; it's plain JSX
                             inside a <script type="text/babel"> tag.
  build_data.py             exports data/*.json -> frontend/results.json,
                             the one file index.html fetches. Re-run this
                             any time the pipeline output changes.
  results.json              generated — commit it so GitHub Pages can
                             serve it as a static file next to index.html
```

## Running the dashboard

```bash
python3 frontend/build_data.py     # regenerate results.json from the pipeline
cd frontend
python3 -m http.server 8000        # any static file server works
```

Open `http://localhost:8000`. No `npm install`, no build step — the browser
downloads React and Babel from a CDN and compiles the JSX on the fly. This
also means: **whatever an AI coding tool generates for you as a React
snippet drops straight into the `<script type="text/babel">` block** — no
adapting it to a Vite/Next.js project structure.

**Deploying (no cloud account, no card, nothing new to sign up for):**
1. Push this repo to GitHub (public, per the organizer's ruling).
2. Repo Settings → Pages → Deploy from a branch → branch `main`,
   folder `/frontend`.
3. GitHub gives you a URL like `https://<user>.github.io/<repo>/` — that's
   your submission link.

Known limitation: review decisions save to the browser's `localStorage`,
so they're per-browser, not shared between judges. That's fine for a demo
— you're showing the loop works, not running it as a shared production
tool. If you want decisions to sync across machines, that's a real backend
(Firestore/Cosmos/etc.), and it's a stretch goal, not a requirement.

## Cloud integration — Firebase Realtime Database

The hackathon rules require meaningfully integrating cloud infrastructure,
not just AI. Gemini covers the AI half; this covers the other half without
adding a server to run or a build step to break.

1. `console.firebase.google.com` → Add project → Build → Realtime Database
   → Create Database → start in test mode (free Spark plan, no card).
2. Copy the database URL (looks like
   `https://your-project-default-rtdb.REGION.firebasedatabase.app`).
3. Paste it into **both**:
   - `FIREBASE_DB_URL` near the top of `frontend/index.html`
   - `FIREBASE_DB_URL` near the top of `frontend/upload_to_firebase.py`
4. Push results to the cloud:
   ```bash
   python3 frontend/build_data.py
   python3 frontend/upload_to_firebase.py
   ```
5. Open `frontend/index.html` (still no build step) — it now reads results
   and writes review decisions to Firebase instead of a local file /
   localStorage, so decisions are shared across anyone viewing the app.

Leaving `FIREBASE_DB_URL` as the placeholder keeps the app working exactly
as before (local `results.json` + `localStorage`) — useful for offline
development before Firebase is set up.

## If you're using an AI tool to extend the frontend

Give it `frontend/results.json`'s shape (one real record is worth more than
a description) and `contracts/fixtures/*.json`, and ask it to work inside
the existing `index.html` rather than scaffold a new project. Keep changes
inside the `<script type="text/babel">` block and the `<style>` block —
that boundary is what keeps this a one-file, no-build-step deploy.

## Why this frontend setup, not a full React project

One HTML file, React from a CDN, no `npm run build`. Given the team's
comfort level, a build toolchain is a place things fail for reasons that
are hard to debug under deadline pressure. This gets you real React —
paste in whatever an AI coding tool generates — without npm, Vite, or a
deploy pipeline that can break. Deploy target is GitHub Pages: free,
already part of the repo you're pushing to, no new account, no card.

## The rule everyone follows

**`process_email()` in `pipeline/shipverify/process.py` is the only way
into the pipeline.** The CLI calls it. The backend worker will call it.
Nobody else re-implements classification or comparison logic elsewhere —
if backend or frontend needs different behavior, that's a sign
`process.py` needs a new parameter, not a parallel code path.

## Current baseline (rules only, no LLM yet)

```json
{
  "final_score": 0.69,
  "stage1_macro_f1": 0.95,
  "stage3_defect_f1": 0.87,
  "end_to_end_rate": 0.46,
  "reliability_escalation_f1": 0.72,
  "rule_pct": 1.0
}
```

Run `python3 eval/wrong_emails.py submission.json data/ground_truth.json`
for the exact list of what's still wrong. As of this baseline, most misses
are: (1) emails the rule classifier defaults to GENERAL instead of
INVOICE_QUERY/SPAM — this is the LLM's job, `classify.py` has a
`llm_classify()` stub — and (2) a few PDF/table layouts where a field isn't
being found. Start there.

## Held-out scoring (don't skip this before the video)

The provided `data/ground_truth.json` is what you develop against. For
final numbers that actually mean something in front of judges, generate
fresh data you haven't tuned on:

```bash
cd generator
python3 generate.py --seed 7   --n 500 --out ../holdouts/seed_7
python3 generate.py --seed 99  --n 500 --out ../holdouts/seed_99
cd ..
python3 cli/run.py holdouts/seed_7  --score holdouts/seed_7/ground_truth.json
python3 cli/run.py holdouts/seed_99 --score holdouts/seed_99/ground_truth.json
```

Report the held-out numbers in the video and slides, not the dev-set number.

## The 7 fields and the label synonym table

`shipper, consignee, notify_party, port_of_loading, port_of_discharge,
container_count, gross_weight_kg`. The same field is labeled differently on
SI vs BL documents (e.g. `Port of Loading` vs `Load Port`, `To the Order of`
vs `Consignee`). The full synonym table observed in the data is in
`extract_rules.py` — add to it as you find more variants, don't hardcode
new fields elsewhere.

## Branching

`main` must always pass `pytest` and produce a valid submission. Work on a
branch, open a PR, CI must pass before merging. Two checkpoints a day
(1 PM / 10 PM MYT): open the live deployed URL and run the pipeline over
the full dataset.

## Provenance

`docs/organizer-provided/` holds the original two zip files the hackathon
organizers gave the team, completely unmodified. Everything under `data/`,
`eval/`, and `generator/` in this repo is a copy of what's in those zips —
see that folder's README for exactly what came from where.
