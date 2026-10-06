"""Styling settings and the neighbor coloring for the map layers (community areas, zip codes, ...).

Moved here 2026-10-05 from notebooks/map_layers_review.ipynb cells 9-10, so the notebook and the
dashboard export (scripts/export_dashboard_data.py) draw every layer the same way. Values and
comments are unchanged from the notebook; the notebook now imports them from here.

Layers themselves come from scripts/fetch_layers.py -> data/raw/layers/<name>.geojson.
"""

# ---------------------------------------------------------------------------
# Styling settings for the per-layer maps (map_layers_review "One large map per layer")
# ---------------------------------------------------------------------------

# How each layer is drawn and which column (if any) labels it.
#   "fill"   = polygon layer, neighbor-aware multi-color fill
#   "single" = polygon layer, one color (used for parks: scattered, not a tiling of the city)
#   "line" / "point" = drawn as lines / markers
# label_column = None means no labels (e.g. ~800 census tracts are too dense to label legibly).
LAYER_STYLE = {
    "wards_2023":         {"kind": "fill",   "label_column": None},  # ward numbers are drawn anyway
    "community_areas":    {"kind": "fill",   "label_column": "community"},
    "neighborhoods":      {"kind": "fill",   "label_column": "pri_neigh"},
    "census_tracts_2020": {"kind": "fill",   "label_column": None},
    "precincts_2023":     {"kind": "fill",   "label_column": None},
    "zip_codes":          {"kind": "fill",   "label_column": "zip"},
    "police_districts":   {"kind": "fill",   "label_column": "dist_num"},
    "parks":              {"kind": "single", "label_column": None},
    "cta_rail_lines":     {"kind": "line",   "label_column": None},
    "cta_rail_stations":  {"kind": "point",  "label_column": None},
    "cps_schools_sy2526": {"kind": "point",  "label_column": None},
    "ward_offices":       {"kind": "point",  "label_column": None},
}

# Fill palette: soft colors so the basemap and ward lines stay visible. Extra
# entries beyond four are there in case the simple coloring method needs them.
FILL_PALETTE = ["#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462", "#b3de69"]
FILL_OPACITY = 0.45
SINGLE_FILL_COLOR = "#2ca25f"      # parks
LINE_COLOR = "#6a3d9a"             # CTA rail lines
POINT_COLOR = "#d7301f"            # stations, schools, ward offices
POINT_SIZE = 14

# Two shapes are "neighbors" (must get different colors) if closer than this.
# NOTE: the notebook applies this to the EPSG:3857 (Web Mercator) frame, so the distance is in
# Mercator meters, about 1.34x ground meters at Chicago's latitude (5 Mercator m = ~3.7 m ground).
NEIGHBOR_DISTANCE_METERS = 5

LAYER_LABEL_FONT_SIZE = 6
LAYER_LABEL_COLOR = "#333333"
WARD_NUMBER_FONT_SIZE = 9
WARD_OUTLINE_WIDTH_LARGE_MAP = 1.4
FIGURE_SIZE_LARGE = (12, 15)

# ---------------------------------------------------------------------------


def neighbor_color_indexes(frame_in_meters):
    """Assign each shape a palette index so that neighboring shapes differ.

    Greedy coloring, most-neighbors-first. Returns a list of indexes aligned
    with the rows of frame_in_meters.
    """
    shapes = frame_in_meters.geometry.reset_index(drop=True)
    grown_shapes = shapes.buffer(NEIGHBOR_DISTANCE_METERS)
    spatial_index = shapes.sindex
    neighbors_of = {}
    for row_number, grown_shape in enumerate(grown_shapes):
        candidate_rows = spatial_index.query(grown_shape, predicate="intersects")
        neighbors_of[row_number] = {int(other) for other in candidate_rows if other != row_number}

    color_of = {}
    for row_number in sorted(neighbors_of, key=lambda row: len(neighbors_of[row]), reverse=True):
        colors_taken = {color_of[other] for other in neighbors_of[row_number] if other in color_of}
        color_of[row_number] = next(index for index in range(len(FILL_PALETTE) + 100) if index not in colors_taken)
    return [color_of[row_number] for row_number in range(len(shapes))]
