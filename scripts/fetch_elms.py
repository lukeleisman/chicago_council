"""Download raw JSON from the Chicago City Clerk eLMS public API.

Exploratory fetch: caches API responses verbatim under data/raw/elms/ so they
can be inspected before any processing is designed. Nothing here transforms
or filters records beyond the query parameters listed in the constants below.

API notes (worked out by probing, 2026-09-29 — no official docs found):
  - Base: https://api.chicityclerkelms.chicago.gov
  - List endpoints (/person, /body, /meeting, /matter) page with `top` and
    `skip`, return {"meta": {...count...}, "data": [...]}.
  - `filter=` takes OData-style expressions (e.g. body eq 'City Council').
    `$filter` is silently ignored. Combining `search` and `filter` errors.
  - List responses leave nested fields null (meeting.agenda,
    meeting.attendance, matter.actions). Those only appear on the detail
    endpoints /meeting/{id} and /matter/{id}.

Usage:
  python scripts/fetch_elms.py lists      # person, body, meeting lists
  python scripts/fetch_elms.py meetings   # detail for council meetings in term
  python scripts/fetch_elms.py matters    # detail for every matter on those agendas
Each step skips files already on disk, so it can be re-run to resume.
"""

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — every choice about what to fetch lives here.
# ---------------------------------------------------------------------------

API_BASE_URL = "https://api.chicityclerkelms.chicago.gov"

# Where raw responses are written (gitignored via data/).
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "elms"

# Page size for list endpoints. 500 worked for /person and /body; the API's
# own default is 100. OPEN QUESTION: maximum allowed page size is unknown.
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


def fetch_matter_details():
    """Detail (actions + per-member votes) for every matter on a council agenda in term."""
    matter_ids = set()
    for meeting_path in (OUTPUT_DIR / "meetings").glob("*.json"):
        meeting = json.loads(meeting_path.read_text())
        for agenda_item in meeting.get("agenda") or []:
            if agenda_item.get("matterId"):
                matter_ids.add(agenda_item["matterId"])
    already_fetched = {path.stem for path in (OUTPUT_DIR / "matters").glob("*.json")}
    remaining_ids = sorted(matter_ids - already_fetched)
    print(f"  {len(matter_ids)} matters on agendas; {len(remaining_ids)} still to fetch; "
          f"{PARALLEL_REQUESTS} requests at a time")

    stop_signal = threading.Event()   # set when the server says slow down / blocked
    progress_lock = threading.Lock()
    finished_count = [0]

    def fetch_one(matter_id):
        if stop_signal.is_set():
            return
        try:
            write_json(OUTPUT_DIR / "matters" / f"{matter_id}.json", fetch_json(f"matter/{matter_id}"))
        except urllib.error.HTTPError as error:
            if error.code in STOP_ON_HTTP_STATUS:
                stop_signal.set()
                print(f"  STOPPING: server returned HTTP {error.code} for {matter_id}")
            else:
                print(f"  FAILED {matter_id}: HTTP {error.code}")
        except Exception as error:  # log and keep going; a re-run retries it
            print(f"  FAILED {matter_id}: {error}")
        with progress_lock:
            finished_count[0] += 1
            if finished_count[0] % 500 == 0:
                print(f"  {finished_count[0]}/{len(remaining_ids)}")

    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
        list(pool.map(fetch_one, remaining_ids))
    if stop_signal.is_set():
        print("  Stopped early because of the server response above. Re-run later to resume.")


if __name__ == "__main__":
    steps = {"lists": fetch_lists, "meetings": fetch_meeting_details, "matters": fetch_matter_details}
    steps[sys.argv[1]]()
