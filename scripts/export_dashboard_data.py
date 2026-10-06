"""Export the data the dashboard page reads: docs/data/*.json (committed; served by GitHub Pages).

Reads data/tables/ (scripts/build_tables.py all) and the tile files (scripts/build_ward_tiles.py all)
and the 2023 ward layer (scripts/fetch_layers.py). Every number is computed by
scripts/council_metrics.py, the same code notebooks/ward_views.ipynb uses; nothing is
re-derived here. The page itself is docs/dashboard/app.js.

Files written (all small; sizes printed at the end):
  wards_real.geojson     2023 ward boundaries, simplified by WARD_SIMPLIFY_TOLERANCE_METERS
  wards_tiles_grid.geojson   one rectangle per ward (pushed tiles are not exported: user, 2026-10-05)
  alders.json            one record per current alder: name, photo URL, tenure, absence
  split_events.json      one record per kept split event: tallies, each current alder's vote, attachments
  meta.json              when exported, and every rule/setting behind the numbers (shown on the page)
  layer_<name>.geojson   Wards tab overlays (DASHBOARD_LAYERS), styled by scripts/map_layers.py

Usage:
  python scripts/export_dashboard_data.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")   # no window; figures are only measured
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_tables
import build_ward_tiles
import council_metrics
import map_layers
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

# Map View labels (user, 2026-10-05: alder names on the real map "as designed in the notebooks").
# Which ward_views label layout each dashboard view uses; sizes and nudges live in scripts/ward_maps.py.
#   "one_block" = ward_maps.draw_ward_labels: "ward\nLast name" centered on the anchor
#   "two_sizes" = ward_maps.draw_ward_two_size_labels: "ward Last" just above the anchor, value just below
# The split-votes view uses "names" (ward_views §4.7 uses §1's labels).
# Value text mirrors the notebook: tenure "19.8" (TENURE_DECIMALS), absence "12.7%" (ABSENCE_PERCENT_DECIMALS).
REAL_MAP_LABEL_LAYOUTS = {
    "names": {"source": "ward_views §1.2 (also §4.7)", "kind": "one_block",
              "font_points": [ward_maps.MAP_LABEL_FONT_SIZE],
              "offsets": ward_maps.LABEL_OFFSET_POINTS_BY_WARD},
    "tenure": {"source": 'ward_views §2.2, TENURE_LABEL_STYLE "two_sizes"', "kind": "two_sizes",
               "font_points": [ward_maps.TENURE_NAME_FONT_SIZE, ward_maps.TENURE_YEARS_FONT_SIZE],
               "offsets": ward_maps.TENURE_LABEL_OFFSETS_BY_STYLE["two_sizes"]},
    "absence": {"source": 'ward_views §3.3, ABSENCE_LABEL_VALUE "percent"', "kind": "two_sizes",
                "font_points": [ward_maps.ABSENCE_NAME_FONT_SIZE, ward_maps.ABSENCE_VALUE_FONT_SIZE],
                "offsets": ward_maps.ABSENCE_LABEL_OFFSETS_BY_VALUE["percent"]},
}
LABEL_VALUE_DECIMALS = 1   # ward_views TENURE_DECIMALS and ABSENCE_PERCENT_DECIMALS (both 1)
# Dashboard-only extra nudges, added to the notebook nudge of EVERY layout above (user, 2026-10-05:
# "all three, same moves"). The notebook (scripts/ward_maps.py) is not changed. Needed because the page
# draws labels REAL_MAP_LABEL_SCALE (1.25) times the notebook size (docs/dashboard/app.js).
# {ward: (right, up)} in points on the FIGURE_SIZE_MAP figure, like the notebook's (1 pt = about 76 m;
# about 0.7 px on a ~500 px wide map). Negative = left / down. Set by the user, 2026-10-05.
DASHBOARD_EXTRA_OFFSET_POINTS_BY_WARD = {
    "03": (0, -8),     # Dowell
    "07": (0, -10),    # Mitchell
    "08": (-3, 8),     # Harris
    "14": (-15, 5),    # Gutierrez
    "15": (5, 16),     # Lopez
    "16": (0, -3),     # Coleman
    "19": (-10, 0),    # O'Shea
    "20": (15, -5),    # Taylor
    "22": (-3, 5),     # Rodriguez
    "24": (-3, 3),     # Scott
    "29": (-12, 3),    # Taliaferro
    "30": (5, 10),     # Cruz
    "33": (0, 8),      # Rodriguez Sanchez
    "35": (-5, 5),     # Quezada (user listed "35 west 5 more" twice; applied once)
    "36": (-3, 0),     # Villegas
    "39": (-3, 3),     # Nugent
    "40": (-3, 3),     # Vasquez, Jr.
    "43": (0, 5),      # Knudsen
    "44": (5, 0),      # Lawson
    "46": (5, 0),      # Clay
    "47": (0, -3),     # Martin
}
# 49/50: user, 2026-10-05: "fine, no actual overlap" (left as the notebook has them).
# White halo width around label text, in points: ward_maps.TEXT_HALO (patheffects linewidth 2.5).
LABEL_HALO_POINTS = 2.5

# Wards tab overlays (user, 2026-10-05): which layers from scripts/fetch_layers.py, in the order of
# map_layers.LAYER_STYLE. No precincts, no census tracts (user). Each is drawn as the notebook's
# large map (notebooks/map_layers_review.ipynb "One large map per layer"), styles from map_layers.py.
DASHBOARD_LAYERS = ["community_areas", "neighborhoods", "zip_codes", "police_districts", "parks",
                    "cta_rail_lines", "cta_rail_stations", "cps_schools_sy2526", "ward_offices"]
# Name shown when hovering a point (stations, schools, ward offices; the plan's choice, 2026-10-05).
# Layers not listed have no hover name. Column = the raw layer's column, copied as is.
LAYER_HOVER_NAME_COLUMN = {
    "cta_rail_stations": "longname",
    "cps_schools_sy2526": "short_name",
    "ward_offices": "address",
}
# Polygons and lines are simplified like the wards (WARD_SIMPLIFY_TOLERANCE_METERS, in SIMPLIFY_CRS).
# Fill colors (color_index) and label points are computed on the UNSIMPLIFIED shapes in PLOT_CRS,
# exactly as the notebook does (map_layers.neighbor_color_indexes on the EPSG:3857 frame, so the
# neighbor distance is in Mercator meters, ~1.34x ground at Chicago; representative_point() in 3857).
LAYER_SIMPLIFY_TOLERANCE_METERS = WARD_SIMPLIFY_TOLERANCE_METERS

# Text under the dashboard (user's wording, 2026-10-05; replaces the "How the numbers are made" and
# "Sources" lists on the page, which stay in meta.json `rules` / `sources` for reference).
# Spelling fixed: "role" -> "roll calls", "In cased" -> "In case", "continous" -> "continuous".
# The sentences state rule values in words, so the export stops if a rule changes (asserts in export_meta).
ABOUT_TEXT_HEADING = "About the data"
ABOUT_TEXT = [
    "Data is sourced from the Chicago City Clerk eLMS API (api.chicityclerkelms.chicago.gov) from the "
    "beginning of the 2023 term.",
    "Tenure history prior to 2023 is sourced from DataMade chicago-council-scrapers nightly export.",
    "Ward boundaries are from the Chicago Data Portal.",
    "The split votes include all council roll call votes with at least one Nay vote.",
    "An alderperson is counted as absent from a meeting if their vote was 'Absent' on more than 50% of "
    "a meeting's roll calls.",
    "In case of missing tenure data, an alderperson's tenure is assumed to be continuous from their start date.",
]

# ---------------------------------------------------------------------------


def round_coordinates(coordinates, decimals=COORDINATE_DECIMALS):
    if isinstance(coordinates[0], (list, tuple)):
        return [round_coordinates(part, decimals) for part in coordinates]
    return [round(coordinates[0], decimals), round(coordinates[1], decimals)]


def write_geojson(shapes, file_name, labels_by_ward=None):
    """shapes: GeoDataFrame with `ward` and geometry. Written as EPSG:4326 GeoJSON with properties
    ward, label_lon, label_lat. Label point = representative_point() (inside the shape; the same
    point ward_maps.draw_ward_labels uses), taken in the shapes' own CRS, then converted.
    labels_by_ward: optional {ward: {layout: [lon, lat]}}, written as property `labels` (Map View
    label anchors from real_map_label_layout(); the page uses these instead of label_lon/lat)."""
    shapes = shapes[["ward", "geometry"]].copy()
    label_points = gpd.GeoSeries(shapes.representative_point(), crs=shapes.crs).to_crs("EPSG:4326")
    shapes["label_lon"] = label_points.x.round(COORDINATE_DECIMALS).values
    shapes["label_lat"] = label_points.y.round(COORDINATE_DECIMALS).values
    collection = json.loads(shapes.to_crs("EPSG:4326").to_json(drop_id=True))
    for feature in collection["features"]:
        feature["geometry"]["coordinates"] = round_coordinates(feature["geometry"]["coordinates"])
        if labels_by_ward is not None:
            feature["properties"]["labels"] = labels_by_ward[feature["properties"]["ward"]]
    write_json(collection, file_name)


def real_map_label_layout(alder_records):
    """Map View label anchors and the points-to-map scale, from the notebook's own figure.

    Rebuilds the ward_views map figure (plt.subplots(figsize=ward_maps.FIGURE_SIZE_MAP), unsimplified
    ward outlines in PLOT_CRS, axis off: fill, basemap, title and color bar don't move the axis) and
    asks matplotlib where each label lands: anchor = representative_point() (as
    ward_maps.draw_ward_labels), plus that layout's nudge in points. Then draws the labels with the
    ward_maps functions and prints ward_maps.label_overlaps (expected 0, as in the notebook).

    Returns ({ward: {layout: [lon, lat]}}, meters_per_point). meters_per_point is in EPSG:3857 units
    on that figure; the page multiplies font sizes in points by it.
    """
    wards = ward_maps.load_ward_shapes("real").sort_values("ward").reset_index(drop=True)
    alder_by_ward = {record["ward"]: record for record in alder_records}
    figure, axis = plt.subplots(figsize=ward_maps.FIGURE_SIZE_MAP)
    ward_maps.draw_ward_outlines(axis, wards)
    axis.set_axis_off()
    figure.canvas.draw()

    # Map meters per typographic point, x and y separately (equal if the axis aspect is equal).
    data_to_pixels = axis.transData
    origin_pixels = data_to_pixels.transform((0, 0))
    pixels_per_meter_x = data_to_pixels.transform((1000, 0))[0] - origin_pixels[0]
    pixels_per_meter_y = data_to_pixels.transform((0, 1000))[1] - origin_pixels[1]
    pixels_per_point = figure.dpi / 72
    meters_per_point = 1000 * pixels_per_point / pixels_per_meter_x
    assert abs(pixels_per_meter_x / pixels_per_meter_y - 1) < 1e-6, "axis aspect is not equal"
    print(f"Map View labels: figure {ward_maps.FIGURE_SIZE_MAP} in, 1 pt = {meters_per_point:.1f} m on the map")

    anchor_by_ward = dict(zip(wards.ward, wards.representative_point()))
    labels_by_ward = {ward: {} for ward in wards.ward}
    # Wards tab: bold ward number at the plain representative point, no nudge
    # (map_layers_review draw_wards_on_top).
    plain_anchors = gpd.GeoSeries(list(anchor_by_ward.values()), crs=ward_maps.PLOT_CRS).to_crs("EPSG:4326")
    for ward, point in zip(anchor_by_ward, plain_anchors):
        labels_by_ward[ward]["ward_number"] = [round(point.x, COORDINATE_DECIMALS), round(point.y, COORDINATE_DECIMALS)]
    for layout_name, layout in REAL_MAP_LABEL_LAYOUTS.items():
        anchors = []
        for ward, anchor in anchor_by_ward.items():
            # Notebook nudge plus the dashboard-only extra nudge.
            notebook_right, notebook_up = layout["offsets"].get(ward, (0, 0))
            extra_right, extra_up = DASHBOARD_EXTRA_OFFSET_POINTS_BY_WARD.get(ward, (0, 0))
            right_points, up_points = notebook_right + extra_right, notebook_up + extra_up
            anchors.append((anchor.x + right_points * meters_per_point, anchor.y + up_points * meters_per_point))
        anchors_lon_lat = gpd.GeoSeries(gpd.points_from_xy(*zip(*anchors)), crs=ward_maps.PLOT_CRS).to_crs("EPSG:4326")
        for ward, point in zip(anchor_by_ward, anchors_lon_lat):
            labels_by_ward[ward][layout_name] = [round(point.x, COORDINATE_DECIMALS), round(point.y, COORDINATE_DECIMALS)]
    plt.close(figure)

    # Overlap check with the notebook's own drawing functions and texts, at the notebook's size and
    # nudges only (the dashboard's larger labels and extra nudges are checked in the browser).
    number_name = {ward: f"{ward.lstrip('0')} {alder_by_ward[ward]['label_name']}" for ward in wards.ward}
    texts_by_layout = {
        "names": {ward: f"{ward.lstrip('0')}\n{alder_by_ward[ward]['label_name']}" for ward in wards.ward},
        "tenure": {ward: f"{alder_by_ward[ward]['years_on_council']:.{LABEL_VALUE_DECIMALS}f}" for ward in wards.ward},
        "absence": {ward: f"{alder_by_ward[ward]['percent_absent']:.{LABEL_VALUE_DECIMALS}f}%" for ward in wards.ward},
    }
    for layout_name, layout in REAL_MAP_LABEL_LAYOUTS.items():
        figure, axis = plt.subplots(figsize=ward_maps.FIGURE_SIZE_MAP)
        ward_maps.draw_ward_outlines(axis, wards)
        if layout["kind"] == "one_block":
            annotations = ward_maps.draw_ward_labels(axis, wards, texts_by_layout[layout_name],
                                                     font_size=layout["font_points"][0], offset_points_by_ward=layout["offsets"])
        else:
            annotations = ward_maps.draw_ward_two_size_labels(axis, wards, number_name, texts_by_layout[layout_name],
                                                              *layout["font_points"], offset_points_by_ward=layout["offsets"])
        axis.set_axis_off()
        figure.canvas.draw()
        overlaps = ward_maps.label_overlaps(figure, annotations)
        plt.close(figure)
        print(f"  {layout_name} ({layout['source']}): overlapping label pairs {len(overlaps)}",
              [f"{ward_a}/{ward_b}" for ward_a, ward_b, *_ in overlaps])
    return labels_by_ward, meters_per_point


def write_json(data, file_name):
    output_path = OUTPUT_DIR / file_name
    output_path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {output_path.relative_to(REPO_DIR)} ({output_path.stat().st_size / 1000:,.0f} KB)")


def export_shapes(labels_by_ward):
    real_wards = ward_maps.load_ward_shapes("real").to_crs(SIMPLIFY_CRS)
    point_count_before = real_wards.geometry.count_coordinates().sum()
    real_wards["geometry"] = real_wards.geometry.simplify(
        WARD_SIMPLIFY_TOLERANCE_METERS * FEET_PER_METER, preserve_topology=True)
    print(f"ward points: {point_count_before:,} -> {real_wards.geometry.count_coordinates().sum():,} "
          f"(tolerance {WARD_SIMPLIFY_TOLERANCE_METERS} m)")
    write_geojson(real_wards, "wards_real.geojson", labels_by_ward=labels_by_ward)
    write_geojson(ward_maps.load_ward_shapes("tiles_grid"), "wards_tiles_grid.geojson")


def export_layers():
    """One GeoJSON per DASHBOARD_LAYERS entry. Properties: label (LAYER_STYLE label column, or null),
    label_lon/label_lat (representative point, unsimplified, PLOT_CRS), color_index ("fill" layers:
    map_layers.neighbor_color_indexes, unsimplified, PLOT_CRS), hover_name (LAYER_HOVER_NAME_COLUMN).
    Returns {layer: {"kind", "has_labels", "feature_count", "colors_used"}} for meta.json."""
    layer_meta = {}
    for layer_name in DASHBOARD_LAYERS:
        style = map_layers.LAYER_STYLE[layer_name]
        raw_path = ward_maps.LAYERS_DIR / f"{layer_name}.geojson"
        frame_plot = gpd.read_file(raw_path).to_crs(ward_maps.PLOT_CRS).reset_index(drop=True)
        properties = pd.DataFrame(index=frame_plot.index)
        properties["label"] = frame_plot[style["label_column"]].astype(str) if style["label_column"] else None
        hover_column = LAYER_HOVER_NAME_COLUMN.get(layer_name)
        properties["hover_name"] = frame_plot[hover_column] if hover_column else None
        colors_used = None
        if style["kind"] == "fill":
            properties["color_index"] = map_layers.neighbor_color_indexes(frame_plot)
            colors_used = int(properties.color_index.max()) + 1
            # Same check and message as the notebook's draw_layer.
            if colors_used > len(map_layers.FILL_PALETTE):
                print(f"WARNING {layer_name}: needed {colors_used} colors, palette has "
                      f"{len(map_layers.FILL_PALETTE)}; colors repeat")
        if style["label_column"]:
            label_points = gpd.GeoSeries(frame_plot.representative_point(), crs=ward_maps.PLOT_CRS).to_crs("EPSG:4326")
            properties["label_lon"] = label_points.x.round(COORDINATE_DECIMALS).values
            properties["label_lat"] = label_points.y.round(COORDINATE_DECIMALS).values

        geometry = frame_plot.geometry.to_crs(SIMPLIFY_CRS)
        point_count_before = int(geometry.count_coordinates().sum())
        if style["kind"] != "point":
            geometry = geometry.simplify(LAYER_SIMPLIFY_TOLERANCE_METERS * FEET_PER_METER, preserve_topology=True)
        point_count_after = int(geometry.count_coordinates().sum())
        export_frame = gpd.GeoDataFrame(properties, geometry=geometry.values, crs=SIMPLIFY_CRS).to_crs("EPSG:4326")
        collection = json.loads(export_frame.to_json(drop_id=True))
        for feature in collection["features"]:
            feature["geometry"]["coordinates"] = round_coordinates(feature["geometry"]["coordinates"])
        print(f"{layer_name}: {len(frame_plot)} features ({style['kind']}), points {point_count_before:,} -> "
              f"{point_count_after:,}" + (f", {colors_used} fill colors" if colors_used else "")
              + f"; raw file {raw_path.stat().st_size / 1e6:.2f} MB")
        write_json(collection, f"layer_{layer_name}.geojson")
        layer_meta[layer_name] = {"kind": style["kind"], "has_labels": bool(style["label_column"]),
                                  "feature_count": len(frame_plot), "colors_used": colors_used}
    return layer_meta


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
    return default_event[0]["event_id"], len(counted_events), alder_records


def export_meta(default_event_id, counted_event_count, meters_per_point, layer_meta):
    # ABOUT_TEXT states these rule values in words; stop if a rule no longer matches the sentence.
    assert council_metrics.SPLIT_MIN_NAY == 1, "ABOUT_TEXT says 'at least one Nay vote'"
    assert council_metrics.SPLIT_ACTION_BY == "City Council" and council_metrics.SPLIT_ROSTER_KINDS == ["roll call"], \
        "ABOUT_TEXT says 'council roll call votes'"
    assert council_metrics.ABSENT_MEETING_SHARE_THRESHOLD == 0.5, "ABOUT_TEXT says 'more than 50%'"
    write_json({
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tenure_as_of": build_tables.AS_OF_DATE,
        "default_split_event_id": default_event_id,
        # Map View labels: font sizes in points on the notebook figure; meters_per_point converts
        # them to EPSG:3857 map units. Anchors are in wards_real.geojson `labels`.
        "real_map_labels": {
            "meters_per_point": meters_per_point,
            "halo_points": LABEL_HALO_POINTS,
            "layouts": {name: {"kind": layout["kind"], "font_points": layout["font_points"], "source": layout["source"]}
                        for name, layout in REAL_MAP_LABEL_LAYOUTS.items()},
        },
        # Wards tab overlays: map_layers.py styles, sizes in points on the notebook's FIGURE_SIZE_LARGE
        # figure (the same size as FIGURE_SIZE_MAP, so meters_per_point above converts them too).
        "layers": {
            "order": DASHBOARD_LAYERS,
            "by_layer": layer_meta,
            "style": {
                "fill_palette": map_layers.FILL_PALETTE, "fill_opacity": map_layers.FILL_OPACITY,
                "fill_edge_color": "#777777", "fill_edge_points": 0.4,          # notebook draw_layer, "fill"
                "single_fill_color": map_layers.SINGLE_FILL_COLOR, "single_opacity": 0.6,
                "single_edge_points": 0.4,                                       # notebook draw_layer, "single"
                "line_color": map_layers.LINE_COLOR, "line_points": 2,           # notebook draw_layer, "line"
                "point_color": map_layers.POINT_COLOR,
                "point_area_points2": map_layers.POINT_SIZE,                     # matplotlib markersize = area in pt^2
                "point_edge_color": "white", "point_edge_points": 0.5,
                "label_font_points": map_layers.LAYER_LABEL_FONT_SIZE, "label_color": map_layers.LAYER_LABEL_COLOR,
                "ward_number_font_points": map_layers.WARD_NUMBER_FONT_SIZE,
                "ward_outline_points": map_layers.WARD_OUTLINE_WIDTH_LARGE_MAP,
            },
        },
        "about_heading": ABOUT_TEXT_HEADING,
        "about_text": ABOUT_TEXT,
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
        },
        "sources": {
            "votes, people, attachments": "Chicago City Clerk eLMS API (api.chicityclerkelms.chicago.gov)",
            "tenure history": "DataMade chicago-council-scrapers nightly export",
            "ward boundaries": "Chicago Data Portal, Boundaries - Wards (2023-)",
        },
    }, "meta.json")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    default_event_id, counted_event_count, alder_records = export_alders_and_votes()
    labels_by_ward, meters_per_point = real_map_label_layout(alder_records)
    export_shapes(labels_by_ward)
    # The layer sizes in points reuse meters_per_point, measured on FIGURE_SIZE_MAP.
    assert tuple(map_layers.FIGURE_SIZE_LARGE) == tuple(ward_maps.FIGURE_SIZE_MAP), "layer figure size differs"
    layer_meta = export_layers()
    export_meta(default_event_id, counted_event_count, meters_per_point, layer_meta)
