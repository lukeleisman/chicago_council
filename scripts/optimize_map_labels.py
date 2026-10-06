"""Search for Map View label nudges that leave no two labels overlapping at a larger label size.

Two sets of maps (both Map View, real ward shapes):
  1. Alders / Votes tabs: names, tenure, absence labels (scripts/export_dashboard_data.py
     REAL_MAP_LABEL_LAYOUTS). Today they sit at the notebook nudge + DASHBOARD_EXTRA_OFFSET_POINTS_BY_WARD,
     drawn REAL_MAP_LABEL_SCALE times the notebook size (docs/dashboard/app.js).
  2. Wards tab: each labeled layer's labels (community areas, neighborhoods, zip codes, police districts)
     plus the bold ward numbers drawn on every layer. Today all sit at the plain representative point
     (no nudges), drawn LAYER_MAP_LABEL_SCALE times the notebook size.

For each label scale the question is: what is the SMALLEST total movement from today's positions that
removes every overlap, with each label's anchor kept inside its own shape (its ward, or its layer
feature; shapes on the city edge may go a little way past it, never into a neighbor)?

The script only PRINTS and WRITES proposals. The export uses them only when its settings say so
(DASHBOARD_LABEL_POSITIONS, WARDS_TAB_LABEL_POSITIONS).

Everything is in typographic points on the notebook figure (ward_maps.FIGURE_SIZE_MAP), the unit of
the existing nudges; 1 pt = meters_per_point (about 76 m) on the map. Label box sizes were measured in
the browser: scripts/map_label_box_sizes.json and scripts/wards_tab_label_box_sizes.json ("about" in each).

Method (plain penalty optimization, scipy L-BFGS-B, exact gradient):
  cost = sum over labels of (squared distance moved from today's position)
       + OVERLAP_WEIGHT  * sum over overlapping box pairs of (smaller of overlap width, height)^2
       + REGION_WEIGHT_PER_OVERLAP_WEIGHT * OVERLAP_WEIGHT
                         * sum over labels of (distance from anchor to its allowed region)^2
  run once per weight in OVERLAP_WEIGHT_STEPS (each starts where the last ended), round to
  ROUND_TO_POINTS, then a brute-force local search on labels still overlapping (LOCAL_SEARCH_*).
  Finally overlaps and regions are checked exactly. Anything left is printed, not hidden.

Usage:
  python scripts/optimize_map_labels.py
Output: data/tables/map_label_optimization.json (gitignored; before/after per scale),
scripts/map_label_offsets_optimized.json (the nudges, read by the export) and a printed summary.
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from scipy.optimize import minimize
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_dashboard_data
import map_layers
import ward_maps

# ---------------------------------------------------------------------------
# Configuration — every choice made in this script lives here.
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent
ALDERS_BOX_SIZES_FILE = REPO_DIR / "scripts" / "map_label_box_sizes.json"
WARDS_TAB_BOX_SIZES_FILE = REPO_DIR / "scripts" / "wards_tab_label_box_sizes.json"
OUTPUT_FILE = REPO_DIR / "data" / "tables" / "map_label_optimization.json"
# Proposed nudges, read by scripts/export_dashboard_data.py (committed, so the export doesn't need
# this script).
OFFSETS_FILE = REPO_DIR / "scripts" / "map_label_offsets_optimized.json"

# --- 1. Alders / Votes Map View ---
# Label scales to try (app.js REAL_MAP_LABEL_SCALE; 1.25 before 2026-10-05). Measured 2026-10-05 in a
# 1470x737 Chrome window: names at 1.25 draw at 9.0 px. "+1 px" on that screen = 1.25 x 10/9 = 1.39.
ALDERS_SCALES_TO_TRY = [1.25, 1.39, 1.5, 1.6]
# Which layouts (export REAL_MAP_LABEL_LAYOUTS keys).
LAYOUTS = ["names", "tenure", "absence"]
# Overlap test for these two-line labels:
#   'per_line' = each text line is its own box (ward number line is narrow, so a neighbor may tuck
#                in beside it)
#   'union'    = one box around both lines per ward (the round-2 browser snippet; stricter)
OVERLAP_BOXES = "per_line"

# --- 2. Wards tab Map View ---
# Label scales to try (app.js LAYER_MAP_LABEL_SCALE; 1.25 on 2026-10-05).
WARDS_TAB_SCALES_TO_TRY = [1.25, 1.5]
# Layers with labels (map_layers.LAYER_STYLE label_column), in DASHBOARD_LAYERS order.
WARDS_TAB_LABELED_LAYERS = [layer for layer in export_dashboard_data.DASHBOARD_LAYERS
                            if map_layers.LAYER_STYLE[layer]["label_column"]]
# Ward numbers on the Wards tab (drawn on every layer, including the street map and unlabeled layers).
# Both options give ONE set of ward number positions for every layer (a number stays put when you
# switch layers):
#   'fixed_first' = ward numbers are moved apart from each other only, then held fixed while each
#                   layer's labels move around them
#   'joint'       = ward numbers and all four layers' labels are solved together; a layer label only
#                   has to avoid ward numbers and labels of its OWN layer. Ward numbers may then move
#                   to make room for layer labels.
# Both are run, printed and written to the offsets file; the export setting
# WARDS_TAB_WARD_NUMBER_OPTION picks one (user, 2026-10-05: "joint looks good").
WARD_NUMBER_OPTIONS = ["fixed_first", "joint"]
# Layer labels keep their center at least this far inside their own shape (user, 2026-10-05: Gage Park
# sat in a corner; "need a little buffer from the very edge, since it's otherwise unclear"). Points on
# the notebook figure; 8 pt = about 600 m, about 4 px on a 1470x737 desktop window (my number).
# A shape whose plain center point (representative point) is closer to its edge than this gets that
# distance instead, so the center point is always allowed.
LAYER_LABEL_EDGE_INSET_POINTS = 8
# Layer labels may NOT go past the outer edge of their layer (unlike wards, EDGE_OUTSIDE_CITY_POINTS):
# lakefront neighborhood labels went out over the lake.
LAYER_LABEL_EDGE_OUTSIDE_POINTS = 0

# --- Shared by both ---
# Which measured box stands for a line of text:
#   'ink'      = the drawn letters (what the eye sees as touching)
#   'line_box' = the browser's text box, font ascent to descent (taller; the round-2 getBBox check).
#                Today's Alders layout "overlaps" by this test yet looks clean (user, 2026-10-05).
BOX_KIND = "ink"
# Overlap allowed between two labels, points on the notebook figure (before scale). 0 = none.
# User, 2026-10-05: "fine to allow a little overlap at the most zoomed out".
ALLOWED_OVERLAP_POINTS = 0.0
# Text widths were measured with macOS Chrome's system font (San Francisco; iOS uses the same family).
# Android draws Roboto, Windows Segoe UI: widths differ by a few percent. Every box width is multiplied
# by this (about the anchor), so labels keep clear on those too. OPEN QUESTION: Roboto / Segoe widths
# not measured; 1.10 is my guess at a safe margin.
WIDTH_SAFETY_FACTOR = 1.10
# Count the white halo as part of the label (half the halo stroke sticks out past the text box).
INCLUDE_HALO = True
# Extra clear space required between boxes, points on the notebook figure (before scale).
MIN_GAP_POINTS = 0.0
# Where an anchor may go: inside its own shape (ward, or layer feature); for shapes on the edge of the
# whole set (the city, or the layer's coverage), also up to this far past that edge, never into another
# shape. Points on the notebook figure.
EDGE_OUTSIDE_CITY_POINTS = 15
# Movement is measured from today's positions; squared movement is weighted equally for every label
# and both directions.

# Penalty weights (see Method). Larger weight = overlaps matter more than movement.
OVERLAP_WEIGHT_STEPS = [10, 100, 1_000, 10_000, 100_000]
# Region weight is this many times the overlap weight at every step, so staying inside its own shape
# wins over removing an overlap (user: the center needs to be in its own shape). Left-over overlap is
# printed instead.
REGION_WEIGHT_PER_OVERLAP_WEIGHT = 100
# The optimizer pushes boxes this much further apart than required, so rounding doesn't reopen overlaps.
OPTIMIZER_EXTRA_GAP_POINTS = 1.0
# Final nudges are rounded to this (the hand nudges are whole points).
ROUND_TO_POINTS = 1
# After rounding, a plain search for labels still overlapping (the smooth optimizer can get stuck when
# two labels sit side by side between walls): for each label in a remaining pair, try every
# whole-point move within LOCAL_SEARCH_RADIUS_POINTS of where it is; keep the single move that most
# lowers (overlap depth total, then movement from today). Repeated up to LOCAL_SEARCH_ROUNDS times.
LOCAL_SEARCH_RADIUS_POINTS = 12
LOCAL_SEARCH_ROUNDS = 60

# ---------------------------------------------------------------------------


def meters_per_point_from_export():
    """The export's own figure measurement (export_dashboard_data.real_map_label_layout prints it).
    Re-measured here the same way, without writing anything."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    wards = ward_maps.load_ward_shapes("real")
    figure, axis = plt.subplots(figsize=ward_maps.FIGURE_SIZE_MAP)
    ward_maps.draw_ward_outlines(axis, wards)
    axis.set_axis_off()
    figure.canvas.draw()
    origin = axis.transData.transform((0, 0))
    pixels_per_meter = axis.transData.transform((1000, 0))[0] - origin[0]
    meters_per_point = 1000 * (figure.dpi / 72) / pixels_per_meter
    plt.close(figure)
    return meters_per_point


def to_points(geometries, meters_per_point):
    """PLOT_CRS (EPSG:3857 meters) shapes -> points on the notebook figure."""
    return [shapely.affinity.scale(geometry, 1 / meters_per_point, 1 / meters_per_point, origin=(0, 0))
            for geometry in geometries]


def anchors_in_points(geometries, meters_per_point):
    """representative_point() of the UNSCALED shapes (as the export), in points."""
    return np.array([[point.x / meters_per_point, point.y / meters_per_point]
                     for point in (geometry.representative_point() for geometry in geometries)])


def allowed_regions(polygons, edge_outside_points=None):
    """Per shape: the shape itself, plus a strip up to edge_outside_points (default
    EDGE_OUTSIDE_CITY_POINTS) outside the union of all the shapes (so only shapes on the outer edge get one)."""
    edge_outside_points = EDGE_OUTSIDE_CITY_POINTS if edge_outside_points is None else edge_outside_points
    if edge_outside_points == 0:
        return list(polygons)
    coverage = unary_union(polygons)
    return [unary_union([polygon, polygon.buffer(edge_outside_points).difference(coverage)])
            for polygon in polygons]


def inset_regions(polygons, center_points):
    """Layer labels: each shape shrunk by LAYER_LABEL_EDGE_INSET_POINTS, or by the plain center point's
    distance to the edge if that is smaller (so the center point stays allowed). Returns (regions, insets)."""
    regions, insets = [], []
    for polygon, (x, y) in zip(polygons, center_points):
        inset = min(LAYER_LABEL_EDGE_INSET_POINTS, shapely.distance(polygon.boundary, shapely.Point(x, y)) * 0.999)
        regions.append(polygon.buffer(-inset))
        insets.append(inset)
    return regions, insets


def box_margin(label_scale):
    halo = export_dashboard_data.LABEL_HALO_POINTS / 2 if INCLUDE_HALO else 0
    return halo * label_scale + MIN_GAP_POINTS / 2


def scaled_box(box, label_scale):
    """[x0, y0, x1, y1] at scale 1 -> at label_scale, widths x WIDTH_SAFETY_FACTOR, halo/gap margin added."""
    x0, y0, x1, y1 = (value * label_scale for value in box)
    margin = box_margin(label_scale)
    return [x0 * WIDTH_SAFETY_FACTOR - margin, y0 - margin, x1 * WIDTH_SAFETY_FACTOR + margin, y1 + margin]


def overlap_depths(anchors, relative_boxes, extra_gap=0.0, with_gradient=False, map_group=None):
    """Every pair of boxes from different labels: depth = smaller of overlap width / height (points),
    minus ALLOWED_OVERLAP_POINTS. relative_boxes: (labels, boxes per label, 4).
    map_group: optional int per label, the map it is drawn on; -1 = drawn on every map. Pairs from
    different maps are skipped.
    Returns (label_index_a, label_index_b, depth) for depth > 0; with_gradient: also the gradient of
    sum(depth^2) with respect to every anchor, shape (labels, 2)."""
    label_count, box_count, _ = relative_boxes.shape
    absolute = relative_boxes + np.concatenate([anchors, anchors], axis=1)[:, None, :]
    flat = absolute.reshape(-1, 4)
    owner = np.repeat(np.arange(label_count), box_count)
    first, second = np.triu_indices(len(flat), k=1)
    different_label = owner[first] != owner[second]
    if map_group is not None:
        group_a, group_b = map_group[owner[first]], map_group[owner[second]]
        different_label &= (group_a == group_b) | (group_a == -1) | (group_b == -1)
    first, second = first[different_label], second[different_label]
    box_a, box_b = flat[first], flat[second]
    overlap_width = np.minimum(box_a[:, 2], box_b[:, 2]) - np.maximum(box_a[:, 0], box_b[:, 0]) + extra_gap
    overlap_height = np.minimum(box_a[:, 3], box_b[:, 3]) - np.maximum(box_a[:, 1], box_b[:, 1]) + extra_gap
    depth = np.minimum(overlap_width, overlap_height) - ALLOWED_OVERLAP_POINTS
    hit = (overlap_width > 0) & (overlap_height > 0) & (depth > 0)
    label_a, label_b = owner[first][hit], owner[second][hit]
    if not with_gradient:
        return label_a, label_b, depth[hit]
    # d(overlap width)/d(x of box a): +1 if a's right edge is the min, -1 if a's left edge is the max.
    # Box b gets the mirror. Same for heights in y. The depth follows whichever of width/height is smaller.
    gradient = np.zeros((label_count, 2))
    a, b = box_a[hit], box_b[hit]
    width_is_smaller = overlap_width[hit] <= overlap_height[hit]
    d_width_d_a = (a[:, 2] < b[:, 2]).astype(float) - (a[:, 0] > b[:, 0]).astype(float)
    d_height_d_a = (a[:, 3] < b[:, 3]).astype(float) - (a[:, 1] > b[:, 1]).astype(float)
    d_width_d_b = (b[:, 2] < a[:, 2]).astype(float) - (b[:, 0] > a[:, 0]).astype(float)
    d_height_d_b = (b[:, 3] < a[:, 3]).astype(float) - (b[:, 1] > a[:, 1]).astype(float)
    twice_depth = 2 * depth[hit]
    np.add.at(gradient[:, 0], label_a, np.where(width_is_smaller, twice_depth * d_width_d_a, 0))
    np.add.at(gradient[:, 1], label_a, np.where(width_is_smaller, 0, twice_depth * d_height_d_a))
    np.add.at(gradient[:, 0], label_b, np.where(width_is_smaller, twice_depth * d_width_d_b, 0))
    np.add.at(gradient[:, 1], label_b, np.where(width_is_smaller, 0, twice_depth * d_height_d_b))
    return label_a, label_b, depth[hit], gradient


def region_distances(anchors, regions):
    return shapely.distance(np.array(regions), shapely.points(anchors))


def optimize(start_offsets, base_anchors, relative_boxes, regions, movable, map_group):
    """Penalty optimization (see Method). Labels with movable False stay at their start."""
    region_array = np.array(regions)
    movable_mask = np.repeat(movable[:, None], 2, axis=1)

    def cost_and_gradient(flat_offsets, overlap_weight):
        offsets = flat_offsets.reshape(-1, 2)
        anchors = base_anchors + offsets
        movement = offsets - start_offsets
        _, _, depths, overlap_gradient = overlap_depths(anchors, relative_boxes, OPTIMIZER_EXTRA_GAP_POINTS,
                                                        with_gradient=True, map_group=map_group)
        # Distance to the allowed region; gradient points away from the nearest allowed point.
        nearest = shapely.get_coordinates(shapely.shortest_line(region_array, shapely.points(anchors)))[0::2]
        away = anchors - nearest          # zero when inside
        region_weight = REGION_WEIGHT_PER_OVERLAP_WEIGHT * overlap_weight
        cost = (movement ** 2).sum() + overlap_weight * (depths ** 2).sum() + region_weight * (away ** 2).sum()
        gradient = 2 * movement + overlap_weight * overlap_gradient + region_weight * 2 * away
        return cost, np.where(movable_mask, gradient, 0).ravel()

    offsets = start_offsets.copy().ravel()
    for overlap_weight in OVERLAP_WEIGHT_STEPS:
        result = minimize(cost_and_gradient, offsets, args=(overlap_weight,), jac=True, method="L-BFGS-B",
                          options={"maxiter": 5000})
        offsets = result.x
    offsets = np.round(offsets.reshape(-1, 2) / ROUND_TO_POINTS) * ROUND_TO_POINTS
    offsets[~movable] = start_offsets[~movable]
    return offsets


def depth_against_others(label_index, candidate_anchors, anchors, relative_boxes, map_group=None):
    """Total overlap depth between label_index placed at each candidate anchor and every other label
    on the same map where it is now. Returns shape (candidates,)."""
    others = np.arange(len(anchors)) != label_index
    if map_group is not None and map_group[label_index] != -1:
        others &= (map_group == map_group[label_index]) | (map_group == -1)
    other_boxes = (relative_boxes[others] + np.concatenate([anchors[others], anchors[others]], axis=1)[:, None, :]).reshape(-1, 4)
    own_boxes = relative_boxes[label_index][None, :, :] + np.concatenate([candidate_anchors, candidate_anchors], axis=1)[:, None, :]
    own = own_boxes[:, :, None, :]                     # candidates, own boxes, 1, 4
    other = other_boxes[None, None, :, :]              # 1, 1, other boxes, 4
    width = np.minimum(own[..., 2], other[..., 2]) - np.maximum(own[..., 0], other[..., 0])
    height = np.minimum(own[..., 3], other[..., 3]) - np.maximum(own[..., 1], other[..., 1])
    depth = np.minimum(width, height) - ALLOWED_OVERLAP_POINTS
    depth = np.where((width > 0) & (height > 0) & (depth > 0), depth, 0)
    return depth.sum(axis=(1, 2))


def local_search(offsets, start_offsets, base_anchors, relative_boxes, regions, movable, map_group):
    """See LOCAL_SEARCH_RADIUS_POINTS. Moves stay inside each label's allowed region."""
    offsets = offsets.copy()
    region_array = np.array(regions)
    steps = np.arange(-LOCAL_SEARCH_RADIUS_POINTS, LOCAL_SEARCH_RADIUS_POINTS + 1)
    moves = np.array([(right, up) for right in steps for up in steps], dtype=float)
    for _ in range(LOCAL_SEARCH_ROUNDS):
        anchors = base_anchors + offsets
        first, second, _ = overlap_depths(anchors, relative_boxes, map_group=map_group)
        if len(first) == 0:
            break
        best_key, best_label, best_offset = (0.0, 0.0), None, None   # (depth change, movement change)
        for label_index in sorted(set(first) | set(second)):
            if not movable[label_index]:
                continue
            candidates = offsets[label_index] + moves
            candidate_anchors = base_anchors[label_index] + candidates
            inside = shapely.contains_xy(region_array[label_index], *candidate_anchors.T)
            if not inside.any():
                continue
            candidates, candidate_anchors = candidates[inside], candidate_anchors[inside]
            depth_now = depth_against_others(label_index, anchors[label_index][None, :], anchors, relative_boxes, map_group)[0]
            depth_change = depth_against_others(label_index, candidate_anchors, anchors, relative_boxes, map_group) - depth_now
            movement_change = (((candidates - start_offsets[label_index]) ** 2).sum(axis=1)
                               - ((offsets[label_index] - start_offsets[label_index]) ** 2).sum())
            order = np.lexsort((movement_change, depth_change))
            key = (depth_change[order[0]], movement_change[order[0]])
            if key < best_key:
                best_key, best_label, best_offset = key, label_index, candidates[order[0]]
        if best_label is None:
            break
        offsets[best_label] = best_offset
    return offsets


def solve(start_offsets, base_anchors, relative_boxes, regions, movable=None, map_group=None):
    if movable is None:
        movable = np.ones(len(base_anchors), dtype=bool)
    offsets = optimize(start_offsets, base_anchors, relative_boxes, regions, movable, map_group)
    return local_search(offsets, start_offsets, base_anchors, relative_boxes, regions, movable, map_group)


def describe(offsets, start_offsets, base_anchors, relative_boxes, regions, names):
    anchors = base_anchors + offsets
    first, second, depths = overlap_depths(anchors, relative_boxes)
    worst = {}
    for a, b, depth in zip(first, second, depths):
        worst[(a, b)] = max(worst.get((a, b), 0), depth)
    pairs = [f"{names[a]} / {names[b]} ({depth:.1f} pt)" for (a, b), depth in sorted(worst.items())]
    outside = region_distances(anchors, regions)
    moved = np.hypot(*(offsets - start_offsets).T)
    return {
        "overlapping_pairs": pairs,
        "anchors_outside_region": {names[i]: round(float(outside[i]), 1) for i in np.flatnonzero(outside > 0.01)},
        "labels_moved": int((moved > 0).sum()),
        "largest_move_points": round(float(moved.max()), 1),
        "total_move_points": round(float(moved.sum()), 1),
    }


def print_line(title, before, after):
    print(f"{title:34s} today: {len(before['overlapping_pairs']):3d} overlaps, "
          f"{len(before['anchors_outside_region'])} outside | proposed: {len(after['overlapping_pairs']):3d} overlaps, "
          f"{len(after['anchors_outside_region'])} outside, {after['labels_moved']} moved, "
          f"largest {after['largest_move_points']} pt, total {after['total_move_points']} pt")
    for pair in after["overlapping_pairs"]:
        print(f"      still overlapping: {pair}")
    for name, distance in after["anchors_outside_region"].items():
        print(f"      anchor outside allowed region: {name} by {distance} pt")


# --- 1. Alders / Votes ---

def alders_current_offsets(layout_name, wards):
    """Today's dashboard nudge (notebook + dashboard extra), points, shape (wards, 2)."""
    notebook = export_dashboard_data.REAL_MAP_LABEL_LAYOUTS[layout_name]["offsets"]
    extra = export_dashboard_data.DASHBOARD_EXTRA_OFFSET_POINTS_BY_WARD
    return np.array([[notebook.get(ward, (0, 0))[0] + extra.get(ward, (0, 0))[0],
                      notebook.get(ward, (0, 0))[1] + extra.get(ward, (0, 0))[1]] for ward in wards], dtype=float)


def alders_boxes(box_sizes, layout_name, wards, label_scale):
    """(wards, 2 lines, 4). The file stores [half_width, bottom, top] per line, centered on the anchor."""
    boxes = []
    for ward in wards:
        lines = [scaled_box([-half_width, bottom, half_width, top], label_scale)
                 for half_width, bottom, top in box_sizes[BOX_KIND][layout_name][ward]]
        if OVERLAP_BOXES == "union":
            lines = [[min(line[0] for line in lines), min(line[1] for line in lines),
                      max(line[2] for line in lines), max(line[3] for line in lines)]]
        boxes.append(lines)
    return np.array(boxes)


def run_alders(wards, ward_polygons_points, ward_anchors, results):
    box_sizes = json.loads(ALDERS_BOX_SIZES_FILE.read_text())
    regions = allowed_regions(ward_polygons_points)
    names = [f"ward {ward}" for ward in wards]
    offsets_by_scale = {}
    for label_scale in ALDERS_SCALES_TO_TRY:
        for layout_name in LAYOUTS:
            start = alders_current_offsets(layout_name, wards)
            boxes = alders_boxes(box_sizes, layout_name, wards, label_scale)
            before = describe(start, start, ward_anchors, boxes, regions, names)
            offsets = solve(start, ward_anchors, boxes, regions)
            after = describe(offsets, start, ward_anchors, boxes, regions, names)
            offsets_by_scale.setdefault(str(label_scale), {})[layout_name] = {
                ward: [int(offsets[i][0]), int(offsets[i][1])] for i, ward in enumerate(wards)}
            results.setdefault("alders_map_view", {}).setdefault(str(label_scale), {})[layout_name] = {
                "today": before, "proposed": after,
                "changed_wards": {ward: {"today": [int(v) for v in start[i]], "proposed": [int(v) for v in offsets[i]]}
                                  for i, ward in enumerate(wards) if not np.array_equal(start[i], offsets[i])}}
            print_line(f"Alders scale {label_scale} {layout_name}", before, after)
    return offsets_by_scale


# --- 2. Wards tab ---

def run_wards_tab(wards, ward_polygons_points, ward_anchors, meters_per_point, results):
    box_sizes = json.loads(WARDS_TAB_BOX_SIZES_FILE.read_text())
    ward_regions = allowed_regions(ward_polygons_points)
    ward_names = [f"ward number {int(ward)}" for ward in wards]
    measured_numbers = [item["text"] for item in box_sizes["ward_numbers"]]
    assert measured_numbers == [str(int(ward)) for ward in wards], "ward number order differs from the measurement"
    # Each layer: features in the export's order (raw file order, PLOT_CRS), label = LAYER_STYLE label column.
    layers = {}
    for layer_name in WARDS_TAB_LABELED_LAYERS:
        frame = gpd.read_file(ward_maps.LAYERS_DIR / f"{layer_name}.geojson").to_crs(ward_maps.PLOT_CRS).reset_index(drop=True)
        texts = frame[map_layers.LAYER_STYLE[layer_name]["label_column"]].astype(str).tolist()
        measured = box_sizes["layers"][layer_name]
        assert texts == [item["text"] for item in measured], f"{layer_name}: label order/text differs from the measurement"
        anchors = anchors_in_points(frame.geometry, meters_per_point)
        polygons = allowed_regions(to_points(frame.geometry, meters_per_point), LAYER_LABEL_EDGE_OUTSIDE_POINTS)
        regions, insets = inset_regions(polygons, anchors)
        smaller = [f"{text} {inset:.1f}" for text, inset in zip(texts, insets) if inset < LAYER_LABEL_EDGE_INSET_POINTS]
        print(f"{layer_name}: {len(smaller)} shapes get a smaller edge inset than {LAYER_LABEL_EDGE_INSET_POINTS} pt: {smaller}")
        layers[layer_name] = {"texts": texts, "anchors": anchors, "regions": regions,
                              "boxes_scale_1": [item[BOX_KIND] for item in measured]}

    offsets_by_scale = {}
    for label_scale in WARDS_TAB_SCALES_TO_TRY:
        scale_key = str(label_scale)
        number_boxes = np.array([[scaled_box(item[BOX_KIND], label_scale)] for item in box_sizes["ward_numbers"]])
        layer_boxes = {name: np.array([[scaled_box(box, label_scale)] for box in layer["boxes_scale_1"]])
                       for name, layer in layers.items()}
        for option in WARD_NUMBER_OPTIONS:
            option_results = results.setdefault("wards_tab", {}).setdefault(scale_key, {}).setdefault(option, {})
            number_start = np.zeros((len(wards), 2))
            if option == "fixed_first":
                # Ward numbers among themselves, then fixed.
                number_offsets = solve(number_start, ward_anchors, number_boxes, ward_regions)
                layer_offsets = {}
                for name, layer in layers.items():
                    count = len(layer["texts"])
                    offsets = solve(np.concatenate([np.zeros((count, 2)), number_offsets]),
                                    np.concatenate([layer["anchors"], ward_anchors]),
                                    np.concatenate([layer_boxes[name], number_boxes]),
                                    layer["regions"] + ward_regions,
                                    movable=np.array([True] * count + [False] * len(wards)))
                    layer_offsets[name] = offsets[:count]
            else:
                # Everything at once; map_group keeps each layer's labels apart from other layers'.
                names_in_order = list(layers)
                counts = [len(layers[name]["texts"]) for name in names_in_order]
                offsets = solve(np.zeros((sum(counts) + len(wards), 2)),
                                np.concatenate([layers[name]["anchors"] for name in names_in_order] + [ward_anchors]),
                                np.concatenate([layer_boxes[name] for name in names_in_order] + [number_boxes]),
                                sum((layers[name]["regions"] for name in names_in_order), []) + ward_regions,
                                map_group=np.array(sum(([group] * count for group, count in enumerate(counts)), [])
                                                   + [-1] * len(wards)))
                splits = np.cumsum(counts)
                layer_offsets = dict(zip(names_in_order, np.split(offsets[:splits[-1]], splits[:-1])))
                number_offsets = offsets[splits[-1]:]
            # Report per map: ward numbers alone (unlabeled layers, street map), then each labeled layer.
            before = describe(number_start, number_start, ward_anchors, number_boxes, ward_regions, ward_names)
            after = describe(number_offsets, number_start, ward_anchors, number_boxes, ward_regions, ward_names)
            option_results["ward_numbers"] = {"today": before, "proposed": after}
            print_line(f"Wards {label_scale} {option} ward numbers", before, after)
            for name, layer in layers.items():
                count = len(layer["texts"])
                base = np.concatenate([layer["anchors"], ward_anchors])
                boxes = np.concatenate([layer_boxes[name], number_boxes])
                regions = layer["regions"] + ward_regions
                label_names = layer["texts"] + ward_names
                today = np.zeros((count + len(wards), 2))
                proposed = np.concatenate([layer_offsets[name], number_offsets])
                before = describe(today, today, base, boxes, regions, label_names)
                after = describe(proposed, today, base, boxes, regions, label_names)
                option_results[name] = {"today": before, "proposed": after}
                print_line(f"Wards {label_scale} {option} {name}", before, after)
            offsets_by_scale.setdefault(scale_key, {})[option] = {
                "ward_numbers": {ward: [int(number_offsets[i][0]), int(number_offsets[i][1])] for i, ward in enumerate(wards)},
                "layers": {name: [[int(right), int(up)] for right, up in layer_offsets[name]] for name in layers}}
    return offsets_by_scale


def main():
    meters_per_point = meters_per_point_from_export()
    wards_frame = ward_maps.load_ward_shapes("real").sort_values("ward").reset_index(drop=True)
    wards = list(wards_frame.ward)
    ward_polygons_points = to_points(wards_frame.geometry, meters_per_point)
    ward_anchors = anchors_in_points(wards_frame.geometry, meters_per_point)
    print(f"1 pt = {meters_per_point:.1f} m. Boxes '{BOX_KIND}', width safety {WIDTH_SAFETY_FACTOR}, "
          f"halo {INCLUDE_HALO}, allowed overlap {ALLOWED_OVERLAP_POINTS} pt, edge allowance "
          f"{EDGE_OUTSIDE_CITY_POINTS} pt.\n")
    settings = {name: value for name, value in globals().items()
                if name.isupper() and isinstance(value, (int, float, str, list, bool))
                and not name.endswith(("_DIR", "_FILE"))}
    results = {"settings": settings}
    alders_offsets = run_alders(wards, ward_polygons_points, ward_anchors, results)
    print()
    wards_tab_offsets = run_wards_tab(wards, ward_polygons_points, ward_anchors, meters_per_point, results)
    OUTPUT_FILE.write_text(json.dumps(results, indent=1))
    OFFSETS_FILE.write_text(json.dumps({
        "about": ("Map View label nudges, typographic points on the notebook figure, [right, up]. "
                  "alders_map_view: {scale: {layout: {ward: nudge}}}, replacing notebook nudge + "
                  "DASHBOARD_EXTRA_OFFSET_POINTS_BY_WARD. wards_tab: {scale: {ward number option: {ward_numbers: {ward: nudge}, "
                  "layers: {layer: [nudge per feature, in the layer file's order]}}}}, from the plain "
                  "representative point. Written by scripts/optimize_map_labels.py; settings below."),
        "settings": settings,
        "alders_map_view": alders_offsets,
        "wards_tab": wards_tab_offsets,
    }, indent=0))
    print(f"\nwrote {OUTPUT_FILE.relative_to(REPO_DIR)} and {OFFSETS_FILE.relative_to(REPO_DIR)}")


if __name__ == "__main__":
    main()
