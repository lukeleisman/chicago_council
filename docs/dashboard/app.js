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
    { key: 'votes', label: 'Split votes' },
    { key: 'wards', label: 'Wards' },
  ];
  const DEFAULT_TAB = 'alders';
  // Dropdown under the Alders tab: what the map colors and labels show.
  const ALDER_MEASURE_OPTIONS = [
    { key: 'names', label: 'Names' },
    { key: 'tenure', label: 'Tenure' },
    { key: 'absence', label: 'Absence' },
  ];
  const DEFAULT_ALDER_MEASURE = 'names';
  // Dropdown under the Wards tab: which map layer is drawn under the wards (user, 2026-10-05; no
  // precincts, no census tracts). Keys = export DASHBOARD_LAYERS; each file is fetched on first pick.
  const LAYER_OPTIONS = [
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
  const DEFAULT_LAYER = 'community_areas';
  // Wards tab, Map View: drawn like notebooks/map_layers_review.ipynb's large maps (styles in
  // meta.json `layers.style`, from scripts/map_layers.py; sizes in points, converted with
  // meta.real_map_labels.meters_per_point). No basemap (plan, 2026-10-05).
  // OPEN QUESTION (for the user): should these labels also get REAL_MAP_LABEL_SCALE (1.25)?
  // 1 = the notebook's proportions.
  const LAYER_MAP_LABEL_SCALE = 1;
  // Multiplies line widths and point sizes on the layer map. 1 = the notebook's proportions
  // (points are about 3.7 pt across, so only ~2.5 px on a 600 px wide map).
  const LAYER_MAP_MARK_SCALE = 1;

  // Labels on tiles: ward number + last name (+ the view's value), font fitted to the tile.
  // Labels on the real map (Map View):
  //   'notebook_layout' = ward_views' labels (user, 2026-10-05): positions, nudges and font sizes from
  //                       scripts/ward_maps.py, converted by scripts/export_dashboard_data.py
  //                       (wards_real.geojson `labels`, meta.json real_map_labels)
  //   'number'          = ward number only, REAL_MAP_NUMBER_FONT_SIZE (the first draft)
  const REAL_MAP_LABEL = 'notebook_layout';
  const REAL_MAP_NUMBER_FONT_SIZE = 22;   // map units (the map is drawn 1020 units wide, then scaled to fit)
  // Which exported label layout each view uses (export REAL_MAP_LABEL_LAYOUTS; votes = §4.7 = §1's labels).
  const REAL_MAP_LAYOUT_BY_VIEW = { names: 'names', votes: 'names', tenure: 'tenure', absence: 'absence' };
  // Multiplies every real-map label size. 1 = the notebook's proportions; the export's no-overlap
  // check only holds at 1. Labels scale with the map, so a narrow screen makes them small.
  // OPEN QUESTION (user, 2026-10-05: "leave as is for now", likely to return, especially for a
  // mobile-friendly version): at ~500 px map width names are ~6 px. Options: (a) scale above 1
  // here (labels then may overlap); (b) let the map grow (MAP_MAX_HEIGHT_VH, or more page width).
  // User, 2026-10-05: 1.25 ("all fonts could be a bit bigger"); collisions this creates are fixed by
  // DASHBOARD_EXTRA_OFFSET_POINTS_BY_WARD in scripts/export_dashboard_data.py.
  const REAL_MAP_LABEL_SCALE = 1.25;
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
#council-app .cc-select { font: inherit; font-size: 14px; padding: 6px 8px; border: 1px solid var(--cc-line); border-radius: 8px; background: var(--cc-surface); color: var(--cc-ink); }
#council-app .cc-layout { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 16px; align-items: start; }
@media (max-width: 860px) { #council-app .cc-layout { grid-template-columns: 1fr; } }
#council-app .cc-card { background: var(--cc-surface); border: 1px solid var(--cc-line); border-radius: 10px; padding: 12px; }
/* Map never taller than MAP_MAX_HEIGHT_VH of the window; narrower maps center. */
#council-app .cc-map svg { width: 100%; height: auto; max-height: ${MAP_MAX_HEIGHT_VH}vh; display: block; margin: 0 auto; }
#council-app .cc-ward { stroke: #333; stroke-width: 0.8; vector-effect: non-scaling-stroke; cursor: pointer; }
#council-app .cc-ward:hover, #council-app .cc-ward.cc-selected { stroke: #000; stroke-width: 2.5; }
#council-app .cc-label { pointer-events: none; text-anchor: middle; dominant-baseline: central; font-weight: 600; }
/* Map View labels: ward_maps.TEXT_HALO = white outline drawn under black text; normal weight (matplotlib default). */
#council-app .cc-label-notebook { font-weight: 400; fill: #000; stroke: #fff; stroke-linejoin: round; paint-order: stroke; }
/* Wards tab layer map: wards are a transparent hit area under the layer; outlines drawn on top. */
#council-app .cc-ward-hit { fill: transparent; stroke: none; cursor: pointer; }
#council-app .cc-ward-hit.cc-selected { fill: rgba(255, 214, 0, 0.25); }
#council-app .cc-layer-shape, #council-app .cc-ward-outline, #council-app .cc-layer-label { pointer-events: none; }
#council-app .cc-layer-point { cursor: default; }
#council-app .cc-layer-label { text-anchor: middle; dominant-baseline: central; font-style: italic; stroke: #fff; stroke-linejoin: round; paint-order: stroke; }
#council-app .cc-ward-number { pointer-events: none; text-anchor: middle; dominant-baseline: central; font-weight: 700; fill: #000; stroke: #fff; stroke-linejoin: round; paint-order: stroke; }
#council-app .cc-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; font-size: 13px; margin-top: 8px; color: var(--cc-ink-2); }
#council-app .cc-swatch { display: inline-block; width: 14px; height: 14px; border-radius: 3px; border: 1px solid #999; vertical-align: -2px; margin-right: 5px; }
#council-app .cc-gradient { width: 180px; height: 12px; border-radius: 3px; border: 1px solid #999; }
#council-app .cc-event-picker { display: flex; flex-direction: column; gap: 6px; width: 100%; }
#council-app .cc-event-picker input, #council-app .cc-event-picker select { font: inherit; font-size: 14px; padding: 6px 8px; border: 1px solid var(--cc-line); border-radius: 6px; width: 100%; background: #fff; }
#council-app .cc-event h2 { font-size: 16px; margin: 0 0 4px; }
#council-app .cc-event .cc-meta { font-size: 13px; color: var(--cc-ink-2); margin-bottom: 8px; }
#council-app .cc-event .cc-title { font-size: 14px; margin-bottom: 8px; }
#council-app .cc-event ol { margin: 4px 0 0 18px; padding: 0; font-size: 13px; }
#council-app .cc-event a { color: var(--cc-accent); }
#council-app .cc-tally { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; margin-bottom: 8px; }
#council-app table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
#council-app th, #council-app td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #eee; }
#council-app th { cursor: pointer; user-select: none; color: var(--cc-ink-2); font-weight: 600; white-space: nowrap; }
#council-app td.cc-num, #council-app th.cc-num { text-align: right; }
#council-app tr.cc-selected td { background: #fff4d6; }
#council-app .cc-table-wrap { max-height: 520px; overflow-y: auto; }
#council-app .cc-tooltip { position: fixed; z-index: 10000; pointer-events: none; background: #fff; border: 1px solid var(--cc-line);
  border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.15); padding: 8px; font-size: 13px; display: none; max-width: 260px; }
#council-app .cc-tooltip img { width: 64px; height: 64px; object-fit: cover; object-position: top; border-radius: 6px; float: left; margin-right: 8px; }
#council-app .cc-tooltip strong { display: block; }
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
    layer: DEFAULT_LAYER,
    view: DEFAULT_ALDER_MEASURE,   // what is drawn: the alder measure on the Alders tab, else the tab (setTab)
    eventId: null,
    selectedWard: null,
    sort: { column: 'ward', ascending: true },
  };
  const data = { shapes: {}, alders: [], alderByWard: {}, events: [], eventById: {}, meta: {}, layers: {} };
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
    return ALDER_FILL;
  }

  // Third label line on tiles: the view's value.
  function valueText(ward) {
    const alder = data.alderByWard[ward];
    if (state.view === 'tenure') return `${alder.years_on_council.toFixed(TENURE_DECIMALS)} yr`;
    if (state.view === 'absence') return `${alder.percent_absent.toFixed(ABSENCE_DECIMALS)}%`;
    if (state.view === 'votes') return voteOf(ward) === NOT_ON_ROSTER_LABEL ? '—' : voteOf(ward);
    return '';
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
      return { ward: feature.properties.ward, rings, labels,
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
    svg.append(definitions);

    if (state.view === 'wards' && state.shapes === 'real') {
      drawLayerMap(svg, projected, toScreen, scale);
      ui.map.replaceChildren(svg);
      drawLegend();
      return;
    }

    projected.forEach((shape) => {
      const pathText = shape.rings.map((ring) => 'M' + ring.map(toScreen).map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L') + 'Z').join('');
      const path = svgEl('path', { d: pathText, fill: fillFor(shape.ward), class: 'cc-ward', 'fill-rule': 'evenodd',
                                   'data-ward': shape.ward });
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
      ui.map.replaceChildren(svg);
      drawLegend();
      return;
    }
    projected.forEach((shape) => {
      const [labelX, labelY] = toScreen(shape.label);
      const fill = fillFor(shape.ward);
      const ink = fill.startsWith('url') ? '#111' : textColorFor(fill);
      const alder = data.alderByWard[shape.ward];
      let lines;
      let fontSize;
      if (state.shapes === 'real' && REAL_MAP_LABEL === 'number') {
        lines = [String(Number(shape.ward))];
        fontSize = REAL_MAP_NUMBER_FONT_SIZE;
      } else {
        // Tile size on screen: from the tile's own ring.
        const xs = shape.rings[0].map((point) => toScreen(point)[0]);
        const ys = shape.rings[0].map((point) => toScreen(point)[1]);
        const tileWidth = Math.max(...xs) - Math.min(...xs);
        const tileHeight = Math.max(...ys) - Math.min(...ys);
        lines = [`${Number(shape.ward)} ${alder.label_name}`];
        if (valueText(shape.ward)) lines.push(valueText(shape.ward));
        // Font fits the tile: width (about 0.58 em per character) and height (lines x 1.2 em).
        const longest = Math.max(...lines.map((line) => line.length));
        fontSize = Math.min(tileWidth / (0.58 * longest), tileHeight / (lines.length * 1.35), 18);
      }
      lines.forEach((line, index) => {
        const offset = (index - (lines.length - 1) / 2) * fontSize * 1.15;
        const text = svgEl('text', { x: labelX.toFixed(1), y: (labelY + offset).toFixed(1), class: 'cc-label',
                                     'font-size': fontSize.toFixed(1), fill: ink });
        text.textContent = line;
        svg.append(text);
      });
    });

    ui.map.replaceChildren(svg);
    drawLegend();
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
  function drawLayerMap(svg, projected, toScreen, scale) {
    const style = data.meta.layers.style;
    const unitsPerPoint = data.meta.real_map_labels.meters_per_point * DEGREES_PER_WEB_MERCATOR_METER * scale;
    const markUnits = unitsPerPoint * LAYER_MAP_MARK_SCALE;
    const labelUnits = unitsPerPoint * LAYER_MAP_LABEL_SCALE;
    const haloWidth = data.meta.real_map_labels.halo_points * labelUnits;
    const layerInfo = data.meta.layers.by_layer[state.layer];
    const collection = data.layers[state.layer];

    // 1. Ward hit areas (transparent).
    projected.forEach((shape) => {
      const pathText = shape.rings.map((ring) => 'M' + ring.map(toScreen).map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L') + 'Z').join('');
      const path = svgEl('path', { d: pathText, class: 'cc-ward-hit', 'fill-rule': 'evenodd', 'data-ward': shape.ward });
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
    if (!collection) {
      const note = svgEl('text', { x: 500, y: 60, 'text-anchor': 'middle', 'font-size': 24 });
      note.textContent = 'Loading layer…';
      svg.append(note);
    } else {
      collection.features.forEach((feature) => {
        const properties = feature.properties;
        if (layerInfo.kind === 'fill') {
          svg.append(svgEl('path', { d: pathData(feature.geometry, toScreen), class: 'cc-layer-shape', 'fill-rule': 'evenodd',
            fill: style.fill_palette[properties.color_index % style.fill_palette.length], 'fill-opacity': style.fill_opacity,
            stroke: style.fill_edge_color, 'stroke-width': (style.fill_edge_points * markUnits).toFixed(2) }));
        } else if (layerInfo.kind === 'single') {
          // matplotlib's alpha applies to fill and edge alike.
          svg.append(svgEl('path', { d: pathData(feature.geometry, toScreen), class: 'cc-layer-shape', 'fill-rule': 'evenodd',
            fill: style.single_fill_color, stroke: style.single_fill_color, opacity: style.single_opacity,
            'stroke-width': (style.single_edge_points * markUnits).toFixed(2) }));
        } else if (layerInfo.kind === 'line') {
          svg.append(svgEl('path', { d: lineData(feature.geometry, toScreen), class: 'cc-layer-shape', fill: 'none',
            stroke: style.line_color, 'stroke-width': (style.line_points * markUnits).toFixed(2), 'stroke-linejoin': 'round' }));
        } else if (layerInfo.kind === 'point') {
          const [pointX, pointY] = toScreen(project(feature.geometry.coordinates));
          // markersize is the marker's area in points^2, so its diameter is the square root.
          const radius = (Math.sqrt(style.point_area_points2) / 2) * markUnits;
          const circle = svgEl('circle', { cx: pointX.toFixed(1), cy: pointY.toFixed(1), r: radius.toFixed(2),
            class: 'cc-layer-point', fill: style.point_color, stroke: style.point_edge_color,
            'stroke-width': (style.point_edge_points * markUnits).toFixed(2) });
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
            'stroke-width': haloWidth.toFixed(2) });
          text.textContent = feature.properties.label;
          svg.append(text);
        });
      }
    }

    // 4. Ward outlines and bold ward numbers on top.
    projected.forEach((shape) => {
      const pathText = shape.rings.map((ring) => 'M' + ring.map(toScreen).map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L') + 'Z').join('');
      svg.append(svgEl('path', { d: pathText, class: 'cc-ward-outline', fill: 'none', stroke: '#000',
        'stroke-width': (style.ward_outline_points * markUnits).toFixed(2), 'stroke-linejoin': 'round' }));
    });
    projected.forEach((shape) => {
      const [numberX, numberY] = toScreen(shape.labels.ward_number);
      const text = svgEl('text', { x: numberX.toFixed(1), y: numberY.toFixed(1), class: 'cc-ward-number',
        'font-size': (style.ward_number_font_points * labelUnits).toFixed(2), 'stroke-width': haloWidth.toFixed(2) });
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
    const layoutName = REAL_MAP_LAYOUT_BY_VIEW[state.view];
    const layout = labelMeta.layouts[layoutName];
    // Points on the notebook figure -> this SVG's units.
    const unitsPerPoint = labelMeta.meters_per_point * DEGREES_PER_WEB_MERCATOR_METER * scale * REAL_MAP_LABEL_SCALE;
    const haloWidth = labelMeta.halo_points * unitsPerPoint;
    function addText(x, y, content, fontPoints, baseline) {
      const text = svgEl('text', { x: x.toFixed(1), y: y.toFixed(1), class: 'cc-label cc-label-notebook',
                                   'font-size': (fontPoints * unitsPerPoint).toFixed(2),
                                   'stroke-width': haloWidth.toFixed(2),
                                   style: `dominant-baseline:${baseline}` });   // inline: the .cc-label CSS would override an attribute
      text.textContent = content;
      svg.append(text);
    }
    projected.forEach((shape) => {
      const [anchorX, anchorY] = toScreen(shape.labels[layoutName]);
      const alder = data.alderByWard[shape.ward];
      const wardNumber = String(Number(shape.ward));
      if (layout.kind === 'one_block') {
        const fontPoints = layout.font_points[0];
        const lineStep = fontPoints * unitsPerPoint * NOTEBOOK_LINE_SPACING;
        addText(anchorX, anchorY - lineStep / 2, wardNumber, fontPoints, 'central');
        addText(anchorX, anchorY + lineStep / 2, alder.label_name, fontPoints, 'central');
      } else {
        const [nameFontPoints, valueFontPoints] = layout.font_points;
        addText(anchorX, anchorY, `${wardNumber} ${alder.label_name}`, nameFontPoints, 'text-after-edge');
        addText(anchorX, anchorY, notebookValueText(shape.ward), valueFontPoints, 'text-before-edge');
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
    } else if (state.view === 'wards') {
      const layerInfo = data.meta.layers.by_layer[state.layer];
      const layerLabel = LAYER_OPTIONS.find((option) => option.key === state.layer).label;
      const colorNote = layerInfo.kind === 'fill' ? `, colored so neighbors differ (${layerInfo.colors_used} colors)` : '';
      items.push(el('span', { text: `${layerLabel}: ${layerInfo.feature_count} features${colorNote}. Black lines and bold numbers = wards.` }));
    } else {
      items.push(el('span', { text: 'Hover or tap a ward for its alder.' }));
    }
    ui.legend.replaceChildren(...items);
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
    if (state.view === 'votes') {
      columns.push({ key: 'vote', label: 'Vote', value: (alder) => voteOf(alder.ward) });
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
    ]).then(() => {
      data.alders.forEach((alder) => { data.alderByWard[alder.ward] = alder; });
      data.events.forEach((event) => { data.eventById[event.event_id] = event; });
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
