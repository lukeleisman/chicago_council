"""Run after scripts/export_dashboard_data.py when only Map View label positions changed.

The export re-projects every shape, which rewrites coordinates with last-digit rounding noise
(1e-6 degree, ~0.1 m; seen 2026-10-05). To keep commits to real changes, this restores the layer
files that carry no labels from git HEAD, and for the files whose label positions changed it keeps
HEAD's file and copies in only the label properties from the new export.
Check `git diff --stat docs/data` afterwards. Don't use it when shapes or other properties really
changed (e.g. new layer data); then commit the full export.

Usage:
  python scripts/keep_label_changes_only.py
"""

import json
import subprocess

# File -> label properties to take from the new export.
LABEL_KEYS = {"docs/data/layer_community_areas.geojson": ["label_lon", "label_lat"],
              "docs/data/layer_neighborhoods.geojson": ["label_lon", "label_lat"],
              "docs/data/layer_zip_codes.geojson": ["label_lon", "label_lat"],
              "docs/data/layer_police_districts.geojson": ["label_lon", "label_lat"],
              "docs/data/wards_real.geojson": ["labels"]}
# Files with no labels: restored from HEAD as they are.
UNCHANGED = ["docs/data/layer_parks.geojson", "docs/data/layer_cta_rail_lines.geojson",
             "docs/data/layer_cta_rail_stations.geojson", "docs/data/layer_cps_schools_sy2526.geojson",
             "docs/data/layer_ward_offices.geojson"]

subprocess.run(["git", "checkout", "--"] + UNCHANGED, check=True)
for path, keys in LABEL_KEYS.items():
    head = json.loads(subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, text=True, check=True).stdout)
    new = json.load(open(path))
    changed = 0
    for old_feature, new_feature in zip(head["features"], new["features"], strict=True):
        # Same feature in the same order (ward number, or layer label text).
        for check_key in ("ward", "label"):
            assert old_feature["properties"].get(check_key) == new_feature["properties"].get(check_key), path
        for key in keys:
            changed += old_feature["properties"].get(key) != new_feature["properties"][key]
            old_feature["properties"][key] = new_feature["properties"][key]
    # Same formatting as export_dashboard_data.write_json.
    open(path, "w").write(json.dumps(head, separators=(",", ":"), ensure_ascii=False))
    print(f"{path}: label properties differing from HEAD: {changed}")
