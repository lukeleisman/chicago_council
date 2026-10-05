# Chicago City Council — who represents each ward, and how they vote

This repository exists to better understand the current Chicago City Council (2023–2027 term)
through its ward map.

## Status: data layer built, views next

Raw eLMS downloads (per-member votes for the current term) are turned into tidy tables; the
ward-map views are next.

## Planned

- A data layer that queries existing open data (not a scraper written from scratch) and writes
  tables usable both from pandas notebooks and from a static web map.
- A ward map showing, per ward: the current alderperson's tenure, roll-call attendance,
  committee memberships, and positions on divided roll-call votes.
- A way to compare wards with community areas / neighborhoods.

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
`data/tables/`: `people`, `meetings`, `attendance`, `vote_events`, `member_votes`, `attachments`. Every rule is
a named constant at the top of the script; corrected values keep the raw value beside them with
a `*_source` column. Nothing is filtered — that is left to the views.

`scripts/build_ward_tiles.py all` writes equal-size ward tiles to `data/tables/`:
`ward_tiles_grid.geojson` (hand-specified grid) and `ward_tiles_pushed.geojson` (tiles started at
each ward and pushed apart). Any view switches shapes with `MAP_SHAPES` (`scripts/ward_maps.py`).

Shared metrics (current alders, absence, split roll calls) live in `scripts/council_metrics.py`,
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
  an ipywidgets dropdown, event details and attachment PDF links).
