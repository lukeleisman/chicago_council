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
- DataMade's nightly Chicago council SQLite export
  ([datamade/chicago-council-scrapers](https://github.com/datamade/chicago-council-scrapers),
  release `nightly`, ~1 GB zipped / 3.5 GB unzipped) — used as a cross-check and for history.

## Tables

`scripts/build_tables.py all` reads the raw downloads (no API calls) and writes CSV tables to
`data/tables/`: `people`, `meetings`, `attendance`, `vote_events`, `member_votes`. Every rule is
a named constant at the top of the script; corrected values keep the raw value beside them with
a `*_source` column. Nothing is filtered — that is left to the views.

## Notebooks

- `notebooks/map_layers_review.ipynb` — draws every map layer for visual review.
- `notebooks/source_comparison.ipynb` — eLMS vs DataMade vote coverage and agreement.
- `notebooks/tables_review.ipynb` — §1: the raw data behind each table-building decision;
  §2: each built table, how the tables link, and known results rebuilt from them.
