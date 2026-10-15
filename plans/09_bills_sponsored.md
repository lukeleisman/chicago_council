# 09 — Bills sponsored (new Alders view) and sponsors on the Votes tab

**Kind: Phase A EXECUTE (explore), then Phase B PLAN-TO-PLAN.** Added by the user 2026-10-15.

## Goal (user, 2026-10-15)
- A new Alders view: **bills sponsored**, with a toggle **total ↔ per year**.
- With sponsor data, **highlight each event's sponsors on the Votes tab**.

## Known (checked 2026-10-15, raw)
- Matter detail files (`data/raw/elms/matters/`, 17,375 files) have a `sponsors` list: sponsorType
  "Sponsor" 17,603 rows, "CoSponsor" 6,584, "Filing Sponsor" 186; each with `personId`, `sponsorName`,
  `office`.
- **Only matters with at least one vote are downloaded** (`MATTER_HAS_VOTES_FILTER`,
  `scripts/fetch_elms.py:117`). Introduced-and-referred-only matters are missing, so sponsor counts from
  our files would undercount.
- `data/raw/elms/matter_list_all_active_in_term.json` (2026-09-30): **34,609** matters (Ordinance 18,539,
  Claim 7,244, Resolution 6,084, Order 1,722, Appointment 615, Communication 166, Report 155, …). Its list
  records have `sponsors: null`, but `filingSponsor` is filled on 34,555 (top: "Misc. Transmittal" 4,335,
  Lopez 2,022, Johnson (Mayor) 1,720, Harris 1,433, Coleman 1,122).
- `/export/matter` returns CSV, up to 500 records per call, with `filter` — sponsor columns unknown.

## Phase A — explore (EXECUTE)
1. Test cheap routes on a few matters, raw output shown: list endpoint with sponsors (expand?),
   `/export/matter` CSV columns, the DataMade SQLite sponsorship table (`data/raw/chicago_council.db`).
2. If only detail fetches work: ~17k more requests — **fetch scope is the user's choice** (all, ordinances
   and resolutions only, sample first).
3. Tables: sponsors per alder × matter type × sponsorType; per year. No metric chosen.
4. Check: does `filingSponsor` equal the "Sponsor" row? Matters with several Sponsors?

## Phase B — choices (each a named setting, every option drawn)
- Which sponsorTypes count: Sponsor only / + CoSponsor / Filing Sponsor.
- Which matter types count: claims, honorary resolutions, sign/driveway orders and other ward-service items
  likely dominate some totals. Show the breakdown; maybe a "substantive only" toggle defined by a named
  table of types.
- Mayor / Clerk / "Misc. Transmittal" items: not alders; show in Votes detail only.
- "Per year": per year on the council within this term (tenure, capped at term start 2023-05-15) vs. per
  calendar year (small multiples?).
- Scheduled workflow: keep sponsors fresh — cost per run.

## Votes tab
- Mark sponsors / co-sponsors on the split-event map (outline, star, label suffix — a display setting, all
  drawn) and list them in the event detail with type.
- Non-alder sponsors (the Mayor) as text.

## Ties
06a (bar chart for this view); 04 (sponsors are the first clue to "why"); 03 (caucus members co-sponsoring).

## Files that will change (Phase B execution)
`scripts/fetch_elms.py`, `scripts/build_tables.py` (new `sponsors` table), `scripts/council_metrics.py`,
`scripts/export_dashboard_data.py`, `docs/dashboard/app.js` (`ALDER_MEASURE_OPTIONS`, Votes tab),
`scripts/check_dashboard_data.py`, `notebooks/ward_views.ipynb` (new section), `notebooks/tables_review.ipynb`.
