"""Download raw JSON from the Chicago City Clerk eLMS public API.

Exploratory fetch: caches API responses verbatim under data/raw/elms/ so they
can be inspected before any processing is designed. Nothing here transforms
or filters records beyond the query parameters listed in the constants below.

API documentation: the API root serves a Swagger UI; the spec is
https://api.chicityclerkelms.chicago.gov/swagger.json (saved 2026-09-30 as
data/raw/elms/swagger.json, version "BETA"). Notes, from the spec and from probing:
  - List endpoints (/person, /body, /meeting, /matter) page with `top` and
    `skip`, return {"meta": {...count...}, "data": [...]}.
    Spec: "The maximum value for the 'top' parameter is 500" (confirmed:
    750 and 1000 are rejected). There is no bulk / return-all option.
  - `filter=` takes OData-style expressions (e.g. body eq 'City Council'),
    including `and`/`or`, parentheses and `actions/any(a: ...)`.
    `$filter` is silently ignored. Combining `search` and `filter` errors.
  - List responses leave nested fields null (meeting.agenda,
    meeting.attendance, matter.actions, sponsors, ...). Those only appear on
    the detail endpoints /meeting/{id} and /matter/{id}.
  - /matter's default order is introductionDate descending, which is not
    unique, and page order is NOT stable: paging the same query returned 3
    matters twice (so it can presumably skip some too). So the matter list
    is fetched without paging — see "date windows" below.

Usage:
  python scripts/fetch_elms.py lists             # person, body, meeting lists
  python scripts/fetch_elms.py matter_list       # matters selected by MATTER_LIST_FILTER
  python scripts/fetch_elms.py meetings          # detail for council meetings in term
  python scripts/fetch_elms.py refresh_meetings  # re-fetch recent meeting details
  python scripts/fetch_elms.py matters           # detail for every matter in the list or on an agenda
  python scripts/fetch_elms.py matters_by_id IDS_FILE SUBFOLDER   # one-off: listed matterIds
  python scripts/fetch_elms.py meeting_matter_votes PAIRS_FILE    # one-off: meeting-side votes
Each step (except refresh_meetings and matter_list) skips files already on
disk, so it can be re-run to resume.
"""

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — every choice about what to fetch lives here.
# ---------------------------------------------------------------------------

API_BASE_URL = "https://api.chicityclerkelms.chicago.gov"

# Where raw responses are written (gitignored via data/).
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "elms"

# Page size for list endpoints: the documented maximum (swagger.json).
LIST_PAGE_SIZE = 500

# Pause between requests (per worker) so we don't hammer a city server.
SECONDS_BETWEEN_REQUESTS = 0.25

# Matter details come one item per request (no bulk endpoint found), so the
# 15k-item backfill runs this many requests at once. 1 = strictly sequential.
PARALLEL_REQUESTS = 4

# If the server answers with one of these HTTP statuses, stop the whole run
# instead of continuing: they mean "slow down" (429) or "blocked" (403).
STOP_ON_HTTP_STATUS = {403, 429}

# The API reports a rate-limit allowance in the X-RateLimit-Remaining response
# header. No rate limit is documented anywhere I could find; measured
# 2026-09-29 while idle, the allowance refilled at ~6.5-7 requests/second and
# leveled off near 500. 4 parallel workers drained it (162 -> 116 in ~27 s).
# So: whenever the last-seen allowance is below this floor, every worker
# pauses before its next request, letting the allowance refill.
RATE_LIMIT_FLOOR = 150
RATE_LIMIT_PAUSE_SECONDS = 10

REQUEST_TIMEOUT_SECONDS = 60

# Only full-council meetings get detail-fetched. Committee meetings are
# listed (in meeting_list.json) but not expanded yet.
COUNCIL_BODY_NAME = "City Council"

# Start of the 2023–2027 term: inauguration of the current council.
# Meetings on or after this date are treated as "current term".
# OPEN QUESTION: confirm date; 2023-05-15 is the inauguration as I understand it.
TERM_START_DATE = "2023-05-15"

# Which matters to download. Agendas alone miss items (found 2026-09-30:
# 1,889 matterIds DataMade has votes for were not on any agenda we saved —
# 21 council meetings have an empty agenda in the API, and items reported
# back from committee can be voted at a meeting without being on its agenda).
# So the item list comes from the /matter list endpoint.
#
# Part 1 — active in the term. Copied from DataMade's scraper
# (opencivicdata/scrapers-us-municipal, chicago/bills.py `_matters`, same on
# master 4a94bc4, 2025-11-21), with their "7/180 days ago" replaced by
# TERM_START_DATE: any action, introduction or record creation after the date.
# "gt" is strictly after 00:00 UTC on TERM_START_DATE (= 7 pm Chicago the
# evening before), so nothing on the start date itself is lost.
# On 2026-09-30 this alone matched 34,609 matters (8,864 created before the
# term, back to 2011, that have an action after it).
MATTER_ACTIVE_IN_TERM_FILTER = (
    f"actions/any(a: a/actionDate gt {TERM_START_DATE}T00:00:00Z)"
    f" or introductionDate gt {TERM_START_DATE}T00:00:00Z"
    f" or recordCreateDate gt {TERM_START_DATE}T00:00:00Z"
)
# Part 2 — has at least one action with votes (any body: council or
# committee). User's choice 2026-09-30: fetch voted matters now, the rest
# later if needed. Matched 17,072 matters together with part 1.
# Matters without votes (introduced/referred only) are NOT downloaded; a
# matter that gets its first vote later is picked up by the next run.
MATTER_HAS_VOTES_FILTER = "actions/any(a: a/votes/any())"
MATTER_LIST_FILTER = f"({MATTER_ACTIVE_IN_TERM_FILTER}) and {MATTER_HAS_VOTES_FILTER}"

# Date windows. Instead of paging (unstable order, see top), the matter list
# is requested as back-to-back, non-overlapping windows of recordCreateDate,
# each small enough (<= LIST_PAGE_SIZE rows) to come back in ONE response,
# so order never matters. Checks: every window returns exactly its reported
# count, and the window counts add up to the whole query's count.
# recordCreateDate: never null in the 34,609 matters seen, whole seconds in
# UTC, at most 22 matters share one exact timestamp.
# ASSUMPTION: a matter's recordCreateDate never changes (the count checks
# would catch a matter moving between windows mid-run).
WINDOW_FIELD = "recordCreateDate"
# The whole range the windows cover. Anything outside it would show up as a
# mismatch against the whole-query count.
WINDOW_RANGE_START = "1900-01-01T00:00:00Z"
WINDOW_RANGE_END = "2100-01-01T00:00:00Z"
# Window boundaries are planned from a previously saved list, packing
# consecutive records into windows of about this many rows (headroom below
# 500 for matters added since). A window that still reports more than
# LIST_PAGE_SIZE is split in half by time and re-requested, repeatedly, until
# every piece fits — so a bad plan costs extra requests, never missing data.
WINDOW_TARGET_ROWS = 450
# Planning sources, first one that exists is used. matter_list.json is this
# step's own output (best estimate). matter_list_all_active_in_term.json is
# the 2026-09-30 list of ALL 34,609 active matters (part 1 only, fetched by
# unstable paging — fine for planning, not used as data); it over-estimates
# the voted matters per window, so the first run uses ~80 windows instead of ~40.
# If none exists, the plan is one window over the whole range (pure splitting).
WINDOW_PLANNING_FILES = ["matter_list.json", "matter_list_all_active_in_term.json"]

# Matters that the API returns HTTP 404 for — by matterId, and not findable
# by record number either (checked 2026-09-30; a control query with a known
# number worked). They exist only in DataMade, which scraped them before they
# were removed from eLMS. Skipped so every run doesn't retry them.
# matterId -> (DataMade record number, DataMade vote date)
KNOWN_DELETED_MATTER_IDS = {
    "959E2995-F614-EE11-8F6D-001DD806F9D9": ("SO2023-0002149", "2023-07-19"),
    "B7701A47-A646-EE11-BE6D-001DD80974AF": ("CL2023-0003796", "2023-07-19"),
    "EA867197-8D37-EE11-BDF4-001DD8301D71": ("R2023-0003259", "2023-09-14"),
    "3696C008-AC50-EE11-BE6E-001DD80974AF": ("R2023-0004053", "2023-09-14"),
    "F2827F46-AF50-EE11-BE6E-001DD8097F7D": ("R2023-0004055", "2023-09-14"),
    "B92A5F77-5DB5-EE11-A568-001DD805215C": ("R2024-0006958", "2024-01-24"),
    "D90D0917-5742-EF11-8409-001DD8306DF0": ("R2024-0010885", "2024-07-17"),
    "53CB3D5E-B484-EF11-AC21-001DD804AA64": ("R2024-0013014", "2024-10-09"),
    "C7A81305-7B90-EF11-AC21-001DD8306DF0": ("SO2024-0013375", "2024-10-22"),
}

# refresh_meetings re-fetches detail for council meetings dated within this
# many days before today (and any later ones), replacing the saved files.
# Why: the API can post agendas and attendance late — e.g. the 2026-09-23
# meeting still had an empty agenda on 2026-09-30 although it has votes.
MEETING_REFRESH_DAYS = 30

# ---------------------------------------------------------------------------


# Most recent X-RateLimit-Remaining value seen (None until the first response).
latest_rate_limit_remaining = None


def fetch_json(path, query_params=None):
    """GET one API path and return parsed JSON. Waits first if the rate-limit allowance is low."""
    global latest_rate_limit_remaining
    while latest_rate_limit_remaining is not None and latest_rate_limit_remaining < RATE_LIMIT_FLOOR:
        print(f"  rate-limit allowance {latest_rate_limit_remaining} < {RATE_LIMIT_FLOOR}; "
              f"pausing {RATE_LIMIT_PAUSE_SECONDS}s")
        time.sleep(RATE_LIMIT_PAUSE_SECONDS)
        latest_rate_limit_remaining = None  # next response reports the refilled value
    url = f"{API_BASE_URL}/{path}"
    if query_params:
        url += "?" + urllib.parse.urlencode(query_params)
    with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
        remaining_header = response.headers.get("X-RateLimit-Remaining")
    if remaining_header is not None:
        latest_rate_limit_remaining = int(remaining_header)
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    return payload


def write_json(output_path, payload):
    # Write to a temporary name, then rename: an interrupted run never leaves
    # a half-written file under the real name (which would be skipped on resume).
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".partial")
    temporary_path.write_text(json.dumps(payload, indent=1))
    temporary_path.replace(output_path)


def fetch_all_pages(endpoint, extra_params=None):
    """Page through a list endpoint and return every record."""
    all_records = []
    skip = 0
    while True:
        params = {"top": LIST_PAGE_SIZE, "skip": skip, **(extra_params or {})}
        page = fetch_json(endpoint, params)
        all_records.extend(page["data"])
        total_count = page["meta"]["count"]
        print(f"  {endpoint}: {len(all_records)}/{total_count}")
        skip += LIST_PAGE_SIZE
        if skip >= total_count:
            break
    return all_records


def fetch_lists():
    """Person, body and meeting lists — small, fetched whole."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for endpoint in ["person", "body", "meeting"]:
        records = fetch_all_pages(endpoint)
        write_json(
            OUTPUT_DIR / f"{endpoint}_list.json",
            {"retrieved_at": retrieved_at, "source": f"{API_BASE_URL}/{endpoint}", "data": records},
        )


def to_filter_time(timestamp_text):
    """'2026-09-01T14:14:35+00:00' -> '2026-09-01T14:14:35Z' (the form the filter accepts)."""
    parsed = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00")).astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def midpoint_time(start_text, end_text):
    """The time halfway between two filter times, rounded down to the second."""
    start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
    return to_filter_time((start + (end - start) / 2).isoformat())


def plan_windows():
    """Window boundaries from the first planning file that exists (see WINDOW_PLANNING_FILES)."""
    for file_name in WINDOW_PLANNING_FILES:
        planning_path = OUTPUT_DIR / file_name
        if planning_path.exists():
            planning_records = json.loads(planning_path.read_text())["data"]
            break
    else:
        return [(WINDOW_RANGE_START, WINDOW_RANGE_END)], "none (one window over the whole range)"

    # Walk the planning records in time order; start a new window once the
    # current one holds WINDOW_TARGET_ROWS — but never between two records
    # with the same timestamp (they must land in the same window).
    # All times have the same text format, so sorting the text sorts by time.
    record_times = sorted(to_filter_time(record[WINDOW_FIELD]) for record in planning_records)
    boundaries = []
    rows_in_current_window = 0
    for index, record_time in enumerate(record_times):
        if rows_in_current_window >= WINDOW_TARGET_ROWS and record_time != record_times[index - 1]:
            boundaries.append(record_time)   # this record starts the next window
            rows_in_current_window = 0
        rows_in_current_window += 1
    edges = [WINDOW_RANGE_START] + boundaries + [WINDOW_RANGE_END]
    return list(zip(edges[:-1], edges[1:])), f"{file_name} ({len(planning_records)} records)"


def fetch_matter_list():
    """Every matter matching MATTER_LIST_FILTER, fetched as date windows (no paging)."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    windows_to_fetch, planning_source = plan_windows()
    print(f"  planned {len(windows_to_fetch)} windows from {planning_source}")

    all_records = []
    window_log = []          # one entry per window actually used, for the output file
    problems = []            # any failed check; the list is saved as FAILED if non-empty
    while windows_to_fetch:
        window_start, window_end = windows_to_fetch.pop(0)
        window_filter = (f"({MATTER_LIST_FILTER}) and {WINDOW_FIELD} ge {window_start}"
                         f" and {WINDOW_FIELD} lt {window_end}")
        page = fetch_json("matter", {"filter": window_filter, "top": LIST_PAGE_SIZE})
        reported_count = page["meta"]["count"]

        if reported_count > LIST_PAGE_SIZE:
            # Too big for one response: split in half by time and put both
            # halves at the front of the queue (keeps time order).
            window_middle = midpoint_time(window_start, window_end)
            if window_middle in (window_start, window_end):
                sys.exit(f"  cannot split window {window_start} - {window_end} further ({reported_count} rows)")
            print(f"  window {window_start} - {window_end}: {reported_count} rows > {LIST_PAGE_SIZE}, splitting")
            windows_to_fetch[0:0] = [(window_start, window_middle), (window_middle, window_end)]
            continue

        rows = page["data"]
        # Check 1: the single response holds every row the window reports.
        if len(rows) != reported_count:
            problems.append(f"window {window_start} - {window_end}: {len(rows)} rows returned, count says {reported_count}")
        # Check 2: every row really lies inside the window (the filter was applied).
        outside = [row["recordNumber"] for row in rows
                   if not (window_start <= to_filter_time(row[WINDOW_FIELD]) < window_end)]
        if outside:
            problems.append(f"window {window_start} - {window_end}: rows outside the window: {outside[:10]}")
        all_records.extend(rows)
        window_log.append({"start": window_start, "end": window_end,
                           "count": reported_count, "rows_returned": len(rows)})
        print(f"  window {window_start} - {window_end}: {len(rows)} rows (total {len(all_records)})")

    # Check 3: windows add up to the whole query, and no matter appears twice.
    whole_query_count = fetch_json("matter", {"filter": MATTER_LIST_FILTER, "top": 1})["meta"]["count"]
    unique_ids = {record["matterId"] for record in all_records}
    if len(all_records) != whole_query_count:
        problems.append(f"windows hold {len(all_records)} rows; whole query count is {whole_query_count}")
    if len(unique_ids) != len(all_records):
        problems.append(f"{len(all_records) - len(unique_ids)} matterIds appear in more than one window")

    output_name = "matter_list.json" if not problems else "matter_list.FAILED.json"
    write_json(
        OUTPUT_DIR / output_name,
        {"retrieved_at": retrieved_at, "source": f"{API_BASE_URL}/matter",
         "filter": MATTER_LIST_FILTER, "window_field": WINDOW_FIELD,
         "window_planning_source": planning_source, "windows": window_log,
         "whole_query_count": whole_query_count, "problems": problems, "data": all_records},
    )
    print(f"  {len(window_log)} windows, {len(all_records)} rows, {len(unique_ids)} unique matterIds, "
          f"whole query count {whole_query_count} -> saved {output_name}")
    if problems:
        print("  CHECKS FAILED:\n    " + "\n    ".join(problems))
        sys.exit(1)


def council_meetings_in_term():
    meeting_list = json.loads((OUTPUT_DIR / "meeting_list.json").read_text())["data"]
    return [
        meeting
        for meeting in meeting_list
        if meeting["body"] == COUNCIL_BODY_NAME and meeting["date"][:10] >= TERM_START_DATE
    ]


def fetch_meeting_details():
    """Detail (agenda + attendance) for each full-council meeting in term."""
    meetings = council_meetings_in_term()
    print(f"  {len(meetings)} council meetings on/after {TERM_START_DATE}")
    for meeting in meetings:
        output_path = OUTPUT_DIR / "meetings" / f"{meeting['meetingId']}.json"
        if output_path.exists():
            continue
        write_json(output_path, fetch_json(f"meeting/{meeting['meetingId']}"))
        print(f"  meeting {meeting['date'][:10]}")


def refresh_meeting_details():
    """Re-fetch (overwrite) detail for council meetings from MEETING_REFRESH_DAYS ago onward.

    Uses meeting_list.json, so run `lists` first to pick up newly scheduled meetings.
    """
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=MEETING_REFRESH_DAYS)).strftime("%Y-%m-%d")
    meetings = [meeting for meeting in council_meetings_in_term() if meeting["date"][:10] >= cutoff_date]
    print(f"  {len(meetings)} council meetings on/after {cutoff_date}")
    for meeting in meetings:
        output_path = OUTPUT_DIR / "meetings" / f"{meeting['meetingId']}.json"
        old_agenda_size = (len(json.loads(output_path.read_text()).get("agenda") or [])
                           if output_path.exists() else None)
        new_meeting = fetch_json(f"meeting/{meeting['meetingId']}")
        write_json(output_path, new_meeting)
        print(f"  meeting {meeting['date'][:10]}: agenda items {old_agenda_size} -> {len(new_meeting.get('agenda') or [])}")


def fetch_matter_details():
    """Detail (actions + per-member votes) for every matter in matter_list.json or on a saved agenda."""
    # Source 1: the matter list (see MATTER_LIST_FILTER).
    matter_list_path = OUTPUT_DIR / "matter_list.json"
    if not matter_list_path.exists():
        sys.exit("  matter_list.json not found — run the matter_list step first")
    listed_ids = {record["matterId"] for record in json.loads(matter_list_path.read_text())["data"]}
    # Source 2: council agendas (kept so nothing downloaded before is dropped).
    agenda_ids = set()
    for meeting_path in (OUTPUT_DIR / "meetings").glob("*.json"):
        meeting = json.loads(meeting_path.read_text())
        for agenda_item in meeting.get("agenda") or []:
            if agenda_item.get("matterId"):
                agenda_ids.add(agenda_item["matterId"])
    matter_ids = (listed_ids | agenda_ids) - set(KNOWN_DELETED_MATTER_IDS)
    already_fetched = {path.stem for path in (OUTPUT_DIR / "matters").glob("*.json")}
    remaining_ids = sorted(matter_ids - already_fetched)
    print(f"  {len(listed_ids)} in matter list; {len(agenda_ids)} on agendas; "
          f"{len(listed_ids & agenda_ids)} in both; {len(KNOWN_DELETED_MATTER_IDS)} known-deleted skipped")
    print(f"  {len(matter_ids)} matters in total; {len(remaining_ids)} still to fetch; "
          f"{PARALLEL_REQUESTS} requests at a time")

    fetch_in_parallel([(f"matter/{matter_id}", OUTPUT_DIR / "matters" / f"{matter_id}.json")
                       for matter_id in remaining_ids])


def fetch_in_parallel(jobs):
    """Fetch each (api_path, output_path) job, PARALLEL_REQUESTS at a time, saving the JSON verbatim."""
    stop_signal = threading.Event()   # set when the server says slow down / blocked
    progress_lock = threading.Lock()
    finished_count = [0]
    failures = []                     # (api_path, reason), printed at the end

    def fetch_one(job):
        api_path, output_path = job
        if stop_signal.is_set():
            return
        try:
            write_json(output_path, fetch_json(api_path))
        except urllib.error.HTTPError as error:
            failures.append((api_path, f"HTTP {error.code}"))
            if error.code in STOP_ON_HTTP_STATUS:
                stop_signal.set()
                print(f"  STOPPING: server returned HTTP {error.code} for {api_path}")
            else:
                print(f"  FAILED {api_path}: HTTP {error.code}")
        except Exception as error:  # log and keep going; a re-run retries it
            failures.append((api_path, str(error)))
            print(f"  FAILED {api_path}: {error}")
        with progress_lock:
            finished_count[0] += 1
            if finished_count[0] % 500 == 0:
                print(f"  {finished_count[0]}/{len(jobs)}")

    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
        list(pool.map(fetch_one, jobs))
    print(f"  done: {len(jobs) - len(failures)} saved, {len(failures)} failed")
    if stop_signal.is_set():
        print("  Stopped early because of the server response above. Re-run later to resume.")
    return failures


def fetch_matters_by_id(ids_file, subfolder):
    """Detail for the matterIds listed in ids_file (JSON: {"matter_ids": [...]}), into data/raw/elms/<subfolder>/.

    For one-off checks (e.g. matters a notebook wants to look at) that are not
    part of the MATTER_LIST_FILTER selection. Always re-fetches (overwrites),
    so the saved copy is the API's state on the day the step ran.
    Also accepts {"record_numbers": [...]}: looked up with /matter/recordNumber/{n}
    and saved as <subfolder>/recordNumber_<n>.json (404 = no record with that number).
    """
    request = json.loads(Path(ids_file).read_text())
    matter_ids = request.get("matter_ids", [])
    record_numbers = request.get("record_numbers", [])
    print(f"  {len(matter_ids)} matterIds and {len(record_numbers)} record numbers from {ids_file} -> {OUTPUT_DIR / subfolder}")
    failures = fetch_in_parallel([(f"matter/{matter_id}", OUTPUT_DIR / subfolder / f"{matter_id}.json")
                                  for matter_id in matter_ids]
                                 + [(f"matter/recordNumber/{urllib.parse.quote(number)}",
                                     OUTPUT_DIR / subfolder / f"recordNumber_{number}.json")
                                    for number in record_numbers])
    # Failures (e.g. HTTP 404 = no such record) are evidence too, so they are saved, not just printed.
    write_json(OUTPUT_DIR / subfolder / "_fetch_log.json",
               {"ran_at": datetime.now(timezone.utc).isoformat(), "request_file": str(ids_file),
                "failures": [{"api_path": api_path, "reason": reason} for api_path, reason in failures]})


def fetch_meeting_matter_votes(pairs_file):
    """Meeting-side votes, /meeting/{meetingId}/matter/{matterId}/votes, for each pair in pairs_file.

    pairs_file: JSON {"pairs": [{"meeting_id": ..., "matter_id": ...}, ...]}.
    Saved to data/raw/elms/meeting_matter_votes/<meetingId>_<matterId>.json.
    Skips pairs already on disk. This endpoint is listed in swagger.json; it
    returned an empty list for matters not voted at that meeting (2 controls,
    2026-09-30), and a roll call for matters that were.
    """
    pairs = json.loads(Path(pairs_file).read_text())["pairs"]
    output_dir = OUTPUT_DIR / "meeting_matter_votes"
    jobs = [(f"meeting/{pair['meeting_id']}/matter/{pair['matter_id']}/votes",
             output_dir / f"{pair['meeting_id']}_{pair['matter_id']}.json") for pair in pairs]
    remaining_jobs = [job for job in jobs if not job[1].exists()]
    print(f"  {len(pairs)} pairs from {pairs_file}; {len(remaining_jobs)} still to fetch")
    fetch_in_parallel(remaining_jobs)


if __name__ == "__main__":
    steps = {"lists": fetch_lists, "matter_list": fetch_matter_list, "meetings": fetch_meeting_details,
             "refresh_meetings": refresh_meeting_details, "matters": fetch_matter_details,
             "matters_by_id": fetch_matters_by_id, "meeting_matter_votes": fetch_meeting_matter_votes}
    # Extra command-line words are passed to the step (e.g. a file name).
    steps[sys.argv[1]](*sys.argv[2:])
