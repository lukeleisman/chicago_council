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

  // Ward shapes offered, in toggle order, and the one shown first.
  //   real = 2023 boundaries; tiles_grid = hand-specified grid; tiles_pushed = pushed-apart tiles
  const SHAPE_OPTIONS = [
    { key: 'tiles_grid', label: 'Grid tiles', file: 'wards_tiles_grid.geojson' },
    { key: 'tiles_pushed', label: 'Pushed tiles', file: 'wards_tiles_pushed.geojson' },
    { key: 'real', label: 'Real map', file: 'wards_real.geojson' },
  ];
  const DEFAULT_SHAPES = 'tiles_grid';

  const VIEW_OPTIONS = [
    { key: 'alders', label: 'Alders' },
    { key: 'tenure', label: 'Tenure' },
    { key: 'absence', label: 'Absence' },
    { key: 'votes', label: 'Split votes' },
  ];
  const DEFAULT_VIEW = 'alders';

  // Labels: on tiles, ward number + last name (+ the view's value). On the real map the wards are
  // too small for names, so ward number only (names are in the hover card and the table).
  const REAL_MAP_LABEL = 'number';
  // Real-map ward number size, in map units (the map is drawn 1020 units wide, then scaled to fit).
  const REAL_MAP_LABEL_FONT_SIZE = 22;

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
#council-app h1 { font-size: 22px; margin: 0 0 2px; color: var(--cc-accent); }
#council-app .cc-sub { color: var(--cc-ink-2); font-size: 13px; margin-bottom: 14px; }
#council-app .cc-controls { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; margin-bottom: 12px; }
#council-app .cc-seg { display: inline-flex; border: 1px solid var(--cc-line); border-radius: 8px; overflow: hidden; background: var(--cc-surface); }
#council-app .cc-seg button { border: 0; background: none; padding: 7px 12px; font: inherit; font-size: 14px; cursor: pointer; color: var(--cc-ink); }
#council-app .cc-seg button + button { border-left: 1px solid var(--cc-line); }
#council-app .cc-seg button[aria-pressed="true"] { background: var(--cc-accent); color: #fff; }
#council-app .cc-layout { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 16px; align-items: start; }
@media (max-width: 860px) { #council-app .cc-layout { grid-template-columns: 1fr; } }
#council-app .cc-card { background: var(--cc-surface); border: 1px solid var(--cc-line); border-radius: 10px; padding: 12px; }
/* Map never taller than the window (MAP_MAX_HEIGHT); narrower maps center. */
#council-app .cc-map svg { width: 100%; height: auto; max-height: 78vh; display: block; margin: 0 auto; }
#council-app .cc-ward { stroke: #333; stroke-width: 0.8; vector-effect: non-scaling-stroke; cursor: pointer; }
#council-app .cc-ward:hover, #council-app .cc-ward.cc-selected { stroke: #000; stroke-width: 2.5; }
#council-app .cc-label { pointer-events: none; text-anchor: middle; dominant-baseline: central; font-weight: 600; }
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
#council-app .cc-foot ul { margin: 4px 0 0 18px; padding: 0; }
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
    view: DEFAULT_VIEW,
    eventId: null,
    selectedWard: null,
    sort: { column: 'ward', ascending: true },
  };
  const data = { shapes: {}, alders: [], alderByWard: {}, events: [], eventById: {}, meta: {} };
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
      return { ward: feature.properties.ward, rings,
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

    projected.forEach((shape) => {
      const pathText = shape.rings.map((ring) => 'M' + ring.map(toScreen).map((point) => point.map((value) => value.toFixed(1)).join(',')).join('L') + 'Z').join('');
      const path = svgEl('path', { d: pathText, fill: fillFor(shape.ward), class: 'cc-ward', 'fill-rule': 'evenodd',
                                   'data-ward': shape.ward });
      if (shape.ward === state.selectedWard) path.classList.add('cc-selected');
      path.addEventListener('mousemove', (event) => showTooltip(shape.ward, event));
      path.addEventListener('mouseleave', hideTooltip);
      path.addEventListener('click', (event) => { selectWard(shape.ward); showTooltip(shape.ward, event); });
      svg.append(path);
    });

    // Labels.
    projected.forEach((shape) => {
      const [labelX, labelY] = toScreen(shape.label);
      const fill = fillFor(shape.ward);
      const ink = fill.startsWith('url') ? '#111' : textColorFor(fill);
      const alder = data.alderByWard[shape.ward];
      let lines;
      let fontSize;
      if (state.shapes === 'real' && REAL_MAP_LABEL === 'number') {
        lines = [String(Number(shape.ward))];
        fontSize = REAL_MAP_LABEL_FONT_SIZE;
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

  function hideTooltip() {
    ui.tooltip.style.display = 'none';
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

  function render() {
    ui.controls.replaceChildren(
      segmented(VIEW_OPTIONS, state.view, (key) => { state.view = key; render(); }),
      segmented(SHAPE_OPTIONS, state.shapes, (key) => { state.shapes = key; render(); }),
    );
    const showVotes = state.view === 'votes';
    ui.eventPicker.style.display = showVotes ? '' : 'none';
    ui.eventDetails.style.display = showVotes ? '' : 'none';
    if (showVotes && !ui.eventPicker.childElementCount) drawEventPicker();
    if (showVotes) drawEventDetails();
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
    const rules = data.meta.rules || {};
    const sources = data.meta.sources || {};
    container.replaceChildren(
      el('h1', { text: 'Chicago City Council, ward by ward' }),
      el('div', { class: 'cc-sub', text: `2023–2027 term · preliminary · data exported ${formatDate((data.meta.exported_at || '').slice(0, 10))}, tenure as of ${formatDate(data.meta.tenure_as_of)}` }),
      ui.controls,
      el('div', { class: 'cc-layout' }, [
        el('div', { class: 'cc-card' }, [ui.map, ui.legend]),
        el('div', { class: 'cc-card' }, [ui.eventPicker, ui.eventDetails, ui.table]),
      ]),
      el('div', { class: 'cc-foot' }, [
        el('strong', { text: 'How the numbers are made' }),
        el('ul', {}, Object.entries(rules).map(([name, text]) => el('li', { text: `${name.replace(/_/g, ' ')}: ${text}` }))),
        el('strong', { text: 'Sources' }),
        el('ul', {}, Object.entries(sources).map(([name, text]) => el('li', { text: `${name}: ${text}` }))),
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
      document.addEventListener('click', (event) => { if (!event.target.closest('.cc-ward')) hideTooltip(); });
    }).catch((error) => {
      container.replaceChildren(el('div', { class: 'cc-error',
        text: `Could not load the dashboard data (${error.message}). If you opened the file directly, serve docs/ with a local web server.` }));
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
