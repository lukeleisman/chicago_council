# 06a — Sorted bar chart for each Alders view

**Kind: EXECUTE after the user's display choices.** Item 6 (bar plots) of the 2026-10-15 list.

## Goal (user, 2026-10-15)
Bring ward_views §2.3 (tenure sorted bar chart) to the dashboard, and a bar chart like it for each Alders
view: absence %, number of committees, maybe age on the Names view "or something else".

## Values per view
| Alders view | Bar value | Where it comes from today |
|---|---|---|
| Tenure | `years_on_council` | `alders.json` |
| Absence | `percent_absent` (later: overall committee + council, see 01) | `alders.json` |
| Committees | number of committees | computed from `committees.json` — or add a field in `export_dashboard_data.export_committees`. Options: standing only / + subcommittees / + joint (ward_views §5 has the per-alder counts: 6:2, 7:4, 8:17, 9:17, 10:10 incl. subcommittees, not joint) |
| Names | age? **OPEN QUESTION: no age in eLMS.** Candidates: Ballotpedia, alder bios, news — each would need a cited reference CSV. Or another value the user picks (e.g. ward area, ward population) or no chart. |
| Bills sponsored (after 09) | sponsored count, total or per year | 09 |

## Display choices (settings at the top of app.js; draw every option for the user)
- Placement: below the map / replacing the side table / a "Map | Bars" toggle.
- Orientation: horizontal bars (50 rows, readable labels) vs. vertical.
- Colors: the map's colormap for that view (tenure / absence ranges already in `tenureRange`,
  `absenceRange`), or one neutral color.
- Labels: ward number + last name (`label_name`), value at bar end with the view's decimals
  (`TENURE_DECIMALS`, `ABSENCE_DECIMALS`).
- Sort: descending / ascending / by ward.
- Interaction: hover = the same hover card; click a bar = select that ward (shared selection with the map
  and table, `scrollTableToSelectedRow`).
- Committees view with one committee picked: bars only make sense for "All committee" overviews — hide or
  show count.

## Implementation notes
- SVG drawn in `docs/dashboard/app.js`, no chart library (matches existing code).
- Python change only if the committee count is exported (then `council_metrics` + `export_dashboard_data`,
  and the notebook gets the same number).
- Load the `dataviz` skill before writing chart code.

## Verification
- Bars match the notebook §2.3 for tenure, and the side table for every value.
- Map View and Tile View; phone width (~400 px); the WordPress embed (page 153) after push.
