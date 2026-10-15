# 05 — Major roads, highways, intersections on the Street map Tile View

**Kind: short PLAN-TO-PLAN, then EXECUTE.** Item 5 of the 2026-10-15 list (raised before, 2026-10-05).

## Today
Wards tab → Street map → Tile View shows each ward's area in square miles (`WARD_AREA_DECIMALS` in
`docs/dashboard/app.js`, `docs/data/ward_areas.json` from `scripts/ward_layer_overlaps.py`). Map View shows
Esri street tiles.

## Options to draw for the user (each as a setting)
- (a) Major streets that cross or run through the ward.
- (b) Expressways only (I-90/94, I-55, I-290, Lake Shore Drive, Skyway, …).
- (c) Main intersections (e.g. "Western & 47th").
- (d) Boundary streets ("bounded by Ashland, Western, 39th, 55th") — likely the most useful to a resident,
  hardest to compute (ward edges follow many streets).
- Combinations; keep area as well?

## Sources to check (record id, date, columns)
- Chicago Data Portal: "Major Streets", "Street Center Lines" (class column) — IDs to verify.
- IDOT functional classification.
- OpenStreetMap: `highway=motorway|trunk|primary|secondary`.

## Rules needing the user's choice (named constants)
- What counts as major (functional class list vs. a named list).
- Minimum length inside the ward (m) to list a street; for boundary streets, share of the ward edge
  within N m of the street.
- How many names fit per tile (`TILE_MAX_LIST_LINES`, "+N more").
- Name format ("Western Ave" vs. "Western").

## Reuse
`scripts/ward_layer_overlaps.py` overlap + `WARD_SUMMARY_RULES` pattern; Tile View list rendering and
"+N more" already used for parks / community areas; `fetch_layers.LAYERS` row for the download.
