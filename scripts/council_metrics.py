"""Council metrics shared by notebooks/ward_views.ipynb and scripts/export_dashboard_data.py.

Moved here 2026-10-05, logic unchanged, from the ward_views notebook cells (generator:
sessions/2026-10-04_build_ward_views_notebook.py) so the notebook and the dashboard compute the
same numbers from the same code:
  current_alders()          <- ward_views §1.1 (current alder per ward, label name)
  absence_*()               <- ward_views §3.1-§3.2 (decision 1.4; same computation as tables_review §2.6)
  split_event_steps()       <- ward_views §4.1 (decision 1.5 plus the user's 2026-10-05 filters)

Every rule is a named constant below, with who decided it and when. The notebook shows the
evidence for each (excluded event, counts at each filter step, cross-checks).
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

TABLES_DIR = Path(__file__).resolve().parent.parent / "data" / "tables"

# --- Current alders (ward_views §1.1) ---
# Current alder = people row with is_active True and a ward number in elms_ward (decision 1.1:
# eLMS /person). Clerk and Mayor rows are active but have no ward number.
# Name shown (user, 2026-10-04: last name only, keep "Jr."):
#   "last"      = text before the LAST comma of display_name ("Cardona, Jr., Felix" -> "Cardona, Jr.")
#   "as_stored" = display_name unchanged
ALDER_LABEL_NAME = "last"

# --- Absence (ward_views §3; decision 1.4, sessions/2026-10-04.md) ---
# An alder is absent from a council meeting if their vote is "Absent" on MORE THAN this share of
# that meeting's counted items (exactly 50% counts as present). Not Voting is not Absent (decision 1.3).
ABSENT_MEETING_SHARE_THRESHOLD = 0.5
ABSENCE_MEETING_BODY = "City Council"        # meetings.body of the meetings counted
ABSENCE_ROSTER_KINDS = ["roll call"]         # vote_events.roster_kind counted (metrics use roll call only)
# Events left out of the absence computation, {event_id: reason} (user, 2026-10-04). ward_views §3.1
# shows the evidence.
EXCLUDE_EVENTS_FROM_ABSENCE = {
    "4016E3F7-F562-EE11-BE6E-001DD80523DD_49707A14-6968-EE11-9AE6-001DD80971B2":
        "R2023-0005012, 2023-10-11: only roll-call event at that meeting; its roster is the previous council's "
        "(Burke, Austin, Tunney, ...), marking Curtis Absent while the meeting's attendance shows all 50 Present",
}
# Denominator (user, 2026-10-04: meetings on roster):
#   "meetings_on_roster" = council meetings where the alder is on at least one counted roll-call roster
#                          (i.e. while seated; Burnett 18, Quezada 24, others 63 on 2026-10-04)
#   "all_meetings"       = every council meeting with a counted roll-call event, for everyone
ABSENCE_DENOMINATOR = "meetings_on_roster"

# --- Split roll calls (ward_views §4.1) ---
# Split = at least this many Nay votes (decision 1.5, sessions/2026-10-04.md).
SPLIT_MIN_NAY = 1
# Which split events are kept (user, 2026-10-05: council roll calls only).
SPLIT_ACTION_BY = "City Council"            # vote_events.action_by
SPLIT_ROSTER_KINDS = ["roll call"]          # vote_events.roster_kind

# ---------------------------------------------------------------------------


def load_tables(tables_dir=TABLES_DIR):
    """Every table the metrics use, read the same way ward_views reads them."""
    tables_dir = Path(tables_dir)
    return {
        "people": pd.read_csv(tables_dir / "people.csv", dtype={"elms_ward": str}),
        "meetings": pd.read_csv(tables_dir / "meetings.csv"),
        "vote_events": pd.read_csv(tables_dir / "vote_events.csv", low_memory=False),
        "member_votes": pd.read_csv(tables_dir / "member_votes.csv"),
        "attendance": pd.read_csv(tables_dir / "attendance.csv"),
        "attachments": pd.read_csv(tables_dir / "attachments.csv"),
    }


def current_alders(people, label_name_rule=ALDER_LABEL_NAME):
    """people rows for current alders, plus label_name and comma_count. Ward is in elms_ward ("01".."50")."""
    has_ward_number = people.elms_ward.str.fullmatch(r"\d+", na=False)
    alders = people[people.is_active & has_ward_number].copy()
    if label_name_rule == "last":
        alders["label_name"] = alders.display_name.str.rsplit(",", n=1).str[0].str.strip()
    elif label_name_rule == "as_stored":
        alders["label_name"] = alders.display_name
    else:
        raise ValueError(label_name_rule)
    alders["comma_count"] = alders.display_name.str.count(",")
    return alders


def absence_counted_events(vote_events, meetings):
    """vote_events rows counted for absence: ABSENCE_ROSTER_KINDS, at ABSENCE_MEETING_BODY meetings,
    minus EXCLUDE_EVENTS_FROM_ABSENCE."""
    council_meeting_ids = set(meetings.loc[meetings.body == ABSENCE_MEETING_BODY, "meeting_id"])
    return vote_events[vote_events.roster_kind.isin(ABSENCE_ROSTER_KINDS)
                       & vote_events.meeting_id.isin(council_meeting_ids)
                       & ~vote_events.event_id.isin(EXCLUDE_EVENTS_FROM_ABSENCE)]


def absence_alder_meetings(member_votes, counted_events, meetings, current_person_ids):
    """One row per current alder x meeting: items, absent_items, share_of_items_absent,
    absent_from_meeting (share > ABSENT_MEETING_SHARE_THRESHOLD), meeting_date."""
    alder_meeting = (member_votes.merge(counted_events[["event_id", "meeting_id"]], on="event_id")
                     .assign(is_absent_vote=lambda frame: frame.vote == "Absent")
                     .groupby(["meeting_id", "person_id"])
                     .agg(items=("is_absent_vote", "size"), absent_items=("is_absent_vote", "sum"))
                     .reset_index())
    alder_meeting["share_of_items_absent"] = alder_meeting.absent_items / alder_meeting["items"]
    alder_meeting["absent_from_meeting"] = alder_meeting.share_of_items_absent > ABSENT_MEETING_SHARE_THRESHOLD
    alder_meeting["meeting_date"] = alder_meeting.meeting_id.map(meetings.set_index("meeting_id").meeting_date)
    return alder_meeting[alder_meeting.person_id.isin(current_person_ids)]   # current alders only


def absence_by_alder(alders, alder_meeting, counted_events, denominator_rule=ABSENCE_DENOMINATOR):
    """One row per alder in `alders` (needs ward, person_id, display_name, label_name):
    meetings_in_denominator, absent_meetings, percent_absent, absent_meeting_dates."""
    if denominator_rule == "meetings_on_roster":
        denominator_by_person = alder_meeting.groupby("person_id").size()
    elif denominator_rule == "all_meetings":
        denominator_by_person = pd.Series(counted_events.meeting_id.nunique(), index=alders.person_id)
    else:
        raise ValueError(denominator_rule)

    absence_table = alders[["ward", "person_id", "display_name", "label_name"]].copy()
    absence_table["meetings_in_denominator"] = absence_table.person_id.map(denominator_by_person).fillna(0).astype(int)
    absence_table["absent_meetings"] = (absence_table.person_id
                                        .map(alder_meeting.groupby("person_id").absent_from_meeting.sum())
                                        .fillna(0).astype(int))
    absence_table["percent_absent"] = 100 * absence_table.absent_meetings / absence_table.meetings_in_denominator
    absence_table["absent_meeting_dates"] = absence_table.person_id.map(
        alder_meeting[alder_meeting.absent_from_meeting].groupby("person_id").meeting_date
        .apply(lambda dates: ", ".join(sorted(dates)))).fillna("")
    return absence_table


def split_event_steps(vote_events):
    """(events with count_nay >= SPLIT_MIN_NAY, ... and action_by == SPLIT_ACTION_BY,
    ... and roster_kind in SPLIT_ROSTER_KINDS). The last one is the kept split events."""
    split_step_all = vote_events[vote_events.count_nay >= SPLIT_MIN_NAY]
    split_step_council = split_step_all[split_step_all.action_by == SPLIT_ACTION_BY]
    split_events = split_step_council[split_step_council.roster_kind.isin(SPLIT_ROSTER_KINDS)].copy()
    return split_step_all, split_step_council, split_events
