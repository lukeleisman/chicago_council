# Plans

One file per improvement, written 2026-10-15 from the user's wish list (items 0–9, plus 9 = bills
sponsored, added the same day). Open items already in the code are collected in [`../TODO.md`](../TODO.md).

Each file says at the top which kind it is:
- **EXECUTE** — detailed enough to code from in one session.
- **PLAN-TO-PLAN** — goal, what's known, what's unknown, questions to answer. Needs its own planning
  session before any code.
- Some are **Phase A EXECUTE / Phase B PLAN-TO-PLAN**: first a short exploration (fetch, show raw data),
  then a planning session using what it found.

Standing rules for every session (global CLAUDE.md + memory): judgment calls are named constants at the top
of a module; never auto-select between sources or thresholds; show raw data before designing; OPEN QUESTION
comments for uncertainty; display choices become settings with every option drawn; stop and ask before any
cleaning or filtering; amounts as numbers; **push to `main` = live on the website**.

| File | Item | Kind | Depends on |
|---|---|---|---|
| [00_readme_update.md](00_readme_update.md) | 0 README | EXECUTE | — |
| [01_committee_attendance_and_votes.md](01_committee_attendance_and_votes.md) | 1 committee attendance + votes | A: EXECUTE, B: PLAN-TO-PLAN | — |
| [02_cps_board_districts.md](02_cps_board_districts.md) | 2 CPS Board of Ed districts | EXECUTE (stop at source choice) | — |
| [03_caucuses.md](03_caucuses.md) | 3 caucuses | PLAN-TO-PLAN | — |
| [04_vote_context.md](04_vote_context.md) | 4 context for votes | PLAN-TO-PLAN (big) | 09 helps |
| [05_street_map_major_roads.md](05_street_map_major_roads.md) | 5 major roads on Street map tiles | short PLAN-TO-PLAN, then EXECUTE | — |
| [06a_alder_bar_charts.md](06a_alder_bar_charts.md) | 6 bar charts per Alders view | EXECUTE after choices | 01, 09 add views later |
| [06b_agreement_matrix.md](06b_agreement_matrix.md) | 6 agreement ("correlation") matrix | PLAN-TO-PLAN | 03 for caucus overlays |
| [07_landing_page.md](07_landing_page.md) | 7 landing page / intro | PLAN-TO-PLAN | do last |
| [08_councilmatic_comparison.md](08_councilmatic_comparison.md) | 8 Councilmatic errors | PLAN-TO-PLAN | — |
| [09_bills_sponsored.md](09_bills_sponsored.md) | new: bills sponsored + sponsors on Votes | A: EXECUTE, B: PLAN-TO-PLAN | — |

## Suggested order
1. 00 README (and the quick items in TODO.md, e.g. the Mon 2026-10-19 scheduled-run check)
2. 02 CPS districts
3. 06a bar charts (Tenure, Absence, Committees; more views added as 01/09 land)
4. 01 committee attendance, phase A
5. 09 bills sponsored, phase A
6. 05 major roads (planning, then execute)
7. 03 caucuses (start with the Councilmatic lead)
8. 08 Councilmatic comparison
9. 06b agreement matrix
10. 04 vote context
11. 07 landing page (last: it describes everything else)

At the end of every session: add a line to the main README if something user-visible changed, tick or
remove items in TODO.md, and write the usual `sessions/<date>_<topic>_handoff.md`.
