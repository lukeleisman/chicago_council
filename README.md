# Chicago City Council — who represents each ward, and how they vote

This repository exists to better understand the current Chicago City Council (2023–2027 term)
through its ward map.

## Status: starting

Nothing is built yet. The first step is confirming what public data exists — in particular,
whether individual alderperson roll-call votes are available for the current term — before
any analysis or map is written.

## Planned

- A data layer that queries existing open data (not a scraper written from scratch) and writes
  tables usable both from pandas notebooks and from a static web map.
- A ward map showing, per ward: the current alderperson's tenure, roll-call attendance,
  committee memberships, and positions on divided roll-call votes.
- A way to compare wards with community areas / neighborhoods.

## Data

Downloaded data is not committed (`data/` is gitignored). Sources, retrieval dates, and known
gaps will be listed here as they are used.
