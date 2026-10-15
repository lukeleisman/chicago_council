# 02 — CPS Board of Education electoral districts on the Wards tab

**Kind: EXECUTE, with a stop at the source choice.** Item 2 of the 2026-10-15 list.

## Goal (user, 2026-10-15)
The 20 Chicago Board of Education electoral districts (elected board: 10 seats elected Nov 2024, all 20 in
2026) as a new Wards-tab layer.
- School attendance boundaries: a **separate future project** (could go on the CPS schools map). In TODO.md.
- CPS administrative networks: interesting, **lower priority**. In TODO.md.

## Step 1 — find the boundary source (STOP and ask)
One web search on 2026-10-15 found only Local School Council voting districts (a different boundary set,
e.g. Data Portal `6mci-28cz`, `a3hw-pyw5`) — not the Board of Ed districts. Candidates to check:
- Chicago Data Portal search: "board of education", "school board", "electoral district".
- Chicago Board of Election Commissioners (chicagoelections.gov) GIS / district maps.
- Illinois General Assembly: the 2024 Public Act that drew the 20 districts (and its map files / block
  equivalency file).
- Cook County Clerk GIS; CPS's own site.
For each: URL, publisher, date, format (GeoJSON / shapefile / block equivalency), whether it's the final
enacted map. Put the table to the user; **the user picks**. Nothing found → stop and write it up.

### Step 1 results (2026-10-15) — waiting on the user's pick
The enacted law is **PA 103-0584** (SB 15, effective 2024-03-18), Article 1 "Chicago Board of Education
District Act", §1-5: **10 districts, each split into 2 subdistricts (1A, 1B … 10B)**, each subdistrict a list
of 2020 census blocks (38,794 blocks in total, none listed twice). §1-10(d)–(g) assign any unlisted or
double-listed part of the city. Text: https://ftp.ilga.gov/Public%20Acts/103/103-0584.htm (ilga.gov blocks
scripts; the ftp mirror is its stated public repository).

| Candidate | Publisher, date | Format | Matches the law? |
|---|---|---|---|
| A. Build from the law: dissolve 2020 blocks per §1-5 list | IL General Assembly (law) + Data Portal `3aji-w8h2` (Census Blocks 2020) | text list + GeoJSON | is the law; 24 listed blocks are missing from `3aji-w8h2`, 14 portal blocks are in no list |
| B. `ERSB_20_Sub_District_Map_FA1_SB_15.zip` (ilsenateredistricting.com, labeled "proposed", Floor Amendment 1) | IL Senate Democrats redistricting site; .shp dated 2024-03-07 | shapefile, 20 rows (LONGNAME "District 1a", DISTRICT 1–20, TOTAL population) | every one of the 38,770 law blocks found on the portal has its interior point inside the matching subdistrict (100% per subdistrict) |
| C. "Chicago Elected School Board 20-District Map" (ArcGIS item `ad7c6d1283b44d28b73460f2b02f012f`, used by the Tribune's lookup app) | Chicago Tribune (owner `cmalon`) | GeoJSON, 20 rows | geometry identical to B (symmetric difference 0 for all 20); adds `School Board Member` (2024 names) and `Elected School Board District` |

Not found: anything on the Chicago Data Portal, chicagoelections.gov, or ArcGIS Hub from the City/CPS/CBOE.
OPEN QUESTION: no later law redrawing the subdistricts was found (HB1713, 104th GA, amends §34-3 but lists
no blocks), but this was not exhaustive.
Scratch evidence (not committed): the comparison scripts and downloads in this session's scratchpad.

## Step 2 — add the layer (same pattern as every other layer)
1. `scripts/fetch_layers.py`: add a row to `LAYERS` (layer_name e.g. `cps_board_districts_2024`,
   dataset id, download_method, portal page id, notes with source and date). Not a Socrata source → a new
   `download_method` value with its own named URL constant and a comment; don't overload
   `resource`/`geospatial`. Manifest entry as usual.
2. `scripts/map_layers.py`: `LAYER_STYLE` entry (label column = district number; color, edges).
3. `notebooks/map_layers_review.ipynb`: run it; the new layer is drawn by the existing loops. Review with the
   user.
4. `scripts/ward_layer_overlaps.py`: run the overlap table; show area shares per ward × district **before**
   choosing a `WARD_SUMMARY_RULES` entry (which districts count as "in" a ward — user's choice, as for the
   other layers). Probably "list" (1–3 districts per ward).
5. `scripts/export_dashboard_data.py`: add to `DASHBOARD_LAYERS`. Run the **full** export by hand (not
   `--data-only`), but keep only the changed files (see `scripts/keep_label_changes_only.py` and the
   round-4 notes on rounding noise in re-exported geojson).
6. `docs/dashboard/app.js`: `LAYER_OPTIONS` entry ("CPS board districts (2024)"), `LAYER_NAME_PREFIX`
   ("District "), hover/table text.
7. Map View labels: check collisions; `scripts/optimize_map_labels.py` if needed.
8. `scripts/check_dashboard_data.py`: confirm the new file is covered by the file checks.

## Choices to put to the user
- Label: district number only, or + current board member (names change with the 2026 election; could be a
  later step, with a reference CSV and citation).
- Show which districts elected in 2024 vs. appointed until 2027? (A setting; default off.)
- Layer color / opacity.

## Verification
- Notebook map review image matches the source's published map.
- Each ward's district list spot-checked against the source map for 3 wards.
- Dashboard locally: `cd docs && python -m http.server 8765` (port 8765 may be held by another server —
  use another port), Map View and Tile View, hover card, table; phone width.
- `python scripts/check_dashboard_data.py` passes.
