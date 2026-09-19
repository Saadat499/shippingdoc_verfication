#!/usr/bin/env python3
"""
Pushes results.json to Firebase Realtime Database so the dashboard reads
live from the cloud instead of a file baked into the repo. This is what
makes cloud infrastructure part of the app's core functionality, not
decoration.

Fill in FIREBASE_DB_URL below once (from the Firebase console), then:

    python3 frontend/build_data.py       # regenerate results.json locally
    python3 frontend/upload_to_firebase.py

Realtime Database's REST API is plain JSON over HTTP — PUT a JSON body at
a path ending in ".json", no SDK, no auth needed for a public test-mode
database. I can't test this call from here (no network access to Firebase
from this sandbox) — this mirrors Firebase's documented REST format, but
run it for real once your project exists and confirm with the printed
status code.
"""
import json
import sys
from pathlib import Path

import requests

# TODO: paste your database URL here, no trailing slash
FIREBASE_DB_URL = "https://YOUR-PROJECT-default-rtdb.YOUR-REGION.firebasedatabase.app"


def main():
    if "YOUR-PROJECT" in FIREBASE_DB_URL:
        print("Edit FIREBASE_DB_URL at the top of this file first.", file=sys.stderr)
        sys.exit(1)

    results_path = Path(__file__).parent / "results.json"
    if not results_path.exists():
        print("results.json not found — run frontend/build_data.py first.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(results_path.read_text())
    resp = requests.put(f"{FIREBASE_DB_URL}/results.json", json=data, timeout=30)
    print(f"PUT /results.json -> {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text, file=sys.stderr)
        sys.exit(1)
    print(f"Uploaded {len(data)} email results to Firebase.")


if __name__ == "__main__":
    main()
