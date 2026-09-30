"""Download map layers (boundaries and points) from the Chicago Data Portal.

Each layer is saved verbatim as GeoJSON under data/raw/layers/<layer_name>.geojson,
plus data/raw/layers/manifest.json recording the URL, dataset ID and
retrieval time for every file.

Usage:
  python scripts/fetch_layers.py            # fetch any layer not yet on disk
  python scripts/fetch_layers.py --force    # re-fetch everything
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PORTAL_BASE_URL = "https://data.cityofchicago.org"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "layers"

REQUEST_TIMEOUT_SECONDS = 120

# Upper bound on rows per request for the /resource endpoint (Socrata defaults to 1,000).
# Largest layer here is precincts (~1,300 rows), so 50,000 leaves wide margin.
RESOURCE_ROW_LIMIT = 50000

# Socrata offers two GeoJSON download URLs. Neither works for every dataset
# (tested 2026-09-29), so each layer below names the one that returned full data:
#   "resource":   /resource/{id}.geojson?$limit=N
#   "geospatial": /api/geospatial/{id}?method=export&format=GeoJSON
#
# Several portal entries are "map" views wrapping an underlying dataset; the
# map-view IDs return empty GeoJSON, so the underlying dataset ID is used and
# the map-view ID is recorded in portal_page_id for reference.
#
# Columns: layer_name, dataset_id, download_method, portal_page_id, notes
LAYERS = [
    ("wards_2023", "p293-wvbd", "resource", "p293-wvbd",
     "Boundaries - Wards (2023-). The 50 current wards."),
    ("community_areas", "igwz-8jzy", "resource", "igwz-8jzy",
     "Boundaries - Community Areas. The 77 official community areas."),
    ("neighborhoods", "y6yq-dbs2", "geospatial", "bbvz-uum9",
     "Boundaries - Neighborhoods (Neighborhoods_2012b). Informal neighborhood names; last updated 2012."),
    ("census_tracts_2020", "7qjk-677h", "resource", "7qjk-677h",
     "Boundaries - Census Tracts - 2020."),
    ("precincts_2023", "6piy-vbxa", "resource", "6piy-vbxa",
     "Boundaries - Ward Precincts (2023-2024)."),
    ("zip_codes", "unjd-c2ca", "resource", "gdcf-axmw",
     "Boundaries - ZIP Codes."),
    ("police_districts", "24zt-jpfn", "resource", "fthy-xz3r",
     "Boundaries - Police Districts (current) = PoliceDistrictDec2012."),
    ("parks", "ejsh-fztr", "resource", "ej32-qgdr",
     "Parks - Chicago Park District Park Boundaries (current) = CPD_Parks; updated 2022."),
    ("cta_rail_lines", "xbyr-jnvx", "resource", "xbyr-jnvx",
     "CTA - 'L' (Rail) Lines."),
    ("cta_rail_stations", "3tzw-cg4m", "resource", "3tzw-cg4m",
     "CTA - 'L' (Rail) Stations."),
    ("cps_schools_sy2526", "pb6d-zzuh", "resource", "pb6d-zzuh",
     "Chicago Public Schools - School Locations SY2526 (latest found)."),
    ("ward_offices", "htai-wnw4", "resource", "htai-wnw4",
     "Ward Offices (alderperson office addresses)."),
]

# ---------------------------------------------------------------------------


def download_url(dataset_id, download_method):
    if download_method == "resource":
        return f"{PORTAL_BASE_URL}/resource/{dataset_id}.geojson?$limit={RESOURCE_ROW_LIMIT}"
    if download_method == "geospatial":
        return f"{PORTAL_BASE_URL}/api/geospatial/{dataset_id}?method=export&format=GeoJSON"
    raise ValueError(f"unknown download_method {download_method!r}")


def main(force_refetch):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for layer_name, dataset_id, download_method, portal_page_id, notes in LAYERS:
        output_path = OUTPUT_DIR / f"{layer_name}.geojson"
        if output_path.exists() and not force_refetch:
            print(f"skip   {layer_name} (on disk)")
            continue
        url = download_url(dataset_id, download_method)
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw_bytes = response.read()
        feature_count = len(json.loads(raw_bytes)["features"])
        output_path.write_bytes(raw_bytes)
        manifest[layer_name] = {
            "dataset_id": dataset_id,
            "portal_page": f"{PORTAL_BASE_URL}/d/{portal_page_id}",
            "download_url": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "feature_count": feature_count,
            "bytes": len(raw_bytes),
            "notes": notes,
        }
        print(f"saved  {layer_name}: {feature_count} features, {len(raw_bytes) / 1e6:.1f} MB")

    manifest_path.write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main(force_refetch="--force" in sys.argv)
