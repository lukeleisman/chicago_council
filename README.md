# Chicago City Council — who represents each ward, and how they vote

This repository exists to better understand the current Chicago City Council (2023–2027 term)
through its ward map.

## Status: dashboard live

The dashboard is served by GitHub Pages from `main` → `/docs` and embedded on the WordPress page
(page 153). **Pushing to `main` updates the live page.** The vote and attendance data have updated
automatically twice a week since 2026-10-15 (see [Automated updates](#automated-updates)).

## What's on the dashboard

Read from `TAB_OPTIONS`, `ALDER_MEASURE_OPTIONS` and `LAYER_OPTIONS` in `docs/dashboard/app.js` (2026-10-15).

- **Alders** tab, with a dropdown: Names, Tenure, Absence, Committees (a second dropdown picks all
  committee chairs, all vice chairs, chairs and vice chairs, or one committee).
- **Votes** tab: split council roll calls (`SPLIT_*` rules in `council_metrics.py`), each alder's vote on the one picked.
- **Wards** tab, with a dropdown of layers drawn under the wards: Street map, Community areas,
  Neighborhoods, ZIP codes, Police districts, Parks, CTA rail lines, CTA rail stations,
  CPS schools (2025–26), Ward offices.
- Every tab: **Map View** (2023 ward boundaries) or **Tile View** (one equal-size tile per ward); zoom;
  a hover card per ward and a side table (clicking a ward scrolls the table to it).

What's next: [`plans/`](plans/README.md) (one file per improvement) and [`TODO.md`](TODO.md) (every open
item in the code).

## Setup

```bash
conda env create -f environment.yml
conda activate chicago-council
python -m ipykernel install --user --name chicago-council --display-name "Chicago Council"
```

Notebook outputs are stripped from git via [nbstripout](https://github.com/kynan/nbstripout)
so committed `.ipynb` files stay small and diffable. The filter is local git config, not
something that travels with the repo, so run this once after cloning:
```bash
nbstripout --install --attributes .gitattributes
```

## Data

Downloaded data is not committed (`data/` is gitignored). Each download script records source
URLs and retrieval times alongside the files it writes.

- `scripts/fetch_elms.py` — Chicago City Clerk eLMS API (`api.chicityclerkelms.chicago.gov`):
  alderpersons, committees, meetings (agendas and attendance), and legislation with per-member
  votes. Resumable; respects the API's rate-limit header.
- `scripts/fetch_layers.py` — map layers from the Chicago Data Portal (wards, community areas,
  neighborhoods, census tracts, precincts, ZIP codes, police districts, parks, CTA, schools,
  ward offices). Dataset IDs are listed in the script.
- `scripts/fetch_photos.py` — current alders' photos from the eLMS profile-picture URLs in
  `data/tables/people.csv` (run `build_tables.py` first), saved to `data/raw/photos/`.
- DataMade's nightly Chicago council SQLite export
  ([datamade/chicago-council-scrapers](https://github.com/datamade/chicago-council-scrapers),
  release `nightly`, ~1 GB zipped / 3.5 GB unzipped) — used as a cross-check and for history.

## Tables

`scripts/build_tables.py all` reads the raw downloads (no API calls) and writes CSV tables to
`data/tables/`: `people`, `meetings`, `attendance`, `vote_events`, `member_votes`, `attachments`, `committee_members` (from eLMS
`body_list.json`). Every rule is
a named constant at the top of the script; corrected values keep the raw value beside them with
a `*_source` column. Nothing is filtered — that is left to the views.

`scripts/build_ward_tiles.py all` writes equal-size ward tiles to `data/tables/`:
`ward_tiles_grid.geojson` (hand-specified grid) and `ward_tiles_pushed.geojson` (tiles started at
each ward and pushed apart). Any view switches shapes with `MAP_SHAPES` (`scripts/ward_maps.py`).

Shared metrics (current alders, absence, split roll calls, current committee assignments) live in `scripts/council_metrics.py`,
used by both the notebooks and the dashboard export.

## Dashboard (preliminary)

A static page in `docs/` (served by GitHub Pages from `main` → `/docs`), in the same pattern as
blanketbox_public: `docs/dashboard/app.js` is one self-contained script that fetches
`docs/data/*.json` and renders into `<div id="council-app">`.

```bash
python scripts/build_tables.py all && python scripts/build_ward_tiles.py all
python scripts/export_dashboard_data.py           # writes docs/data/ (committed)
cd docs && python -m http.server 8765             # then open http://localhost:8765/
```

To embed on another site (e.g. a WordPress Custom HTML block):
```html
<div id="council-app"></div>
<script src="https://lukeleisman.github.io/chicago_council/dashboard/app.js"></script>
```
The script finds `data/` relative to its own URL.

## Automated updates

`.github/workflows/update-data.yml` updates the dashboard data **Mondays and Thursdays at 09:00 UTC**
(4 am Chicago in daylight time, 3 am in standard time). It can also be started by hand: Actions tab →
"Update dashboard data" → "Run workflow".

Each run:
1. downloads the last raw-data snapshot (GitHub Release `raw-data`, asset `raw_data_snapshot.tar.gz`)
   and unpacks it (`scripts/raw_snapshot.py unpack`);
2. `scripts/fetch_elms.py update`: lists, new matters, and saved matters whose `lastPublicationDate`
   changed (`MATTER_REFRESH_RULE`), plus recent council meetings. It appends a record to
   `data/raw/elms/update_runs.json`, including what eLMS had posted per recent meeting (for measuring
   how long votes take to appear);
3. `build_tables.py all` → `export_dashboard_data.py --data-only` (alders, split events, committees,
   meta; the ward shapes and map layers are exported only by hand) → `check_dashboard_data.py`;
4. if the hard checks pass: commits `docs/data/` to `main` if it changed (this is what updates the live
   page), and replaces the snapshot asset with a new one.

Checks (`scripts/check_dashboard_data.py`; every threshold is a named constant there):
- **Hard** (nothing is published, the run fails, GitHub emails you): a missing or broken `docs/data`
  file; not exactly one current alder per ward; a current alder without a tenure start date, photo, or
  absence denominator; table row counts or saved-file counts going down; fewer split events; a file
  shrinking too much; total size too large. The build's own stops (a new vote value, an unknown
  duplicate) also fail the run.
- **Soft** (published; a comment on the open issue "Data update warnings", which emails you): a ward's
  alder changed; a committee, chair, or vice chair changed; an alder's absent-meeting count jumped;
  many new split events; unmatched placeholder person IDs; a recent council meeting still missing its
  agenda or attendance; no new council meeting for a long time; matters that failed to download.

The report from every run is on that run's summary page.

**New alder warning.** A newly appointed alder has no DataMade start date (tenure comes from the frozen
extract `reference/datamade_council_memberships.csv`), so the hard check stops the publish. Fix: add
an entry to `TENURE_START_OVERRIDES` in `scripts/build_tables.py` with a citation, or download a newer
DataMade database and run `scripts/extract_datamade_memberships.py`. Then commit and re-run the
workflow. The Map View labels may also need re-optimizing (`scripts/optimize_map_labels.py`).

**Local copy of the published data.** To work with the same raw data the live dashboard was built from:
```bash
gh release download raw-data --pattern raw_data_snapshot.tar.gz --dir data/snapshot --clobber
python scripts/raw_snapshot.py unpack --overwrite   # replaces those files under data/; leaves others alone
python scripts/build_tables.py all
```
`build_tables.AS_OF_DATE_RULE` is `"run_date"` (tenure counts to today); set it to `"fixed"` to
reproduce older numbers.

## Notebooks

- `notebooks/map_layers_review.ipynb` — draws every map layer for visual review.
- `notebooks/source_comparison.ipynb` — eLMS vs DataMade vote coverage and agreement.
- `notebooks/tables_review.ipynb` — §1: the raw data behind each table-building decision;
  §2: each built table, how the tables link, and known results rebuilt from them.
- `notebooks/ward_tiles.ipynb` — the grid and pushed-apart ward tiles, their options, and how
  well each keeps real-map neighbors.
- `notebooks/ward_views.ipynb` — ward-map views built from `data/tables/` (drawing helpers in
  `scripts/ward_maps.py`). §1: alder map (ward number + name) and photo grid; §2: tenure map
  (continuous color, capped at 22 years) and sorted bar chart; §3: absence map (% of council
  meetings absent) and ranked table; §4: split roll calls (table of the 224 council roll calls
  with ≥1 Nay, alder-by-alder agreement matrix, and a map of each alder's vote on one event with
  an ipywidgets dropdown, event details and attachment PDF links); §5: committee assignments
  (assignments table and checks; maps of all chairs, all vice chairs, chairs and vice chairs; display
  options side by side; one committee; any committee by dropdown).

## Scripts

Descriptions from each script's docstring. "By hand" = run when that input changes; nothing else runs it.

| Script | Reads → writes | When to run |
|---|---|---|
| `fetch_elms.py` | eLMS API → `data/raw/elms/` (verbatim JSON; `update` also appends `update_runs.json`) | `update` in every scheduled run; the other subcommands (`lists`, `matter_list`, `meetings`, `matters`, …) for a full download |
| `fetch_layers.py` | Chicago Data Portal → `data/raw/layers/*.geojson` + `manifest.json` | by hand, once (`--force` re-fetches) |
| `fetch_photos.py` | `data/tables/people.csv` photo URLs → `data/raw/photos/` + `manifest.json` | by hand, after `build_tables.py` (used by ward_views §1 only; the dashboard links the eLMS photo URLs) |
| `extract_datamade_memberships.py` | DataMade SQLite → `reference/datamade_council_memberships.csv` (committed) | by hand, after downloading a newer DataMade database |
| `raw_snapshot.py` | `data/` ↔ `data/snapshot/raw_data_snapshot.tar.gz` (+ manifest) | `unpack` / `pack` in every scheduled run; `unpack` for a local copy |
| `build_tables.py` | `data/raw/` → `data/tables/*.csv` | after any fetch; every scheduled run |
| `build_ward_tiles.py` | ward layer → `data/tables/ward_tiles_*.geojson` | by hand, when the tile layout changes |
| `council_metrics.py` | (module) current alders, absence, split roll calls, committee assignments | imported by the notebooks and the export |
| `ward_maps.py` | (module) ward shapes, drawing helpers, committee display settings | imported by the notebooks and the export |
| `map_layers.py` | (module) map-layer styles and neighbor coloring | imported by the notebooks and the export |
| `ward_layer_overlaps.py` | wards × raw layers → `data/tables/ward_layer_overlaps.csv`, `docs/data/ward_layer_summary.json` | by hand, when a layer or its summary rule changes |
| `export_dashboard_data.py` | `data/tables/`, tiles, layers → `docs/data/*.json`, `*.geojson` | `--data-only` in every scheduled run; full export by hand when shapes or layers change |
| `check_dashboard_data.py` | new build vs. last published data → `data/check/` report; exit 1 on a hard failure | every scheduled run; by hand before pushing a manual export |
| `optimize_map_labels.py` | label box sizes → `scripts/map_label_offsets_optimized.json` (+ `data/tables/map_label_optimization.json`) | by hand, when Map View labels change (e.g. a new alder) |
| `measure_label_boxes.js` | pasted in the browser console on the local dashboard; posts label box sizes | by hand, to re-measure label boxes for `optimize_map_labels.py` |
| `label_measure_receiver.py` | local server (127.0.0.1:8766) that saves what `measure_label_boxes.js` posts | with `measure_label_boxes.js` |
| `keep_label_changes_only.py` | after a full export: restores unchanged shape files from git, keeps only label changes | by hand, when only label positions changed |

Data files in `scripts/` (committed): `map_label_box_sizes.json` (Alders/Votes tab label boxes) and
`wards_tab_label_box_sizes.json` (Wards tab label boxes), both measured in the browser and read by
`optimize_map_labels.py`; `map_label_offsets_optimized.json`, its output, read by the export.

## Related projects

- [Chicago Councilmatic](https://chicago.councilmatic.org/) (DataMade) — searchable legislation,
  meetings and votes, built on DataMade's scrapers
  ([datamade/chicago-council-scrapers](https://github.com/datamade/chicago-council-scrapers)).
- This repo is map-first: every number is shown per ward, and every rule behind it is a named
  setting in the code and on the page.
