# 00 — Update the README

**Kind: EXECUTE** (one short session). Item 0 of the 2026-10-15 wish list.

## Why
`README.md` was written when only the data layer existed. It still says "Status: data layer built, views
next", lists the dashboard and ward map as "Planned", and leaves out several scripts, a table, and a
notebook section.

## Edits (each one checked against the repo, not from memory)
1. **Status** → the dashboard is live: GitHub Pages from `main` → `/docs`, embedded on the WordPress page
   (page 153). Pushing to `main` updates the live page. Automated data updates live since 2026-10-15.
2. **"Planned" section** → replace with a short **"What's on the dashboard"**:
   - Tabs: Alders (dropdown: Names / Tenure / Absence / Committees), Votes (split roll calls), Wards
     (layers: Street map, community areas, neighborhoods, ZIP codes, police districts, parks, CTA rail
     lines and stations, CPS schools 2025–26, ward offices). Read the current list from `TAB_OPTIONS`,
     `ALDER_MEASURE_OPTIONS`, `LAYER_OPTIONS` in `docs/dashboard/app.js` at the time of the edit.
   - Map View / Tile View; zoom; hover card + side table.
   - Pointer to `plans/` and `TODO.md` for what's next.
3. **Tables** list: add `committee_members` (built by `build_tables.py`, from eLMS `body_list.json`).
4. **Shared metrics** line: `council_metrics.py` also has current committee assignments.
5. **Notebooks**: add ward_views §5 (committee assignments: chairs/vice-chairs overviews, one committee,
   dropdown).
6. **Scripts table** (new): script → what it reads / writes → when to run. Must cover every file in
   `scripts/`: `fetch_elms.py`, `fetch_layers.py`, `fetch_photos.py`, `extract_datamade_memberships.py`,
   `build_tables.py`, `build_ward_tiles.py`, `council_metrics.py`, `ward_maps.py`, `map_layers.py`,
   `ward_layer_overlaps.py`, `export_dashboard_data.py`, `check_dashboard_data.py`, `raw_snapshot.py`,
   `optimize_map_labels.py` (+ `measure_label_boxes.js`, `label_measure_receiver.py`,
   `keep_label_changes_only.py`, and the `*_label_box_sizes.json` / `map_label_offsets_optimized.json`
   files). Read each script's docstring for the description; don't guess.
7. **Related projects**: link Councilmatic (https://chicago.councilmatic.org/) and DataMade's scrapers;
   one sentence on how this repo differs (map-first, every rule shown). Item 07 will expand this.

## Don't change
The Setup, Data, Automated updates, and "Local copy" sections are current (written 2026-10-15) — only
fix them if something is found wrong.

## Verification
- `ls scripts notebooks` vs. the README: every file appears once.
- Copy-paste each command block in a fresh shell (conda env active) — they run.
- Read the rendered README on GitHub after the push.
