/* Chicago City Council ward dashboard (preliminary).
 *
 * Same pattern as blanketbox_public/docs/prices/app.js: one self-contained script that injects its
 * own CSS, fetches JSON, and renders into a div. Works locally (docs/index.html) and embedded in
 * any page (e.g. a WordPress Custom HTML block):
 *   <div id="council-app"></div>
 *   <script src="https://<user>.github.io/chicago_council/dashboard/app.js"></script>
 *
 * Data: docs/data/*.json, written by scripts/export_dashboard_data.py. Every number is computed in
 * Python (scripts/council_metrics.py, the same code as notebooks/ward_views.ipynb); this file only
 * draws. Display choices are the named settings below, mirroring the notebook's choices.
 */
(function () {
  'use strict';

  /* ── Settings ─────────────────────────────────────────────────────────── */

  // Data folder, found from this script's own URL (dashboard/app.js -> data/), so the page works
  // wherever docs/ is served.
  const SCRIPT_URL = document.currentScript ? document.currentScript.src : window.location.href;
  const DATA_BASE_URL = new URL('../data/', SCRIPT_URL).href;

  const CONTAINER_ID = 'council-app';

  // Page title and version (user, 2026-10-05). The version line opens the footer text.
  const PAGE_TITLE = 'Chicago City Council 2023–2027 term';
  const DASHBOARD_VERSION = '0.1';

  // Map never taller than this share of the window height (vh). Was 78; raised to 82 when the
  // subtitle line (about 32 px, ~4vh on a 784 px window) was removed (user, 2026-10-05: "slightly
  // more than 78%"), so the page is about as tall as before.
  const MAP_MAX_HEIGHT_VH = 82;

  // Clicking a ward on the map scrolls the side table (only the table, not the page) so the
  // highlighted row is visible. false = the table stays where it is (the first draft).
  const SCROLL_TABLE_TO_SELECTED_WARD = true;

  // Zoom (user, 2026-10-05: option A, zoom within the drawn map, in every view). Written here, not
  // with a library: wheel, drag, pinch and +/−/reset buttons. Zoom is kept per Map View / Tile View.
  const ZOOM_MAX = 12;          // most zoomed in, times the whole-city view
  const ZOOM_BUTTON_STEP = 1.5; // + and − buttons multiply / divide the zoom by this
  // Mouse wheel / trackpad:
  //   'modifier' = zoom only with Ctrl or ⌘ held (and trackpad pinch, which browsers report as Ctrl+wheel);
  //                a plain wheel scrolls the page, so the map doesn't trap scrolling in WordPress
  //   'always'   = every wheel turn over the map zooms
  const ZOOM_WHEEL = 'modifier';
  // A press that moves less than this (screen px) is a click (select a ward), not a drag.
  const ZOOM_DRAG_THRESHOLD_PX = 4;
  // Label size while zoomed, per view (user, 2026-10-05: "keep the labels the same size for now"; a
  // setting, to see both; "grow to a certain size, then stay" is 'grow_until'):
  //   'constant'   = labels (and layer points) keep their on-screen size as you zoom
  //   'grow'       = labels grow with the map
  //   'grow_until' = labels grow with the map up to ZOOM_LABEL_MAX_GROWTH times, then stay that size
  //   'grow_until_px' = labels grow with the map until the largest label text is ZOOM_LABEL_MAX_PX tall on
  //                screen, then stay that size (a phone, whose labels start smaller, gets more growth).
  //                Labels never grow faster than the map, so zooming in can't make labels overlap.
  // Tile View is 'grow': its text is fitted inside each tile, so constant-size text never gets
  // easier to read there. OPEN QUESTION for the user.
  // 2026-10-05: real -> 'grow_until_px' is my trial of the user's "increase the font size a bit when
  // zooming, then stop"; was 'constant'. Not chosen by the user yet.
  const ZOOM_LABELS_BY_SHAPES = { real: 'grow_until_px', tiles_grid: 'grow' };
  const ZOOM_LABEL_MAX_GROWTH = 2;
  // Font size (screen px) where 'grow_until_px' stops. My number, 2026-10-05: 16 px (page body text
  // size; names start at ~10 px on a 1470x737 desktop window, ~7 px on a 400 px wide phone).
  const ZOOM_LABEL_MAX_PX = 16;
  // Wards tab layer labels (community areas, neighborhoods, zips, police; class cc-layer-label) get their
  // own cap (user, 2026-10-05: "perhaps a cap of 14 for the layer labels"). They start smaller (6 pt vs
  // 9 pt ward numbers, the notebook's ratio), so with one shared cap they stopped at ~10.7 px.
  // Every other label (ward numbers, Alders/Votes labels) and layer points use ZOOM_LABEL_MAX_PX.
  const ZOOM_LAYER_LABEL_MAX_PX = 14;
  const LAYER_LABEL_SELECTOR = '.cc-layer-label';
  // Line widths drawn in map units (layer edges, rail lines, ward outlines on the Wards tab):
  //   'constant' = keep their on-screen width; 'grow' = thicken with the map
  // (Alders/Votes ward outlines already keep a constant screen width: CSS non-scaling-stroke.)
  const ZOOM_LINE_WIDTH = 'constant';
  // Street map: sharper tiles as you zoom. Tile zoom = STREET_MAP_TILE_ZOOM + floor(log2(zoom)),
  // at most this; the detail tiles cover only what's on screen, over the whole-city base tiles.
  const STREET_MAP_MAX_TILE_ZOOM = 17;
  // Wait this long after the last zoom/pan movement before loading detail tiles (ms).
  const STREET_MAP_DETAIL_DELAY_MS = 250;

  // Ward shapes offered, in toggle order, and the one shown first (user, 2026-10-05: real map
  // first and default; pushed tiles dropped from the dashboard).
  //   real = 2023 boundaries; tiles_grid = hand-specified grid
  const SHAPE_OPTIONS = [
    { key: 'real', label: 'Map View', file: 'wards_real.geojson' },
    { key: 'tiles_grid', label: 'Tile View', file: 'wards_tiles_grid.geojson' },
  ];
  const DEFAULT_SHAPES = 'real';

  // Tabs, in button order (user, 2026-10-05: tenure and absence moved into a dropdown under Alders).
  const TAB_OPTIONS = [
    { key: 'alders', label: 'Alders' },
    { key: 'votes', label: 'Votes' },   // was 'Split votes' (user, 2026-10-05)
    { key: 'wards', label: 'Wards' },
  ];
  const DEFAULT_TAB = 'alders';
  // Dropdown under the Alders tab: what the map colors and labels show.
  const ALDER_MEASURE_OPTIONS = [
    { key: 'names', label: 'Names' },
    { key: 'tenure', label: 'Tenure' },
    { key: 'absence', label: 'Absence' },
    { key: 'committees', label: 'Committees' },   // user, 2026-10-07
  ];
  const DEFAULT_ALDER_MEASURE = 'names';
  // Committees (user, 2026-10-07): a second dropdown picks "All committee chairs" (the default) or one
  // committee. Data and every display rule: docs/data/committees.json, written by
  // scripts/export_dashboard_data.py from scripts/council_metrics.py (which assignments are current)
  // and scripts/ward_maps.py (colors, short labels, stars, bold/italic), the same code ward_views §5 uses.
  // Overview entries ("All committee chairs", "All committee vice chairs", "All chairs and vice chairs") come
  // from committees.json `overviews` (ward_maps.OVERVIEW_VIEWS); the first is the default (user: chairs).
  // Dropdown groups, by eLMS body type (committee order within each: council_metrics).
  const COMMITTEE_GROUP_LABELS = { 'Committee': 'Committees', 'Sub-Committee': 'Subcommittees', 'Joint Committee': 'Joint committees' };
  // Role words in the hover card, table and tiles (eLMS memberType -> shown).
  const COMMITTEE_ROLE_TEXT = { 'Chair': 'Chair', 'Vice Chair': 'Vice chair', 'Member': 'Member' };
  // Joint committees in the hover card (an alder sits on up to 17; each joint roster looks like both
  // committees' members together):
  //   'count_and_roles' = the count, then only the ones the alder chairs or vice-chairs (my pick, 2026-10-07)
  //   'all'             = every joint committee by short label
  //   'count'           = the count only (user, 2026-10-07: joint chairs / vice chairs are those of the two
  //                       committees joined; checked for all 19 in ward_views §5.1)
  const TOOLTIP_JOINT_COMMITTEES = 'count';
  // Dropdown under the Wards tab: which map layer is drawn under the wards (user, 2026-10-05; no
  // precincts, no census tracts). Keys = export DASHBOARD_LAYERS; each file is fetched on first pick.
  const LAYER_OPTIONS = [
    { key: 'street_map', label: 'Street map' },   // not a data layer: basemap tiles + ward fill (below)
    { key: 'community_areas', label: 'Community areas' },
    { key: 'neighborhoods', label: 'Neighborhoods' },
    { key: 'zip_codes', label: 'ZIP codes' },
    { key: 'police_districts', label: 'Police districts' },
    { key: 'parks', label: 'Parks' },
    { key: 'cta_rail_lines', label: 'CTA rail lines' },
    { key: 'cta_rail_stations', label: 'CTA rail stations' },
    { key: 'cps_schools_sy2526', label: 'CPS schools (2025–26)' },
    { key: 'ward_offices', label: 'Ward offices' },
  ];
  const DEFAULT_LAYER = 'street_map';   // user, 2026-10-05: Wards tab opens on the street map (was community_areas)
  // Wards tab, Map View: drawn like notebooks/map_layers_review.ipynb's large maps (styles in
  // meta.json `layers.style`, from scripts/map_layers.py; sizes in points, converted with
  // meta.real_map_labels.meters_per_point). No basemap (plan, 2026-10-05).
  // Multiplies layer labels and ward numbers. 1 = the notebook's proportions. User, 2026-10-05: 1.25
  // (same as REAL_MAP_LABEL_SCALE). 2026-10-05 later: 1.5 with positions from scripts/optimize_map_labels.py
  // made for 1.5 (export WARDS_TAB_LABEL_POSITIONS, WARDS_TAB_OPTIMIZED_FOR_SCALE); trial, not chosen yet.
  const LAYER_MAP_LABEL_SCALE = 1.5;
  // Multiplies point sizes (stations, schools, ward offices) on the layer map. 1 = the notebook's
  // proportions (points about 3.7 pt across, ~2.5 px on a 600 px wide map). User, 2026-10-05: 1.5.
  const LAYER_MAP_POINT_SCALE = 1.5;
  // Multiplies line widths (layer edges, rail lines, ward outlines). 1 = the notebook's proportions.
  const LAYER_MAP_LINE_SCALE = 1;
  // "Street map" (user, 2026-10-05: like map_layers_review cell [7]'s wards_2023 map, "more see
  // through"): Esri street tiles (the notebook's BASEMAP_CHOICE "street"), wards filled by
  // neighbor color (wards_real.geojson color_index, FILL_PALETTE) at STREET_MAP_WARD_FILL_OPACITY,
  // then the usual black outlines and bold ward numbers.
  const STREET_MAP_TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';
  // Tile zoom level. 12 = about 38 m per tile pixel at Chicago; the whole city is ~5 x 6 tiles
  // (~1,300 px of tile across), sharp on a ~700 px wide map at 2x screen density.
  const STREET_MAP_TILE_ZOOM = 12;
  // Each tile drawn this many map units wider/taller, so anti-aliasing doesn't leave hairline seams.
  const STREET_MAP_TILE_SEAM_OVERLAP = 0.5;
  const STREET_MAP_WARD_FILL_OPACITY = 0.25;   // notebook FILL_OPACITY is 0.45; user asked for more see-through
  // Attribution, as contextily prints it on the notebook map (Esri requires it).
  const STREET_MAP_ATTRIBUTION = 'Tiles © Esri — Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, 2012';

  // What each ward holds, per layer: docs/data/ward_layer_summary.json, made by
  // scripts/ward_layer_overlaps.py (rules there: WARD_SUMMARY_RULES). Each layer is "list" (names on
  // the tile) or "count" (number on the tile; names in the hover card and the table).
  // Tile View, Wards tab: at most this many names on a tile; the rest become "+N more".
  const TILE_MAX_LIST_LINES = 4;
  // Largest tile text, in map units (same cap as the other tile labels).
  const TILE_MAX_FONT_SIZE = 18;
  // Tile View, Wards tab: how the font is sized.
  //   'per_tile' = each tile's text fitted to that tile (the other tabs' method; sizes differ)
  //   'uniform'  = one size for every tile: the smallest of the per-tile fits
  const WARDS_TILE_FONT_FIT = 'uniform';
  // Word after a count, per layer (singular, plural).
  const LAYER_COUNT_NOUN = {
    parks: ['park', 'parks'],
    cta_rail_lines: ['station', 'stations'],   // rail lines show the station count for now (user, 2026-10-05)
    cta_rail_stations: ['station', 'stations'],
    cps_schools_sy2526: ['school', 'schools'],
  };
  // Text put before a name when shown (names themselves are as in the raw data, e.g. community
  // areas in capitals).
  const LAYER_NAME_PREFIX = { police_districts: 'District ' };
  // Tile View: in these layers the names are word-wrapped to fill the tile, at the largest font that
  // fits (user, 2026-10-05: ward office addresses "bigger with line wrapping ... very close to the
  // edges"). Widths are measured with the page's own font. Replaced the earlier split at ", ".
  const TILE_WRAP_LAYERS = ['ward_offices'];
  // Street map, Tile View / hover card / table: each ward's area (user, 2026-10-05: the street map tile
  // view "should show something. Perhaps ward area?"). docs/data/ward_areas.json, made by
  // scripts/ward_layer_overlaps.py (same measurement as its ward_area_m2). Square miles, this many decimals.
  const WARD_AREA_DECIMALS = 1;
  // Space kept free inside the tile edge for wrapped text, as a share of the tile's width / height.
  const TILE_WRAP_EDGE_MARGIN = 0.03;
  // Line step for tile text, in font sizes (the drawing loop's spacing).
  const TILE_LINE_STEP = 1.15;

  // Labels on tiles: ward number + last name (+ the view's value), font fitted to the tile.
  // Labels on the real map (Map View):
  //   'notebook_layout' = ward_views' labels (user, 2026-10-05): positions, nudges and font sizes from
  //                       scripts/ward_maps.py, converted by scripts/export_dashboard_data.py
  //                       (wards_real.geojson `labels`, meta.json real_map_labels)
  //   'number'          = ward number only, REAL_MAP_NUMBER_FONT_SIZE (the first draft)
  const REAL_MAP_LABEL = 'notebook_layout';
  const REAL_MAP_NUMBER_FONT_SIZE = 22;   // map units (the map is drawn 1020 units wide, then scaled to fit)
  // Which exported label layout each view uses (export REAL_MAP_LABEL_LAYOUTS; votes = §4.7 = §1's labels).
  // Committees use the names anchors ("ward" over "Last name"; a chair's short committee label is a third line).
  const REAL_MAP_LAYOUT_BY_VIEW = { names: 'names', votes: 'names', tenure: 'tenure', absence: 'absence', committees: 'names' };
  // Multiplies every real-map label size. 1 = the notebook's proportions; the export's no-overlap
  // check only holds at 1. Labels scale with the map, so a narrow screen makes them small.
  // OPEN QUESTION (user, 2026-10-05: "leave as is for now", likely to return, especially for a
  // mobile-friendly version): at ~500 px map width names are ~6 px. Options: (a) scale above 1
  // here (labels then may overlap); (b) let the map grow (MAP_MAX_HEIGHT_VH, or more page width).
  // User, 2026-10-05: 1.25 ("all fonts could be a bit bigger"); collisions this creates are fixed by
  // DASHBOARD_EXTRA_OFFSET_POINTS_BY_WARD in scripts/export_dashboard_data.py.
  // 2026-10-05: 1.39 was my trial of the user's "+1 on everything" (names 9 -> 10 px on the user's
  // 1470x737 window); user then asked to see 1.5 (names 10.8 px). Label positions from
  // scripts/optimize_map_labels.py made for this scale (export DASHBOARD_LABEL_POSITIONS,
  // DASHBOARD_OPTIMIZED_FOR_SCALE). Not chosen by the user yet.
  // Back to today: 1.25 here and DASHBOARD_LABEL_POSITIONS = "hand" in the export.
  const REAL_MAP_LABEL_SCALE = 1.5;
  // matplotlib's line spacing for multi-line text ("ward\nLast name"): 1.2 x font size.
  const NOTEBOOK_LINE_SPACING = 1.2;
  // Degrees of this page's Mercator per EPSG:3857 meter (Earth radius 6,378,137 m), to convert
  // meta.real_map_labels.meters_per_point.
  const DEGREES_PER_WEB_MERCATOR_METER = 180 / (Math.PI * 6378137);

  // Tenure colors: ward_views §2 (user, 2026-10-04): reversed viridis, yellow = newest,
  // dark purple = longest; scale from the lowest value to 22 years (anyone above gets the top color).
  const TENURE_COLORMAP = 'viridis_r';
  const TENURE_COLOR_CAP_YEARS = 22;
  const TENURE_DECIMALS = 1;

  // Absence colors: ward_views §3 (user, 2026-10-04): viridis, yellow = most absent; 0 to highest.
  const ABSENCE_COLORMAP = 'viridis';
  const ABSENCE_DECIMALS = 1;

  // Vote colors: ward_views VOTE_COLORS (user, 2026-10-05): Yea/Nay strong (blue/orange, readable
  // with red-green color blindness), every other value gray. Not on roster = white, hatched.
  const VOTE_COLORS = {
    'Yea': '#1f78b4',
    'Nay': '#e66101',
    'Absent': '#bdbdbd',
    'Not Voting': '#878787',
    'Recused': '#4d4d4d',
    'Present': '#d9d9d9',
    'Rising Vote': '#a0a0a0',
    'Vacant': '#f0f0f0',
  };
  const NOT_ON_ROSTER_LABEL = 'Not on roster';

  const ALDER_FILL = '#e8e6df';   // "Alders" view: one neutral fill

  // matplotlib/d3 viridis, sampled at 0, 0.1, ..., 1 (linear interpolation in between).
  const VIRIDIS_STOPS = ['#440154', '#482475', '#414487', '#355f8d', '#2a788e', '#21918c',
                         '#22a884', '#44bf70', '#7ad151', '#bddf26', '#fde725'];

  /* ── CSS (scoped to #council-app so host-page styles don't conflict) ─── */
  const CSS = `
#council-app {
  --cc-ink: #1a1a1a; --cc-ink-2: #555; --cc-line: #d6d3ca; --cc-surface: #ffffff; --cc-page: #f5f4ef;
  --cc-accent: #1C3D5A;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: var(--cc-ink); background: var(--cc-page); -webkit-font-smoothing: antialiased;
  padding: 16px; line-height: 1.4;
}
#council-app *, #council-app *::before, #council-app *::after { box-sizing: border-box; }
#council-app h1 { font-size: 22px; margin: 0 0 12px; color: var(--cc-accent); }
#council-app .cc-controls { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; margin-bottom: 12px; }
#council-app .cc-seg { display: inline-flex; border: 1px solid var(--cc-line); border-radius: 8px; overflow: hidden; background: var(--cc-surface); }
#council-app .cc-seg button { border: 0; background: none; padding: 7px 12px; font: inherit; font-size: 14px; cursor: pointer; color: var(--cc-ink); }
#council-app .cc-seg button + button { border-left: 1px solid var(--cc-line); }
#council-app .cc-seg button[aria-pressed="true"] { background: var(--cc-accent); color: #fff; }
/* width/display: host themes (e.g. WordPress Jadro) stretch selects to 100% width. */
#council-app select.cc-select { width: auto; display: inline-block; max-width: 100%; }
#council-app .cc-select { font: inherit; font-size: 14px; padding: 6px 8px; border: 1px solid var(--cc-line); border-radius: 8px; background: var(--cc-surface); color: var(--cc-ink); }
#council-app .cc-layout { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 16px; align-items: start; }
@media (max-width: 860px) { #council-app .cc-layout { grid-template-columns: 1fr; } }
#council-app .cc-card { background: var(--cc-surface); border: 1px solid var(--cc-line); border-radius: 10px; padding: 12px; }
/* Map never taller than MAP_MAX_HEIGHT_VH of the window; narrower maps center. */
#council-app .cc-map svg { width: 100%; height: auto; max-height: ${MAP_MAX_HEIGHT_VH}vh; display: block; margin: 0 auto; }
/* Zoom: the frame clips the zoomed map; buttons sit in its top-right corner. */
#council-app .cc-zoom-frame { position: relative; overflow: hidden; }
#council-app .cc-zoom-frame svg { cursor: grab; user-select: none; -webkit-user-select: none; }
#council-app .cc-zoom-frame svg:active { cursor: grabbing; }
#council-app .cc-zoom-buttons { position: absolute; top: 6px; right: 6px; display: flex; flex-direction: column; gap: 4px; }
#council-app .cc-zoom-buttons button { width: 30px; height: 30px; padding: 0; font: inherit; font-size: 18px; line-height: 1; cursor: pointer;
  background: var(--cc-surface); color: var(--cc-ink); border: 1px solid var(--cc-line); border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
#council-app .cc-zoom-hint { font-size: 11px; color: var(--cc-ink-2); text-align: right; margin-top: 2px; }
#council-app .cc-ward { stroke: #333; stroke-width: 0.8; vector-effect: non-scaling-stroke; cursor: pointer; }
#council-app .cc-ward:hover, #council-app .cc-ward.cc-selected { stroke: #000; stroke-width: 2.5; }
#council-app .cc-label { pointer-events: none; text-anchor: middle; dominant-baseline: central; font-weight: 600; }
/* Map View labels: ward_maps.TEXT_HALO = white outline drawn under black text; normal weight (matplotlib default). */
#council-app .cc-label-notebook { font-weight: 400; fill: #000; stroke: #fff; stroke-linejoin: round; paint-order: stroke; }
/* Wards tab layer map: wards are a transparent hit area under the layer; outlines drawn on top. */
#council-app .cc-ward-hit { fill: transparent; stroke: none; cursor: pointer; }
#council-app .cc-ward-hit.cc-selected { fill: rgba(255, 214, 0, 0.25) !important; fill-opacity: 1 !important; }
#council-app .cc-layer-shape, #council-app .cc-ward-outline, #council-app .cc-layer-label { pointer-events: none; }
#council-app .cc-layer-point { cursor: default; }
#council-app .cc-layer-label { text-anchor: middle; dominant-baseline: central; font-style: italic; stroke: #fff; stroke-linejoin: round; paint-order: stroke; }
#council-app .cc-ward-number { pointer-events: none; text-anchor: middle; dominant-baseline: central; font-weight: 700; fill: #000; stroke: #fff; stroke-linejoin: round; paint-order: stroke; }
#council-app .cc-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; font-size: 13px; margin-top: 8px; color: var(--cc-ink-2); }
/* Committees legend: one committee per line (user, 2026-10-07). */
#council-app .cc-legend-committee { flex-basis: 100%; }
#council-app .cc-swatch { display: inline-block; width: 14px; height: 14px; border-radius: 3px; border: 1px solid #999; vertical-align: -2px; margin-right: 5px; }
#council-app .cc-gradient { width: 180px; height: 12px; border-radius: 3px; border: 1px solid #999; }
#council-app .cc-event-picker { display: flex; flex-direction: column; gap: 6px; width: 100%; }
#council-app .cc-event-picker input, #council-app .cc-event-picker select { font: inherit; font-size: 14px; padding: 6px 8px; border: 1px solid var(--cc-line); border-radius: 6px; width: 100%; background: #fff; }
/* Dropdown arrow drawn here (user, 2026-10-05: no arrow on the WordPress page; the theme sets
   appearance:none and our background rules clear any arrow image). Same arrow in every browser. */
#council-app select.cc-select, #council-app .cc-event-picker select { -webkit-appearance: none; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%23555' stroke-width='1.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center; background-size: 10px 6px; padding-right: 28px; }
#council-app .cc-event h2 { font-size: 16px; margin: 0 0 4px; }
#council-app .cc-event .cc-meta { font-size: 13px; color: var(--cc-ink-2); margin-bottom: 8px; }
#council-app .cc-event .cc-title { font-size: 14px; margin-bottom: 8px; }
#council-app .cc-event ol { margin: 4px 0 0 18px; padding: 0; font-size: 13px; }
#council-app .cc-event a { color: var(--cc-accent); }
#council-app .cc-tally { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; margin-bottom: 8px; }
#council-app table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
#council-app th, #council-app td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #eee; }
/* Header row stays at the top while the table scrolls (user, 2026-10-05). */
#council-app thead th { position: sticky; top: 0; z-index: 1; background: var(--cc-surface); box-shadow: inset 0 -1px 0 var(--cc-line); }
#council-app th { cursor: pointer; user-select: none; color: var(--cc-ink-2); font-weight: 600; white-space: nowrap; }
#council-app td.cc-num, #council-app th.cc-num { text-align: right; }
#council-app tr.cc-selected td { background: #fff4d6; }
#council-app .cc-table-wrap { max-height: 520px; overflow-y: auto; }
#council-app .cc-tooltip { position: fixed; z-index: 10000; pointer-events: none; background: #fff; border: 1px solid var(--cc-line);
  border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.15); padding: 8px; font-size: 13px; display: none; max-width: 260px; }
#council-app .cc-tooltip img { width: 64px; height: 64px; object-fit: cover; object-position: top; border-radius: 6px; float: left; margin-right: 8px; }
#council-app .cc-tooltip strong { display: block; }
#council-app .cc-tooltip-list { clear: both; margin-top: 6px; }
#council-app .cc-foot { margin-top: 16px; font-size: 12px; color: var(--cc-ink-2); }
#council-app .cc-foot p { margin: 4px 0 0; max-width: 80ch; }
#council-app .cc-error { color: #a00; }
`;

  /* ── Helpers ──────────────────────────────────────────────────────────── */

  function el(tag, attributes, children) {
    const element = document.createElement(tag);
    Object.entries(attributes || {}).forEach(([name, value]) => {
      if (name === 'text') element.textContent = value;
      else if (name.startsWith('on')) element.addEventListener(name.slice(2), value);
      else element.setAttribute(name, value);
    });
    (children || []).forEach((child) => child && element.append(child));
    return element;
  }

  function svgEl(tag, attributes) {
    const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attributes || {}).forEach(([name, value]) => element.setAttribute(name, value));
    return element;
  }

  function hexToRgb(hex) {
    const value = parseInt(hex.slice(1), 16);
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  }

  // Colormap value at fraction 0..1 (clipped), linear between VIRIDIS_STOPS.
  function colormap(name, fraction) {
    let position = Math.min(1, Math.max(0, fraction));
    if (name === 'viridis_r') position = 1 - position;
    const scaled = position * (VIRIDIS_STOPS.length - 1);
    const lowIndex = Math.floor(scaled);
    const highIndex = Math.min(VIRIDIS_STOPS.length - 1, lowIndex + 1);
    const weight = scaled - lowIndex;
    const low = hexToRgb(VIRIDIS_STOPS[lowIndex]);
    const high = hexToRgb(VIRIDIS_STOPS[highIndex]);
    const mixed = low.map((channel, index) => Math.round(channel + (high[index] - channel) * weight));
    return `rgb(${mixed.join(',')})`;
  }

  function gradientCss(name) {
    const steps = [];
    for (let index = 0; index <= 10; index += 1) steps.push(`${colormap(name, index / 10)} ${index * 10}%`);
    return `linear-gradient(to right, ${steps.join(', ')})`;
  }

  // Dark text on light fills, white text on dark fills (relative luminance).
  function textColorFor(fill) {
    const match = fill.match(/\d+/g);
    const [red, green, blue] = fill.startsWith('#') ? hexToRgb(fill) : match.map(Number);
    const luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255;
    return luminance > 0.55 ? '#111' : '#fff';
  }

  // Web Mercator, the projection the tiles were built in (rectangles stay rectangles).
  function project([longitude, latitude]) {
    const radians = (latitude * Math.PI) / 180;
    return [longitude, (Math.log(Math.tan(Math.PI / 4 + radians / 2)) * 180) / Math.PI];
  }

  function forEachRing(geometry, callback) {
    const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
    polygons.forEach((polygon) => polygon.forEach((ring) => callback(ring)));
  }

  function fetchJson(fileName) {
    return fetch(DATA_BASE_URL + fileName).then((response) => {
      if (!response.ok) throw new Error(`${fileName}: HTTP ${response.status}`);
      return response.json();
    });
  }

  function formatDate(isoDate) {
    if (!isoDate) return '';
    const [year, month, day] = isoDate.split('-').map(Number);
    return new Date(year, month - 1, day).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  /* ── State ────────────────────────────────────────────────────────────── */

  const state = {
    shapes: DEFAULT_SHAPES,
    tab: DEFAULT_TAB,
    alderMeasure: DEFAULT_ALDER_MEASURE,
    committee: null,   // an overview key (default: the first overview, set at start) or a committee index
    layer: DEFAULT_LAYER,
    view: DEFAULT_ALDER_MEASURE,   // what is drawn: the alder measure on the Alders tab, else the tab (setTab)
    eventId: null,
    selectedWard: null,
    sort: { column: 'ward', ascending: true },
    // Zoom per ward shapes: scale k and translation (x, y) in SVG units; k = 1 = whole city.
    zoomByShapes: Object.fromEntries(SHAPE_OPTIONS.map((option) => [option.key, { k: 1, x: 0, y: 0 }])),
  };
  const data = { shapes: {}, alders: [], alderByWard: {}, events: [], eventById: {}, meta: {}, layers: {},
                 wardLayerSummary: {}, wardAreas: {}, committees: null };
  const ui = {};

  /* ── Values per view ──────────────────────────────────────────────────── */

  function tenureRange() {
    const years = data.alders.map((alder) => alder.years_on_council);
    return [Math.min(...years), TENURE_COLOR_CAP_YEARS];
  }

  function absenceRange() {
    return [0, Math.max(...data.alders.map((alder) => alder.percent_absent))];
  }

  function currentEvent() {
    return data.eventById[state.eventId];
  }

  function voteOf(ward) {
    const event = currentEvent();
    return (event && event.votes_by_ward[ward]) || NOT_ON_ROSTER_LABEL;
  }

  function fillFor(ward) {
    const alder = data.alderByWard[ward];
    if (state.view === 'tenure') {
      const [low, high] = tenureRange();
      return colormap(TENURE_COLORMAP, (alder.years_on_council - low) / (high - low));
    }
    if (state.view === 'absence') {
      const [low, high] = absenceRange();
      return colormap(ABSENCE_COLORMAP, (alder.percent_absent - low) / (high - low));
    }
    if (state.view === 'votes') {
      const vote = voteOf(ward);
      return vote === NOT_ON_ROSTER_LABEL ? 'url(#cc-hatch)' : (VOTE_COLORS[vote] || '#ffffff');
    }
    if (state.view === 'committees') return committeeFill(ward);
    return ALDER_FILL;
  }

  // Third label line on tiles: the view's value.
  function valueText(ward) {
    const alder = data.alderByWard[ward];
    if (state.view === 'tenure') return `${alder.years_on_council.toFixed(TENURE_DECIMALS)} yr`;
    if (state.view === 'absence') return `${alder.percent_absent.toFixed(ABSENCE_DECIMALS)}%`;
    if (state.view === 'votes') return voteOf(ward) === NOT_ON_ROSTER_LABEL ? '—' : voteOf(ward);
    if (state.view === 'committees') return committeeValueText(ward);
    return '';
  }

  /* ── Committees view (committees.json) ────────────────────────────────── */

  function committeeList() {
    return data.committees.committees;
  }

  // Overview maps (ward_maps.OVERVIEW_VIEWS, computed in Python: committees.json `overviews`). state.committee
  // is an overview key (text) or a committee index (number).
  function currentOverview() {
    return data.committees.overviews.find((overview) => overview.key === state.committee) || null;
  }

  // This ward's assignments, in committee order: [{ committee, index, role }] (role = eLMS memberType).
  function wardAssignments(ward) {
    return (data.committees.by_ward[ward] || []).map(([index, role]) => ({ committee: committeeList()[index], index, role }));
  }

  // The ward's role on one committee (by index), or null if not on it.
  function committeeRoleIn(ward, index) {
    const found = wardAssignments(ward).find((assignment) => assignment.index === index);
    return found ? found.role : null;
  }

  // Overview entry for a ward: { fills: [{color, opacity}], roles, short_labels }, or null (uncolored).
  function overviewEntry(ward) {
    return currentOverview().by_ward[ward] || null;
  }

  // Roles marked on the name (star, bold / italic): an overview = the ward's roles on that map;
  // one committee = the role on that committee.
  function committeeMarkRoles(ward) {
    if (currentOverview()) return (overviewEntry(ward) || { roles: [] }).roles;
    const role = committeeRoleIn(ward, state.committee);
    return role ? [role] : [];
  }

  function nameWithRoleMarks(labelName, roles) {
    const style = data.committees.style;
    const marks = [];
    if (roles.includes('Chair')) marks.push(style.chair_mark);
    if (roles.includes('Vice Chair')) marks.push(style.vice_chair_mark);
    return [labelName, ...marks].join(' ');
  }

  // Inline CSS for a name line: chair bold, vice chair italic, both bold italic
  // (ward_maps CHAIR_FONT_WEIGHT / VICE_CHAIR_FONT_STYLE).
  function roleFontCss(roles) {
    const style = data.committees.style;
    return (roles.includes('Chair') ? `font-weight:${style.chair_font_weight};` : '')
      + (roles.includes('Vice Chair') ? `font-style:${style.vice_chair_font_style};` : '');
  }

  // [fill, opacity] for a ward. Several fills: stripes (drawMap's <defs>), each stripe with its own opacity.
  function committeeFillAndOpacity(ward) {
    const style = data.committees.style;
    if (currentOverview()) {
      const entry = overviewEntry(ward);
      if (!entry) return [style.uncolored_fill, style.fill_opacity];
      if (entry.fills.length === 1) return [entry.fills[0].color, entry.fills[0].opacity];
      return [`url(#cc-stripes-${ward})`, 1];
    }
    if (!committeeRoleIn(ward, state.committee)) return [style.uncolored_fill, style.fill_opacity];
    const committee = committeeList()[state.committee];
    return [(style.view_fill === 'committee_color' && committee.color) || style.member_fallback_fill, style.fill_opacity];
  }

  function committeeFill(ward) {
    return committeeFillAndOpacity(ward)[0];
  }

  // Value line (tiles) / third line (Map View): an overview with committee_line = the short labels; the
  // combined overview = none; one committee = the alder's role on it.
  function committeeValueText(ward) {
    const overview = currentOverview();
    if (overview) return overview.committee_line && overviewEntry(ward) ? overviewEntry(ward).short_labels.join(' / ') : '';
    const role = committeeRoleIn(ward, state.committee);
    return role ? COMMITTEE_ROLE_TEXT[role] || role : '';
  }

  // <pattern> per ward with more than one fill on an overview: 45° stripes, one per fill (chair first),
  // each style.multi_chair_stripe_points wide (points -> map units like the labels).
  function addStripePatterns(definitions, scale) {
    if (state.view !== 'committees' || !currentOverview()) return;
    const stripeUnits = data.committees.style.multi_chair_stripe_points
      * data.meta.real_map_labels.meters_per_point * DEGREES_PER_WEB_MERCATOR_METER * scale;
    Object.entries(currentOverview().by_ward).forEach(([ward, entry]) => {
      if (entry.fills.length < 2) return;
      const size = stripeUnits * entry.fills.length;
      const pattern = svgEl('pattern', { id: `cc-stripes-${ward}`, patternUnits: 'userSpaceOnUse', width: size, height: size,
                                         patternTransform: 'rotate(45)' });
      pattern.append(svgEl('rect', { width: size, height: size, fill: data.committees.style.uncolored_fill }));
      entry.fills.forEach((fill, index) => pattern.append(svgEl('rect', { x: index * stripeUnits, y: 0, width: stripeUnits, height: size,
                                                                          fill: fill.color, 'fill-opacity': fill.opacity })));
      definitions.append(pattern);
    });
  }

  /* ── Wards tab: what each ward holds (ward_layer_summary.json) ─────────── */

  function layerEntry(ward) {
    const layerSummary = data.wardLayerSummary[state.layer];
    return { tile: layerSummary.tile, ...layerSummary.by_ward[ward] };
  }

  function wardAreaText(ward) {
    return `${data.wardAreas[ward].area_sq_mi.toFixed(WARD_AREA_DECIMALS)} sq mi`;
  }

  function displayName(name) {
    return (LAYER_NAME_PREFIX[state.layer] || '') + name;
  }

  function countText(count) {
    const [singular, plural] = LAYER_COUNT_NOUN[state.layer] || ['item', 'items'];
    return `${count} ${count === 1 ? singular : plural}`;
  }

  // Names with the share of the ward each covers, where the rule has one ("NORTH CENTER 45%").
  function namesWithShares(entry) {
    return entry.names.map((name, index) => displayName(name)
      + (entry.shares ? ` ${Math.round(entry.shares[index] * 100)}%` : ''));
  }

  // Largest font (steps of 0.25, up to TILE_MAX_FONT_SIZE) at which `heading` plus `body`, word-wrapped,
  // fits inside the tile less TILE_WRAP_EDGE_MARGIN. Widths measured on a canvas with the page's font.
  const measureCanvas = document.createElement('canvas').getContext('2d');
  function textWidth(content, fontSize, weight) {
    measureCanvas.font = `${weight} ${fontSize}px ${getComputedStyle(document.getElementById(CONTAINER_ID)).fontFamily}`;
    return measureCanvas.measureText(content).width;
  }
  function wrapToTile(heading, body, tileWidth, tileHeight) {
    const usableWidth = tileWidth * (1 - 2 * TILE_WRAP_EDGE_MARGIN);
    const usableHeight = tileHeight * (1 - 2 * TILE_WRAP_EDGE_MARGIN);
    const words = body.split(' ');
    for (let fontSize = TILE_MAX_FONT_SIZE; fontSize > 1; fontSize -= 0.25) {
      if (textWidth(heading, fontSize, 700) > usableWidth) continue;
      const wrapped = [];
      let current = '';
      let fits = true;
      words.forEach((word) => {
        const candidate = current ? `${current} ${word}` : word;
        if (textWidth(candidate, fontSize, 400) <= usableWidth) { current = candidate; return; }
        if (current) wrapped.push(current);
        current = word;
        if (textWidth(word, fontSize, 400) > usableWidth) fits = false;   // one word wider than the tile
      });
      if (current) wrapped.push(current);
      const lineCount = wrapped.length + 1;
      if (fits && lineCount * fontSize * TILE_LINE_STEP <= usableHeight) return { lines: [heading, ...wrapped], fontSize };
    }
    return { lines: [heading, body], fontSize: 1 };
  }

  /* ── Map ──────────────────────────────────────────────────────────────── */

  function drawMap() {
    const collection = data.shapes[state.shapes];
    const projected = collection.features.map((feature) => {
      const rings = [];
      forEachRing(feature.geometry, (ring) => rings.push(ring.map(project)));
      // labels: Map View anchors per layout, {layout: [lon, lat]} (real wards only).
      const labels = {};
      Object.entries(feature.properties.labels || {}).forEach(([layout, lonLat]) => { labels[layout] = project(lonLat); });
      return { ward: feature.properties.ward, rings, labels, colorIndex: feature.properties.color_index,
               label: project([feature.properties.label_lon, feature.properties.label_lat]) };
    });

    // Fit: bounding box of every ring, with a margin; y flipped (north up).
    let minX = Infinity; let minY = Infinity; let maxX = -Infinity; let maxY = -Infinity;
    projected.forEach((shape) => shape.rings.forEach((ring) => ring.forEach(([x, y]) => {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    })));
    const width = 1000;
    const scale = width / (maxX - minX);
    const height = (maxY - minY) * scale;
    const margin = 10;
    const toScreen = ([x, y]) => [margin + (x - minX) * scale, margin + (maxY - y) * scale];

    const svg = svgEl('svg', { viewBox: `0 0 ${width + 2 * margin} ${height + 2 * margin}`, role: 'img',
                               'aria-label': `Chicago wards, ${state.view}` });
    const definitions = svgEl('defs');
    const hatch = svgEl('pattern', { id: 'cc-hatch', patternUnits: 'userSpaceOnUse', width: 8, height: 8,
                                     patternTransform: 'rotate(45)' });
    hatch.append(svgEl('rect', { width: 8, height: 8, fill: '#fff' }));
    hatch.append(svgEl('line', { x1: 0, y1: 0, x2: 0, y2: 8, stroke: '#999', 'stroke-width': 2 }));
    definitions.append(hatch);
    addStripePatterns(definitions, scale);
    svg.append(definitions);

    const geometry = { toScreen, bounds: { minX, maxX, minY, maxY }, width: width + 2 * margin, height: height + 2 * margin,
                       fromScreen: ([screenX, screenY]) => [minX + (screenX - margin) / scale, maxY - (screenY - margin) / scale] };
    if (state.view === 'wards' && state.shapes === 'real') {
      drawLayerMap(svg, projected, toScreen, scale, geometry.bounds);
      finishMap(svg, geometry);
      return;
    }

    projected.forEach((shape) => {
      const pathText = shape.rings.map((ring) => 'M' + ring.map(toScreen).map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L') + 'Z').join('');
      const path = svgEl('path', { d: pathText, fill: fillFor(shape.ward), class: 'cc-ward', 'fill-rule': 'evenodd',
                                   'data-ward': shape.ward });
      // Committees: ward_maps COMMITTEE_FILL_OPACITY, as the notebook map (other views fill solid).
      if (state.view === 'committees') path.setAttribute('fill-opacity', committeeFillAndOpacity(shape.ward)[1]);
      if (shape.ward === state.selectedWard) path.classList.add('cc-selected');
      path.addEventListener('mousemove', (event) => showTooltip(shape.ward, event));
      path.addEventListener('mouseleave', hideTooltip);
      path.addEventListener('click', (event) => {
        selectWard(shape.ward);
        showTooltip(shape.ward, event);
        if (SCROLL_TABLE_TO_SELECTED_WARD) scrollTableToSelectedRow();
      });
      svg.append(path);
    });

    // Labels.
    if (state.shapes === 'real' && REAL_MAP_LABEL === 'notebook_layout') {
      drawNotebookLabels(svg, projected, toScreen, scale);
      finishMap(svg, geometry);
      return;
    }
    const tileLabels = [];   // Wards tab: drawn after sizing (WARDS_TILE_FONT_FIT)
    projected.forEach((shape) => {
      const [labelX, labelY] = toScreen(shape.label);
      const fill = fillFor(shape.ward);
      const ink = fill.startsWith('url') ? '#111' : textColorFor(fill);
      const alder = data.alderByWard[shape.ward];
      let lines;
      let fontSize;
      let lineStyles = [];   // inline CSS per line ('' = the .cc-label default)
      if (state.shapes === 'real' && REAL_MAP_LABEL === 'number') {
        lines = [String(Number(shape.ward))];
        fontSize = REAL_MAP_NUMBER_FONT_SIZE;
      } else {
        // Tile size on screen: from the tile's own ring.
        const xs = shape.rings[0].map((point) => toScreen(point)[0]);
        const ys = shape.rings[0].map((point) => toScreen(point)[1]);
        const tileWidth = Math.max(...xs) - Math.min(...xs);
        const tileHeight = Math.max(...ys) - Math.min(...ys);
        if (state.view === 'wards' && !data.wardLayerSummary[state.layer]) {
          lines = [String(Number(shape.ward)), wardAreaText(shape.ward)];   // Street map: ward area
        } else if (state.view === 'wards') {
          // Ward number, then the layer's names (at most TILE_MAX_LIST_LINES) or its count.
          const entry = layerEntry(shape.ward);
          lines = [String(Number(shape.ward))];
          if (entry.tile === 'count') {
            lines.push(countText(entry.names.length));
          } else {
            const shown = entry.names.slice(0, TILE_MAX_LIST_LINES).map(displayName);
            const hidden = entry.names.length - shown.length;
            lines.push(...(hidden > 0 ? [...shown.slice(0, -1), `+${hidden + 1} more`] : shown));
          }
        } else if (state.view === 'committees') {
          // Name line with the role mark, chair bold / vice chair italic on a normal-weight base (the
          // .cc-label default, 600, would hide the bold); then the committee line.
          const roles = committeeMarkRoles(shape.ward);
          lines = [`${Number(shape.ward)} ${nameWithRoleMarks(alder.label_name, roles)}`];
          lineStyles = [`font-weight:400;${roleFontCss(roles)}`, 'font-weight:400'];
          if (valueText(shape.ward)) lines.push(valueText(shape.ward));
        } else {
          lines = [`${Number(shape.ward)} ${alder.label_name}`];
          if (valueText(shape.ward)) lines.push(valueText(shape.ward));
        }
        // Font fits the tile: width (about 0.58 em per character) and height (lines x 1.2 em).
        const longest = Math.max(...lines.map((line) => line.length));
        fontSize = Math.min(tileWidth / (0.58 * longest), tileHeight / (lines.length * 1.35), TILE_MAX_FONT_SIZE);
        if (state.view === 'wards' && TILE_WRAP_LAYERS.includes(state.layer)) {
          ({ lines, fontSize } = wrapToTile(lines[0], lines.slice(1).join(' '), tileWidth, tileHeight));
        }
      }
      if (state.view === 'wards') { tileLabels.push({ labelX, labelY, ink, lines, fontSize }); return; }
      lines.forEach((line, index) => {
        const offset = (index - (lines.length - 1) / 2) * fontSize * 1.15;
        const text = svgEl('text', { x: labelX.toFixed(1), y: (labelY + offset).toFixed(1), class: 'cc-label',
                                     'font-size': fontSize.toFixed(1), fill: ink,
                                     'data-anchor-x': labelX.toFixed(1), 'data-anchor-y': labelY.toFixed(1),
                                     style: lineStyles[index] || '' });
        text.textContent = line;
        svg.append(text);
      });
    });

    const uniformSize = Math.min(...tileLabels.map((label) => label.fontSize));
    tileLabels.forEach(({ labelX, labelY, ink, lines, fontSize }) => {
      const size = WARDS_TILE_FONT_FIT === 'uniform' ? uniformSize : fontSize;
      lines.forEach((line, index) => {
        const offset = (index - (lines.length - 1) / 2) * size * TILE_LINE_STEP;
        // First line = ward number, bold; the rest normal weight.
        const text = svgEl('text', { x: labelX.toFixed(1), y: (labelY + offset).toFixed(1), class: 'cc-label',
                                     'font-size': size.toFixed(1), fill: ink,
                                     'data-anchor-x': labelX.toFixed(1), 'data-anchor-y': labelY.toFixed(1),
                                     style: index === 0 ? 'font-weight:700' : 'font-weight:400' });
        text.textContent = line;
        svg.append(text);
      });
    });

    finishMap(svg, geometry);
  }

  /* ── Zoom ─────────────────────────────────────────────────────────────── */

  // Moves everything drawn (not <defs>) into one group that zooms, puts the map on the page, adds
  // the zoom buttons and handlers, and re-applies this view's saved zoom.
  function finishMap(svg, geometry) {
    const zoomLayer = svgEl('g', { class: 'cc-zoom-layer' });
    [...svg.childNodes].filter((node) => node.tagName !== 'defs').forEach((node) => zoomLayer.append(node));
    svg.append(zoomLayer);
    ui.mapGeometry = geometry;
    ui.zoomLayer = zoomLayer;
    ui.mapSvg = svg;
    const button = (label, title, onClick) => el('button', { type: 'button', title, 'aria-label': title, text: label, onclick: onClick });
    const controls = el('div', { class: 'cc-zoom-buttons' }, [
      button('+', 'Zoom in', () => zoomBy(ZOOM_BUTTON_STEP)),
      button('−', 'Zoom out', () => zoomBy(1 / ZOOM_BUTTON_STEP)),
      button('⟲', 'Show the whole city', () => setZoom({ k: 1, x: 0, y: 0 })),
    ]);
    const hint = el('div', { class: 'cc-zoom-hint', text: ZOOM_WHEEL === 'modifier' ? 'Ctrl/⌘ + scroll or pinch to zoom · drag to move' : 'Scroll to zoom · drag to move' });
    ui.map.replaceChildren(el('div', { class: 'cc-zoom-frame' }, [svg, controls, hint]));
    attachZoomHandlers(svg);
    applyZoom();
    drawLegend();
  }

  function currentZoom() {
    return state.zoomByShapes[state.shapes];
  }

  // Keeps the map covering its frame: no panning past the city's edges, no zooming out past 1.
  function clampZoom({ k, x, y }) {
    const { width, height } = ui.mapGeometry;
    const scale = Math.min(ZOOM_MAX, Math.max(1, k));
    return { k: scale, x: Math.min(0, Math.max(width * (1 - scale), x)), y: Math.min(0, Math.max(height * (1 - scale), y)) };
  }

  function setZoom(zoom) {
    state.zoomByShapes[state.shapes] = clampZoom(zoom);
    applyZoom();
  }

  // Zoom by `factor` about a point in SVG units (default: the middle of the map).
  function zoomBy(factor, point) {
    const zoom = currentZoom();
    const [pointX, pointY] = point || [ui.mapGeometry.width / 2, ui.mapGeometry.height / 2];
    const newScale = Math.min(ZOOM_MAX, Math.max(1, zoom.k * factor));
    const ratio = newScale / zoom.k;
    setZoom({ k: newScale, x: pointX - (pointX - zoom.x) * ratio, y: pointY - (pointY - zoom.y) * ratio });
  }

  // How much labels are scaled back so their screen size follows ZOOM_LABELS_BY_SHAPES.
  // isLayerLabel: the element is a Wards tab layer label (own cap, ZOOM_LAYER_LABEL_MAX_PX).
  function labelCounterScale(k, isLayerLabel) {
    const mode = ZOOM_LABELS_BY_SHAPES[state.shapes];
    if (mode === 'grow') return 1;
    if (mode === 'grow_until') return Math.min(k, ZOOM_LABEL_MAX_GROWTH) / k;
    if (mode === 'grow_until_px') {
      const capPx = isLayerLabel ? ZOOM_LAYER_LABEL_MAX_PX : ZOOM_LABEL_MAX_PX;
      return Math.min(k, Math.max(1, capPx / largestLabelPx(isLayerLabel))) / k;
    }
    return 1 / k;   // constant
  }

  // Largest label font on screen at zoom 1 (screen px) in one group (layer labels, or all other labels):
  // biggest font-size among those zooming labels, times the map's SVG-unit-to-screen-px factor (the
  // outer <svg>, not the zoom group).
  function largestLabelPx(isLayerLabel) {
    const sizes = [...ui.zoomLayer.querySelectorAll('text[data-anchor-x]')]
      .filter((text) => text.matches(LAYER_LABEL_SELECTOR) === isLayerLabel)
      .map((text) => parseFloat(text.getAttribute('font-size')));
    const matrix = ui.mapSvg.getScreenCTM();
    if (!sizes.length || !matrix) return isLayerLabel ? ZOOM_LAYER_LABEL_MAX_PX : ZOOM_LABEL_MAX_PX;
    return Math.max(...sizes) * matrix.a;
  }

  function applyZoom() {
    const { k, x, y } = currentZoom();
    ui.zoomLayer.setAttribute('transform', `translate(${x.toFixed(2)},${y.toFixed(2)}) scale(${k.toFixed(4)})`);
    // Labels and layer points: scaled about their own anchor, so a label's lines stay together.
    const labelScales = { other: labelCounterScale(k, false), layer: labelCounterScale(k, true) };
    ui.zoomLayer.querySelectorAll('[data-anchor-x]').forEach((element) => {
      const anchorX = element.dataset.anchorX; const anchorY = element.dataset.anchorY;
      const labelScale = element.matches(LAYER_LABEL_SELECTOR) ? labelScales.layer : labelScales.other;
      if (labelScale === 1) element.removeAttribute('transform');
      else element.setAttribute('transform', `translate(${anchorX},${anchorY}) scale(${labelScale.toFixed(4)}) translate(${-anchorX},${-anchorY})`);
    });
    const lineScale = ZOOM_LINE_WIDTH === 'constant' ? 1 / k : 1;
    ui.zoomLayer.querySelectorAll('[data-base-stroke]').forEach((element) => {
      element.setAttribute('stroke-width', (element.dataset.baseStroke * lineScale).toFixed(3));
    });
    ui.mapSvg.style.touchAction = k > 1 ? 'none' : 'pan-x pan-y';   // at whole-city view a finger scrolls the page
    scheduleDetailTiles();
  }

  // Street map: after zooming stops, load sharper tiles for what's on screen.
  function scheduleDetailTiles() {
    clearTimeout(ui.detailTimer);
    ui.detailTimer = setTimeout(loadDetailTiles, STREET_MAP_DETAIL_DELAY_MS);
  }

  function loadDetailTiles() {
    const detailGroup = ui.zoomLayer && ui.zoomLayer.querySelector('.cc-tiles-detail');
    if (!detailGroup) return;
    const { k, x, y } = currentZoom();
    const tileZoom = Math.min(STREET_MAP_MAX_TILE_ZOOM, STREET_MAP_TILE_ZOOM + Math.floor(Math.log2(k)));
    if (tileZoom === STREET_MAP_TILE_ZOOM) { detailGroup.replaceChildren(); return; }
    // Visible part of the map, in this page's map coordinates. Measured from the SVG element's box on
    // screen, which can be wider than the drawing (height-limited maps leave side margins that show
    // zoomed content too).
    const { fromScreen, toScreen } = ui.mapGeometry;
    const box = ui.mapSvg.getBoundingClientRect();
    const [screenLeft, screenTop] = svgPoint(ui.mapSvg, box.left, box.top);
    const [screenRight, screenBottom] = svgPoint(ui.mapSvg, box.right, box.bottom);
    const [left, top] = fromScreen([(screenLeft - x) / k, (screenTop - y) / k]);
    const [right, bottom] = fromScreen([(screenRight - x) / k, (screenBottom - y) / k]);
    const temporary = svgEl('g');
    const newTiles = drawStreetTiles(temporary, toScreen, { minX: left, maxX: right, minY: bottom, maxY: top }, tileZoom, 'cc-tiles-detail');
    detailGroup.replaceWith(newTiles);
  }

  function svgPoint(svg, clientX, clientY) {
    const point = new DOMPoint(clientX, clientY).matrixTransform(svg.getScreenCTM().inverse());
    return [point.x, point.y];
  }

  // Wheel (see ZOOM_WHEEL), drag to pan, two-finger pinch. A press that moves less than
  // ZOOM_DRAG_THRESHOLD_PX stays a click, so wards can still be selected.
  function attachZoomHandlers(svg) {
    svg.addEventListener('wheel', (event) => {
      if (ZOOM_WHEEL === 'modifier' && !event.ctrlKey && !event.metaKey) return;   // let the page scroll
      event.preventDefault();
      zoomBy(Math.exp(-event.deltaY * 0.002), svgPoint(svg, event.clientX, event.clientY));
    }, { passive: false });

    const pointers = new Map();   // pointerId -> latest [clientX, clientY]
    let gesture = null;           // start of the current drag or pinch
    let dragged = false;
    const startGesture = () => {
      const points = [...pointers.values()];
      const zoom = currentZoom();
      if (points.length === 1) {
        gesture = { kind: 'drag', start: points[0], zoom: { ...zoom } };
      } else if (points.length === 2) {
        const middle = [(points[0][0] + points[1][0]) / 2, (points[0][1] + points[1][1]) / 2];
        gesture = { kind: 'pinch', distance: Math.hypot(points[0][0] - points[1][0], points[0][1] - points[1][1]),
                    middle: svgPoint(svg, ...middle), zoom: { ...zoom } };
      }
    };
    svg.addEventListener('pointerdown', (event) => {
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      pointers.set(event.pointerId, [event.clientX, event.clientY]);
      dragged = false;
      startGesture();
    });
    // Pan for a one-pointer drag that has moved to (clientX, clientY).
    const dragTo = (clientX, clientY, pointerId) => {
      const moveX = clientX - gesture.start[0]; const moveY = clientY - gesture.start[1];
      if (!dragged && Math.hypot(moveX, moveY) < ZOOM_DRAG_THRESHOLD_PX) return;
      if (!dragged) { dragged = true; svg.setPointerCapture(pointerId); hideTooltip(); }
      const unitsPerPixel = 1 / svg.getScreenCTM().a;
      setZoom({ k: gesture.zoom.k, x: gesture.zoom.x + moveX * unitsPerPixel, y: gesture.zoom.y + moveY * unitsPerPixel });
    };
    svg.addEventListener('pointermove', (event) => {
      if (!pointers.has(event.pointerId) || !gesture) return;
      pointers.set(event.pointerId, [event.clientX, event.clientY]);
      const points = [...pointers.values()];
      if (gesture.kind === 'drag' && points.length === 1) {
        dragTo(event.clientX, event.clientY, event.pointerId);
      } else if (gesture.kind === 'pinch' && points.length === 2) {
        dragged = true;
        const distance = Math.hypot(points[0][0] - points[1][0], points[0][1] - points[1][1]);
        const newScale = Math.min(ZOOM_MAX, Math.max(1, gesture.zoom.k * distance / gesture.distance));
        const ratio = newScale / gesture.zoom.k;
        const [middleX, middleY] = gesture.middle;
        setZoom({ k: newScale, x: middleX - (middleX - gesture.zoom.x) * ratio, y: middleY - (middleY - gesture.zoom.y) * ratio });
      }
    });
    const endPointer = (event) => {
      // A release far from the press counts as a drag even if no move events arrived in between.
      if (event.type === 'pointerup' && gesture && gesture.kind === 'drag') dragTo(event.clientX, event.clientY, event.pointerId);
      pointers.delete(event.pointerId);
      gesture = null;
      if (pointers.size) startGesture();   // pinch -> one finger left: continue as a drag
    };
    svg.addEventListener('pointerup', endPointer);
    svg.addEventListener('pointercancel', endPointer);
    // After a drag, swallow the click so the ward under the pointer isn't selected.
    svg.addEventListener('click', (event) => { if (dragged) { event.stopPropagation(); dragged = false; } }, true);
  }

  function pathData(geometry, toScreen) {
    const rings = [];
    forEachRing(geometry, (ring) => rings.push(ring));
    return rings.map((ring) => 'M' + ring.map(project).map(toScreen)
      .map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L') + 'Z').join('');
  }

  function lineData(geometry, toScreen) {
    const lines = geometry.type === 'LineString' ? [geometry.coordinates] : geometry.coordinates;
    return lines.map((line) => 'M' + line.map(project).map(toScreen)
      .map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L')).join('');
  }

  // Wards tab, Map View: map_layers_review's large map, in its drawing order: layer (fill colors by
  // color_index / parks one green / rail lines / points), italic layer labels with a white halo,
  // then black ward outlines and bold ward numbers on top. Wards stay clickable through a
  // transparent hit area drawn first; points sit above it so they can be hovered.
  // Esri tiles covering the map's bounding box, each placed by its corners (this page's projection is
  // Web Mercator in degrees, the same as the tiles', so tiles are plain rectangles).
  function drawStreetTiles(svg, toScreen, bounds, tileZoom = STREET_MAP_TILE_ZOOM, groupClass = 'cc-tiles-base') {
    const group = svgEl('g', { class: groupClass });
    const tileCount = 2 ** tileZoom;
    const tileX = (longitude) => Math.floor(((longitude + 180) / 360) * tileCount);
    const tileY = (mercatorDegrees) => Math.floor(((1 - mercatorDegrees / 180) / 2) * tileCount);
    const cornerLongitude = (x) => (x / tileCount) * 360 - 180;
    const cornerMercator = (y) => (1 - (2 * y) / tileCount) * 180;
    for (let x = tileX(bounds.minX); x <= tileX(bounds.maxX); x += 1) {
      for (let y = tileY(bounds.maxY); y <= tileY(bounds.minY); y += 1) {
        const [left, top] = toScreen([cornerLongitude(x), cornerMercator(y)]);
        const [right, bottom] = toScreen([cornerLongitude(x + 1), cornerMercator(y + 1)]);
        group.append(svgEl('image', { href: STREET_MAP_TILE_URL.replace('{z}', tileZoom).replace('{x}', x).replace('{y}', y),
          x: left.toFixed(2), y: top.toFixed(2),
          width: (right - left + STREET_MAP_TILE_SEAM_OVERLAP).toFixed(2), height: (bottom - top + STREET_MAP_TILE_SEAM_OVERLAP).toFixed(2),
          preserveAspectRatio: 'none', class: 'cc-layer-shape' }));
      }
    }
    svg.append(group);
    return group;
  }

  function drawLayerMap(svg, projected, toScreen, scale, bounds) {
    const style = data.meta.layers.style;
    const isStreetMap = state.layer === 'street_map';
    const unitsPerPoint = data.meta.real_map_labels.meters_per_point * DEGREES_PER_WEB_MERCATOR_METER * scale;
    const markUnits = unitsPerPoint * LAYER_MAP_LINE_SCALE;
    const pointUnits = unitsPerPoint * LAYER_MAP_POINT_SCALE;
    const labelUnits = unitsPerPoint * LAYER_MAP_LABEL_SCALE;
    const haloWidth = data.meta.real_map_labels.halo_points * labelUnits;
    const layerInfo = data.meta.layers.by_layer[state.layer];
    if (data.meta.layers.positions_for_scale !== undefined && data.meta.layers.positions_for_scale !== LAYER_MAP_LABEL_SCALE) {
      console.warn(`Wards tab label positions were set for scale ${data.meta.layers.positions_for_scale} (${data.meta.layers.label_positions}); page draws ${LAYER_MAP_LABEL_SCALE}`);
    }
    const collection = data.layers[state.layer];

    if (isStreetMap) {
      drawStreetTiles(svg, toScreen, bounds);
      svg.append(svgEl('g', { class: 'cc-tiles-detail' }));   // filled by loadDetailTiles after zooming
    }
    // 1. Ward hit areas (transparent; on the street map, filled by neighbor color).
    projected.forEach((shape) => {
      const pathText = shape.rings.map((ring) => 'M' + ring.map(toScreen).map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L') + 'Z').join('');
      const path = svgEl('path', { d: pathText, class: 'cc-ward-hit', 'fill-rule': 'evenodd', 'data-ward': shape.ward });
      if (isStreetMap) {
        path.style.fill = style.fill_palette[shape.colorIndex % style.fill_palette.length];
        path.style.fillOpacity = STREET_MAP_WARD_FILL_OPACITY;
      }
      if (shape.ward === state.selectedWard) path.classList.add('cc-selected');
      path.addEventListener('mousemove', (event) => showTooltip(shape.ward, event));
      path.addEventListener('mouseleave', hideTooltip);
      path.addEventListener('click', (event) => {
        selectWard(shape.ward);
        showTooltip(shape.ward, event);
        if (SCROLL_TABLE_TO_SELECTED_WARD) scrollTableToSelectedRow();
      });
      svg.append(path);
    });

    // 2. The layer.
    if (isStreetMap) {
      // nothing more: tiles and ward fill are drawn above
    } else if (!collection) {
      const note = svgEl('text', { x: 500, y: 60, 'text-anchor': 'middle', 'font-size': 24 });
      note.textContent = 'Loading layer…';
      svg.append(note);
    } else {
      collection.features.forEach((feature) => {
        const properties = feature.properties;
        if (layerInfo.kind === 'fill') {
          svg.append(svgEl('path', { d: pathData(feature.geometry, toScreen), class: 'cc-layer-shape', 'fill-rule': 'evenodd',
            fill: style.fill_palette[properties.color_index % style.fill_palette.length], 'fill-opacity': style.fill_opacity,
            stroke: style.fill_edge_color, 'stroke-width': (style.fill_edge_points * markUnits).toFixed(2),
            'data-base-stroke': (style.fill_edge_points * markUnits).toFixed(2) }));
        } else if (layerInfo.kind === 'single') {
          // matplotlib's alpha applies to fill and edge alike.
          svg.append(svgEl('path', { d: pathData(feature.geometry, toScreen), class: 'cc-layer-shape', 'fill-rule': 'evenodd',
            fill: style.single_fill_color, stroke: style.single_fill_color, opacity: style.single_opacity,
            'stroke-width': (style.single_edge_points * markUnits).toFixed(2),
            'data-base-stroke': (style.single_edge_points * markUnits).toFixed(2) }));
        } else if (layerInfo.kind === 'line') {
          svg.append(svgEl('path', { d: lineData(feature.geometry, toScreen), class: 'cc-layer-shape', fill: 'none',
            stroke: style.line_color, 'stroke-width': (style.line_points * markUnits).toFixed(2), 'stroke-linejoin': 'round',
            'data-base-stroke': (style.line_points * markUnits).toFixed(2) }));
        } else if (layerInfo.kind === 'point') {
          const [pointX, pointY] = toScreen(project(feature.geometry.coordinates));
          // markersize is the marker's area in points^2, so its diameter is the square root.
          const radius = (Math.sqrt(style.point_area_points2) / 2) * pointUnits;
          const circle = svgEl('circle', { cx: pointX.toFixed(1), cy: pointY.toFixed(1), r: radius.toFixed(2),
            class: 'cc-layer-point', fill: style.point_color, stroke: style.point_edge_color,
            'stroke-width': (style.point_edge_points * pointUnits).toFixed(2),
            'data-anchor-x': pointX.toFixed(1), 'data-anchor-y': pointY.toFixed(1) });
          circle.addEventListener('mousemove', (event) => showLayerTooltip(properties, event));
          circle.addEventListener('mouseleave', hideTooltip);
          svg.append(circle);
        }
      });
      // 3. Layer labels (only layers with a LAYER_STYLE label column).
      if (layerInfo.has_labels) {
        collection.features.forEach((feature) => {
          const [labelX, labelY] = toScreen(project([feature.properties.label_lon, feature.properties.label_lat]));
          const text = svgEl('text', { x: labelX.toFixed(1), y: labelY.toFixed(1), class: 'cc-layer-label',
            'font-size': (style.label_font_points * labelUnits).toFixed(2), fill: style.label_color,
            'stroke-width': haloWidth.toFixed(2), 'data-anchor-x': labelX.toFixed(1), 'data-anchor-y': labelY.toFixed(1) });
          text.textContent = feature.properties.label;
          svg.append(text);
        });
      }
    }

    // 4. Ward outlines and bold ward numbers on top.
    projected.forEach((shape) => {
      const pathText = shape.rings.map((ring) => 'M' + ring.map(toScreen).map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L') + 'Z').join('');
      svg.append(svgEl('path', { d: pathText, class: 'cc-ward-outline', fill: 'none', stroke: '#000',
        'stroke-width': (style.ward_outline_points * markUnits).toFixed(2), 'stroke-linejoin': 'round',
        'data-base-stroke': (style.ward_outline_points * markUnits).toFixed(2) }));
    });
    projected.forEach((shape) => {
      const [numberX, numberY] = toScreen(shape.labels.ward_number);
      const text = svgEl('text', { x: numberX.toFixed(1), y: numberY.toFixed(1), class: 'cc-ward-number',
        'font-size': (style.ward_number_font_points * labelUnits).toFixed(2), 'stroke-width': haloWidth.toFixed(2),
        'data-anchor-x': numberX.toFixed(1), 'data-anchor-y': numberY.toFixed(1) });
      text.textContent = String(Number(shape.ward));   // the notebook prints the layer's unpadded ward
      svg.append(text);
    });
  }

  // Map View labels as ward_views draws them (scripts/ward_maps.py draw_ward_labels and
  // draw_ward_two_size_labels): black text with a white halo, normal weight, at the exported anchor.
  //   one_block: "ward" over "Last name", the block centered on the anchor
  //   two_sizes: "ward Last" with its bottom at the anchor, the value with its top at the anchor
  function drawNotebookLabels(svg, projected, toScreen, scale) {
    const labelMeta = data.meta.real_map_labels;
    if (labelMeta.positions_for_scale !== undefined && labelMeta.positions_for_scale !== REAL_MAP_LABEL_SCALE) {
      console.warn(`Map View label positions were set for scale ${labelMeta.positions_for_scale} (${labelMeta.positions}); page draws ${REAL_MAP_LABEL_SCALE}`);
    }
    const layoutName = REAL_MAP_LAYOUT_BY_VIEW[state.view];
    const layout = labelMeta.layouts[layoutName];
    // Points on the notebook figure -> this SVG's units.
    const unitsPerPoint = labelMeta.meters_per_point * DEGREES_PER_WEB_MERCATOR_METER * scale * REAL_MAP_LABEL_SCALE;
    const haloWidth = labelMeta.halo_points * unitsPerPoint;
    function addText(x, y, content, fontPoints, baseline, anchor, extraCss = '') {
      const text = svgEl('text', { x: x.toFixed(1), y: y.toFixed(1), class: 'cc-label cc-label-notebook',
                                   'data-anchor-x': anchor[0].toFixed(1), 'data-anchor-y': anchor[1].toFixed(1),
                                   'font-size': (fontPoints * unitsPerPoint).toFixed(2),
                                   'stroke-width': haloWidth.toFixed(2),
                                   style: `dominant-baseline:${baseline};${extraCss}` });   // inline: the .cc-label CSS would override an attribute
      text.textContent = content;
      svg.append(text);
    }
    projected.forEach((shape) => {
      const [anchorX, anchorY] = toScreen(shape.labels[layoutName]);
      const alder = data.alderByWard[shape.ward];
      const wardNumber = String(Number(shape.ward));
      if (layout.kind === 'one_block') {
        // "ward" over "Last name", the block centered on the anchor. Committees: the name carries the
        // role mark and font (ward_maps.draw_ward_line_labels), plus a third line on chairs' wards.
        const fontPoints = layout.font_points[0];
        const lineStep = fontPoints * unitsPerPoint * NOTEBOOK_LINE_SPACING;
        const lines = [[wardNumber, ''], [alder.label_name, '']];
        if (state.view === 'committees') {
          const roles = committeeMarkRoles(shape.ward);
          lines[1] = [nameWithRoleMarks(alder.label_name, roles), roleFontCss(roles)];
          if (currentOverview() && committeeValueText(shape.ward)) lines.push([committeeValueText(shape.ward), '']);
        }
        lines.forEach(([content, css], index) => {
          const lineY = anchorY + (index - (lines.length - 1) / 2) * lineStep;
          addText(anchorX, lineY, content, fontPoints, 'central', [anchorX, anchorY], css);
        });
      } else {
        const [nameFontPoints, valueFontPoints] = layout.font_points;
        addText(anchorX, anchorY, `${wardNumber} ${alder.label_name}`, nameFontPoints, 'text-after-edge', [anchorX, anchorY]);
        addText(anchorX, anchorY, notebookValueText(shape.ward), valueFontPoints, 'text-before-edge', [anchorX, anchorY]);
      }
    });
  }

  // Value line on Map View labels, as the notebook writes it (export LABEL_VALUE_DECIMALS).
  function notebookValueText(ward) {
    const alder = data.alderByWard[ward];
    if (state.view === 'tenure') return alder.years_on_council.toFixed(TENURE_DECIMALS);
    if (state.view === 'absence') return `${alder.percent_absent.toFixed(ABSENCE_DECIMALS)}%`;
    return '';
  }

  function drawLegend() {
    const items = [];
    if (state.view === 'tenure') {
      const [low, high] = tenureRange();
      items.push(el('span', { text: `${low.toFixed(TENURE_DECIMALS)} yr` }),
                 el('span', { class: 'cc-gradient', style: `background:${gradientCss(TENURE_COLORMAP)}` }),
                 el('span', { text: `${high}+ yr (years on council)` }));
    } else if (state.view === 'absence') {
      const [low, high] = absenceRange();
      items.push(el('span', { text: `${low}%` }),
                 el('span', { class: 'cc-gradient', style: `background:${gradientCss(ABSENCE_COLORMAP)}` }),
                 el('span', { text: `${high.toFixed(ABSENCE_DECIMALS)}% of council meetings absent` }));
    } else if (state.view === 'votes') {
      const counts = {};
      Object.keys(data.alderByWard).forEach((ward) => { const vote = voteOf(ward); counts[vote] = (counts[vote] || 0) + 1; });
      [...Object.keys(VOTE_COLORS), NOT_ON_ROSTER_LABEL].filter((vote) => counts[vote]).forEach((vote) => {
        const swatchStyle = vote === NOT_ON_ROSTER_LABEL
          ? 'background: repeating-linear-gradient(45deg, #fff 0 3px, #999 3px 5px)'
          : `background:${VOTE_COLORS[vote]}`;
        items.push(el('span', {}, [el('span', { class: 'cc-swatch', style: swatchStyle }),
                                   document.createTextNode(`${vote} (${counts[vote]})`)]));
      });
    } else if (state.view === 'committees') {
      items.push(...committeeLegendItems());
    } else if (state.view === 'wards' && state.layer === 'street_map') {
      items.push(el('span', { text: state.shapes === 'real'
        ? 'Wards colored so neighbors differ, over a street map.'
        : 'Tiles show each ward\'s area in square miles (2023 boundaries). The street map is in Map View.' }));
      if (state.shapes === 'real') items.push(el('span', { style: 'font-size:11px', text: STREET_MAP_ATTRIBUTION }));
    } else if (state.view === 'wards') {
      const layerInfo = data.meta.layers.by_layer[state.layer];
      const layerLabel = LAYER_OPTIONS.find((option) => option.key === state.layer).label;
      const colorNote = layerInfo.kind === 'fill' ? `, colored so neighbors differ (${layerInfo.colors_used} colors)` : '';
      const rule = data.wardLayerSummary[state.layer];
      const tileNote = rule.tile === 'count' ? 'Tiles show the count; hover or see the table for names.'
        : `Tiles show up to ${TILE_MAX_LIST_LINES} names; hover or see the table for all.`;
      items.push(el('span', { text: state.shapes === 'real'
        ? `${layerLabel}: ${layerInfo.feature_count} features${colorNote}. Black lines and bold numbers = wards.`
        : `${layerLabel}. ${tileNote}` }));
    } else {
      items.push(el('span', { text: 'Hover or tap a ward for its alder.' }));
    }
    ui.legend.replaceChildren(...items);
  }

  // Chairs view: one swatch per colored committee, "short label — full name"; one committee: member
  // swatch and counts. Both: what the star / bold / italic mean.
  function committeeLegendItems() {
    const style = data.committees.style;
    const swatch = (color) => el('span', { class: 'cc-swatch', style: `background:${color};opacity:${style.fill_opacity}` });
    const markKey = (role, text) => el('span', { style: roleFontCss([role]), text: `${role === 'Chair' ? style.chair_mark : style.vice_chair_mark} ${text}` });
    const overview = currentOverview();
    if (overview) {
      const colored = committeeList().filter((committee) => committee.in_chairs_view);
      const items = [];
      if (overview.roles.includes('Chair')) items.push(markKey('Chair', 'bold = chair'));
      if (overview.roles.includes('Vice Chair')) items.push(markKey('Vice Chair', 'italic = vice chair'));
      const multiple = Object.values(overview.by_ward).filter((entry) => entry.fills.length > 1).length;
      if (multiple) {
        items.push(el('span', {}, [el('span', { class: 'cc-swatch', style: 'background: repeating-linear-gradient(45deg, #888 0 3px, #ddd 3px 6px)' }),
          document.createTextNode(`striped = more than one (${multiple} wards)`)]));
      }
      if (overview.roles.length > 1 && style.combined_view_vice_chair_fill === 'lighter') {
        items.push(el('span', { text: 'full color = chair, light = vice chair' }));
      }
      colored.forEach((committee) => items.push(el('span', { class: 'cc-legend-committee' }, [
        swatch(committee.color), el('strong', { text: committee.short_label }), document.createTextNode(` — ${committee.name}`)])));
      return items;
    }
    const committee = committeeList()[state.committee];
    const members = Object.keys(data.alderByWard).filter((ward) => committeeRoleIn(ward, state.committee));
    return [
      el('span', {}, [swatch(committeeFill(members[0])), document.createTextNode(`${committee.name}: ${members.length} members`)]),
      markKey('Chair', `bold = chair (${committee.chair_wards.length})`),
      markKey('Vice Chair', `italic = vice chair (${committee.vice_chair_wards.length})`),
    ];
  }

  /* ── Tooltip (hover card) ─────────────────────────────────────────────── */

  function showTooltip(ward, mouseEvent) {
    const alder = data.alderByWard[ward];
    const lines = [
      el('strong', { text: `Ward ${Number(ward)}: ${alder.display_name}` }),
      el('div', { text: `On council ${alder.years_on_council.toFixed(TENURE_DECIMALS)} years (since ${formatDate(alder.council_start_date)})` }),
      el('div', { text: `Absent ${alder.absent_meetings} of ${alder.meetings_in_denominator} meetings (${alder.percent_absent.toFixed(ABSENCE_DECIMALS)}%)` }),
    ];
    if (state.view === 'votes' && currentEvent()) {
      lines.push(el('div', { text: `Vote on ${currentEvent().record_number}: ${voteOf(ward)}` }));
    }
    if (state.view === 'wards' && state.layer === 'street_map') {
      lines.push(el('div', { text: `Area: ${wardAreaText(ward)}` }));
    }
    if (state.view === 'committees') lines.push(committeeTooltipList(ward));
    if (state.view === 'wards' && data.wardLayerSummary[state.layer]) {
      const entry = layerEntry(ward);
      const layerLabel = LAYER_OPTIONS.find((option) => option.key === state.layer).label;
      const heading = entry.tile === 'count' ? `${layerLabel}: ${countText(entry.names.length)}` : `${layerLabel}:`;
      lines.push(el('div', { class: 'cc-tooltip-list' }, [el('strong', { text: heading }),
        document.createTextNode(namesWithShares(entry).join(', ') || 'none')]));
    }
    const children = [];
    if (alder.photo_url) children.push(el('img', { src: alder.photo_url, alt: '' }));
    ui.tooltip.replaceChildren(...children, ...lines);
    ui.tooltip.style.display = 'block';
    const padding = 14;
    const box = ui.tooltip.getBoundingClientRect();
    let left = mouseEvent.clientX + padding;
    let top = mouseEvent.clientY + padding;
    if (left + box.width > window.innerWidth) left = mouseEvent.clientX - box.width - padding;
    if (top + box.height > window.innerHeight) top = mouseEvent.clientY - box.height - padding;
    ui.tooltip.style.left = `${Math.max(4, left)}px`;
    ui.tooltip.style.top = `${Math.max(4, top)}px`;
  }

  // Hover card, committees view: every current assignment, short labels, chairs first.
  //   Chair: Ethics · Vice chair: … · Member: … · Joint committees (n): …
  function committeeTooltipList(ward) {
    const assignments = wardAssignments(ward);
    const rows = [];
    ['Chair', 'Vice Chair', 'Member'].forEach((role) => {
      const names = assignments.filter((assignment) => assignment.role === role && assignment.committee.body_type !== 'Joint Committee')
        .map((assignment) => assignment.committee.short_label);
      if (names.length) rows.push(el('div', {}, [el('span', { style: roleFontCss([role]), text: `${COMMITTEE_ROLE_TEXT[role]}: ` }),
                                                 document.createTextNode(names.join(', '))]));
    });
    const joint = assignments.filter((assignment) => assignment.committee.body_type === 'Joint Committee');
    const jointShown = TOOLTIP_JOINT_COMMITTEES === 'all' ? joint
      : TOOLTIP_JOINT_COMMITTEES === 'count' ? [] : joint.filter((assignment) => assignment.role !== 'Member');
    if (joint.length && !jointShown.length) rows.push(el('div', { text: `Joint committees: ${joint.length}` }));
    if (jointShown.length) {
      rows.push(el('div', { text: `Joint committees (${joint.length})${jointShown.length < joint.length ? ', chair or vice chair of' : ''}: ` + jointShown.map((assignment) =>
        assignment.committee.short_label + (assignment.role !== 'Member' ? ` (${COMMITTEE_ROLE_TEXT[assignment.role] || assignment.role})` : '')).join(', ') }));
    }
    return el('div', { class: 'cc-tooltip-list' }, [el('strong', { text: 'Committees' }), ...rows]);
  }

  // Hover card for a point on the layer map: its hover_name (export LAYER_HOVER_NAME_COLUMN).
  function showLayerTooltip(properties, mouseEvent) {
    const layerLabel = LAYER_OPTIONS.find((option) => option.key === state.layer).label;
    ui.tooltip.replaceChildren(el('strong', { text: properties.hover_name || '' }), el('div', { text: layerLabel }));
    ui.tooltip.style.display = 'block';
    ui.tooltip.style.left = `${mouseEvent.clientX + 14}px`;
    ui.tooltip.style.top = `${mouseEvent.clientY + 14}px`;
  }

  function hideTooltip() {
    ui.tooltip.style.display = 'none';
  }

  // Moves the table's own scroll box so the selected row sits in the middle (page doesn't move).
  function scrollTableToSelectedRow() {
    const wrap = ui.table.querySelector('.cc-table-wrap');
    const row = wrap && wrap.querySelector('tr.cc-selected');
    if (!row) return;
    const rowTop = row.getBoundingClientRect().top - wrap.getBoundingClientRect().top + wrap.scrollTop;
    wrap.scrollTop = rowTop - (wrap.clientHeight - row.offsetHeight) / 2;
  }

  function selectWard(ward) {
    state.selectedWard = state.selectedWard === ward ? null : ward;
    drawMap();
    drawTable();
  }

  /* ── Side panel: event details (votes view) and table ─────────────────── */

  function eventOptionText(event) {
    const title = event.title.length > 90 ? event.title.slice(0, 87) + '…' : event.title;
    return `${event.action_date} · ${event.record_number} · ${event.tallies.count_yea}–${event.tallies.count_nay} · ${title}`;
  }

  function drawEventPicker() {
    const search = el('input', { type: 'search', placeholder: `Search ${data.events.length} split votes (title, record number, date)…` });
    const select = el('select', { 'aria-label': 'Split vote' });
    function fillOptions() {
      const query = search.value.trim().toLowerCase();
      const matches = data.events.filter((event) => !query
        || `${event.title} ${event.record_number} ${event.action_date}`.toLowerCase().includes(query));
      select.replaceChildren(...matches.map((event) => {
        const option = el('option', { value: event.event_id, text: eventOptionText(event) });
        if (event.event_id === state.eventId) option.selected = true;
        return option;
      }));
      if (matches.length && !matches.some((event) => event.event_id === state.eventId)) {
        state.eventId = matches[0].event_id;
        render();
      }
    }
    search.addEventListener('input', fillOptions);
    select.addEventListener('change', () => { state.eventId = select.value; render(); });
    fillOptions();
    ui.eventPicker.replaceChildren(el('div', { class: 'cc-event-picker' }, [search, select]));
  }

  function drawEventDetails() {
    const event = currentEvent();
    if (!event) { ui.eventDetails.replaceChildren(); return; }
    const tallyNames = { count_yea: 'Yea', count_nay: 'Nay', count_absent: 'Absent', count_not_voting: 'Not Voting',
                         count_present: 'Present', count_recused: 'Recused', count_vacant: 'Vacant', count_rising_vote: 'Rising Vote' };
    const tally = Object.entries(event.tallies).filter(([, count]) => count > 0)
      .map(([column, count]) => el('span', { text: `${tallyNames[column]} ${count}` }));
    const attachments = event.attachments.length
      ? el('ol', {}, event.attachments.map((attachment) => el('li', {}, [
          document.createTextNode(`${attachment.attachment_type}: `),
          el('a', { href: attachment.url, target: '_blank', rel: 'noopener', text: attachment.file_name })])))
      : el('div', { text: 'No attachments in eLMS.' });
    ui.eventDetails.replaceChildren(el('div', { class: 'cc-event' }, [
      el('h2', { text: `${event.record_number} — ${event.action_name}` }),
      el('div', { class: 'cc-meta', text: `${formatDate(event.action_date)} · ${event.matter_type} · full council roll call (all voters, incl. anyone no longer seated)` }),
      el('div', { class: 'cc-tally' }, tally),
      el('div', { class: 'cc-title', text: event.title }),
      el('strong', { text: `Documents (${event.attachments.length})` }),
      attachments,
    ]));
  }

  function tableColumns() {
    const columns = [
      { key: 'ward', label: 'Ward', value: (alder) => Number(alder.ward), num: true },
      { key: 'name', label: 'Alder', value: (alder) => alder.display_name },
    ];
    if (state.view === 'committees' && currentOverview()) {
      // Counts leave out joint committees (they are listed in the hover card).
      const shortLabels = (alder, role) => wardAssignments(alder.ward)
        .filter((assignment) => assignment.role === role && assignment.committee.body_type !== 'Joint Committee')
        .map((assignment) => assignment.committee.short_label).join(', ');
      columns.push(
        { key: 'chair_of', label: 'Chair of', value: (alder) => shortLabels(alder, 'Chair') },
        { key: 'vice_chair_of', label: 'Vice chair of', value: (alder) => shortLabels(alder, 'Vice Chair') },
        { key: 'committee_count', label: 'Committees', num: true, value: (alder) => wardAssignments(alder.ward)
          .filter((assignment) => assignment.committee.body_type !== 'Joint Committee').length });
    } else if (state.view === 'committees') {
      // Sorted chair, vice chair, member, not on it.
      const roleOrder = ['Chair', 'Vice Chair', 'Member'];
      columns.push({ key: 'role', label: 'Role', value: (alder) => {
        const role = committeeRoleIn(alder.ward, state.committee);
        return role ? roleOrder.indexOf(role) : roleOrder.length;
      }, format: (value) => (value < roleOrder.length ? COMMITTEE_ROLE_TEXT[roleOrder[value]] : '—') });
    } else if (state.view === 'votes') {
      columns.push({ key: 'vote', label: 'Vote', value: (alder) => voteOf(alder.ward) });
    } else if (state.view === 'wards' && state.layer === 'street_map') {
      columns.push({ key: 'area', label: 'Area (sq mi)', value: (alder) => data.wardAreas[alder.ward].area_sq_mi, num: true,
                     format: (value) => value.toFixed(WARD_AREA_DECIMALS) });
    } else if (state.view === 'wards' && data.wardLayerSummary[state.layer]) {
      // Count, then every name (with the share of the ward, where the rule has one).
      columns.push(
        { key: 'count', label: 'Count', value: (alder) => layerEntry(alder.ward).names.length, num: true },
        { key: 'names', label: LAYER_OPTIONS.find((option) => option.key === state.layer).label,
          value: (alder) => namesWithShares(layerEntry(alder.ward)).join(', ') });
    } else {
      columns.push(
        { key: 'years', label: 'Years', value: (alder) => alder.years_on_council, num: true,
          format: (value) => value.toFixed(TENURE_DECIMALS) },
        { key: 'absent', label: '% absent', value: (alder) => alder.percent_absent, num: true,
          format: (value) => value.toFixed(ABSENCE_DECIMALS) },
        { key: 'meetings', label: 'Absent / meetings', value: (alder) => alder.absent_meetings, num: true,
          format: (value, alder) => `${alder.absent_meetings} / ${alder.meetings_in_denominator}` });
    }
    return columns;
  }

  function drawTable() {
    const columns = tableColumns();
    const sortColumn = columns.find((column) => column.key === state.sort.column) || columns[0];
    const rows = [...data.alders].sort((first, second) => {
      const a = sortColumn.value(first); const b = sortColumn.value(second);
      const order = a < b ? -1 : a > b ? 1 : 0;
      return state.sort.ascending ? order : -order;
    });
    const header = el('tr', {}, columns.map((column) => el('th', {
      class: column.num ? 'cc-num' : '',
      text: column.label + (column.key === sortColumn.key ? (state.sort.ascending ? ' ▲' : ' ▼') : ''),
      onclick: () => {
        state.sort = { column: column.key, ascending: column.key === state.sort.column ? !state.sort.ascending : true };
        drawTable();
      },
    })));
    const body = rows.map((alder) => {
      const row = el('tr', { class: alder.ward === state.selectedWard ? 'cc-selected' : '' },
        columns.map((column) => {
          const value = column.value(alder);
          return el('td', { class: column.num ? 'cc-num' : '', text: column.format ? column.format(value, alder) : String(value) });
        }));
      row.addEventListener('click', () => selectWard(alder.ward));
      return row;
    });
    ui.table.replaceChildren(el('div', { class: 'cc-table-wrap' }, [el('table', {}, [el('thead', {}, [header]), el('tbody', {}, body)])]));
  }

  /* ── Controls and page ────────────────────────────────────────────────── */

  function segmented(options, currentKey, onChoose) {
    return el('div', { class: 'cc-seg', role: 'group' }, options.map((option) => el('button', {
      type: 'button', 'aria-pressed': String(option.key === currentKey), text: option.label,
      onclick: () => onChoose(option.key),
    })));
  }

  // The drawn view follows the tab, and on the Alders tab the dropdown.
  function updateView() {
    state.view = state.tab === 'alders' ? state.alderMeasure : state.tab;
  }

  function alderMeasureSelect() {
    const select = el('select', { class: 'cc-select', 'aria-label': 'Alder measure' },
      ALDER_MEASURE_OPTIONS.map((option) => {
        const element = el('option', { value: option.key, text: option.label });
        if (option.key === state.alderMeasure) element.selected = true;
        return element;
      }));
    select.addEventListener('change', () => { state.alderMeasure = select.value; updateView(); render(); });
    return select;
  }

  // Committees dropdown: the overview maps, then every committee grouped by body type.
  function committeeSelect() {
    const select = el('select', { class: 'cc-select', 'aria-label': 'Committee' });
    data.committees.overviews.forEach((overview) => {
      const option = el('option', { value: overview.key, text: overview.label });
      if (overview.key === state.committee) option.selected = true;
      select.append(option);
    });
    Object.entries(COMMITTEE_GROUP_LABELS).forEach(([bodyType, groupLabel]) => {
      const group = el('optgroup', { label: groupLabel });
      committeeList().forEach((committee, index) => {
        if (committee.body_type !== bodyType) return;
        const option = el('option', { value: String(index), text: committee.name });
        if (index === state.committee) option.selected = true;
        group.append(option);
      });
      if (group.childElementCount) select.append(group);
    });
    select.addEventListener('change', () => {
      const isOverview = data.committees.overviews.some((overview) => overview.key === select.value);
      state.committee = isOverview ? select.value : Number(select.value);
      render();
    });
    return select;
  }

  function layerSelect() {
    const select = el('select', { class: 'cc-select', 'aria-label': 'Map layer' },
      LAYER_OPTIONS.map((option) => {
        const element = el('option', { value: option.key, text: option.label });
        if (option.key === state.layer) element.selected = true;
        return element;
      }));
    select.addEventListener('change', () => { state.layer = select.value; render(); });
    return select;
  }

  // Each layer file is fetched the first time it is shown; the map redraws when it arrives.
  function ensureLayerLoaded() {
    const layer = state.layer;
    if (layer === 'street_map') return;   // no layer file
    if (data.layers[layer] || data.layers[`${layer}:loading`]) return;
    data.layers[`${layer}:loading`] = true;
    fetchJson(`layer_${layer}.geojson`).then((collection) => {
      data.layers[layer] = collection;
      if (state.view === 'wards' && state.layer === layer) drawMap();
    }).catch((error) => {
      ui.map.replaceChildren(el('div', { class: 'cc-error', text: `Could not load layer ${layer} (${error.message}).` }));
    });
  }

  function render() {
    ui.controls.replaceChildren(...[
      segmented(TAB_OPTIONS, state.tab, (key) => { state.tab = key; updateView(); render(); }),
      state.tab === 'alders' ? alderMeasureSelect() : null,   // dropdown only on the Alders tab
      state.view === 'committees' ? committeeSelect() : null, // second dropdown: which committee
      state.tab === 'wards' ? layerSelect() : null,           // layer dropdown only on the Wards tab
      segmented(SHAPE_OPTIONS, state.shapes, (key) => { state.shapes = key; render(); }),
    ].filter(Boolean));
    const showVotes = state.view === 'votes';
    ui.eventPicker.style.display = showVotes ? '' : 'none';
    ui.eventDetails.style.display = showVotes ? '' : 'none';
    if (showVotes && !ui.eventPicker.childElementCount) drawEventPicker();
    if (showVotes) drawEventDetails();
    if (state.view === 'wards') ensureLayerLoaded();
    drawMap();
    drawTable();
  }

  function buildPage(container) {
    ui.controls = el('div', { class: 'cc-controls' });
    ui.map = el('div', { class: 'cc-map' });
    ui.legend = el('div', { class: 'cc-legend' });
    ui.eventPicker = el('div', { style: 'margin-bottom:10px' });
    ui.eventDetails = el('div', { style: 'margin-bottom:12px' });
    ui.table = el('div');
    ui.tooltip = el('div', { class: 'cc-tooltip', role: 'tooltip' });
    container.replaceChildren(
      el('h1', { text: PAGE_TITLE }),
      ui.controls,
      el('div', { class: 'cc-layout' }, [
        el('div', { class: 'cc-card' }, [ui.map, ui.legend]),
        el('div', { class: 'cc-card' }, [ui.eventPicker, ui.eventDetails, ui.table]),
      ]),
      // Footer: the user's text, from meta.json (export ABOUT_TEXT), as one paragraph.
      el('div', { class: 'cc-foot' }, [
        el('strong', { text: data.meta.about_heading || '' }),
        el('p', { text: [
          `Version ${DASHBOARD_VERSION}, preliminary dashboard.`,
          `Data exported ${formatDate((data.meta.exported_at || '').slice(0, 10))}, alder tenure as of ${formatDate(data.meta.tenure_as_of)}.`,
          ...(data.meta.about_text || []),
        ].join(' ') }),
      ]),
      ui.tooltip,
    );
  }

  function start() {
    const container = document.getElementById(CONTAINER_ID);
    if (!container) return;
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.append(style);
    container.textContent = 'Loading…';

    Promise.all([
      ...SHAPE_OPTIONS.map((option) => fetchJson(option.file).then((collection) => { data.shapes[option.key] = collection; })),
      fetchJson('alders.json').then((alders) => { data.alders = alders; }),
      fetchJson('split_events.json').then((events) => { data.events = events; }),
      fetchJson('meta.json').then((meta) => { data.meta = meta; }),
      fetchJson('ward_layer_summary.json').then((summary) => { data.wardLayerSummary = summary; }),
      fetchJson('ward_areas.json').then((areas) => { data.wardAreas = areas.by_ward; }),
      fetchJson('committees.json').then((committees) => { data.committees = committees; }),
    ]).then(() => {
      data.alders.forEach((alder) => { data.alderByWard[alder.ward] = alder; });
      data.events.forEach((event) => { data.eventById[event.event_id] = event; });
      state.committee = data.committees.overviews[0].key;   // default overview (ward_maps.OVERVIEW_VIEWS order)
      state.eventId = data.meta.default_split_event_id || (data.events[0] && data.events[0].event_id);
      buildPage(container);
      render();
      document.addEventListener('click', (event) => { if (!event.target.closest('.cc-ward, .cc-ward-hit')) hideTooltip(); });
    }).catch((error) => {
      container.replaceChildren(el('div', { class: 'cc-error',
        text: `Could not load the dashboard data (${error.message}). If you opened the file directly, serve docs/ with a local web server.` }));
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
