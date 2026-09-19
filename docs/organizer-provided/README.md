# Organizer-provided files (untouched)

These two zip files are exactly what the Averis x Monash organizers gave
the team — byte-for-byte, unmodified. Kept here for provenance, in case a
judge or teammate wants to see precisely what was handed out versus what
the team built on top of it.

- **sdoc-hackathon-bundle.zip** — the participant dataset: `inbox/`,
  `attachments/`, `sample_submission.json`, `loader.py`. Its contents are
  copied (not moved) into `/data` at the repo root, where the pipeline
  actually reads from.
- **sdoc-hackathon-docker.zip** — the local scoring server, the answer key
  (`data_v2/ground_truth.json`), and the synthetic-data generator. Its
  ground truth is copied into `/data/ground_truth.json`, the scorer into
  `/eval`, and the generator into `/generator` — again, copies, not the
  only version.

Nothing in this folder is imported or read by any code in the repo. It
exists purely as a record of the original source material.
