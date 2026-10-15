"""Pack / unpack the raw files the dashboard is built from, as one .tar.gz (the GitHub Release asset).

The scheduled update (.github/workflows/update-data.yml) starts from an empty checkout: it downloads
the last snapshot from the GitHub Release tagged RELEASE_TAG, unpacks it, fetches only what changed
(scripts/fetch_elms.py update), rebuilds, checks, and, only if the hard checks pass, packs a new
snapshot and replaces the release asset (user, 2026-10-10: latest only).

The same snapshot gives a local checkout the exact data the live dashboard was built from:
  gh release download raw-data --pattern raw_data_snapshot.tar.gz --dir data/snapshot
  python scripts/raw_snapshot.py unpack --overwrite

The snapshot also holds a manifest (MANIFEST_PATH) with the row count of every table in
data/tables/, the number of files in each folder, and every vote event (VOTE_EVENT_MANIFEST_COLUMNS),
as they were when it was packed. The dashboard check (scripts/check_dashboard_data.py) compares a new
build against them (e.g. to list vote events eLMS has removed since).

Usage:
  python scripts/raw_snapshot.py pack                 # data/ -> SNAPSHOT_FILE (+ manifest)
  python scripts/raw_snapshot.py unpack [--overwrite] # SNAPSHOT_FILE -> data/
"""

import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent

# What goes in the snapshot (paths relative to the repo). Everything the build and export read that
# is not committed. Checked 2026-10-13 by running the export from a fresh clone plus an unpacked snapshot.
SNAPSHOT_PATHS = [
    # eLMS: what scripts/build_tables.py reads, plus the lists fetch_elms.py update starts from.
    "data/raw/elms/person_list.json",
    "data/raw/elms/body_list.json",
    "data/raw/elms/meeting_list.json",
    "data/raw/elms/matter_list.json",      # also fetch_elms.py's window plan for the next matter list
    "data/raw/elms/meetings",
    "data/raw/elms/matters",
    "data/raw/elms/update_runs.json",      # the per-run log (posting lag); appended by every run
    # Map layers (scripts/fetch_layers.py). Frozen here, not re-downloaded by scheduled runs, so the
    # overlay maps never change without notice.
    "data/raw/layers",
    # Ward tiles (scripts/build_ward_tiles.py all); the export reads the grid one.
    "data/tables/ward_tiles_grid.geojson",
    "data/tables/ward_tiles_pushed.geojson",
]
# Paths in SNAPSHOT_PATHS that may be missing when packing (the first run has no log yet).
OPTIONAL_PATHS = ["data/raw/elms/update_runs.json"]

# The manifest (written by pack, inside the snapshot): table row counts and file counts.
MANIFEST_PATH = REPO_DIR / "data" / "raw" / "snapshot_manifest.json"
TABLES_DIR = REPO_DIR / "data" / "tables"
# Folders whose file count goes in the manifest (each must be in SNAPSHOT_PATHS).
COUNTED_FOLDERS = ["data/raw/elms/meetings", "data/raw/elms/matters"]
# Per vote event (vote_events.csv), saved in the manifest as {event_id: [these values]}: enough to
# list a removed event in the check report without the old tables.
VOTE_EVENT_MANIFEST_COLUMNS = ["record_number", "action_date", "action_by", "voter_count"]

# The snapshot file, and the GitHub Release it is uploaded to (the workflow runs gh with these names).
SNAPSHOT_FILE = REPO_DIR / "data" / "snapshot" / "raw_data_snapshot.tar.gz"
RELEASE_TAG = "raw-data"

# ---------------------------------------------------------------------------


def table_row_counts():
    """{table name: rows} for every CSV in data/tables/ (read with pandas, so multi-line text fields count once)."""
    return {path.stem: len(pd.read_csv(path, low_memory=False)) for path in sorted(TABLES_DIR.glob("*.csv"))}


def vote_event_index():
    """{event_id: [VOTE_EVENT_MANIFEST_COLUMNS values]} from data/tables/vote_events.csv."""
    events = pd.read_csv(TABLES_DIR / "vote_events.csv", usecols=["event_id", *VOTE_EVENT_MANIFEST_COLUMNS],
                         low_memory=False)
    events = events.astype(object).where(events.notna(), None)   # blank -> null in JSON
    return {row[0]: [*row[1:]] for row in events[["event_id", *VOTE_EVENT_MANIFEST_COLUMNS]].itertuples(index=False)}


def pack():
    missing = [path for path in SNAPSHOT_PATHS if not (REPO_DIR / path).exists() and path not in OPTIONAL_PATHS]
    if missing:
        sys.exit(f"missing, not packing: {missing}")
    manifest = {
        "packed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "paths": SNAPSHOT_PATHS,
        "file_counts": {folder: sum(1 for _ in (REPO_DIR / folder).glob("*.json")) for folder in COUNTED_FOLDERS},
        "table_row_counts": table_row_counts(),
        "vote_event_columns": VOTE_EVENT_MANIFEST_COLUMNS,
        "vote_events": vote_event_index(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=1))
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = SNAPSHOT_FILE.with_suffix(".partial")
    with tarfile.open(temporary_file, "w:gz") as archive:
        for path in SNAPSHOT_PATHS + [str(MANIFEST_PATH.relative_to(REPO_DIR))]:
            if (REPO_DIR / path).exists():
                archive.add(REPO_DIR / path, arcname=path)
    temporary_file.replace(SNAPSHOT_FILE)
    print(json.dumps({key: manifest[key] for key in ["packed_at", "file_counts", "table_row_counts"]}, indent=1))
    print(f"wrote {SNAPSHOT_FILE.relative_to(REPO_DIR)} ({SNAPSHOT_FILE.stat().st_size / 1e6:.1f} MB)")


def unpack(overwrite=False):
    if not SNAPSHOT_FILE.exists():
        sys.exit(f"{SNAPSHOT_FILE.relative_to(REPO_DIR)} not found; download it first: "
                 f"gh release download {RELEASE_TAG} --pattern {SNAPSHOT_FILE.name} --dir {SNAPSHOT_FILE.parent.relative_to(REPO_DIR)}")
    with tarfile.open(SNAPSHOT_FILE, "r:gz") as archive:
        members = archive.getmembers()
        allowed_roots = SNAPSHOT_PATHS + [str(MANIFEST_PATH.relative_to(REPO_DIR))]
        outside = [member.name for member in members
                   if not any(member.name == root or member.name.startswith(root + "/") for root in allowed_roots)]
        if outside:
            sys.exit(f"snapshot holds paths outside SNAPSHOT_PATHS, not unpacking: {outside[:10]}")
        existing = [member.name for member in members if member.isfile() and (REPO_DIR / member.name).exists()]
        if existing and not overwrite:
            sys.exit(f"{len(existing)} files already exist (e.g. {existing[:3]}); re-run with --overwrite to replace them")
        # filter="data": refuses absolute paths, links out of the folder, and special files.
        archive.extractall(REPO_DIR, filter="data")
    file_count = sum(member.isfile() for member in members)
    print(f"unpacked {file_count} files ({len(existing)} replaced) from {SNAPSHOT_FILE.relative_to(REPO_DIR)}")
    print("Files on disk that are not in the snapshot were left as they are.")
    manifest = json.loads(MANIFEST_PATH.read_text())
    print(json.dumps({key: manifest[key] for key in ["packed_at", "file_counts", "table_row_counts"]}, indent=1))
    print(f"{len(manifest['vote_events'])} vote events listed in the manifest")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "pack":
        pack()
    elif len(sys.argv) >= 2 and sys.argv[1] == "unpack":
        unpack(overwrite="--overwrite" in sys.argv[2:])
    else:
        sys.exit("usage: python scripts/raw_snapshot.py {pack | unpack [--overwrite]}")
