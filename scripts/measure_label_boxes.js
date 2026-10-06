// Wards tab label box measurement (2026-10-05). Paste into the browser console (or javascript_tool)
// on http://localhost:8765/ with the Wards tab's Map View showing at zoom 1, while
// scripts/label_measure_receiver.py runs. Posts layer_label_boxes.json to the receiver.
// Values are in points AS DRAWN at MEASURED_SCALE (= app.js LAYER_MAP_LABEL_SCALE when measured);
// divide by it to get scale-1 points, as scripts/wards_tab_label_box_sizes.json stores them.
// The Alders tab file (scripts/map_label_box_sizes.json) was measured the same way, per text line
// (two_sizes baselines: getBBox top + font ascent), and copied out by hand.
const MEASURED_SCALE = 1.25;   // set to the page's LAYER_MAP_LABEL_SCALE
const sel = document.querySelector('.cc-controls select');
const meta = await fetch('data/meta.json').then((r) => r.json());
const style = meta.layers.style;
const ctx = document.createElement('canvas').getContext('2d');
function measure(text, fontPoints) {
  const fontSize = parseFloat(text.getAttribute('font-size'));
  const css = getComputedStyle(text);
  ctx.font = `${css.fontStyle} ${css.fontWeight} 100px ${css.fontFamily}`;
  ctx.textAlign = 'center';
  const metrics = ctx.measureText(text.textContent);
  const k = fontSize / 100;                                  // canvas px -> SVG units
  const box = text.getBBox();
  const anchorX = +text.dataset.anchorX, anchorY = +text.dataset.anchorY;
  const unitsPerPoint = fontSize / fontPoints / MEASURED_SCALE;
  // dominant-baseline central: baseline from the middle of the getBBox box.
  const baseline = (box.y + box.height / 2) + (metrics.fontBoundingBoxAscent - metrics.fontBoundingBoxDescent) / 2 * k;
  const centerX = box.x + box.width / 2;
  const round = (values) => values.map((value) => +(value / unitsPerPoint).toFixed(2));
  return {
    text: text.textContent,
    // [x0, y0, x1, y1] relative to the anchor, y up
    ink: round([centerX - anchorX - metrics.actualBoundingBoxLeft * k, -(baseline + metrics.actualBoundingBoxDescent * k - anchorY),
                centerX - anchorX + metrics.actualBoundingBoxRight * k, -(baseline - metrics.actualBoundingBoxAscent * k - anchorY)]),
    line_box: round([box.x - anchorX, -(box.y + box.height - anchorY), box.x + box.width - anchorX, -(box.y - anchorY)]),
  };
}
const out = { measured_at_scale: MEASURED_SCALE, label_font_points: style.label_font_points,
              ward_number_font_points: style.ward_number_font_points, browser: navigator.userAgent, layers: {} };
for (const layer of ['community_areas', 'neighborhoods', 'zip_codes', 'police_districts']) {
  sel.value = layer; sel.dispatchEvent(new Event('change'));
  await new Promise((resolve) => setTimeout(resolve, 800));
  out.layers[layer] = [...document.querySelectorAll('.cc-layer-label')].map((text) => measure(text, style.label_font_points));
}
out.ward_numbers = [...document.querySelectorAll('.cc-ward-number')].map((text) => measure(text, style.ward_number_font_points));
await fetch('http://localhost:8766/layer_label_boxes.json', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(out) })
  .then((response) => response.text());
