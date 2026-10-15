# TODO

Every open item in the repo, collected 2026-10-15 (item 9 of the wish list). Each line says where it comes
from; read it there before acting. Larger projects have their own files in [`plans/`](plans/README.md).
When an item is done, delete the line (and the OPEN QUESTION comment in the code, if any).

To refresh this list: `grep -rnE "TODO|FIXME|OPEN QUESTION|not chosen|my pick|trial" scripts docs/dashboard .github sessions`
and read each hit in context.

## Check after the first scheduled run (Mon 2026-10-19, 09:00 UTC)
Steps in `sessions/2026-10-15_auto_update_handoff.md` ("Check after the first scheduled run").
- [ ] Did the bot's push (GITHUB_TOKEN) trigger the Pages build? If not, fix the workflow.
- [ ] Does `lastPublicationDate` change when a saved matter gains a vote? (`scripts/fetch_elms.py:182`,
      `MATTER_REFRESH_RULE`)
- [ ] Read any "Data update warnings" issue.
- [ ] After ~4 weeks (mid-Nov 2026): posting lag from `data/raw/elms/update_runs.json`; revisit run days and
      the initial-guess thresholds in `scripts/check_dashboard_data.py`.

## Open questions in code
- [ ] `scripts/fetch_elms.py:90` — confirm term start `TERM_START_DATE = "2023-05-15"`.
- [ ] `scripts/fetch_elms.py:211` — `UPDATE_CONTINUES_ON_HTTP_STATUS = {404}`: soft warning vs. fail the run.
- [ ] `scripts/check_dashboard_data.py:107` — next inauguration date not in our data (`CURRENT_TERM_END_DATE`).
- [ ] `.github/workflows/update-data.yml:12` — GitHub may disable scheduled workflows after 60 days without
      repo activity; unknown whether bot commits count.
- [ ] `scripts/build_tables.py:174` — blank-meetingId events matched only by date are not relabeled City Council.
- [ ] `scripts/council_metrics.py:72` — 3 joint-committee rows active in eLMS with a past end date
      (Quezada, Reilly, Conway).
- [ ] `scripts/ward_layer_overlaps.py:68` — parks: official name vs. short label on tiles.
- [ ] `scripts/ward_layer_overlaps.py:70` — rail lines: raw service list, not split.
- [ ] `scripts/build_ward_tiles.py:73` — start columns of the four southern tile rows (draft).
- [ ] `scripts/optimize_map_labels.py:114` — `WIDTH_SAFETY_FACTOR = 1.10` guess; Roboto / Segoe widths not measured.

## Display settings not chosen by the user yet
- [ ] `docs/dashboard/app.js:58` — zoom label behavior per view (`ZOOM_LABELS_BY_SHAPES`; real =
      'grow_until_px' is a trial).
- [ ] `docs/dashboard/app.js:143` — `LAYER_MAP_LABEL_SCALE = 1.5` with optimized positions (trial).
- [ ] `docs/dashboard/app.js:211` — real-map labels small on narrow screens (~6 px at 500 px); "leave as is
      for now", returns with a mobile-friendly version.
- [ ] `scripts/export_dashboard_data.py:142` — label optimizer picks (trial).
- [ ] `scripts/ward_maps.py:176` — `COMMITTEE_PALETTE = "glasbey_light"`.
- [ ] `scripts/ward_maps.py:204` — `COMBINED_VIEW_VICE_CHAIR_FILL = "same"`.
- [ ] `scripts/ward_maps.py:221` — committee short labels.
- [ ] Committees, Map View: chairs' third label line collides in several wards (26/36/37/29/1, 40/33/47);
      options in `sessions/2026-10-07_committees_handoff.md` ("Open: chairs-view label collisions").
- [ ] ward_views §4.5: RdBu white midpoint at ~69%, not 50% — pin at 50%? (`sessions/2026-10-05_phase3_handoff.md`)

## On hold
- [ ] `ward_seats` table: extend the eLMS download back in time, re-check vs. DataMade
      (`sessions/2026-10-04_running_log.md:104`).
- [ ] ward_views §4.7: show the predecessor's vote for wards whose current alder wasn't seated (27, 35)?
      (`sessions/2026-10-05_phase3_handoff.md`)
- [ ] ward_views §4.7: extra matter fields (sponsors, introduction date, referral, status) — see plans/09.

## Future projects
- [ ] CPS school attendance boundaries (could go with the CPS schools layer). User, 2026-10-15.
- [ ] CPS administrative networks (lower priority). User, 2026-10-15.
- [ ] Each file in [`plans/`](plans/README.md): 00 README, 01 committee attendance, 02 CPS board districts,
      03 caucuses, 04 vote context, 05 major roads, 06a bar charts, 06b agreement matrix, 07 landing page,
      08 Councilmatic comparison, 09 bills sponsored.
