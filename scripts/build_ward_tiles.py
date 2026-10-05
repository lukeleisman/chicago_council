"""Build equal-size ward tiles ("abstract Chicago"): one rectangle per ward.

Plan: sessions/2026-10-04_plan.md, Phase 4. Two kinds of tiles:
  4a "grid":   the user's hand-specified grid (GRID_LAYOUTS)
  4b "pushed": each tile starts at its real ward and overlapping tiles are pushed apart
               ("explode"); no grid

Reads data/raw/layers/wards_2023.geojson (via scripts/ward_maps.py, so the ward key is the
same zero-padded "01".."50" as everywhere else) and writes
data/tables/ward_tiles_grid.geojson and data/tables/ward_tiles_pushed.geojson (gitignored via data/).

Output columns: grid: ward, grid_row, grid_column, geometry.
                pushed: ward, anchor_x, anchor_y (start point, TILE_BUILD_CRS), geometry.
Saved in EPSG:4326 like the ward layer; scripts/ward_maps.py reprojects it to PLOT_CRS.

Usage:
  python scripts/build_ward_tiles.py grid
  python scripts/build_ward_tiles.py pushed
  python scripts/build_ward_tiles.py all
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.affinity import translate as shapely_translate
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ward_maps

# ---------------------------------------------------------------------------
# Configuration — every choice made in this script lives here.
# ---------------------------------------------------------------------------

REPO_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_DIR / "data" / "tables"
GRID_OUTPUT_FILE = "ward_tiles_grid.geojson"
PUSHED_OUTPUT_FILE = "ward_tiles_pushed.geojson"
OUTPUT_FILE_CRS = "EPSG:4326"   # same as the ward layer file

# Grid layouts, north to south. Each row is (start column, [wards west to east]); column 0 is
# the westernmost column used by any layout (ward 41's). None = an empty cell. Every start
# column is written out, so where each row sits is visible here and nowhere else.
GRID_LAYOUTS = {
    # The plan's layout (user, 2026-10-04): 13 rows, right-aligned (46 under 48), no shifts.
    "plan_2026_10_04": [
        (3, [50, 49]),
        (0, [41, 45, 39, 40, 48]),
        (1, [38, 33, 47, 46]),
        (0, [30, 31, 35, 32, 44]),
        (1, [36, 26, 1, 43]),
        (1, [29, 37, 27, 2]),
        (1, [24, 28, 34, 42]),
        (1, [25, 11, 3, 4]),
        (2, [22, 12, None]),
        (1, [14, 15, 16, 20]),
        (1, [13, 23, None, 5]),
        (0, [18, 17, 6, 8, 7]),
        (1, [19, 21, 9, 10]),
    ],
    # User, 2026-10-05: squish the south and shift it east, toward the real map.
    #   - 22 and 12 join the row with 25, 11, 3, 4 (user). Order west to east by each ward's
    #     real east-west position (representative point, km east of ward 41's):
    #     22 15.0, 12 18.2, 25 19.4, 11 21.8, 3 23.6, 4 24.4.
    #   - 13, 23, 14, 15, 16, 20, 5 in one row (user), in the order the user listed them,
    #     which is also their real west-to-east order (12.2 .. 26.9 km).
    #   - Rows 0-6 (50/49 down to 24 28 34 42) unchanged from the plan layout.
    #   - Start columns of the four southern rows: DRAFT, set by hand from the real east-west
    #     positions above (printed per ward in ward_tiles.ipynb §3), so the lakefront steps east
    #     going south (real: 49 at 19.6 km ... 4 at 24.4, 5 at 26.9, 7 and 10 at 29.0).
    #     OPEN QUESTION: user to confirm each start column; §5 draws one column less for each.
    "south_squished_2026_10_05": [
        (3, [50, 49]),
        (0, [41, 45, 39, 40, 48]),
        (1, [38, 33, 47, 46]),
        (0, [30, 31, 35, 32, 44]),
        (1, [36, 26, 1, 43]),
        (1, [29, 37, 27, 2]),
        (1, [24, 28, 34, 42]),
        (1, [22, 12, 25, 11, 3, 4]),         # 22 under 24, 12 under 28
        (1, [13, 23, 14, 15, 16, 20, 5]),    # 13 under 22
        (4, [18, 17, 6, 8, 7]),              # 17 under 16, 6 under 20, 8 under 5
        (4, [19, 21, 9, 10]),                # 19 under 18, 21 under 17, 9 under 6
    ],
    # User, 2026-10-05 (later): "the 6 wide one feels like too many" (22 12 25 11 3 4).
    # Two ways to break it up; both otherwise as south_squished_2026_10_05.
    # Real positions (km east / km north of the westernmost / southernmost ward point):
    #   24 15.9/18.4, 28 18.1/20.2, 34 21.7/20.9, 42 23.6/21.9, 25 19.4/17.5,
    #   22 15.0/15.1, 12 18.2/15.1, 11 21.8/16.2, 3 23.6/15.6, 4 24.4/16.5.
    # Option A: 22 and 12 back in their own row (as in the plan layout). 12 rows.
    "south_squished_A_22_12_own_row": [
        (3, [50, 49]),
        (0, [41, 45, 39, 40, 48]),
        (1, [38, 33, 47, 46]),
        (0, [30, 31, 35, 32, 44]),
        (1, [36, 26, 1, 43]),
        (1, [29, 37, 27, 2]),
        (1, [24, 28, 34, 42]),
        (2, [25, 11, 3, 4]),                 # 25 under 28, 11 under 34, 3 under 42
        (1, [22, 12]),                       # 22 under 24's column, 12 under 25
        (1, [13, 23, 14, 15, 16, 20, 5]),
        (4, [18, 17, 6, 8, 7]),
        (4, [19, 21, 9, 10]),
    ],
    # Option B: 25 moves up into the 24 28 34 42 row (its real north position, 17.5 km, is
    # between the two rows; real east 19.4 puts it between 28 and 34). 11 rows.
    "south_squished_B_25_up": [
        (3, [50, 49]),
        (0, [41, 45, 39, 40, 48]),
        (1, [38, 33, 47, 46]),
        (0, [30, 31, 35, 32, 44]),
        (1, [36, 26, 1, 43]),
        (1, [29, 37, 27, 2]),
        (1, [24, 28, 25, 34, 42]),           # 42 now one column east of 2
        (1, [22, 12, 11, 3, 4]),             # 22 under 24, 4 under 42
        (1, [13, 23, 14, 15, 16, 20, 5]),
        (4, [18, 17, 6, 8, 7]),
        (4, [19, 21, 9, 10]),
    ],
}
# User, 2026-10-05 (latest): the plan layout with 2:1 tiles "looks pretty good", initial draft.
# The squished layouts stay above as options (with 1.3 tiles the user preferred them;
# their 6-wide row 22 12 25 11 3 4 was "too many": A and B are the two fixes drawn).
GRID_LAYOUT = "plan_2026_10_04"

# Tile shape: width / height. 1.0 = squares; >1 = wider "hamburger" rectangles (plan).
# User, 2026-10-05: 2.0 with the plan layout (initial draft). For the squished layouts the user
# preferred 1.3. Used by the grid tiles; the pushed tiles have their own PUSHED_TILE_ASPECT.
TILE_ASPECT = 2.0

# Empty space between neighboring tiles, as a fraction of one grid cell's width (and height).
# 0 = tiles touch. Each tile is the cell shrunk by half the gap on every side.
TILE_GAP = 0.08

# How big the whole grid is drawn, so it can sit on top of the real map for comparison:
#   "city_height" = grid's total height = north-south extent of the 50 real wards
#   "city_width"  = grid's total width  = east-west extent of the 50 real wards
# The grid is centered on the center of the real wards' bounding box either way.
# This only affects where the grid sits when drawn over the real map (§3 of the notebook);
# the tile map on its own looks the same either way. Plan layout with 2:1 tiles: 13 rows and
# 5 columns x 2 = 10 tile-heights wide, close to the city's own shape, so "city_height"
# (grid spans the city north to south; about 32 km wide vs the city's 35). The notebook draws both.
GRID_SIZE_FIT = "city_height"

# Coordinate system the rectangles are built in. PLOT_CRS (Web Mercator) so tiles are exact
# rectangles on every map we draw. (A square built in another CRS, e.g. IL State Plane
# EPSG:3435, would come out very slightly rotated and stretched after reprojection.)
TILE_BUILD_CRS = ward_maps.PLOT_CRS

EXPECTED_WARD_COUNT = 50

# Overlap check: two tiles "overlap" if they share more than this area, in square meters of
# TILE_BUILD_CRS. Not 0 because with TILE_GAP = 0 neighboring edges are computed by separate
# floating-point sums and can overlap by a sliver far below 1 m² (a tile is about 2e7 m²).
OVERLAP_AREA_TOLERANCE_SQUARE_METERS = 1.0

# --- 4b push-apart ("explode") tiles ---
# Steps (plan 4b): (1) one start point per ward, (2) squish north-south, (3) one equal-size tile
# centered on each point, (4) repeatedly push overlapping pairs apart until none overlap.

# (1) Start point of each tile:
#   "representative_point" = shapely's point guaranteed inside the ward (same point the real-map
#                            labels use, ward_maps.draw_ward_labels)
#   "centroid"             = center of mass (can fall outside an oddly-shaped ward)
PUSHED_ANCHOR_METHOD = "representative_point"

# Hand moves of single start points, {ward: (km east, km north)} on the ground, applied before
# the squish. User, 2026-10-05: bring 41 in (east) a bit, "since the ward is weighted heavily by
# O'Hare airport". 41's representative point is about 11 km west of 45's.
# DRAFT 5 km (my pick, for the user to confirm); ward_tiles.ipynb §7 draws 0, 3, 5, 7 km.
PUSHED_START_SHIFT_KM_BY_WARD = {"41": (5.0, 0.0)}
# Hand moves are made in this coordinate system (IL State Plane East, feet), where distances are
# ground distances, then converted back to TILE_BUILD_CRS.
SHIFT_CRS = "EPSG:3435"
FEET_PER_KILOMETER = 3280.84

# (2) North-south squish: every start point's distance north of the city's center is multiplied
# by this. 1.0 = no squish. Plan default 0.90 (user, 2026-10-04: "10-20% squish"); the user
# also said 2026-10-05 the city is "too tall for easy viewing". DRAFT 0.75 (my pick from the
# options drawn in ward_tiles.ipynb §7, for the user to confirm). Notebook draws 1.0, 0.9, 0.75.
PUSHED_VERTICAL_SCALE = 0.75

# (3) Tile size. Tile width = PUSHED_TILE_SIZE_FACTOR x the median distance from a start point
# to its nearest other start point (after the squish). Bigger = tiles push further apart and
# the map spreads out more. At 1.0 the 2:1 tiles barely touch and stay small (1 push round);
# User, 2026-10-05: "something more like 1.5, with a bit more space between" -> 1.5 (read as this
# size factor; the notebook also draws PUSHED_TILE_ASPECT 1.5 in case that was meant).
PUSHED_TILE_SIZE_FACTOR = 1.5
# Width / height, as TILE_ASPECT for the grid. Notebook draws 1.3 and 2.0.
PUSHED_TILE_ASPECT = 2.0
# Empty space kept between pushed tiles, as a fraction of tile width (left-right) and height
# (up-down). Tiles are pushed apart as if this much bigger, then drawn at their own size.
# User, 2026-10-05: "a bit more space between" -> 0.20 (was 0.08). Notebook draws 0.08, 0.20, 0.30.
PUSHED_TILE_GAP = 0.20

# (4) Pushing. Each round, every overlapping pair is moved apart by half their overlap each
# (plus PUSH_EXTRA_FRACTION of the overlap, so they clear instead of ending exactly edge to edge),
# along whichever axis (east-west or north-south) has the SMALLER overlap: the shorter way out.
# All pushes in a round are computed from the same positions, then applied together, so the
# result doesn't depend on the order wards are listed in.
PUSH_EXTRA_FRACTION = 0.01
# Smallest push per pair per round, as a fraction of tile width (east-west push) or height
# (north-south push). Without it a tile squeezed from both sides gets pushes that nearly cancel
# while the overlap shrinks toward zero but never reaches it, so the build never finishes
# (seen 2026-10-05 for every tile size above 1.0). Larger = finishes sooner, tiles end up a
# little further apart.
PUSH_MIN_STEP_FRACTION = 0.01
# After each round's pushes, every tile moves this fraction of the way back toward its start
# point. 0 = no pull (plan default). Pull keeps tiles nearer home but can slow or stop
# convergence; the build fails loudly if overlaps remain after PUSH_MAX_ROUNDS.
PUSH_ANCHOR_PULL = 0.0
PUSH_MAX_ROUNDS = 2000

# ---------------------------------------------------------------------------


def grid_cells(layout_rows=GRID_LAYOUTS[GRID_LAYOUT]):
    """List of (ward as int, row index, column index) for every non-empty cell of a layout."""
    cells = []
    for row_index, (start_column, row) in enumerate(layout_rows):
        for position, ward in enumerate(row):
            if ward is not None:
                cells.append((ward, row_index, start_column + position))
    return cells


def check_every_ward_once(cells):
    wards = [ward for ward, _, _ in cells]
    expected = set(range(1, EXPECTED_WARD_COUNT + 1))
    missing = sorted(expected - set(wards))
    extra = sorted(set(wards) - expected)
    repeated = sorted({ward for ward in wards if wards.count(ward) > 1})
    assert not (missing or extra or repeated), f"missing {missing}, not a ward {extra}, repeated {repeated}"
    positions = [(row, column) for _, row, column in cells]
    assert len(positions) == len(set(positions)), "two wards in the same grid cell (check start columns)"


def build_grid_tiles(layout_rows=GRID_LAYOUTS[GRID_LAYOUT],
                     tile_aspect=TILE_ASPECT, tile_gap=TILE_GAP, grid_size_fit=GRID_SIZE_FIT):
    """GeoDataFrame in TILE_BUILD_CRS: ward ("01".."50"), grid_row, grid_column, geometry.

    Arguments default to the settings above; the review notebook passes others to draw options.
    """
    cells = grid_cells(layout_rows)
    check_every_ward_once(cells)

    real_wards = ward_maps.load_ward_shapes("real").to_crs(TILE_BUILD_CRS)
    city_min_x, city_min_y, city_max_x, city_max_y = real_wards.total_bounds
    city_center_x = (city_min_x + city_max_x) / 2
    city_center_y = (city_min_y + city_max_y) / 2

    row_count = len(layout_rows)
    column_count = 1 + max(column for _, _, column in cells) - min(column for _, _, column in cells)
    leftmost_column = min(column for _, _, column in cells)

    # One grid cell is cell_width x cell_height, with cell_width = tile_aspect * cell_height.
    if grid_size_fit == "city_height":
        cell_height = (city_max_y - city_min_y) / row_count
    elif grid_size_fit == "city_width":
        cell_height = (city_max_x - city_min_x) / column_count / tile_aspect
    else:
        raise ValueError(f"grid_size_fit must be 'city_height' or 'city_width', got {grid_size_fit!r}")
    cell_width = cell_height * tile_aspect

    # Top-left corner of the grid, so the grid is centered on the city's bounding-box center.
    grid_left = city_center_x - column_count * cell_width / 2
    grid_top = city_center_y + row_count * cell_height / 2

    records = []
    for ward, row_index, column_index in cells:
        cell_left = grid_left + (column_index - leftmost_column) * cell_width
        cell_top = grid_top - row_index * cell_height
        half_gap_x = tile_gap * cell_width / 2
        half_gap_y = tile_gap * cell_height / 2
        rectangle = box(cell_left + half_gap_x, cell_top - cell_height + half_gap_y,
                        cell_left + cell_width - half_gap_x, cell_top - half_gap_y)
        records.append({"ward": f"{ward:02d}", "grid_row": row_index, "grid_column": column_index,
                        "geometry": rectangle})

    tiles = gpd.GeoDataFrame(records, crs=TILE_BUILD_CRS).sort_values("ward").reset_index(drop=True)
    check_no_overlaps(tiles)
    return tiles


def check_no_overlaps(tiles):
    """No two tiles may overlap (plan verification). Touching edges are allowed."""
    for position, first in tiles.reset_index(drop=True).iterrows():
        for _, second in tiles.reset_index(drop=True).iloc[position + 1:].iterrows():
            assert first.geometry.intersection(second.geometry).area <= OVERLAP_AREA_TOLERANCE_SQUARE_METERS, \
                f"tiles {first.ward} and {second.ward} overlap"


def pushed_start_points(anchor_method=PUSHED_ANCHOR_METHOD, vertical_scale=PUSHED_VERTICAL_SCALE,
                        start_shift_km_by_ward=PUSHED_START_SHIFT_KM_BY_WARD):
    """DataFrame: ward, anchor_x, anchor_y (real point, TILE_BUILD_CRS), shifted_x, shifted_y (after
    hand moves), start_x, start_y (after hand moves and squish)."""
    real_wards = ward_maps.load_ward_shapes("real").to_crs(TILE_BUILD_CRS)
    if anchor_method == "representative_point":
        points = real_wards.representative_point()
    elif anchor_method == "centroid":
        points = real_wards.centroid
    else:
        raise ValueError(f"anchor_method must be 'representative_point' or 'centroid', got {anchor_method!r}")
    _, city_min_y, _, city_max_y = real_wards.total_bounds
    city_center_y = (city_min_y + city_max_y) / 2
    starts = real_wards[["ward"]].copy()
    starts["anchor_x"] = points.x.values
    starts["anchor_y"] = points.y.values

    # Hand moves, in ground km (SHIFT_CRS), then back to TILE_BUILD_CRS.
    points_for_shift = gpd.GeoSeries(points.values, crs=TILE_BUILD_CRS).to_crs(SHIFT_CRS)
    shifted_points = gpd.GeoSeries([
        shapely_translate(point, *(km * FEET_PER_KILOMETER for km in start_shift_km_by_ward.get(ward, (0.0, 0.0))))
        for ward, point in zip(starts.ward, points_for_shift)], crs=SHIFT_CRS).to_crs(TILE_BUILD_CRS)
    starts["shifted_x"] = shifted_points.x.values
    starts["shifted_y"] = shifted_points.y.values

    starts["start_x"] = starts.shifted_x
    starts["start_y"] = city_center_y + (starts.shifted_y - city_center_y) * vertical_scale
    return starts.sort_values("ward").reset_index(drop=True)


def push_apart(center_x, center_y, box_width, box_height, start_x, start_y,
               extra_fraction=PUSH_EXTRA_FRACTION, min_step_fraction=PUSH_MIN_STEP_FRACTION,
               anchor_pull=PUSH_ANCHOR_PULL, max_rounds=PUSH_MAX_ROUNDS):
    """Move equal boxes (box_width x box_height, centered at center_x/center_y) until none overlap.

    Returns (final center_x, final center_y, rounds used). Raises if overlaps remain after max_rounds.
    """
    center_x = np.array(center_x, dtype=float)
    center_y = np.array(center_y, dtype=float)
    tile_count = len(center_x)
    for round_number in range(1, max_rounds + 1):
        move_x = np.zeros(tile_count)
        move_y = np.zeros(tile_count)
        overlap_count = 0
        for first in range(tile_count):
            for second in range(first + 1, tile_count):
                gap_x = center_x[second] - center_x[first]
                gap_y = center_y[second] - center_y[first]
                overlap_x = box_width - abs(gap_x)     # > 0 means the boxes overlap east-west
                overlap_y = box_height - abs(gap_y)    # > 0 means they overlap north-south
                if overlap_x <= 0 or overlap_y <= 0:
                    continue
                overlap_count += 1
                # Push along the axis with the smaller overlap; the second tile goes the way it
                # already sits relative to the first (ties: second goes east / north).
                if overlap_x / box_width <= overlap_y / box_height:
                    push = max(overlap_x * (0.5 + extra_fraction), min_step_fraction * box_width)
                    direction = 1.0 if gap_x >= 0 else -1.0
                    move_x[first] -= direction * push
                    move_x[second] += direction * push
                else:
                    push = max(overlap_y * (0.5 + extra_fraction), min_step_fraction * box_height)
                    direction = 1.0 if gap_y >= 0 else -1.0
                    move_y[first] -= direction * push
                    move_y[second] += direction * push
        if overlap_count == 0:
            return center_x, center_y, round_number - 1
        center_x += move_x
        center_y += move_y
        center_x += anchor_pull * (np.asarray(start_x) - center_x)
        center_y += anchor_pull * (np.asarray(start_y) - center_y)
    raise RuntimeError(f"overlaps remain after {max_rounds} rounds (PUSH_MAX_ROUNDS / PUSH_ANCHOR_PULL)")


def build_pushed_tiles(anchor_method=PUSHED_ANCHOR_METHOD, vertical_scale=PUSHED_VERTICAL_SCALE,
                       tile_size_factor=PUSHED_TILE_SIZE_FACTOR, tile_aspect=PUSHED_TILE_ASPECT,
                       tile_gap=PUSHED_TILE_GAP, anchor_pull=PUSH_ANCHOR_PULL,
                       start_shift_km_by_ward=PUSHED_START_SHIFT_KM_BY_WARD):
    """GeoDataFrame in TILE_BUILD_CRS: ward, anchor_x, anchor_y, start_x, start_y, rounds, geometry.

    Arguments default to the settings above; the review notebook passes others to draw options.
    """
    starts = pushed_start_points(anchor_method, vertical_scale, start_shift_km_by_ward)

    # Median nearest-neighbor distance between start points sets the tile size.
    start_xy = starts[["start_x", "start_y"]].to_numpy()
    pair_distances = np.hypot(start_xy[:, None, 0] - start_xy[None, :, 0], start_xy[:, None, 1] - start_xy[None, :, 1])
    np.fill_diagonal(pair_distances, np.inf)
    median_nearest_distance = np.median(pair_distances.min(axis=1))
    tile_width = tile_size_factor * median_nearest_distance
    tile_height = tile_width / tile_aspect

    # Push as if each tile were bigger by the gap, then draw it at its own size.
    final_x, final_y, rounds = push_apart(
        starts.start_x, starts.start_y, tile_width * (1 + tile_gap), tile_height * (1 + tile_gap),
        starts.start_x, starts.start_y, anchor_pull=anchor_pull)

    tiles = starts.copy()
    tiles["center_x"] = final_x
    tiles["center_y"] = final_y
    tiles["rounds"] = rounds
    tiles["tile_width"] = tile_width
    tiles["tile_height"] = tile_height
    tiles = gpd.GeoDataFrame(
        tiles, geometry=[box(x - tile_width / 2, y - tile_height / 2, x + tile_width / 2, y + tile_height / 2)
                         for x, y in zip(final_x, final_y)], crs=TILE_BUILD_CRS)
    check_no_overlaps(tiles)
    return tiles


def write_grid_tiles():
    tiles = build_grid_tiles()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / GRID_OUTPUT_FILE
    tiles.to_crs(OUTPUT_FILE_CRS).to_file(output_path, driver="GeoJSON")
    print(f"{output_path}: layout {GRID_LAYOUT}, {len(tiles)} tiles, {tiles.grid_row.nunique()} rows, "
          f"{tiles.grid_column.nunique()} columns")


def write_pushed_tiles():
    tiles = build_pushed_tiles()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / PUSHED_OUTPUT_FILE
    tiles[["ward", "anchor_x", "anchor_y", "geometry"]].to_crs(OUTPUT_FILE_CRS).to_file(output_path, driver="GeoJSON")
    print(f"{output_path}: {len(tiles)} tiles, {tiles.rounds.iloc[0]} push rounds")


STEPS = {"grid": write_grid_tiles, "pushed": write_pushed_tiles}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in [*STEPS, "all"]:
        sys.exit(f"usage: python scripts/build_ward_tiles.py {{{'|'.join([*STEPS, 'all'])}}}")
    for step_name in (list(STEPS) if sys.argv[1] == "all" else [sys.argv[1]]):
        STEPS[step_name]()
