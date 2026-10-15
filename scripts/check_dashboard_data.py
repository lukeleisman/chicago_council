"""Check a fresh build before it is published: hard checks block the publish, soft checks only warn.

Run after scripts/fetch_elms.py update, scripts/build_tables.py all and scripts/export_dashboard_data.py.
Compares the new data/tables/ and docs/data/ against:
  - the last published docs/data/ (git HEAD; in a scheduled run that is what the live page shows)
  - the previous snapshot's table row counts and file counts (data/raw/snapshot_manifest.json,
    unpacked from the GitHub Release by scripts/raw_snapshot.py; replaced when a new snapshot is packed)
  - the newest record in data/raw/elms/update_runs.json (written by fetch_elms.py update)

Writes (gitignored, under CHECK_OUTPUT_DIR):
  check_report.md   every check, with the raw before/after numbers, every run
  soft_warnings.md  only the soft warnings (body of the GitHub issue), empty if none
  result.json       counts the workflow reads: hard failures, soft warnings, whether docs/data changed,
                    and the numbers for the commit message
Exits 1 if any hard check failed (the workflow then publishes nothing, and GitHub emails the failure).

The build's own stops (a new raw vote value, an unknown duplicate roster row, ...: assert statements in
scripts/build_tables.py and export_dashboard_data.py) fail the run before this script is reached.

Usage:
  python scripts/check_dashboard_data.py
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_tables
import fetch_elms
import raw_snapshot

# ---------------------------------------------------------------------------
# Configuration — every threshold is a named constant.
# All values marked "initial guess" were set 2026-10-13 (user: "put them in, but mark them as
# initial guesses"); revisit after a few weeks of check reports.
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent
DOCS_DATA_DIR = REPO_DIR / "docs" / "data"
TABLES_DIR = REPO_DIR / "data" / "tables"
CHECK_OUTPUT_DIR = REPO_DIR / "data" / "check"

# --- Hard: files ---
# Every file the page loads, with the keys each must have. "list:" = a JSON list whose records have
# these keys; "dict:" = a JSON object with these keys; "features" = a GeoJSON FeatureCollection.
# ward_areas.json and ward_layer_summary.json are written by scripts/ward_layer_overlaps.py, not by
# the scheduled export, so they only have to exist and parse.
EXPECTED_DOCS_DATA_FILES = {
    "alders.json": ("list", ["ward", "person_id", "display_name", "label_name", "photo_url",
                             "council_start_date", "years_on_council", "absent_meetings",
                             "meetings_in_denominator", "percent_absent"]),
    "split_events.json": ("list", ["event_id", "record_number", "action_date", "tallies", "votes_by_ward"]),
    "committees.json": ("dict", ["rules", "style", "committees", "by_ward", "overviews"]),
    "meta.json": ("dict", ["exported_at", "tenure_as_of", "newest_meeting_date", "data_changed_at",
                           "default_split_event_id", "real_map_labels", "layers", "about_text"]),
    "wards_real.geojson": ("features", []),
    "wards_tiles_grid.geojson": ("features", []),
    **{f"layer_{name}.geojson": ("features", []) for name in [
        "community_areas", "neighborhoods", "zip_codes", "police_districts", "parks",
        "cta_rail_lines", "cta_rail_stations", "cps_schools_sy2526", "ward_offices"]},
    "ward_areas.json": ("any", []),
    "ward_layer_summary.json": ("any", []),
}

# --- Hard: alders ---
EXPECTED_WARDS = [f"{ward:02d}" for ward in range(1, 51)]   # one current alder per ward, "01".."50"

# --- Hard: row counts never go down (vs the previous snapshot's manifest) ---
# Tables in data/tables/ and folders in the snapshot whose counts are compared.
ROW_COUNT_TABLES = ["member_votes", "vote_events", "attendance", "meetings"]
FILE_COUNT_FOLDERS = ["data/raw/elms/matters", "data/raw/elms/meetings"]
ALLOWED_ROW_DECREASE = 0              # initial guess: rows (or files) a count may drop by
# Removed vote events (user, 2026-10-15: soft, list them and publish). eLMS sometimes removes a roll
# call (2026-10-15: O2026-0025202 and O2026-0027938 each lost a 50-vote council roll call). Removed
# events are found by event_id against the snapshot manifest and listed as a soft warning. The
# vote_events / member_votes count checks above subtract those removed rows before comparing, so a
# removal alone never blocks the publish.

# --- Hard: file sizes (vs the published docs/data/ at git HEAD) ---
MAX_FILE_SHRINK_FRACTION = 0.10       # initial guess: any one docs/data file may shrink by at most 10%
MAX_TOTAL_DOCS_DATA_MB = 15           # initial guess (user, 2026-10-13: "a bit higher, 15"); 1.9 MB on 2026-10-10

# --- Soft (publish, but open/update the GitHub issue) ---
# Absence moves in meetings, not percentage points (user, 2026-10-13: the percent depends on how
# many meetings an alder has been seated for). Warn when any alder's absent_meetings count moves
# by more than this many meetings, up or down, since the published file.
ABSENT_MEETINGS_JUMP = 1              # initial guess
MAX_NEW_SPLIT_EVENTS_PER_RUN = 40     # initial guess
# Council meetings that should have data by now: dated more than EMPTY_MEETING_GRACE_DAYS ago, but
# within fetch_elms.MEETING_REFRESH_DAYS (older meetings are not re-fetched, so a warning about them
# could never clear). Warn when such a meeting has NO attendance AND NO vote events (user,
# 2026-10-15; the agenda is not checked: eLMS often leaves it empty, e.g. 2026-09-23 has 1,223 vote
# events and no agenda). Meetings with a status in MEETING_STATUSES_SKIPPED are not checked.
EMPTY_MEETING_GRACE_DAYS = 14         # initial guess
MEETING_STATUSES_SKIPPED = ["Cancelled"]   # eLMS meeting status, as recorded
STALE_AFTER_DAYS = 45                 # initial guess: warn if meta.newest_meeting_date is older than this
# New council term (user, 2026-10-15: scheduled runs export the data files only, "unless it's a new
# council term"). The shapes and layers don't depend on who is on the council, but a new term brings
# new alder names (Map View labels need re-optimizing) and a new fetch_elms.TERM_START_DATE. From this
# date on, a soft warning says to do those by hand and run the full export.
# 2027-05-16 = the end date DataMade gives every current alder's membership (build_tables, Tenure).
# OPEN QUESTION: the next inauguration date itself is not in our data.
CURRENT_TERM_END_DATE = "2027-05-16"
# person_id_source value of a placeholder personId that no name rule replaced (build_tables decision 1.7).
UNMATCHED_PLACEHOLDER_SOURCE = "placeholder, unmatched"

# --- Change detection (does this run commit?) ---
# docs/data counts as changed if any file differs from git HEAD, with these fields left out.
# exported_at changes every run. Note: with build_tables.AS_OF_DATE_RULE "run_date", alders.json
# years_on_council changes every day, so a run on a new day always commits.
IGNORE_FOR_CHANGE_DETECTION = {"meta.json": ["exported_at"]}

# ---------------------------------------------------------------------------


class Report:
    """Collects check lines. Each check: tier ('hard' / 'soft' / 'info'), name, passed, detail lines."""

    def __init__(self):
        self.checks = []

    def add(self, tier, name, passed, details=()):
        self.checks.append({"tier": tier, "name": name, "passed": passed, "details": list(details)})

    def failures(self, tier):
        return [check for check in self.checks if check["tier"] == tier and not check["passed"]]

    def markdown(self, checks=None, title="Dashboard data check"):
        lines = [f"## {title}", ""]
        for check in checks if checks is not None else self.checks:
            mark = "PASS" if check["passed"] else ("FAIL" if check["tier"] == "hard" else "WARN")
            if check["tier"] == "info":
                mark = "INFO"
            lines.append(f"- **{mark}** ({check['tier']}) {check['name']}")
            lines.extend(f"  - {detail}" for detail in check["details"])
        return "\n".join(lines) + "\n"


def published_file(file_name):
    """docs/data/<file_name> as committed at git HEAD (bytes), or None if HEAD doesn't have it."""
    completed = subprocess.run(["git", "show", f"HEAD:docs/data/{file_name}"], cwd=REPO_DIR, capture_output=True)
    return completed.stdout if completed.returncode == 0 else None


def published_json(file_name):
    content = published_file(file_name)
    return json.loads(content) if content is not None else None


def check_files(report):
    for file_name, (kind, required_keys) in EXPECTED_DOCS_DATA_FILES.items():
        path = DOCS_DATA_DIR / file_name
        if not path.exists():
            report.add("hard", f"{file_name} exists", False, ["missing"])
            continue
        try:
            content = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            report.add("hard", f"{file_name} parses", False, [str(error)])
            continue
        problems = []
        if kind == "list":
            if not isinstance(content, list) or not content:
                problems.append("not a non-empty list")
            else:
                records_missing = [index for index, record in enumerate(content)
                                   if not set(required_keys) <= set(record)]
                if records_missing:
                    problems.append(f"{len(records_missing)} records miss a required key (first: #{records_missing[0]})")
        elif kind == "dict":
            missing_keys = [key for key in required_keys if key not in content]
            if missing_keys:
                problems.append(f"missing keys {missing_keys}")
        elif kind == "features":
            if content.get("type") != "FeatureCollection" or not content.get("features"):
                problems.append("not a non-empty FeatureCollection")
        report.add("hard", f"{file_name} exists, parses, has its required keys", not problems, problems)


def check_alders(report, alders):
    wards = [record["ward"] for record in alders]
    report.add("hard", f"exactly {len(EXPECTED_WARDS)} current alders, wards 01-50 each once",
               sorted(wards) == EXPECTED_WARDS,
               [f"{len(wards)} alders; missing wards {sorted(set(EXPECTED_WARDS) - set(wards))}; "
                f"repeated wards {sorted({ward for ward in wards if wards.count(ward) > 1})}"])
    no_start = [f"{record['ward']} {record['display_name']}" for record in alders if not record.get("council_start_date")]
    no_photo = [f"{record['ward']} {record['display_name']}" for record in alders if not record.get("photo_url")]
    no_meetings = [f"{record['ward']} {record['display_name']}" for record in alders
                   if not record.get("meetings_in_denominator")]
    report.add("hard", "every current alder has a tenure start date", not no_start,
               [f"none for: {no_start} (fix: build_tables.TENURE_START_OVERRIDES, or a newer DataMade extract)"] if no_start else [])
    report.add("hard", "every current alder has a photo URL", not no_photo, [f"none for: {no_photo}"] if no_photo else [])
    report.add("hard", "every current alder has an absence denominator > 0", not no_meetings,
               [f"0 meetings for: {no_meetings}"] if no_meetings else [])


def check_counts(report, manifest, new_table_counts, new_file_counts, removed_rows):
    """removed_rows: {table name: rows that belonged to removed vote events} (check_removed_vote_events)."""
    if manifest is None:
        report.add("hard", "previous snapshot manifest found", False,
                   [f"{raw_snapshot.MANIFEST_PATH.relative_to(REPO_DIR)} missing: unpack the snapshot first"])
        return
    report.add("info", "previous snapshot", True, [f"packed {manifest['packed_at']}"])
    for table_name in ROW_COUNT_TABLES:
        before, after = manifest["table_row_counts"].get(table_name), new_table_counts[table_name]
        removed = removed_rows.get(table_name, 0)
        passed = before is not None and after >= before - removed - ALLOWED_ROW_DECREASE
        report.add("hard", f"{table_name} rows do not decrease (beyond removed vote events)", passed,
                   [f"before {before}, after {after}, change {after - before if before is not None else 'n/a'}; "
                    f"rows of removed vote events {removed}"])
    for folder in FILE_COUNT_FOLDERS:
        before, after = manifest["file_counts"].get(folder), new_file_counts[folder]
        passed = before is not None and after >= before - ALLOWED_ROW_DECREASE
        report.add("hard", f"{folder} file count does not decrease", passed,
                   [f"before {before}, after {after}, change {after - before if before is not None else 'n/a'}"])


def check_removed_vote_events(report, manifest):
    """Soft: vote events in the previous snapshot that are gone now.
    Returns ({table: removed rows}, set of removed event_ids)."""
    if manifest is None or "vote_events" not in manifest:
        report.add("info", "removed vote events", True, ["no vote event list in the previous manifest to compare"])
        return {}, set()
    columns = manifest["vote_event_columns"]
    new_ids = set(pd.read_csv(TABLES_DIR / "vote_events.csv", usecols=["event_id"]).event_id)
    removed = {event_id: dict(zip(columns, values)) for event_id, values in manifest["vote_events"].items()
               if event_id not in new_ids}
    report.add("soft", "no vote events removed by eLMS since the previous snapshot", not removed,
               [f"{event['record_number']}, {event['action_date']}, {event['action_by']}, {event['voter_count']} voters "
                f"({event_id})" for event_id, event in sorted(removed.items(), key=lambda item: str(item[1]['action_date']))])
    removed_rows = {"vote_events": len(removed), "member_votes": sum(int(event["voter_count"]) for event in removed.values())}
    return removed_rows, set(removed)


def check_new_term(report):
    today = pd.Timestamp.now(tz=build_tables.LOCAL_TIMEZONE).strftime("%Y-%m-%d")
    report.add("soft", f"still in the term ending {CURRENT_TERM_END_DATE}", today <= CURRENT_TERM_END_DATE,
               [] if today <= CURRENT_TERM_END_DATE else [
                   "new council term: update fetch_elms.TERM_START_DATE and CURRENT_TERM_END_DATE here, re-optimize the "
                   "Map View labels (scripts/optimize_map_labels.py), and run the full export by hand "
                   "(python scripts/export_dashboard_data.py, without --data-only)"])


def check_sizes(report):
    rows, problems, total_bytes = [], [], 0
    for path in sorted(DOCS_DATA_DIR.glob("*")):
        size_after = path.stat().st_size
        total_bytes += size_after
        published = published_file(path.name)
        size_before = len(published) if published is not None else None
        if size_before:
            shrink = (size_before - size_after) / size_before
            rows.append(f"{path.name}: {size_before:,} -> {size_after:,} bytes ({-shrink:+.1%})")
            if shrink > MAX_FILE_SHRINK_FRACTION:
                problems.append(path.name)
        else:
            rows.append(f"{path.name}: new file, {size_after:,} bytes")
    report.add("hard", f"no docs/data file shrinks by more than {MAX_FILE_SHRINK_FRACTION:.0%}", not problems,
               ([f"too much: {problems}"] if problems else []) + rows)
    report.add("hard", f"docs/data total under {MAX_TOTAL_DOCS_DATA_MB} MB", total_bytes / 1e6 < MAX_TOTAL_DOCS_DATA_MB,
               [f"{total_bytes / 1e6:.2f} MB"])


def check_split_events(report, split_events, published_split_events, removed_event_ids):
    """Hard: split event count doesn't drop, except by published split events eLMS removed (soft-listed)."""
    before = len(published_split_events) if published_split_events is not None else None
    after = len(split_events)
    removed_split = ({event["event_id"] for event in published_split_events} & removed_event_ids
                     if published_split_events is not None else set())
    report.add("hard", "number of split events does not decrease (beyond removed vote events)",
               before is None or after >= before - len(removed_split),
               [f"before {before}, after {after}; removed by eLMS {len(removed_split)}"])
    if before is not None:
        new_ids = sorted({event["event_id"] for event in split_events}
                         - {event["event_id"] for event in published_split_events})
        report.add("soft", f"at most {MAX_NEW_SPLIT_EVENTS_PER_RUN} new split events", len(new_ids) <= MAX_NEW_SPLIT_EVENTS_PER_RUN,
                   [f"{len(new_ids)} new"])


def check_alder_changes(report, alders, published_alders):
    if published_alders is None:
        report.add("info", "alder changes", True, ["no published alders.json to compare"])
        return
    before = {record["ward"]: record for record in published_alders}
    after = {record["ward"]: record for record in alders}
    changed = [f"ward {ward}: {before[ward]['display_name']} -> {after[ward]['display_name']}"
               for ward in sorted(set(before) & set(after)) if before[ward]["person_id"] != after[ward]["person_id"]]
    report.add("soft", "no ward's alder changed", not changed,
               changed + (["new alder: the Map View labels may need re-optimizing (scripts/optimize_map_labels.py)"]
                          if changed else []))
    jumps = []
    for ward in sorted(set(before) & set(after)):
        if before[ward]["person_id"] != after[ward]["person_id"]:
            continue
        old_count, new_count = before[ward]["absent_meetings"], after[ward]["absent_meetings"]
        if abs(new_count - old_count) > ABSENT_MEETINGS_JUMP:
            jumps.append(f"ward {ward} {after[ward]['display_name']}: absent meetings {old_count} -> {new_count} "
                         f"(of {before[ward]['meetings_in_denominator']} -> {after[ward]['meetings_in_denominator']})")
    report.add("soft", f"no alder's absent meetings moved by more than {ABSENT_MEETINGS_JUMP}", not jumps, jumps)


def check_committee_changes(report, committees, published_committees):
    if published_committees is None:
        report.add("info", "committee changes", True, ["no published committees.json to compare"])
        return

    def by_name(content):
        return {record["name"]: record for record in content["committees"]}

    before, after = by_name(published_committees), by_name(committees)
    changes = [f"new committee: {name}" for name in sorted(set(after) - set(before))]
    changes += [f"committee gone: {name}" for name in sorted(set(before) - set(after))]
    for name in sorted(set(before) & set(after)):
        for field in ["chair_wards", "vice_chair_wards", "member_count"]:
            if before[name][field] != after[name][field]:
                changes.append(f"{name}: {field} {before[name][field]} -> {after[name][field]}")
    report.add("soft", "no committee, chair or vice chair changed", not changes, changes)


def check_placeholders(report):
    rows, total = [], 0
    for table_name in ["member_votes", "attendance"]:
        table = pd.read_csv(TABLES_DIR / f"{table_name}.csv", usecols=["person_id_source", "voter_name"])
        unmatched = table[table.person_id_source == UNMATCHED_PLACEHOLDER_SOURCE]
        total += len(unmatched)
        rows.append(f"{table_name}: {len(unmatched)} rows"
                    + (f" (names: {sorted(unmatched.voter_name.astype(str).unique())})" if len(unmatched) else ""))
    report.add("soft", f"no '{UNMATCHED_PLACEHOLDER_SOURCE}' rows (add the name to build_tables.PLACEHOLDER_PERSON_ID_BY_NAME)",
               total == 0, rows)


def check_recent_meetings(report, meetings):
    today = pd.Timestamp.now(tz=build_tables.LOCAL_TIMEZONE).normalize().tz_localize(None)
    oldest = (today - timedelta(days=fetch_elms.MEETING_REFRESH_DAYS)).strftime("%Y-%m-%d")
    newest = (today - timedelta(days=EMPTY_MEETING_GRACE_DAYS)).strftime("%Y-%m-%d")
    window = meetings[(meetings.body == build_tables.COUNCIL_BODY)
                      & (meetings.meeting_date >= oldest) & (meetings.meeting_date < newest)]
    checked = window[~window.status.isin(MEETING_STATUSES_SKIPPED)]
    empty = checked[~checked.has_attendance & (checked.vote_event_count == 0)]
    report.add("soft", f"council meetings dated {oldest} to before {newest} (not {MEETING_STATUSES_SKIPPED}) "
                       f"have attendance or vote events", empty.empty,
               [f"{'NO DATA ' if row.meeting_id in set(empty.meeting_id) else ''}{row.meeting_date} ({row.status}): "
                f"agenda items {row.agenda_item_count}, attendance members {row.attendance_member_count}, "
                f"vote events {row.vote_event_count}" for row in window.itertuples()] or ["no council meetings in that window"])


def check_staleness(report, meta):
    newest = meta.get("newest_meeting_date")
    age_days = (pd.Timestamp.now(tz=build_tables.LOCAL_TIMEZONE).tz_localize(None).normalize()
                - pd.Timestamp(newest)).days if newest else None
    report.add("soft", f"newest council meeting with roll calls is at most {STALE_AFTER_DAYS} days old",
               age_days is not None and age_days <= STALE_AFTER_DAYS, [f"newest {newest}, {age_days} days ago"])


def check_download_failures(report, last_run):
    if last_run is None:
        report.add("soft", "update run log found", False, [f"{fetch_elms.UPDATE_RUN_LOG.name} has no runs"])
        return
    report.add("info", "update run", True, [
        f"started {last_run['started_at']}, {last_run['request_count']} requests",
        f"{len(last_run['new_matter_ids'])} new matters; {len(last_run['refetched_matter_ids'])} re-fetched: "
        f"{last_run.get('refetched_because_date_changed')} with a new date ({last_run['matter_refresh_rule']}), "
        f"{last_run.get('refetched_because_not_in_list')} not in the list ({last_run.get('matter_refresh_unlisted')})",
        *[f"meeting {meeting['date_utc'][:10]} {meeting['status']}: agenda {meeting['agenda_items']}, "
          f"attendance roll calls {meeting['attendance_roll_calls']}, vote events {meeting['vote_events']}"
          for meeting in last_run["recent_council_meetings"]],
    ])
    failures = last_run["failures"]
    report.add("soft", "no matter download failed (404 = removed from eLMS; the old saved file, if any, is kept)",
               not failures, [f"{failure['api_path']}: {failure['reason']}" for failure in failures])


def docs_data_changed():
    """(changed?, [changed file names]) vs git HEAD, leaving out IGNORE_FOR_CHANGE_DETECTION fields."""
    changed = []
    for path in sorted(DOCS_DATA_DIR.glob("*")):
        published = published_file(path.name)
        if published is None:
            changed.append(path.name)
            continue
        if path.name in IGNORE_FOR_CHANGE_DETECTION:
            left_out = IGNORE_FOR_CHANGE_DETECTION[path.name]
            new_content = {key: value for key, value in json.loads(path.read_text()).items() if key not in left_out}
            old_content = {key: value for key, value in json.loads(published).items() if key not in left_out}
            if new_content != old_content:
                changed.append(path.name)
        elif path.read_bytes() != published:
            changed.append(path.name)
    return bool(changed), changed


def main():
    report = Report()
    check_files(report)
    if report.failures("hard"):
        alders = split_events = committees = meta = None
    else:
        alders = json.loads((DOCS_DATA_DIR / "alders.json").read_text())
        split_events = json.loads((DOCS_DATA_DIR / "split_events.json").read_text())
        committees = json.loads((DOCS_DATA_DIR / "committees.json").read_text())
        meta = json.loads((DOCS_DATA_DIR / "meta.json").read_text())

    manifest = json.loads(raw_snapshot.MANIFEST_PATH.read_text()) if raw_snapshot.MANIFEST_PATH.exists() else None
    new_table_counts = {name: len(pd.read_csv(TABLES_DIR / f"{name}.csv", low_memory=False)) for name in ROW_COUNT_TABLES}
    new_file_counts = {folder: sum(1 for _ in (REPO_DIR / folder).glob("*.json")) for folder in FILE_COUNT_FOLDERS}
    removed_rows, removed_event_ids = check_removed_vote_events(report, manifest)
    check_counts(report, manifest, new_table_counts, new_file_counts, removed_rows)
    check_sizes(report)
    if alders is not None:
        check_alders(report, alders)
        check_split_events(report, split_events, published_json("split_events.json"), removed_event_ids)
        check_alder_changes(report, alders, published_json("alders.json"))
        check_committee_changes(report, committees, published_json("committees.json"))
        check_staleness(report, meta)
    check_placeholders(report)
    check_new_term(report)
    check_recent_meetings(report, pd.read_csv(TABLES_DIR / "meetings.csv"))
    runs = json.loads(fetch_elms.UPDATE_RUN_LOG.read_text()) if fetch_elms.UPDATE_RUN_LOG.exists() else []
    last_run = runs[-1] if runs else None
    check_download_failures(report, last_run)

    changed, changed_files = docs_data_changed()
    report.add("info", "docs/data changed vs git HEAD (decides the commit)", True,
               [f"changed: {changed_files}" if changed else "nothing changed",
                f"ignored fields: {IGNORE_FOR_CHANGE_DETECTION}"])

    previous_vote_events = manifest["table_row_counts"].get("vote_events") if manifest else None
    result = {
        "hard_failures": len(report.failures("hard")),
        "soft_warnings": len(report.failures("soft")),
        "docs_data_changed": changed,
        "changed_files": changed_files,
        "new_vote_events": (new_table_counts["vote_events"] - previous_vote_events) if previous_vote_events is not None else None,
        "matters_refetched": len(last_run["refetched_matter_ids"]) if last_run else None,
        "new_matters": len(last_run["new_matter_ids"]) if last_run else None,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    CHECK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (CHECK_OUTPUT_DIR / "check_report.md").write_text(
        report.markdown() + "\n```\n" + json.dumps(result, indent=1) + "\n```\n")
    soft = report.failures("soft")
    (CHECK_OUTPUT_DIR / "soft_warnings.md").write_text(
        report.markdown(soft, title=f"Data update warnings, {result['checked_at'][:10]}") if soft else "")
    (CHECK_OUTPUT_DIR / "result.json").write_text(json.dumps(result, indent=1))
    print(report.markdown())
    print(json.dumps(result, indent=1))
    if result["hard_failures"]:
        sys.exit(f"{result['hard_failures']} hard checks failed: not publishing")


if __name__ == "__main__":
    main()
