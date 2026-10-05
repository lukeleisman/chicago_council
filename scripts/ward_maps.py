"""Shared drawing helpers for the ward-map views (notebooks/ward_views.ipynb).

Mirrors the settings and helpers in notebooks/map_layers_review.ipynb
(PLOT_CRS, BASEMAP_OPTIONS, TEXT_HALO, ward outlines + labels) so every view
draws wards the same way. Each constant below is a default; the notebook can
pass a different value to any function.

Ward key: data/tables/people.csv stores elms_ward zero-padded ("01"), the
ward layer stores "1". load_ward_shapes() pads the layer side to two digits,
the same conversion as sessions/2026-10-04_build_tables_review_notebook.py
(ward_offices_view["ward"] = ...astype(int).map("{:02d}".format)). The
layer's original value is kept as ward_raw.
"""

from pathlib import Path

import contextily
import geopandas as gpd
from matplotlib import patheffects

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

LAYERS_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "layers"
WARD_LAYER_FILE = "wards_2023.geojson"

# Coordinate system for plotting. Web Mercator is what basemap tiles use
# (same as map_layers_review).
PLOT_CRS = "EPSG:3857"

# Ward shapes: "real" = 2023 ward boundaries. "tiles" = equal-size ward tiles
# (plan Phase 4; not built yet, so asking for it raises an error).
MAP_SHAPES_OPTIONS = ("real", "tiles")

# Street basemap choices. The two Esri entries are map_layers_review's
# BASEMAP_OPTIONS (tested 2026-09-29: CARTO needs a key, OpenStreetMap blocks
# contextily). "none" draws no basemap and needs no internet.
BASEMAP_OPTIONS = {
    "street": contextily.providers.Esri.WorldStreetMap,   # colored, street names, parks
    "gray": contextily.providers.Esri.WorldGrayCanvas,    # light gray, minimal labels
    "none": None,
}

# Ward outlines.
WARD_OUTLINE_COLOR = "black"
WARD_OUTLINE_WIDTH = 1.0

# Ward labels.
WARD_LABEL_FONT_SIZE = 7

# White outline around text so labels stay readable over any fill or basemap
# (same as map_layers_review).
TEXT_HALO = [patheffects.withStroke(linewidth=2.5, foreground="white")]

# ---------------------------------------------------------------------------


def load_ward_shapes(map_shapes="real", layers_dir=LAYERS_DIR):
    """Ward shapes in PLOT_CRS, with `ward` zero-padded ("01".."50") and the original value in `ward_raw`."""
    if map_shapes not in MAP_SHAPES_OPTIONS:
        raise ValueError(f"map_shapes must be one of {MAP_SHAPES_OPTIONS}, got {map_shapes!r}")
    if map_shapes == "tiles":
        raise NotImplementedError("ward tiles are plan Phase 4 (scripts/build_ward_tiles.py), not built yet")
    wards = gpd.read_file(Path(layers_dir) / WARD_LAYER_FILE)
    wards["ward_raw"] = wards["ward"]
    wards["ward"] = wards["ward_raw"].astype(int).map("{:02d}".format)
    return wards[["ward", "ward_raw", "geometry"]].to_crs(PLOT_CRS)


def draw_ward_outlines(axis, wards, color=WARD_OUTLINE_COLOR, line_width=WARD_OUTLINE_WIDTH):
    wards.boundary.plot(ax=axis, color=color, linewidth=line_width)


def draw_ward_labels(axis, wards, label_by_ward, font_size=WARD_LABEL_FONT_SIZE, offset_points_by_ward=None):
    """Write label_by_ward[ward] at each ward's representative point (a point guaranteed inside the shape).

    offset_points_by_ward: {ward: (dx, dy)} hand nudges in typographic points (1/72 inch on the
    figure, so they depend on figure size); wards not listed are not moved.
    Returns {ward: annotation} so label_overlaps() can measure the drawn labels.
    """
    offset_points_by_ward = offset_points_by_ward or {}
    annotation_by_ward = {}
    for ward, label_point in zip(wards["ward"], wards.representative_point()):
        annotation_by_ward[ward] = axis.annotate(
            label_by_ward[ward], (label_point.x, label_point.y),
            xytext=offset_points_by_ward.get(ward, (0, 0)), textcoords="offset points",
            fontsize=font_size, ha="center", va="center", path_effects=TEXT_HALO, annotation_clip=True)
    return annotation_by_ward


def label_overlaps(figure, annotation_by_ward):
    """Every pair of drawn labels whose text boxes overlap on the rendered figure.

    Returns a list of (ward_a, ward_b, overlap_width_pixels, overlap_height_pixels).
    The box is the text itself, not its white halo.
    """
    renderer = figure.canvas.get_renderer()
    box_by_ward = {ward: annotation.get_window_extent(renderer) for ward, annotation in annotation_by_ward.items()}
    wards_in_order = sorted(box_by_ward)
    overlaps = []
    for position, ward_a in enumerate(wards_in_order):
        for ward_b in wards_in_order[position + 1:]:
            box_a, box_b = box_by_ward[ward_a], box_by_ward[ward_b]
            overlap_width = min(box_a.x1, box_b.x1) - max(box_a.x0, box_b.x0)
            overlap_height = min(box_a.y1, box_b.y1) - max(box_a.y0, box_b.y0)
            if overlap_width > 0 and overlap_height > 0:
                overlaps.append((ward_a, ward_b, round(overlap_width, 1), round(overlap_height, 1)))
    return overlaps


def crop_to_square(image, vertical_anchor):
    """Square crop for display only (the file is not changed). Keeps the full width of a tall
    image (or full height of a wide one). vertical_anchor: "top" keeps the top of a tall image,
    "center" cuts equally from top and bottom."""
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    if vertical_anchor == "top":
        top = 0
    elif vertical_anchor == "center":
        top = (height - side) // 2
    else:
        raise ValueError(f"vertical_anchor must be 'top' or 'center', got {vertical_anchor!r}")
    return image.crop((left, top, left + side, top + side))


def add_basemap(axis, basemap_choice):
    """Draw the basemap named basemap_choice (a key of BASEMAP_OPTIONS) under what is already on axis."""
    tiles = BASEMAP_OPTIONS[basemap_choice]
    if tiles is not None:
        contextily.add_basemap(axis, source=tiles, crs=PLOT_CRS)
