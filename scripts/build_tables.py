"""Build tidy tables from the raw downloads (no API calls; re-runnable).

Reads data/raw/ only (written by scripts/fetch_elms.py and the DataMade SQLite
database) and writes CSV tables to data/tables/ (gitignored via data/).

Every rule here was decided in notebooks/tables_review.ipynb section 1 (the
raw data behind each decision is shown there). Each rule is a named constant
below, with the decision number. Nothing is dropped: every person, meeting
file, vote action and roster row in the raw files gets a row. Corrections keep
the raw value beside the corrected one, with a *_source column saying which
rule (if any) changed it. Filtering is left to the views.

Tables (reviewed in notebooks/tables_review.ipynb section 2):
  people        one row per person in the eLMS person list
  meetings      one row per eLMS meeting file (all City Council)
  attendance    one row per meeting x attendance roll call x member
  vote_events   one row per action (any body) in the eLMS item files that has a per-member roster
  member_votes  one row per vote_event x roster row
  attachments   one row per eLMS item file x entry in its `attachments` list (added 2026-10-05;
                items with no attachments, 153 today, have no rows)

How they link:
  member_votes.event_id -> vote_events.event_id
  member_votes.person_id, attendance.person_id -> people.person_id
  vote_events.meeting_id, attendance.meeting_id -> meetings.meeting_id
  attachments.matter_id -> vote_events.matter_id (many events can share one matter)

Not in eLMS, so not in any table: the 9 matters in KNOWN_DELETED_MATTER_IDS
(scripts/fetch_elms.py), which exist only in DataMade.

Usage:
  python scripts/build_tables.py all        # every table, in dependency order
  python scripts/build_tables.py people     # one table (also: meetings, attendance, vote_events, member_votes, attachments)
"""

import hashlib
import json
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration — every choice made in this script lives here.
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent
ELMS_DIR = REPO_DIR / "data" / "raw" / "elms"
DATAMADE_DB_PATH = REPO_DIR / "data" / "raw" / "chicago_council.db"
OUTPUT_DIR = REPO_DIR / "data" / "tables"

# Table format (decided 2026-10-04): CSV, so tables open anywhere.

# "Today" for tenure: years on council are counted up to this date at most.
# Same value as AS_OF_DATE in notebooks/tables_review.ipynb.
AS_OF_DATE = "2026-10-04"

# DataMade's organization name for the full council (from its `organization` table).
DATAMADE_COUNCIL_ORGANIZATION = "Chicago City Council"

# Display names (decided 2026-10-04): strip leading/trailing whitespace only.
# Nothing else changes (middle initials, suffixes and accents stay as eLMS has them).

# Matching an eLMS person to a DataMade person (decision 1.2, same rule as
# notebooks/tables_review.ipynb §1.2): the whitespace-stripped eLMS displayName
# equals DataMade's person_name exactly. A person with no exact match gets no
# DataMade dates (start_source = "no DataMade match").

# Tenure (decision 1.2, extended 2026-10-04 to every person, not only current alders):
#   council_start_date = earliest DataMade "Chicago City Council" membership start for that
#                        person (gaps between memberships are ignored), unless overridden below.
#   tenure_end_date    = the earlier of (latest DataMade membership end, AS_OF_DATE). Current
#                        alders' DataMade memberships end at the end of the term (2027-05-16),
#                        which is in the future, so they are counted to AS_OF_DATE.
#   years_on_council   = (tenure_end_date - council_start_date) in days / DAYS_PER_YEAR.
# Gaps are ignored because the Reilly and Sposato gaps (2019-05 to 2022) are DataMade artifacts
# (user, Wikipedia, and DataMade's own votes for both in every year; tables_review §1.2 follow-up).
DAYS_PER_YEAR = 365.25

# Hand corrections to council_start_date: {eLMS personId: (start date "YYYY-MM-DD", citation)}.
# Empty: no correction has been needed yet.
TENURE_START_OVERRIDES = {}

# Placeholder personIds (decision 1.7, same table as notebooks/tables_review.ipynb).
# eLMS uses this ID for the 13 alders first seated in May 2023 at the term's first meetings
# (2023-05-24, -25, -31); their names are right. Replaced here only to count each person's vote
# and attendance rows correctly. Includes "Col?n, Rey" (2011; added 2026-10-04).
PLACEHOLDER_PERSON_ID = "00000000-0000-0000-0000-000000000000"
PLACEHOLDER_PERSON_ID_BY_NAME = {
    "Chico, Peter":            "4C168A10-6BF3-ED11-A7C6-001DD804FC2B",  # ward 10
    "Clay, Angela":            "5F4C907D-6CF3-ED11-A7C6-001DD804FC2B",  # ward 46
    "Conway, William":         "4C380420-6CF3-ED11-A7C6-001DD804FC2B",  # ward 34
    "Cruz, Ruth":              "C7422EFD-6BF3-ED11-A7C6-001DD804FC2B",  # ward 30
    "Fuentes, Jessica":        "85DA45DD-6BF3-ED11-A7C6-001DD804FC2B",  # ward 26; listed as "Fuentes, Jessica L."
    "Gutierrez, Jeylu B.":     "2E2DFB80-6BF3-ED11-A7C6-001DD804FC2B",  # ward 14
    "Hall, William E.":        "7D95D6BB-6AF3-ED11-A7C6-001DD804FC2B",  # ward 06
    "Lawson, Bennett R.":      "1628D550-6CF3-ED11-A7C6-001DD804FC2B",  # ward 44
    "Manaa-Hoppenworth, Leni": "561B99CA-6CF3-ED11-A7C6-001DD804FC2B",  # ward 48
    "Mosley, Ronnie L.":       "8B0682AE-6BF3-ED11-A7C6-001DD804FC2B",  # ward 21
    "Ramirez, Julia M.":       "9E248041-6BF3-ED11-A7C6-001DD804FC2B",  # ward 12
    "Robinson, Lamont J.":     "80D52B16-6AF3-ED11-A7C6-001DD804FC2B",  # ward 04
    "Yancy, Desmon C.":        "E0AC4B85-6AF3-ED11-A7C6-001DD804FC2B",  # ward 05
    # Added 2026-10-04 (user): 4 votes in 2011, before this term. "?" is a broken "ó"; the
    # person list has him as "Colon, Rey" (ward 35, inactive) and no other Colon/Colón.
    "Col?n, Rey":              "184EE8BE-ABFD-ED11-8847-001DD8068005",  # ward 35
}

# Columns of the `people` table, in order, with where each comes from.
PEOPLE_COLUMNS = {
    "person_id":                "eLMS personId",
    "display_name":             "eLMS displayName, leading/trailing whitespace stripped",
    "display_name_raw":         "eLMS displayName as recorded",
    "elms_ward":                "eLMS `ward` as recorded (text: '06', 'Clerk', 'Mayor', ...); for "
                                "inactive people, the ward eLMS last lists, not a full history",
    "is_active":                "eLMS isActive",
    "photo_url":                "eLMS photo",
    "site":                     "eLMS site",
    "elms_last_publication":    "eLMS lastPublicationDate (raw UTC timestamp)",
    "datamade_person_name":     "DataMade person_name matched by exact stripped name (blank = no match)",
    "datamade_membership_count": "number of DataMade council membership records for that name",
    "council_start_date":       "see Tenure above",
    "start_source":             "'DataMade earliest' / 'override' / 'no DataMade match'",
    "start_citation":           "citation for an override (blank otherwise)",
    "datamade_last_end_date":   "latest DataMade council membership end",
    "tenure_end_date":          "earlier of datamade_last_end_date and AS_OF_DATE",
    "years_on_council":         "see Tenure above (unrounded)",
    "member_vote_rows":         "number of per-member vote rows in eLMS item files with this person_id "
                                "(after the placeholder replacement); all bodies, all dates",
    "attendance_rows":          "number of attendance roll-call rows in eLMS meeting files with this person_id "
                                "(after the placeholder replacement)",
}

# eLMS dates are UTC timestamps, converted to a Chicago calendar date (same rule as
# notebooks/source_comparison.ipynb §3 and notebooks/tables_review.ipynb).
LOCAL_TIMEZONE = "America/Chicago"

# Raw eLMS timestamps that mean "no date entered" (decision 1.8; same constant as
# notebooks/source_comparison.ipynb, identified by the user 2026-09-30 as entry errors).
# A vote action with this date gets the date of the council meeting its meetingId points to
# (action_date_source = "meeting date"); with no such meeting, the date is left blank
# (action_date_source = "missing (1900 placeholder)").
ELMS_PLACEHOLDER_TIMESTAMPS = ["1900-01-01T00:00:00+00:00"]

# Body name of a full-council meeting in eLMS meeting files.
COUNCIL_BODY = "City Council"

# Blank meetingIds (decided 2026-10-04): fill from the date only when exactly one City Council
# meeting file falls on the action's Chicago date. meeting_id_source = "date match".
MATCH_MEETING_BY_DATE = True

# Blank actionByName (decision 1.6): relabel "City Council" when the action has
# COUNCIL_VOTER_COUNT voters AND its raw meetingId is a City Council meeting file.
# action_by_source = "relabeled (blank, 50 voters, council meeting)".
# OPEN QUESTION (for the user): the evidence for 1.6 (tables_review §1.6) used the RAW meetingId,
# so a blank-meetingId event that only gets its meeting from the date match is NOT relabeled here.
# The review notebook lists how many such events there are.
COUNCIL_VOTER_COUNT = 50
RELABEL_BLANK_ACTION_BY_AS = "City Council"

# roster_kind (decided 2026-10-04, tables_review §1.4d): one label per vote event. Rules are
# checked top to bottom; the first match wins. Only "roll call" events count toward absence metrics.
# The tests are written out in assign_roster_kind() below.
ROSTER_KIND_RULES = [
    ("voice vote",           "actionText contains 'voice vote' (case-insensitive)"),
    ("vote not taken",       "actionText contains 'vote not taken' (case-insensitive)"),
    ("rising vote",          "roster has 'Rising Vote' and no Yea/Nay"),
    ("committee attendance", "actionByName (raw) starts with 'Committee' and roster has no Yea/Nay"),
    ("present roster",       "any other roster with no Yea/Nay"),
    ("roll call",            "everything else"),
]

# Every raw vote value seen in the item files (tables_review §1.3; decision 1.3: kept as recorded,
# no recode). The build stops if a new value appears, so it can be looked at first.
# Each becomes a count column in vote_events: "Not Voting" -> count_not_voting, etc.
VOTE_VALUES = ["Yea", "Nay", "Absent", "Not Voting", "Present", "Recused", "Rising Vote", "Vacant"]

# Duplicate roster rows that are in the raw eLMS file itself (kept, not de-duplicated).
# (record number, personId): why. The build stops if any other duplicate appears.
KNOWN_DUPLICATE_MEMBER_VOTES = {
    ("Or2026-0023123", "886B5C20-F788-EC11-8D20-001DD804FD38"):
        "Harris listed twice (both Not Voting) on the Rule 44 'vote not taken' action, 2026-02-11",
}
# Same for attendance: (meeting Chicago date, roll call name, personId): why.
KNOWN_DUPLICATE_ATTENDANCE = {
    ("2026-03-11", "Global Attendance", "886B5C20-F788-EC11-8D20-001DD804FD38"):
        "Harris listed twice (both Absent) in the 2026-03-11 meeting's attendance",
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_elms_people():
    return pd.DataFrame(json.loads((ELMS_DIR / "person_list.json").read_text())["data"])


def load_datamade_council_memberships():
    with sqlite3.connect(DATAMADE_DB_PATH) as connection:
        return pd.read_sql_query("""
            SELECT m.person_name, m.start_date, m.end_date
            FROM membership m
            JOIN organization o ON o.id = m.organization_id
            WHERE o.name = ?
        """, connection, params=[DATAMADE_COUNCIL_ORGANIZATION])


def real_person_id(person_id, voter_name):
    """Decision 1.7: swap a placeholder personId for the real one, by name; otherwise unchanged."""
    if person_id == PLACEHOLDER_PERSON_ID:
        return PLACEHOLDER_PERSON_ID_BY_NAME.get(voter_name, person_id)
    return person_id


def to_local_date(utc_timestamps):
    """UTC timestamp text -> Chicago calendar date text (YYYY-MM-DD)."""
    return (pd.to_datetime(utc_timestamps, utc=True).dt.tz_convert(LOCAL_TIMEZONE)
            .dt.strftime("%Y-%m-%d"))


def with_real_person_ids(frame):
    """Decision 1.7: keep the raw ID in person_id_raw; replace placeholder IDs found in the name table."""
    frame = frame.copy()
    frame["person_id_raw"] = frame.person_id
    frame["person_id"] = [real_person_id(person_id, voter_name)
                          for person_id, voter_name in zip(frame.person_id_raw, frame.voter_name)]
    is_placeholder = frame.person_id_raw == PLACEHOLDER_PERSON_ID
    frame["person_id_source"] = "as recorded"
    frame.loc[is_placeholder & (frame.person_id != PLACEHOLDER_PERSON_ID), "person_id_source"] = "name match"
    frame.loc[is_placeholder & (frame.person_id == PLACEHOLDER_PERSON_ID), "person_id_source"] = "placeholder, unmatched"
    return frame


@lru_cache(maxsize=None)
def load_raw_meetings():
    """Every meeting file -> (one row per meeting, one row per attendance roster row). Nothing changed."""
    meeting_rows, attendance_rows = [], []
    for meeting_file in sorted((ELMS_DIR / "meetings").glob("*.json")):
        meeting = json.loads(meeting_file.read_text())
        roll_calls = meeting.get("attendance") or []
        meeting_rows.append({
            "meeting_id": meeting["meetingId"],
            "meeting_datetime_utc": meeting["date"],
            "body": meeting["body"],
            "status": meeting["status"],
            "attendance_roll_call_count": len(roll_calls),
            "attendance_roll_call_names": "; ".join(str(roll_call.get("name")) for roll_call in roll_calls),
            "attendance_member_count": sum(len(roll_call.get("votes") or []) for roll_call in roll_calls),
            "agenda_item_count": len(meeting.get("agenda") or []),
        })
        for roll_call in roll_calls:
            for member in roll_call.get("votes") or []:
                attendance_rows.append({
                    "meeting_id": meeting["meetingId"], "roll_call_name": roll_call.get("name"),
                    "person_id": member["personId"], "voter_name": member["voterName"], "status": member["vote"],
                })
    return pd.DataFrame(meeting_rows), pd.DataFrame(attendance_rows)


@lru_cache(maxsize=None)
def load_raw_actions():
    """Every item file -> (one row per action with a roster, one row per roster row). Nothing changed."""
    event_rows, member_vote_rows = [], []
    for matter_file in sorted((ELMS_DIR / "matters").glob("*.json")):
        matter = json.loads(matter_file.read_text())
        for action in matter.get("actions") or []:
            votes = action.get("votes") or []
            if not votes:
                continue
            event_id = f"{matter['matterId']}_{action['historyId']}"
            event_rows.append({
                "event_id": event_id, "matter_id": matter["matterId"], "history_id": action["historyId"],
                "record_number": matter["recordNumber"], "title": matter["title"],
                "matter_type": matter["type"], "matter_category": matter["matterCategory"],
                "agreed_calendar": matter["agreedCalendar"], "routine": matter["routine"],
                "action_date_raw": action["actionDate"], "action_by_raw": action["actionByName"],
                "action_name": action["actionName"], "action_text": action["actionText"],
                "meeting_id_raw": action["meetingId"], "voter_count": len(votes),
            })
            for member in votes:
                member_vote_rows.append({"event_id": event_id, "person_id": member["personId"],
                                         "voter_name": member["voterName"], "vote": member["vote"]})
    return pd.DataFrame(event_rows), pd.DataFrame(member_vote_rows)


def build_attachments():
    """One row per entry in each item file's `attachments` list, in eLMS's order. Nothing changed.

    Columns:
      matter_id, record_number  the item (same values as vote_events)
      attachment_position       1-based position in eLMS's list (eLMS gives no other order or date)
      attachment_type           eLMS attachmentType as recorded ("Legislation", "Committee Letter", ...)
      file_name                 eLMS fileName as recorded
      url                       eLMS path as recorded (a public PDF link)
    """
    rows = []
    expected_row_count = 0
    for matter_file in sorted((ELMS_DIR / "matters").glob("*.json")):
        matter = json.loads(matter_file.read_text())
        attachments = matter.get("attachments") or []
        expected_row_count += len(attachments)
        for position, attachment in enumerate(attachments, start=1):
            rows.append({
                "matter_id": matter["matterId"], "record_number": matter["recordNumber"],
                "attachment_position": position, "attachment_type": attachment["attachmentType"],
                "file_name": attachment["fileName"], "url": attachment["path"],
            })
    attachments = pd.DataFrame(rows)
    # Checks: every raw entry has a row; one row per (item, position).
    assert len(attachments) == expected_row_count
    assert not attachments.duplicated(["matter_id", "attachment_position"]).any(), "(matter_id, position) must be unique"
    return attachments


def assign_roster_kind(row):
    """ROSTER_KIND_RULES, first match wins (mirrors tables_review §1.4d)."""
    text = (row.action_text or "").lower()
    has_yea_or_nay = (row.count_yea + row.count_nay) > 0
    if "voice vote" in text:
        return "voice vote"
    if "vote not taken" in text:
        return "vote not taken"
    if not has_yea_or_nay and row.count_rising_vote > 0:
        return "rising vote"
    if not has_yea_or_nay and (row.action_by_raw or "").startswith("Committee"):
        return "committee attendance"
    if not has_yea_or_nay:
        return "present roster"
    return "roll call"


def count_column(vote_value):
    return "count_" + vote_value.lower().replace(" ", "_")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def build_people():
    elms_people = load_elms_people()
    people = pd.DataFrame({
        "person_id": elms_people.personId,
        "display_name": elms_people.displayName.str.strip(),
        "display_name_raw": elms_people.displayName,
        "elms_ward": elms_people.ward,
        "is_active": elms_people.isActive,
        "photo_url": elms_people.photo,
        "site": elms_people.site,
        "elms_last_publication": elms_people.lastPublicationDate,
    })

    # DataMade dates per person name (all of that name's council memberships).
    memberships = load_datamade_council_memberships()
    datamade_per_name = (memberships.groupby("person_name")
                         .agg(datamade_membership_count=("start_date", "size"),
                              datamade_first_start=("start_date", "min"),
                              datamade_last_end_date=("end_date", "max"))
                         .reset_index())
    people = people.merge(datamade_per_name, left_on="display_name", right_on="person_name", how="left")
    people = people.rename(columns={"person_name": "datamade_person_name"})
    people["datamade_membership_count"] = people.datamade_membership_count.astype("Int64")  # blank when no match

    # Tenure start: DataMade earliest, then any hand override.
    people["council_start_date"] = people.datamade_first_start
    people["start_source"] = people.datamade_first_start.notna().map(
        {True: "DataMade earliest", False: "no DataMade match"})
    people["start_citation"] = None
    for person_id, (start_date, citation) in TENURE_START_OVERRIDES.items():
        is_person = people.person_id == person_id
        assert is_person.sum() == 1, f"override personId not found exactly once: {person_id}"
        people.loc[is_person, ["council_start_date", "start_source", "start_citation"]] = \
            [start_date, "override", citation]

    # Tenure end and years.
    people["tenure_end_date"] = people.datamade_last_end_date.where(
        people.datamade_last_end_date.isna() | (people.datamade_last_end_date < AS_OF_DATE), AS_OF_DATE)
    people.loc[people.council_start_date.isna(), "tenure_end_date"] = None
    tenure_days = (pd.to_datetime(people.tenure_end_date) - pd.to_datetime(people.council_start_date)).dt.days
    people["years_on_council"] = tenure_days / DAYS_PER_YEAR

    # Row counts from the vote and attendance files.
    member_vote_rows = build_member_votes().person_id.value_counts()
    attendance_rows = build_attendance().person_id.value_counts()
    people["member_vote_rows"] = people.person_id.map(member_vote_rows).fillna(0).astype(int)
    people["attendance_rows"] = people.person_id.map(attendance_rows).fillna(0).astype(int)

    people = people[list(PEOPLE_COLUMNS)].sort_values(["is_active", "elms_ward", "display_name"],
                                                      ascending=[False, True, True])

    # Checks: one row per eLMS person, unique IDs, no tenure end before start.
    assert len(people) == len(elms_people), "people must have one row per eLMS person"
    assert people.person_id.is_unique, "person_id must be unique"
    assert (people.years_on_council.dropna() >= 0).all(), "tenure end before start"
    return people


@lru_cache(maxsize=None)
def build_attendance():
    raw_meetings, raw_attendance = load_raw_meetings()
    attendance = with_real_person_ids(raw_attendance)
    meeting_dates = raw_meetings.set_index("meeting_id").meeting_datetime_utc
    attendance.insert(1, "meeting_date", to_local_date(attendance.meeting_id.map(meeting_dates)))
    attendance = attendance[["meeting_id", "meeting_date", "roll_call_name", "person_id", "person_id_raw",
                             "person_id_source", "voter_name", "status"]]
    # Checks: every row kept; the only (meeting, roll call, person) duplicates are the known raw ones.
    assert len(attendance) == len(raw_attendance)
    duplicates = attendance[attendance.duplicated(["meeting_id", "roll_call_name", "person_id"], keep=False)]
    found = set(zip(duplicates.meeting_date, duplicates.roll_call_name, duplicates.person_id))
    assert found == set(KNOWN_DUPLICATE_ATTENDANCE), f"unexpected duplicate attendance rows: {found}"
    return attendance


@lru_cache(maxsize=None)
def build_member_votes():
    _, raw_member_votes = load_raw_actions()
    unknown_values = set(raw_member_votes.vote) - set(VOTE_VALUES)
    assert not unknown_values, f"new raw vote values (add to VOTE_VALUES after review): {unknown_values}"
    member_votes = with_real_person_ids(raw_member_votes)
    member_votes = member_votes[["event_id", "person_id", "person_id_raw", "person_id_source", "voter_name", "vote"]]
    # Checks: every row kept; the only (event, person) duplicates are the known raw ones.
    assert len(member_votes) == len(raw_member_votes)
    duplicates = member_votes[member_votes.duplicated(["event_id", "person_id"], keep=False)
                              & (member_votes.person_id != PLACEHOLDER_PERSON_ID)]
    record_by_event = load_raw_actions()[0].set_index("event_id").record_number
    found = set(zip(duplicates.event_id.map(record_by_event), duplicates.person_id))
    assert found == set(KNOWN_DUPLICATE_MEMBER_VOTES), f"unexpected duplicate roster rows: {found}"
    return member_votes


@lru_cache(maxsize=None)
def build_vote_events():
    raw_events, _ = load_raw_actions()
    raw_meetings, _ = load_raw_meetings()
    events = raw_events.copy()
    meeting_date_by_id = raw_meetings.assign(meeting_date=to_local_date(raw_meetings.meeting_datetime_utc)) \
                                     .set_index("meeting_id").meeting_date
    council_meeting_ids = set(raw_meetings.loc[raw_meetings.body == COUNCIL_BODY, "meeting_id"])

    # Date (decision 1.8): Chicago date; placeholder 1900 dates -> linked meeting's date, else blank.
    is_placeholder_date = events.action_date_raw.isin(ELMS_PLACEHOLDER_TIMESTAMPS)
    events["action_date"] = to_local_date(events.action_date_raw.where(~is_placeholder_date))
    linked_meeting_date = events.meeting_id_raw.map(meeting_date_by_id)
    gets_meeting_date = is_placeholder_date & linked_meeting_date.notna()
    events.loc[gets_meeting_date, "action_date"] = linked_meeting_date[gets_meeting_date]
    events["action_date_source"] = "eLMS"
    events.loc[gets_meeting_date, "action_date_source"] = "meeting date"
    events.loc[is_placeholder_date & ~gets_meeting_date, "action_date_source"] = "missing (1900 placeholder)"

    # Meeting (MATCH_MEETING_BY_DATE): fill a blank meetingId when exactly one council meeting is on that date.
    events["meeting_id"] = events.meeting_id_raw.replace("", None)
    events["meeting_id_source"] = events.meeting_id.notna().map({True: "eLMS", False: "blank"})
    if MATCH_MEETING_BY_DATE:
        council_meetings_per_date = (raw_meetings[raw_meetings.body == COUNCIL_BODY]
                                     .assign(meeting_date=lambda frame: to_local_date(frame.meeting_datetime_utc))
                                     .groupby("meeting_date").meeting_id.agg(list))
        candidates = events.action_date.map(council_meetings_per_date)
        single_match = (events.meeting_id_source == "blank") & candidates.apply(
            lambda ids: isinstance(ids, list) and len(ids) == 1)
        events.loc[single_match, "meeting_id"] = candidates[single_match].str[0]
        events.loc[single_match, "meeting_id_source"] = "date match"
    events["meeting_has_file"] = events.meeting_id.isin(set(raw_meetings.meeting_id))

    # Counts per raw vote value, and the roster signature.
    member_votes = build_member_votes()
    counts = (member_votes.pivot_table(index="event_id", columns="vote", values="person_id",
                                       aggfunc="count", fill_value=0)
              .reindex(columns=VOTE_VALUES, fill_value=0))
    counts.columns = [count_column(vote_value) for vote_value in counts.columns]
    events = events.join(counts, on="event_id")
    # roster_signature: first 16 hex characters of the SHA-1 of the sorted "person_id=vote" pairs.
    # Two events with the same signature have exactly the same roster (who, and how each voted).
    signatures = (member_votes.assign(pair=member_votes.person_id + "=" + member_votes.vote)
                  .groupby("event_id").pair
                  .agg(lambda pairs: hashlib.sha1("|".join(sorted(pairs)).encode()).hexdigest()[:16]))
    events["roster_signature"] = events.event_id.map(signatures)

    # roster_kind (ROSTER_KIND_RULES), on the raw actionByName.
    events["roster_kind"] = events.apply(assign_roster_kind, axis=1)

    # actionByName (decision 1.6): relabel blank + 50 voters + raw meetingId is a council meeting file.
    events["action_by"] = events.action_by_raw
    relabel = ((events.action_by_raw.fillna("") == "") & (events.voter_count == COUNCIL_VOTER_COUNT)
               & events.meeting_id_raw.isin(council_meeting_ids))
    events.loc[relabel, "action_by"] = RELABEL_BLANK_ACTION_BY_AS
    events["action_by_source"] = relabel.map({True: "relabeled (blank, 50 voters, council meeting)",
                                              False: "eLMS"})

    events = events[[
        "event_id", "matter_id", "history_id", "record_number", "title", "matter_type", "matter_category",
        "agreed_calendar", "routine",
        "action_date", "action_date_source", "action_date_raw",
        "meeting_id", "meeting_id_source", "meeting_id_raw", "meeting_has_file",
        "action_by", "action_by_source", "action_by_raw", "action_name", "action_text",
        "roster_kind", "voter_count", *counts.columns, "roster_signature",
    ]]
    # Checks: one row per action with a roster; counts add up to voter_count.
    assert len(events) == len(raw_events)
    assert events.event_id.is_unique, "event_id must be unique"
    assert (events[list(counts.columns)].sum(axis=1) == events.voter_count).all(), "counts != voter_count"
    return events


@lru_cache(maxsize=None)
def build_meetings():
    raw_meetings, _ = load_raw_meetings()
    meetings = raw_meetings.copy()
    meetings.insert(1, "meeting_date", to_local_date(meetings.meeting_datetime_utc))
    meetings["has_attendance"] = meetings.attendance_member_count > 0
    # Links from vote_events (after the date match), for checking how the tables connect.
    events = build_vote_events()
    meetings["vote_event_count"] = meetings.meeting_id.map(events.meeting_id.value_counts()).fillna(0).astype(int)
    roll_call_events = events[events.roster_kind == "roll call"]
    meetings["roll_call_event_count"] = (meetings.meeting_id.map(roll_call_events.meeting_id.value_counts())
                                         .fillna(0).astype(int))
    meetings = meetings.sort_values("meeting_datetime_utc").reset_index(drop=True)
    # Checks: one row per meeting file.
    assert meetings.meeting_id.is_unique, "meeting_id must be unique"
    return meetings


def write_table(table, name):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{name}.csv"
    table.to_csv(output_path, index=False)
    print(f"wrote {output_path} ({len(table):,} rows, {len(table.columns)} columns)")


STEPS = {
    "member_votes": build_member_votes,
    "attendance": build_attendance,
    "vote_events": build_vote_events,
    "meetings": build_meetings,
    "people": build_people,
    "attachments": build_attachments,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in [*STEPS, "all"]:
        sys.exit(f"usage: python scripts/build_tables.py {{all | {' | '.join(STEPS)}}}")
    step_names = list(STEPS) if sys.argv[1] == "all" else [sys.argv[1]]
    for step_name in step_names:
        write_table(STEPS[step_name](), step_name)
