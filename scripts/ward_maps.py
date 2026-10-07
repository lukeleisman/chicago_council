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
import matplotlib
from matplotlib import patheffects
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.transforms import Bbox

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

LAYERS_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "layers"
WARD_LAYER_FILE = "wards_2023.geojson"
TABLES_DIR = Path(__file__).resolve().parent.parent / "data" / "tables"

# Coordinate system for plotting. Web Mercator is what basemap tiles use
# (same as map_layers_review).
PLOT_CRS = "EPSG:3857"

# Ward shapes: "real" = 2023 ward boundaries. "tiles_grid" = equal-size ward tiles on the
# user's hand-specified grid (plan Phase 4a). "tiles_pushed" = equal-size tiles started at each
# real ward and pushed apart (plan 4b). Both written by scripts/build_ward_tiles.py.
MAP_SHAPES_OPTIONS = ("real", "tiles_grid", "tiles_pushed")
TILE_FILE_BY_MAP_SHAPES = {"tiles_grid": "ward_tiles_grid.geojson", "tiles_pushed": "ward_tiles_pushed.geojson"}

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
# Real-map label layout (notebooks/ward_views.ipynb §1-§4; moved here 2026-10-05 from
# sessions/2026-10-04_build_ward_views_notebook.py so scripts/export_dashboard_data.py draws the
# dashboard's Map View labels the same way). Values and comments unchanged from the notebook.
# Nudges are in typographic points on a FIGURE_SIZE_MAP figure; the export converts them to map
# coordinates with matplotlib's own transform on that same figure size.
# ---------------------------------------------------------------------------

FIGURE_SIZE_MAP = (12, 15)

# Label font on the §1.2 map (user, 2026-10-04: as large as possible). 9 is the largest size for
# which hand nudges were found that leave no two labels overlapping; §1.2's sweep shows counts by size.
MAP_LABEL_FONT_SIZE = 9

# Hand nudges for labels that would otherwise overlap at MAP_LABEL_FONT_SIZE on FIGURE_SIZE_MAP.
# {ward: (right, up)} in typographic points; negative = left / down. Wards not listed sit at
# their representative point. Set by eye on 2026-10-04, checked by ward_maps.label_overlaps.
LABEL_OFFSET_POINTS_BY_WARD = {
    "40": (-4, -22),   # Vasquez, Jr.: down into the lower part of the narrow ward, clear of 48 and 50
    "48": (28, 8),     # Manaa-Hoppenworth: right and up toward the lakefront (text extends over the lake)
    "33": (-12, 0),    # Rodriguez Sanchez: left, clear of 47
    "47": (8, 0),      # Martin: right, clear of 33
    "14": (0, 4),      # Gutierrez: up, clear of 15
    "15": (6, -12),    # Lopez: down and right, clear of 14
    "03": (0, -5),     # Dowell: down, clear of 4
    "04": (0, 5),      # Robinson: up, clear of 3
    "43": (10, 3),     # Knudsen: right and slightly up, clear of 32 and 2
    "35": (-5, 0),     # Quezada: left, clear of 32
    "50": (0, -3),     # Silverstein: down, clear of 49
    "49": (0, 2),      # Hadden: up, clear of 50
}

# Tenure map labels (ward_views §2).
TENURE_NAME_FONT_SIZE = 8            # user, 2026-10-04 (was 7)
TENURE_YEARS_FONT_SIZE = 10          # user, 2026-10-04 (was 12)
# Hand nudges per style, {ward: (right, up)} points, for FIGURE_SIZE_MAP. Set by eye 2026-10-04 and
# checked by ward_maps.label_overlaps (§2.2). Most follow §1's nudges for the same crowded wards.
TENURE_LABEL_OFFSETS_BY_STYLE = {
    "three_lines": {
        "40": (-4, -22), "48": (28, 8),     # north lakefront: as §1
        "33": (-12, 0), "47": (8, 0),       # as §1
        "14": (0, 6), "15": (6, -16),       # as §1, a bit further apart (three lines are taller)
        "03": (0, -9), "04": (0, 8),        # as §1, further apart
        "43": (10, 3), "02": (0, -7),       # Knudsen as §1; Hopkins down, clear of 43
        "35": (-5, 0),                      # as §1
        "50": (0, -3), "49": (0, 2),        # as §1
        "46": (0, 7), "44": (6, 0),         # Clay up, Lawson right: clear of each other and of 32
        "29": (0, -6),                      # Taliaferro down, clear of 36
        "20": (4, 4), "16": (0, -3),        # Taylor up-right, Coleman down: clear of each other
    },
    "two_sizes": {                          # set for names 8 pt / years 10 pt
        "40": (-4, -22),                    # Vasquez, Jr.: as §1
        "48": (14, 8),                      # Manaa-Hoppenworth: right and up, less far east than §1 (user)
        "33": (-18, 0), "47": (8, 0), "46": (6, 0),   # long name lines in a row: spread left/right
        "30": (-8, 0), "31": (2, -6),       # Cruz left, Cardona down: clear of each other and of 35
        "35": (4, 8),                       # Quezada up-right, clear of 31 and 32
        "43": (12, 2),                      # Knudsen right, clear of 32 and 1
        "29": (-6, -4),                     # Taliaferro down-left, clear of 37
        "42": (4, 6),                       # Reilly up-right, clear of 34
        "14": (0, 6), "15": (6, -12),       # as §1
        "03": (0, -8), "04": (0, 8),        # as §1, further apart
        "50": (0, -4), "49": (0, 3),        # as §1, slightly further apart
    },
}

# Absence map labels (ward_views §3).
ABSENCE_NAME_FONT_SIZE = 8                  # same sizes as the tenure "two_sizes" labels
ABSENCE_VALUE_FONT_SIZE = 10
# Hand nudges per label value, {ward: (right, up)} points, for FIGURE_SIZE_MAP. Checked in §3.3.
ABSENCE_LABEL_OFFSETS_BY_VALUE = {
    # Same width class as the tenure "two_sizes" labels: their nudges give no overlaps.
    "percent": TENURE_LABEL_OFFSETS_BY_STYLE["two_sizes"],
    # "12.7% (8/63)" is about 3x wider: 34 wards nudged, set by eye 2026-10-04, mostly sideways
    # apart from the neighbor they hit.
    "both": {
        "40": (-4, -22), "48": (14, 8), "49": (0, 3), "50": (0, -4),          # north lakefront: as tenure
        "33": (-30, 4), "47": (6, -8), "46": (16, 9), "44": (4, -10),         # 33/47/46/44 row
        "30": (-16, 4), "31": (4, -10), "35": (8, 10),                        # 30/31/35
        "36": (-10, 4), "26": (2, 2), "29": (-20, -4), "37": (6, 0),          # 36/26, 29/37
        "01": (2, 8), "02": (8, -10), "43": (20, 2), "42": (4, 6),            # downtown / near north
        "24": (-8, 6), "25": (8, -4), "22": (-12, 0), "12": (8, 0),           # 24/25, 22/12
        "04": (6, 8), "11": (-10, 0), "03": (0, -8),                          # 4/11/3
        "14": (0, 6), "15": (4, -8), "23": (-6, -12), "16": (14, -4),         # 14/15/23/16
        "08": (-20, 0), "07": (12, -10), "19": (-14, 0), "21": (10, 0),       # 8/7, 19/21
    },
}

# ---------------------------------------------------------------------------
# Committee maps (notebooks/ward_views.ipynb §5 and the dashboard's Alders > Committees view; added
# 2026-10-07). Which assignments are current: scripts/council_metrics.py (COMMITTEE_BODY_TYPES,
# CURRENT_COMMITTEE_RULE). Everything below is display only.
# ---------------------------------------------------------------------------

# Fill colors for the "All committee chairs" view: one color per committee, in committee order
# (council_metrics: body type, then name A-Z). User, 2026-10-07: "a more expansive palette" (22
# committees). Options, the first 22 colors of each, copied as hex so no extra package is needed:
#   "glasbey_light" = colorcet 3.0.1 glasbey_light (Glasbey et al. 2007: colors picked to be as far
#                     apart as possible; the "light" set leaves out dark colors, so black labels stay readable)
#   "glasbey"       = colorcet 3.0.1 glasbey (same method, includes dark colors)
#   "tab20_plus"    = matplotlib tab20 (10 strong, then their 10 light versions) + 2 from tab20b
# No 22-color set keeps every pair apart for color-blind readers; the short label on each ward carries
# the committee's identity, the color helps. ward_views §5.3 draws every option.
COMMITTEE_PALETTE_OPTIONS = {
    "glasbey_light": ["#d60000", "#018700", "#b500ff", "#05acc6", "#97ff00", "#ffa52f", "#ff8ec8", "#79525e",
                      "#00fdcf", "#afa5ff", "#93ac83", "#9a6900", "#366962", "#d3008c", "#fdf490", "#c86e66",
                      "#9ee2ff", "#00c846", "#a877ac", "#b8ba01", "#f4bfb1", "#ff28fd"],
    "glasbey": ["#d60000", "#8c3bff", "#018700", "#00acc6", "#97ff00", "#ff7ed1", "#6b004f", "#ffa52f",
                "#573b00", "#005659", "#0000dd", "#00fdcf", "#a17569", "#bcb6ff", "#95b577", "#bf03b8",
                "#645474", "#790000", "#0774d8", "#fdf490", "#004b00", "#8e7900"],
    "tab20_plus": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
                   "#bcbd22", "#17becf", "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94",
                   "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5", "#393b79", "#e7cb94"],
}
COMMITTEE_PALETTE = "glasbey_light"   # my pick for the first draft (lightest of the three); not chosen by the user
COMMITTEE_FILL_OPACITY = 0.85         # same as the tenure / absence / vote maps
# Wards not colored in a view (non-chairs on the chairs view, non-members on a one-committee view).
COMMITTEE_UNCOLORED_FILL = "#ffffff"

# Which committees get a color on the overview maps below (eLMS bodyType). User, 2026-10-07: leave the
# joint committees out ("the correct call"): each joint committee's chairs and vice chairs are the chairs
# and vice chairs of the two committees it joins (all 19 checked in ward_views §5.1).
CHAIRS_VIEW_BODY_TYPES = ["Committee", "Sub-Committee"]

# Overview maps: dropdown entries above the single committees (user, 2026-10-07), in this order; the first
# is the default (user: chairs). Each colors a ward by the CHAIRS_VIEW_BODY_TYPES committees on which its
# alder holds one of `roles`.
#   committee_line = the short committee label as a third label line (user: none on the combined map,
#                    "labels would get too crowded"; it shows colors / stripes and the names only)
OVERVIEW_VIEWS = {
    "all_chairs": {"label": "All committee chairs", "roles": ["Chair"], "committee_line": True},
    "all_vice_chairs": {"label": "All committee vice chairs", "roles": ["Vice Chair"], "committee_line": True},
    "all_chairs_and_vice_chairs": {"label": "All chairs and vice chairs", "roles": ["Chair", "Vice Chair"],
                                   "committee_line": False},
}
# A ward with more than one colored role (today: 9 wards on the combined map, a chair and a vice chair
# each; nobody chairs two, nobody vice-chairs two): 45° stripes, one per committee color, each this wide
# (points on the FIGURE_SIZE_MAP figure; the dashboard converts). Chair stripe first.
MULTI_CHAIR_STRIPE_POINTS = 4
# Vice chair fill on the combined map (ward_views §5.3 draws both):
#   "same"    = the committee's color, as for the chair (role shown only by ★ bold / ☆ italic)
#   "lighter" = the committee's color at VICE_CHAIR_LIGHTER_OPACITY_FACTOR x COMMITTEE_FILL_OPACITY
# My pick for the first draft: "same"; not chosen by the user.
COMBINED_VIEW_VICE_CHAIR_FILL = "same"
VICE_CHAIR_LIGHTER_OPACITY_FACTOR = 0.4

# One-committee view fill (any committee from the dropdown):
#   "committee_color" = the committee's color from the chairs view (joint committees, which have none,
#                       get COMMITTEE_MEMBER_FALLBACK_FILL)
#   "fixed"           = COMMITTEE_MEMBER_FALLBACK_FILL for every committee
COMMITTEE_VIEW_FILL = "committee_color"
COMMITTEE_MEMBER_FALLBACK_FILL = "#2a78d6"   # blue

# Committee names shown (legend, hover, dropdown):
#   "collapse_spaces" = eLMS body name with runs of spaces made single ("Joint Committee:   Finance; Aviation"
#                       -> "Joint Committee: Finance; Aviation")
#   "as_recorded"     = eLMS body name unchanged
COMMITTEE_NAME_DISPLAY = "collapse_spaces"
# Short label on the map: eLMS bodyAbbreviation ("Zoning", "Budget", "Rules", "Traffic", ...), except
# these, {eLMS body name: short label}. My picks (2026-10-07), shorter for the map; not chosen by the user.
COMMITTEE_SHORT_LABEL_OVERRIDES = {
    "Committee on Finance: Subcommittee on Revenue": "Revenue",                            # eLMS: "Subcommittee on Revenue"
    "Committee on Workforce Development: Subcommittee on Youth Employment": "Youth Employment",  # eLMS: "Subcommittee on Youth Employment"
}

# Role marks (user, 2026-10-07: stars; bold chair, italic vice chair). Mark goes after the last name.
CHAIR_MARK = "\u2605"           # ★
VICE_CHAIR_MARK = "\u2606"      # ☆
CHAIR_FONT_WEIGHT = "bold"
VICE_CHAIR_FONT_STYLE = "italic"
# Overview maps mark the roles of that map (an alder with both on the combined map: "★ ☆", bold italic);
# one-committee maps mark the role on that committee.

# ---------------------------------------------------------------------------


def load_ward_shapes(map_shapes="real", layers_dir=LAYERS_DIR):
    """Ward shapes in PLOT_CRS, with `ward` zero-padded ("01".."50") and the original value in `ward_raw`."""
    if map_shapes not in MAP_SHAPES_OPTIONS:
        raise ValueError(f"map_shapes must be one of {MAP_SHAPES_OPTIONS}, got {map_shapes!r}")
    if map_shapes in TILE_FILE_BY_MAP_SHAPES:
        # Tile files already store ward zero-padded; ward_raw is the unpadded number, as for real wards.
        tiles = gpd.read_file(TABLES_DIR / TILE_FILE_BY_MAP_SHAPES[map_shapes])
        tiles["ward_raw"] = tiles["ward"].astype(int).astype(str)
        return tiles[["ward", "ward_raw", "geometry"]].to_crs(PLOT_CRS)
    wards = gpd.read_file(Path(layers_dir) / WARD_LAYER_FILE)
    wards["ward_raw"] = wards["ward"]
    wards["ward"] = wards["ward_raw"].astype(int).map("{:02d}".format)
    return wards[["ward", "ward_raw", "geometry"]].to_crs(PLOT_CRS)


def draw_ward_outlines(axis, wards, color=WARD_OUTLINE_COLOR, line_width=WARD_OUTLINE_WIDTH):
    wards.boundary.plot(ax=axis, color=color, linewidth=line_width)


def draw_ward_fill(axis, wards, value_column, colormap_name, value_min, value_max, opacity):
    """Fill each ward by its value in value_column on a continuous colormap.

    Colors are linear from value_min (bottom of colormap) to value_max (top); the caller picks
    the range. Values outside the range get the end color (clip=True): above value_max -> top
    color, below value_min -> bottom color. Returns the ScalarMappable, so the caller can draw a
    matching color bar.
    """
    color_scale = Normalize(vmin=value_min, vmax=value_max, clip=True)
    colormap = matplotlib.colormaps[colormap_name]
    fill_colors = [colormap(color_scale(value)) for value in wards[value_column]]
    wards.plot(ax=axis, color=fill_colors, alpha=opacity, edgecolor="none")
    return ScalarMappable(norm=color_scale, cmap=colormap)


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


def draw_ward_two_size_labels(axis, wards, top_text_by_ward, bottom_text_by_ward, top_font_size, bottom_font_size,
                              offset_points_by_ward=None):
    """Two lines per ward in different font sizes: top_text sits just above the anchor, bottom_text
    just below it. Anchor = representative point, moved by offset_points_by_ward like draw_ward_labels.

    Returns {ward: [top_annotation, bottom_annotation]}; label_overlaps() treats the pair as one box.
    """
    offset_points_by_ward = offset_points_by_ward or {}
    annotations_by_ward = {}
    for ward, label_point in zip(wards["ward"], wards.representative_point()):
        offset = offset_points_by_ward.get(ward, (0, 0))
        common = dict(xy=(label_point.x, label_point.y), xytext=offset, textcoords="offset points",
                      ha="center", path_effects=TEXT_HALO, annotation_clip=True)
        annotations_by_ward[ward] = [
            axis.annotate(top_text_by_ward[ward], va="bottom", fontsize=top_font_size, **common),
            axis.annotate(bottom_text_by_ward[ward], va="top", fontsize=bottom_font_size, **common),
        ]
    return annotations_by_ward


def label_overlaps(figure, annotation_by_ward):
    """Every pair of drawn labels whose text boxes overlap on the rendered figure.

    annotation_by_ward values are one annotation or a list of them (a multi-part label, measured
    as the smallest box around all its parts).
    Returns a list of (ward_a, ward_b, overlap_width_pixels, overlap_height_pixels).
    The box is the text itself, not its white halo.
    """
    renderer = figure.canvas.get_renderer()
    box_by_ward = {}
    for ward, annotations in annotation_by_ward.items():
        parts = annotations if isinstance(annotations, list) else [annotations]
        box_by_ward[ward] = Bbox.union([part.get_window_extent(renderer) for part in parts])
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


def committee_display_table(assignments, palette=COMMITTEE_PALETTE, chairs_view_body_types=CHAIRS_VIEW_BODY_TYPES,
                            name_display=COMMITTEE_NAME_DISPLAY):
    """One row per committee in `assignments` (council_metrics.current_committee_assignments), in
    committee_order: body_id, body_type, body_name (as recorded), name (COMMITTEE_NAME_DISPLAY),
    short_label, in_chairs_view, color (palette color, in order, for chairs-view committees; None
    otherwise), chair_wards, vice_chair_wards, member_count (every role)."""
    committees = (assignments.sort_values("committee_order").drop_duplicates("body_id")
                  [["body_id", "body_type", "body_name", "body_abbreviation", "committee_order"]].reset_index(drop=True))
    if name_display == "collapse_spaces":
        committees["name"] = committees.body_name.str.split().str.join(" ")
    elif name_display == "as_recorded":
        committees["name"] = committees.body_name
    else:
        raise ValueError(name_display)
    committees["short_label"] = [COMMITTEE_SHORT_LABEL_OVERRIDES.get(body_name, abbreviation)
                                 for body_name, abbreviation in zip(committees.body_name, committees.body_abbreviation)]
    committees["in_chairs_view"] = committees.body_type.isin(chairs_view_body_types)
    colors = COMMITTEE_PALETTE_OPTIONS[palette]
    chairs_view_count = int(committees.in_chairs_view.sum())
    assert chairs_view_count <= len(colors), f"{chairs_view_count} committees, palette {palette} has {len(colors)} colors"
    committees["color"] = None
    committees.loc[committees.in_chairs_view, "color"] = colors[:chairs_view_count]
    wards_by_role = assignments.groupby(["body_id", "member_type"]).ward.apply(sorted)
    committees["chair_wards"] = [wards_by_role.get((body_id, "Chair"), []) for body_id in committees.body_id]
    committees["vice_chair_wards"] = [wards_by_role.get((body_id, "Vice Chair"), []) for body_id in committees.body_id]
    committees["member_count"] = committees.body_id.map(assignments.body_id.value_counts())
    return committees


def name_with_role_mark(label_name, roles):
    """Last name plus CHAIR_MARK and/or VICE_CHAIR_MARK. roles: a list of eLMS memberType values (or empty)."""
    marks = [mark for role, mark in [("Chair", CHAIR_MARK), ("Vice Chair", VICE_CHAIR_MARK)] if role in roles]
    return " ".join([label_name, *marks])


def role_font(roles):
    """matplotlib font keywords for a name line: bold chair, italic vice chair (both: bold italic)."""
    font = {}
    if "Chair" in roles:
        font["fontweight"] = CHAIR_FONT_WEIGHT
    if "Vice Chair" in roles:
        font["fontstyle"] = VICE_CHAIR_FONT_STYLE
    return font


def overview_by_ward(assignments, committees, view):
    """One overview map (OVERVIEW_VIEWS key): {ward: {"fills": [{"color", "opacity"}, ...], "roles": [...],
    "short_labels": [...]}} for wards with at least one colored role, chair roles first, then committee order.
    committees = committee_display_table(assignments). The dashboard gets this same dict (committees.json)."""
    roles = OVERVIEW_VIEWS[view]["roles"]
    colored = committees[committees.in_chairs_view].set_index("body_id")
    rows = assignments[assignments.body_id.isin(colored.index) & assignments.member_type.isin(roles)].copy()
    rows["role_order"] = rows.member_type.map({role: position for position, role in enumerate(roles)})
    by_ward = {}
    for row in rows.sort_values(["ward", "role_order", "committee_order"]).itertuples():
        committee = colored.loc[row.body_id]
        opacity = COMMITTEE_FILL_OPACITY
        if len(roles) > 1 and row.member_type == "Vice Chair" and COMBINED_VIEW_VICE_CHAIR_FILL == "lighter":
            opacity = COMMITTEE_FILL_OPACITY * VICE_CHAIR_LIGHTER_OPACITY_FACTOR
        elif COMBINED_VIEW_VICE_CHAIR_FILL not in ("same", "lighter"):
            raise ValueError(COMBINED_VIEW_VICE_CHAIR_FILL)
        entry = by_ward.setdefault(row.ward, {"fills": [], "roles": [], "short_labels": []})
        entry["fills"].append({"color": committee.color, "opacity": opacity})
        if row.member_type not in entry["roles"]:
            entry["roles"].append(row.member_type)
        entry["short_labels"].append(committee.short_label)
    return by_ward


def draw_ward_line_labels(axis, wards, lines_by_ward, font_size, offset_points_by_ward=None, line_spacing=1.2):
    """Several lines per ward, each with its own font keywords, the block centered on the anchor
    (representative point moved by offset_points_by_ward, as draw_ward_labels).

    lines_by_ward: {ward: [(text, {matplotlib font keywords}), ...]}.
    Returns {ward: [annotation, ...]}; label_overlaps() treats each ward's lines as one box."""
    offset_points_by_ward = offset_points_by_ward or {}
    annotations_by_ward = {}
    for ward, label_point in zip(wards["ward"], wards.representative_point()):
        right, up = offset_points_by_ward.get(ward, (0, 0))
        lines = lines_by_ward[ward]
        annotations_by_ward[ward] = []
        for line_number, (line_text, font_keywords) in enumerate(lines):
            line_up = ((len(lines) - 1) / 2 - line_number) * font_size * line_spacing
            annotations_by_ward[ward].append(axis.annotate(
                line_text, (label_point.x, label_point.y), xytext=(right, up + line_up), textcoords="offset points",
                fontsize=font_size, ha="center", va="center", path_effects=TEXT_HALO, annotation_clip=True,
                **font_keywords))
    return annotations_by_ward


def stripe_pieces(geometry, colors, stripe_width_meters):
    """Cut one ward shape into diagonal (45°) stripes, colors repeating in order. Returns
    [(piece, color)], for a ward with more than one fill color (MULTI_CHAIR_STRIPE_POINTS)."""
    from shapely.affinity import rotate
    from shapely.geometry import box
    min_x, min_y, max_x, max_y = geometry.bounds
    center = ((min_x + max_x) / 2, (min_y + max_y) / 2)
    reach = max(max_x - min_x, max_y - min_y)
    pieces = []
    for stripe_number, left in enumerate(range(0, int(2 * reach / stripe_width_meters) + 1)):
        x0 = center[0] - reach + left * stripe_width_meters
        band = rotate(box(x0, center[1] - reach, x0 + stripe_width_meters, center[1] + reach), 45, origin=center)
        piece = geometry.intersection(band)
        if not piece.is_empty:
            pieces.append((piece, colors[stripe_number % len(colors)]))
    return pieces
