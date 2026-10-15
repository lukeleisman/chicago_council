# 06b — Agreement ("correlation") matrix on the dashboard

**Kind: PLAN-TO-PLAN.** Item 6 (correlation plots) of the 2026-10-15 list.

## Goal (user, 2026-10-15)
Bring ward_views §4.3–4.6 (alder-by-alder agreement on split roll calls, orderings, display options) to
the dashboard. Needs thought: a new tab, or under something else? Could showcase the caucuses and how
strong they are or aren't (03).

## What exists
`notebooks/ward_views.ipynb` §4.3 agreement between alders, §4.4 orderings, §4.5 matrix, §4.6 display
options side by side (generator: `sessions/2026-10-04_build_ward_views_notebook.py`). Split events from
`council_metrics.split_event_steps`. The agreement computation lives in the notebook — move it to
`council_metrics.py` (logic unchanged) before exporting, as was done for absence.

## Questions for the planning session
- **Where**: a new tab ("Voting blocs" / "Agreement") vs. a view under Votes vs. inside the hover card.
- **Form**: 50×50 matrix (dense; hard on a phone) vs. alternatives — a 2-D layout of alders by voting
  similarity (scatter), a "most / least similar alders" list per alder, one alder's row drawn on the map
  (color each ward by agreement with the selected alder — fits the map-first design).
- **Ordering**: ward, clustering, caucus (after 03), committee.
- **Which events**: all split roll calls / hand-picked votes of interest / by year.
- **Caucus cohesion**: within-caucus mean agreement vs. between caucuses; needs 03.
- What the user wants to read from it — answers decide the form.
