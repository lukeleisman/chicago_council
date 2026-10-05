"""Export the data the dashboard page reads: docs/data/*.json (committed; served by GitHub Pages).

Reads data/tables/ (scripts/build_tables.py all) and the tile files (scripts/build_ward_tiles.py all)
and the 2023 ward layer (scripts/fetch_layers.py). Every number is computed by
scripts/council_metrics.py, the same code notebooks/ward_views.ipynb uses; nothing is
re-derived here. The page itself is docs/dashboard/app.js.

Files written (all small; sizes printed at the end):
  wards_real.geojson     2023 ward boundaries, simplified by WARD_SIMPLIFY_TOLERANCE_METERS
  wards_tiles_grid.geojson, wards_tiles_pushed.geojson   one rectangle per ward
  alders.json            one record per current alder: name, photo URL, tenure, absence
  split_events.json      one record per kept split event: tallies, each current alder's vote, attachments
  meta.json              when exported, and every rule/setting behind the numbers (shown on the page)

Usage:
  python scripts/export_dashboard_data.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_tables
import build_ward_tiles
import council_metrics
import ward_maps

# ---------------------------------------------------------------------------
# Configuration — every choice made in this script lives here.
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_DIR / "docs" / "data"

# Ward boundaries are simplified for the web (user, 2026-10-05: "I don't want to lose much").
# Measured 2026-10-05 (notebook check in sessions/2026-10-05.md): the raw layer has 89,500 points
# (3.5 MB; 1.3 MB compressed). Simplifying at 1 m keeps 7,966 points, 47 KB compressed, and moves
# no boundary more than 1.2 m (one screen pixel at full-city view is about 50 m).
# Simplified in IL State Plane (feet) so the tolerance is a ground distance. Each ward is
# simplified on its own, so shared borders can differ by up to the tolerance (gaps/slivers <= 1 m).
WARD_SIMPLIFY_TOLERANCE_METERS = 1.0
SIMPLIFY_CRS = "EPSG:3435"
FEET_PER_METER = 1 / 0.3048

# Coordinate decimals in the exported GeoJSON (longitude/latitude). 6 decimals = about 0.1 m.
COORDINATE_DECIMALS = 6

# Alder photos: "elms_url" = the page loads each photo from eLMS's public URL (people.photo_url).
# Chosen so the public repo doesn't carry copies of the photos (data/raw/photos/ stays local).
PHOTO_SOURCE = "elms_url"

# Split events: all kept events (council_metrics.split_event_steps), newest first in the dropdown.
SPLIT_EVENT_ORDER = "newest_first"
# Default event shown on the page: same as ward_views SPLIT_EVENT_TO_SHOW (user, 2026-10-05: 2025 budget).
DEFAULT_SPLIT_EVENT_RECORD_NUMBER = "SO2024-0013682"

TALLY_COLUMNS = ["count_yea", "count_nay", "count_absent", "count_not_voting", "count_present",
                 "count_recused", "count_vacant", "count_rising_vote"]

# ---------------------------------------------------------------------------


def round_coordinates(coordinates, decimals=COORDINATE_DECIMALS):
    if isinstance(coordinates[0], (list, tuple)):
        return [round_coordinates(part, decimals) for part in coordinates]
    return [round(coordinates[0], decimals), round(coordinates[1], decimals)]


def write_geojson(shapes, file_name):
    """shapes: GeoDataFrame with `ward` and geometry. Written as EPSG:4326 GeoJSON with properties
    ward, label_lon, label_lat. Label point = representative_point() (inside the shape; the same
    point ward_maps.draw_ward_labels uses), taken in the shapes' own CRS, then converted."""
    shapes = shapes[["ward", "geometry"]].copy()
    label_points = gpd.GeoSeries(shapes.representative_point(), crs=shapes.crs).to_crs("EPSG:4326")
    shapes["label_lon"] = label_points.x.round(COORDINATE_DECIMALS).values
    shapes["label_lat"] = label_points.y.round(COORDINATE_DECIMALS).values
    collection = json.loads(shapes.to_crs("EPSG:4326").to_json(drop_id=True))
    for feature in collection["features"]:
        feature["geometry"]["coordinates"] = round_coordinates(feature["geometry"]["coordinates"])
    write_json(collection, file_name)


def write_json(data, file_name):
    output_path = OUTPUT_DIR / file_name
    output_path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {output_path.relative_to(REPO_DIR)} ({output_path.stat().st_size / 1000:,.0f} KB)")


def export_shapes():
    real_wards = ward_maps.load_ward_shapes("real").to_crs(SIMPLIFY_CRS)
    point_count_before = real_wards.geometry.count_coordinates().sum()
    real_wards["geometry"] = real_wards.geometry.simplify(
        WARD_SIMPLIFY_TOLERANCE_METERS * FEET_PER_METER, preserve_topology=True)
    print(f"ward points: {point_count_before:,} -> {real_wards.geometry.count_coordinates().sum():,} "
          f"(tolerance {WARD_SIMPLIFY_TOLERANCE_METERS} m)")
    write_geojson(real_wards, "wards_real.geojson")
    write_geojson(ward_maps.load_ward_shapes("tiles_grid"), "wards_tiles_grid.geojson")
    write_geojson(ward_maps.load_ward_shapes("tiles_pushed"), "wards_tiles_pushed.geojson")


def export_alders_and_votes():
    tables = council_metrics.load_tables()
    alders = council_metrics.current_alders(tables["people"]).rename(columns={"elms_ward": "ward"})
    assert alders.ward.is_unique and len(alders) == 50, "expected one current alder per ward"

    # Absence: same calls, same order as ward_views §3.1-§3.2.
    counted_events = council_metrics.absence_counted_events(tables["vote_events"], tables["meetings"])
    alder_meeting = council_metrics.absence_alder_meetings(tables["member_votes"], counted_events,
                                                           tables["meetings"], alders.person_id)
    absence = council_metrics.absence_by_alder(alders, alder_meeting, counted_events).set_index("person_id")

    alder_records = []
    for alder in alders.sort_values("ward").itertuples():
        alder_records.append({
            "ward": alder.ward, "person_id": alder.person_id, "display_name": alder.display_name,
            "label_name": alder.label_name,
            "photo_url": alder.photo_url if PHOTO_SOURCE == "elms_url" else None,
            "site": alder.site if isinstance(alder.site, str) else None,
            "council_start_date": alder.council_start_date, "years_on_council": alder.years_on_council,
            "absent_meetings": int(absence.absent_meetings[alder.person_id]),
            "meetings_in_denominator": int(absence.meetings_in_denominator[alder.person_id]),
            "percent_absent": absence.percent_absent[alder.person_id],
            "absent_meeting_dates": absence.absent_meeting_dates[alder.person_id],
        })
    write_json(alder_records, "alders.json")

    # Split events: kept events (ward_views §4.1), each current alder's raw vote, attachments in eLMS order.
    _, _, split_events = council_metrics.split_event_steps(tables["vote_events"])
    ascending = SPLIT_EVENT_ORDER != "newest_first"
    split_events = split_events.sort_values(["action_date", "record_number"], ascending=ascending)
    ward_by_person = dict(zip(alders.person_id, alders.ward))
    split_votes = tables["member_votes"][tables["member_votes"].event_id.isin(split_events.event_id)
                                         & tables["member_votes"].person_id.isin(ward_by_person)]
    votes_by_event = {event_id: dict(zip(rows.person_id.map(ward_by_person), rows.vote))
                      for event_id, rows in split_votes.groupby("event_id")}
    attachments = tables["attachments"].sort_values(["matter_id", "attachment_position"])
    attachments_by_matter = {matter_id: rows[["attachment_type", "file_name", "url"]].to_dict("records")
                             for matter_id, rows in attachments[attachments.matter_id.isin(split_events.matter_id)]
                             .groupby("matter_id")}
    event_records = []
    for event in split_events.itertuples():
        event_records.append({
            "event_id": event.event_id, "matter_id": event.matter_id, "record_number": event.record_number,
            "action_date": event.action_date, "title": event.title, "matter_type": event.matter_type,
            "action_name": event.action_name,
            "tallies": {column: int(getattr(event, column)) for column in TALLY_COLUMNS},
            # {ward: raw vote}; a ward missing here = its current alder is not on this event's roster.
            "votes_by_ward": votes_by_event.get(event.event_id, {}),
            "attachments": attachments_by_matter.get(event.matter_id, []),
        })
    write_json(event_records, "split_events.json")
    print(f"alders: {len(alder_records)}; split events: {len(event_records)}; "
          f"events with attachments: {sum(bool(record['attachments']) for record in event_records)}")

    default_event = [record for record in event_records if record["record_number"] == DEFAULT_SPLIT_EVENT_RECORD_NUMBER]
    assert len(default_event) == 1, f"{DEFAULT_SPLIT_EVENT_RECORD_NUMBER} must match exactly one kept split event"
    return default_event[0]["event_id"], len(counted_events)


def export_meta(default_event_id, counted_event_count):
    write_json({
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tenure_as_of": build_tables.AS_OF_DATE,
        "default_split_event_id": default_event_id,
        "rules": {
            "current_alder": "eLMS person list: active, with a ward number (decision 1.1)",
            "tenure": "years from earliest DataMade council membership start to the as-of date, gaps ignored (decision 1.2)",
            "absence": (f"absent from a council meeting = vote 'Absent' on more than "
                        f"{council_metrics.ABSENT_MEETING_SHARE_THRESHOLD:.0%} of that meeting's roll-call items; "
                        f"percent of meetings while seated ({council_metrics.ABSENCE_DENOMINATOR}); "
                        f"{counted_event_count} roll-call items counted; "
                        f"{len(council_metrics.EXCLUDE_EVENTS_FROM_ABSENCE)} event excluded (R2023-0005012, previous council's roster)"),
            "split_event": (f"council roll call ({council_metrics.SPLIT_ACTION_BY}, roster kind "
                            f"{', '.join(council_metrics.SPLIT_ROSTER_KINDS)}) with at least "
                            f"{council_metrics.SPLIT_MIN_NAY} Nay vote (decision 1.5)"),
            "ward_boundaries": f"2023 wards, simplified at {WARD_SIMPLIFY_TOLERANCE_METERS} m",
            "tiles_grid": f"hand-specified grid, layout {build_ward_tiles.GRID_LAYOUT}",
            "tiles_pushed": "each tile starts at its ward and overlapping tiles are pushed apart",
        },
        "sources": {
            "votes, people, attachments": "Chicago City Clerk eLMS API (api.chicityclerkelms.chicago.gov)",
            "tenure history": "DataMade chicago-council-scrapers nightly export",
            "ward boundaries": "Chicago Data Portal, Boundaries - Wards (2023-)",
        },
    }, "meta.json")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    export_shapes()
    default_event_id, counted_event_count = export_alders_and_votes()
    export_meta(default_event_id, counted_event_count)
