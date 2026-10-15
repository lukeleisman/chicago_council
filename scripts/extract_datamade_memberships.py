"""Freeze the DataMade council memberships that build_tables.py uses into a small committed CSV.

build_tables.py reads only the tenure dates from the 3.5 GB DataMade SQLite database: every
"Chicago City Council" membership (person_name, start_date, end_date). Scheduled runs on GitHub
can't carry the database, so this script copies exactly that query's result to
reference/datamade_council_memberships.csv. build_tables.DATAMADE_MEMBERSHIP_SOURCE chooses
which one the build reads.

The SQL is build_tables.load_datamade_council_memberships_from_sqlite() itself (called, not
copied), so the two can't drift apart. Rows are written in the order the query returns them,
sorted by (person_name, start_date, end_date) so re-running on the same database gives the
same file.

A new alder appointed after the database's download date has no row here. The dashboard check
(scripts/check_dashboard_data.py) stops the publish when a current alder has no start date. Fix
by hand: a build_tables.TENURE_START_OVERRIDES entry, or download a newer database and re-run
this script.

Usage:
  python scripts/extract_datamade_memberships.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_tables

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_PATH = build_tables.DATAMADE_EXTRACT_PATH
# When the database was downloaded: data/raw/chicago_council.db.zip.retrieved (written when the
# zip was fetched). Copied into OUTPUT_PATH's .retrieved note.
DATABASE_RETRIEVED_NOTE = build_tables.DATAMADE_DB_PATH.parent / "chicago_council.db.zip.retrieved"
SORT_COLUMNS = ["person_name", "start_date", "end_date"]

# ---------------------------------------------------------------------------

if __name__ == "__main__":
    memberships = build_tables.load_datamade_council_memberships_from_sqlite()
    memberships = memberships.sort_values(SORT_COLUMNS).reset_index(drop=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    memberships.to_csv(OUTPUT_PATH, index=False)
    retrieved_at = DATABASE_RETRIEVED_NOTE.read_text().strip()
    note_path = OUTPUT_PATH.with_name(OUTPUT_PATH.name + ".retrieved")
    note_path.write_text(
        f"DataMade database downloaded: {retrieved_at}\n"
        f"Organization: {build_tables.DATAMADE_COUNCIL_ORGANIZATION}\n"
        f"Rows: {len(memberships)}; people: {memberships.person_name.nunique()}\n")
    print(f"wrote {OUTPUT_PATH} ({len(memberships)} rows, {memberships.person_name.nunique()} people); "
          f"database downloaded {retrieved_at}")
