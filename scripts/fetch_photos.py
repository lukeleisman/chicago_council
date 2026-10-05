"""Download current alders' photos from the eLMS profile-picture URLs.

Which people: rows of data/tables/people.csv with is_active = True and a ward
number in elms_ward (the 50 sitting alders; the Clerk and Mayor are left out).
Run `python scripts/build_tables.py all` first.

Each photo is saved verbatim as data/raw/photos/<person_id>.<ext>, plus
data/raw/photos/manifest.json recording the URL, retrieval time, size and
content type for every file. Mirrors scripts/fetch_layers.py.

Usage:
  python scripts/fetch_photos.py            # fetch any photo not yet on disk
  python scripts/fetch_photos.py --force    # re-fetch everything
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent
PEOPLE_TABLE_PATH = REPO_DIR / "data" / "tables" / "people.csv"
OUTPUT_DIR = REPO_DIR / "data" / "raw" / "photos"

REQUEST_TIMEOUT_SECONDS = 60

# File extension for each content type the server may return. Any other type
# stops the script, so an unexpected response (e.g. an HTML error page) is
# never saved as a photo.
EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
}

# Number of people expected (one per ward). The script stops if the selection
# from people.csv gives a different count.
EXPECTED_PEOPLE_COUNT = 50

# ---------------------------------------------------------------------------


def select_current_alders():
    people = pd.read_csv(PEOPLE_TABLE_PATH, dtype={"elms_ward": str})
    has_ward_number = people.elms_ward.str.fullmatch(r"\d+", na=False)   # excludes "Clerk", "Mayor"
    current_alders = people[people.is_active & has_ward_number]
    if len(current_alders) != EXPECTED_PEOPLE_COUNT:
        raise SystemExit(f"expected {EXPECTED_PEOPLE_COUNT} current alders, found {len(current_alders)}")
    missing_url = current_alders[current_alders.photo_url.isna()]
    if len(missing_url):
        raise SystemExit(f"no photo_url for: {missing_url.display_name.tolist()}")
    return current_alders


def main(force_refetch):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for row in select_current_alders().itertuples():
        if row.person_id in manifest and (OUTPUT_DIR / manifest[row.person_id]["file"]).exists() and not force_refetch:
            print(f"skip   {row.elms_ward} {row.display_name} (on disk)")
            continue
        with urllib.request.urlopen(row.photo_url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw_bytes = response.read()
            content_type = response.headers.get_content_type()
        if content_type not in EXTENSION_BY_CONTENT_TYPE:
            raise SystemExit(f"{row.display_name}: unexpected content type {content_type!r} from {row.photo_url}")
        file_name = f"{row.person_id}.{EXTENSION_BY_CONTENT_TYPE[content_type]}"
        (OUTPUT_DIR / file_name).write_bytes(raw_bytes)
        manifest[row.person_id] = {
            "file": file_name,
            "display_name": row.display_name,
            "elms_ward": row.elms_ward,
            "photo_url": row.photo_url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "content_type": content_type,
            "bytes": len(raw_bytes),
        }
        print(f"saved  {row.elms_ward} {row.display_name}: {content_type}, {len(raw_bytes) / 1e3:.0f} KB")

    manifest_path.write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main(force_refetch="--force" in sys.argv)
