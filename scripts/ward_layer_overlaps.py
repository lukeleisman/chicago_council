"""Ward x map-layer overlap table: which community areas, zip codes, parks, stations, ... are in each ward.

For the dashboard's Wards tab, Tile View (plan Step 5). Two steps:
  1. MEASURE: every ward/feature pair that touches is written with its raw numbers (no pair dropped).
  2. SUMMARIZE: WARD_SUMMARY_RULES (user, 2026-10-05) pick, per layer, which features count as "in"
     a ward, and what the dashboard shows. Written to docs/data/ward_layer_summary.json.

Computed on the UNSIMPLIFIED shapes (data/raw/layers/, scripts/fetch_layers.py) in SIMPLIFY_CRS
(IL State Plane East, feet; areas and lengths are converted to meters below). Wards come from
ward_maps.load_ward_shapes("real") (ward zero-padded "01".."50", as everywhere else).

Output (data/tables/, gitignored like the other tables):
  ward_layer_overlaps.csv   one row per (layer, ward, feature) that intersects. Columns:
    layer, kind, ward, feature_row (row number in the raw layer file), feature_name (NAME_COLUMN),
    feature_name_alternative (ALTERNATIVE_NAME_COLUMN, blank if none),
    polygons: overlap_area_m2, ward_area_m2, feature_area_m2, share_of_ward, share_of_feature
    lines:    overlap_length_m, feature_length_m, share_of_feature
    points:   (a point row means the point is inside or on the ward's edge)
    raw_ward_attribute: the layer's own `ward` column where it has one (parks, ward_offices);
                        shown for comparison only; used ONLY where WARD_SUMMARY_RULES says so
                        (ward_offices, user 2026-10-05).

Output (docs/data/, committed, read by docs/dashboard/app.js):
  ward_layer_summary.json   {layer: {"tile": "list"|"count", "source_layer", "rule",
                             "by_ward": {ward: {"names": [...], "shares": [...] or null}}}}
  ward_areas.json           {"unit", "method", "by_ward": {ward: {"area_m2", "area_sq_mi"}}}: each ward's
                            area, measured exactly as ward_area_m2 above (Wards tab "Street map" tiles,
                            user 2026-10-05: "perhaps ward area"). Area of the boundary polygon as
                            published, so any water inside a ward's boundary counts.

Usage:
  python scripts/ward_layer_overlaps.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_dashboard_data
import map_layers
import ward_maps

# ---------------------------------------------------------------------------
# Configuration — every choice made in this script lives here.
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_DIR / "data" / "tables" / "ward_layer_overlaps.csv"
SUMMARY_PATH = REPO_DIR / "docs" / "data" / "ward_layer_summary.json"
WARD_AREAS_PATH = REPO_DIR / "docs" / "data" / "ward_areas.json"

# Layers measured: the dashboard's Wards tab layers (export DASHBOARD_LAYERS).
LAYERS = export_dashboard_data.DASHBOARD_LAYERS

# Measured in IL State Plane East (feet), the same CRS the export simplifies in.
MEASURE_CRS = export_dashboard_data.SIMPLIFY_CRS
SQUARE_METERS_PER_SQUARE_FOOT = 0.3048 ** 2
SQUARE_METERS_PER_SQUARE_MILE = 1609.344 ** 2
METERS_PER_FOOT = 0.3048

# Name written for each feature. Polygon layers with a label use their LAYER_STYLE label column
# (the name drawn on the map). The others: the plan's hover names (export LAYER_HOVER_NAME_COLUMN),
# and for parks and rail lines the columns below.
# OPEN QUESTION (parks): `park` = official name in capitals, e.g. "MCGUANE (JOHN)"; `label` = short
# name, e.g. "McGuane". Both are written (feature_name / feature_name_alternative); pick one for tiles.
# OPEN QUESTION (rail lines): `lines` is the raw service list, e.g. "Brown, Purple (Express), Red";
# names are written as in the data and not split or normalized here.
NAME_COLUMN = {
    layer: map_layers.LAYER_STYLE[layer]["label_column"]
    for layer in LAYERS if map_layers.LAYER_STYLE[layer]["label_column"]
}
NAME_COLUMN.update(export_dashboard_data.LAYER_HOVER_NAME_COLUMN)
NAME_COLUMN.update({"parks": "park", "cta_rail_lines": "lines"})
ALTERNATIVE_NAME_COLUMN = {"parks": "label", "cta_rail_lines": "description"}

# Layers whose raw data carries its own ward number (shown for comparison; used only by the
# "raw_ward_attribute" rule below).
RAW_WARD_COLUMN = {"parks": "ward", "ward_offices": "ward"}

# Which features count as "in" a ward, per Wards-tab layer, and what the tile shows (user, 2026-10-05).
#   keep:  "share_of_ward"      feature covers at least `minimum` of the ward's area
#          "share_of_feature"   at least `minimum` of the feature's area is in the ward
#          "inside"             point is inside the ward (or on its edge; none are, measured 2026-10-05)
#          "raw_ward_attribute" the layer's own ward column (ward offices: wards 2 and 34 list City Hall,
#                               which lies in ward 42; by location they'd have no office)
#   name:  "feature_name" or "feature_name_alternative" (see NAME_COLUMN / ALTERNATIVE_NAME_COLUMN)
#   order: "largest_share_first" (share_of_ward, descending) or "alphabetical"
#   tile:  "list" = names on the tile; "count" = number on the tile, names in hover card and table
#   source_layer: the layer whose features are summarized (rail lines show the station count for now:
#                 user, 2026-10-05, "just do station count"; line names wait for the CTA repo's code)
WARD_SUMMARY_RULES = {
    "community_areas":    {"source_layer": "community_areas", "keep": "share_of_ward", "minimum": 0.01,
                           "name": "feature_name", "order": "largest_share_first", "tile": "list"},
    "neighborhoods":      {"source_layer": "neighborhoods", "keep": "share_of_ward", "minimum": 0.01,
                           "name": "feature_name", "order": "largest_share_first", "tile": "list"},
    "zip_codes":          {"source_layer": "zip_codes", "keep": "share_of_ward", "minimum": 0.01,
                           "name": "feature_name", "order": "largest_share_first", "tile": "list"},
    "police_districts":   {"source_layer": "police_districts", "keep": "share_of_ward", "minimum": 0.01,
                           "name": "feature_name", "order": "largest_share_first", "tile": "list"},
    # Parks: rule B, >= 1% of the PARK in the ward (1% of the ward drops most parks); short `label` names.
    "parks":              {"source_layer": "parks", "keep": "share_of_feature", "minimum": 0.01,
                           "name": "feature_name_alternative", "order": "largest_share_first", "tile": "count"},
    "cta_rail_lines":     {"source_layer": "cta_rail_stations", "keep": "inside",
                           "name": "feature_name", "order": "alphabetical", "tile": "count"},
    "cta_rail_stations":  {"source_layer": "cta_rail_stations", "keep": "inside",
                           "name": "feature_name", "order": "alphabetical", "tile": "count"},
    "cps_schools_sy2526": {"source_layer": "cps_schools_sy2526", "keep": "inside",
                           "name": "feature_name", "order": "alphabetical", "tile": "count"},
    "ward_offices":       {"source_layer": "ward_offices", "keep": "raw_ward_attribute",
                           "name": "feature_name", "order": "alphabetical", "tile": "list"},
}

# ---------------------------------------------------------------------------


def load_layer(layer_name):
    frame = gpd.read_file(ward_maps.LAYERS_DIR / f"{layer_name}.geojson").to_crs(MEASURE_CRS).reset_index(drop=True)
    frame["feature_row"] = frame.index
    frame["feature_name"] = frame[NAME_COLUMN[layer_name]].astype(str)
    alternative = ALTERNATIVE_NAME_COLUMN.get(layer_name)
    frame["feature_name_alternative"] = frame[alternative].astype(str) if alternative else ""
    raw_ward = RAW_WARD_COLUMN.get(layer_name)
    frame["raw_ward_attribute"] = frame[raw_ward] if raw_ward else None
    return frame


def overlaps_for_layer(layer_name, wards):
    """Every (ward, feature) pair that intersects, with raw measurements."""
    kind = map_layers.LAYER_STYLE[layer_name]["kind"]
    frame = load_layer(layer_name)
    invalid_count = int((~frame.geometry.is_valid).sum())
    # Pairs that touch at all (spatial index); measured one by one below.
    # Join column renamed: parks and ward_offices have their own `ward` column.
    pairs = gpd.sjoin(frame, wards[["ward", "geometry"]].rename(columns={"ward": "joined_ward"}),
                      how="inner", predicate="intersects")
    ward_shape_by_ward = dict(zip(wards.ward, wards.geometry))
    rows = []
    for pair in pairs.itertuples():
        feature_shape = pair.geometry
        ward_shape = ward_shape_by_ward[pair.joined_ward]
        row = {"layer": layer_name, "kind": kind, "ward": pair.joined_ward, "feature_row": pair.feature_row,
               "feature_name": pair.feature_name, "feature_name_alternative": pair.feature_name_alternative,
               "raw_ward_attribute": pair.raw_ward_attribute}
        if kind in ("fill", "single"):
            overlap_area = feature_shape.intersection(ward_shape).area * SQUARE_METERS_PER_SQUARE_FOOT
            ward_area = ward_shape.area * SQUARE_METERS_PER_SQUARE_FOOT
            feature_area = feature_shape.area * SQUARE_METERS_PER_SQUARE_FOOT
            row.update(overlap_area_m2=overlap_area, ward_area_m2=ward_area, feature_area_m2=feature_area,
                       share_of_ward=overlap_area / ward_area, share_of_feature=overlap_area / feature_area)
        elif kind == "line":
            overlap_length = feature_shape.intersection(ward_shape).length * METERS_PER_FOOT
            feature_length = feature_shape.length * METERS_PER_FOOT
            row.update(overlap_length_m=overlap_length, feature_length_m=feature_length,
                       share_of_feature=overlap_length / feature_length)
        rows.append(row)
    table = pd.DataFrame(rows)
    on_two_wards = 0
    if kind == "point":
        on_two_wards = int((table.groupby("feature_row").size() > 1).sum())
    print(f"{layer_name} ({kind}): {len(frame)} features, {invalid_count} invalid geometries, "
          f"{len(table)} ward/feature pairs, {table.feature_row.nunique()} features touch a ward, "
          f"{len(frame) - table.feature_row.nunique()} touch none"
          + (f", {on_two_wards} points on two wards' shared edge" if kind == "point" else ""))
    return table


def summarize(overlaps):
    """Apply WARD_SUMMARY_RULES to the overlap table. Prints, per layer, how many names per ward."""
    all_wards = [f"{number:02d}" for number in range(1, 51)]
    summary = {}
    for layer_name, rule in WARD_SUMMARY_RULES.items():
        if rule["keep"] == "raw_ward_attribute":
            # Not from the overlap table: every feature goes to the ward its own column names.
            frame = load_layer(rule["source_layer"])
            kept = pd.DataFrame({"ward": frame.raw_ward_attribute.astype(int).map("{:02d}".format),
                                 "feature_name": frame.feature_name,
                                 "feature_name_alternative": frame.feature_name_alternative,
                                 "share_of_ward": None})
        else:
            rows = overlaps[overlaps.layer == rule["source_layer"]]
            kept = rows if rule["keep"] == "inside" else rows[rows[rule["keep"]] >= rule["minimum"]]
        if rule["order"] == "largest_share_first":
            kept = kept.sort_values(["ward", "share_of_ward"], ascending=[True, False])
        else:
            kept = kept.sort_values(["ward", rule["name"]])
        # Shares only where the rule is about the ward's area (a park's share of the ward is ~0%).
        with_shares = rule["keep"] == "share_of_ward"
        by_ward = {}
        for ward in all_wards:
            ward_rows = kept[kept.ward == ward]
            by_ward[ward] = {"names": ward_rows[rule["name"]].tolist(),
                             # share of the WARD's area each feature covers (round to 0.1%)
                             "shares": ward_rows.share_of_ward.round(3).tolist() if with_shares else None}
        counts = pd.Series({ward: len(entry["names"]) for ward, entry in by_ward.items()})
        print(f"  {layer_name:<20} {rule['keep']:<19} names per ward: min {counts.min()}, median "
              f"{counts.median():.0f}, max {counts.max()}; wards with none: {(counts == 0).sum()}")
        summary[layer_name] = {"tile": rule["tile"], "source_layer": rule["source_layer"],
                               "rule": {key: value for key, value in rule.items() if key != "tile"},
                               "by_ward": by_ward}
    SUMMARY_PATH.write_text(json.dumps(summary, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {SUMMARY_PATH.relative_to(REPO_DIR)} ({SUMMARY_PATH.stat().st_size / 1000:,.0f} KB)")


def write_ward_areas(wards):
    """docs/data/ward_areas.json: each ward's area, the same measurement as ward_area_m2 in the table
    (unsimplified shape, MEASURE_CRS square feet -> square meters), plus square miles."""
    by_ward = {}
    for ward, shape in zip(wards.ward, wards.geometry):
        area_m2 = shape.area * SQUARE_METERS_PER_SQUARE_FOOT
        by_ward[ward] = {"area_m2": round(area_m2), "area_sq_mi": round(area_m2 / SQUARE_METERS_PER_SQUARE_MILE, 3)}
    areas = pd.Series({ward: entry["area_sq_mi"] for ward, entry in by_ward.items()})
    print(f"ward areas (sq mi): min {areas.min()} (ward {areas.idxmin()}), median {areas.median():.2f}, "
          f"max {areas.max()} (ward {areas.idxmax()}), total {areas.sum():.1f}")
    WARD_AREAS_PATH.write_text(json.dumps({
        "unit": "square miles (area_sq_mi) and square meters (area_m2)",
        "method": f"Unsimplified 2023 ward boundary polygons, area in {MEASURE_CRS} (IL State Plane East, feet), "
                  "converted; includes any water inside a ward's boundary.",
        "by_ward": dict(sorted(by_ward.items())),
    }, indent=0))
    print(f"wrote {WARD_AREAS_PATH.relative_to(REPO_DIR)}")


if __name__ == "__main__":
    wards = ward_maps.load_ward_shapes("real").to_crs(MEASURE_CRS)
    tables = [overlaps_for_layer(layer_name, wards) for layer_name in LAYERS]
    overlaps = pd.concat(tables, ignore_index=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    overlaps.to_csv(OUTPUT_PATH, index=False)
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_DIR)}: {len(overlaps):,} rows")
    summarize(overlaps)
    write_ward_areas(wards)
