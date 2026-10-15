# 01 — Committee attendance and committee votes

**Kind: Phase A EXECUTE (explore raw data), then Phase B PLAN-TO-PLAN.** Item 1 of the 2026-10-15 list.
Also queued in `sessions/2026-10-15_auto_update_handoff.md` ("Next session" 1).

## Goal (user, 2026-10-15)
- The Absence view counts committee meetings as well as council meetings.
- Hover card and table show **overall** attendance (committee + council) **and the breakdown**: council
  meetings (count, %) and committee meetings (count, %).
- Any recorded / divided committee votes go into the Votes tab too. (User expects most committee votes are
  voice votes.)

## Known facts (checked 2026-10-15, raw)
- `data/raw/elms/meeting_list.json`: **912 meetings since 2023-05-15**: City Council 90; committees: Budget
  98, Finance 95, Economic/Capital/Technology 57, Housing 53, Zoning 50, Transportation 49, Public Safety
  43, Pedestrian & Traffic Safety 41, License 37, Health 36, Police & Fire 32, Workforce 32, Education 28,
  Ethics 28, Immigrant & Refugee Rights 24, Environment 19, Contracting 19, Committees & Rules 18, Special
  Events 17, Aviation 10; joint committees 1–7 each; subcommittees (Revenue, Youth Employment) 3 each.
- In the list file every meeting's `agenda` and `attendance` are `null`. Details (agenda + attendance) are
  fetched only for `COUNCIL_BODY_NAME = "City Council"` (`scripts/fetch_elms.py:86`, filter at `:393`).
  **Committee meeting details have never been fetched**, so we don't yet know if eLMS has committee
  attendance at all.
- Committee meetings list files: Agenda, **Summary** (e.g. "Meeting Summary 101426 FINAL.pdf"), Notice.
  OPEN QUESTION: if the detail endpoint has no attendance, the Summary PDF may be the only source.
- **Lead from the user (2026-10-15): Councilmatic shows committee attendance**, so the data exists
  somewhere. If our committee detail fetch comes back without attendance, check where Councilmatic gets it:
  the `datamade/chicago-council-scrapers` events scraper (which endpoint / field), and the DataMade SQLite
  `data/raw/chicago_council.db` (event participants / attendance for committee events). Compare a few
  meetings across Councilmatic, DataMade, and eLMS raw — keeping in mind the user has seen Councilmatic
  double-count meetings in attendance (see 08).
- Committee votes in our matter files (`vote_events`): only **19** events with a roster not by City
  Council — 17 `roll call`, 2 `committee attendance` (`build_tables.ROSTER_KIND_RULES`). **5** have ≥ 1 Nay
  (License and Consumer Protection 4, Special Events 1). So almost no committee votes are recorded per
  member in eLMS — consistent with the user's guess.
- Membership: `committee_members` table; current assignments from
  `council_metrics.current_committee_assignments` (ward_views §5).
- Today's absence rule: `council_metrics.py` constants `ABSENT_MEETING_SHARE_THRESHOLD` (0.5),
  `ABSENCE_MEETING_BODY`, `ABSENCE_ROSTER_KINDS`, `EXCLUDE_EVENTS_FROM_ABSENCE`, `ABSENCE_DENOMINATOR`
  ("meetings_on_roster") — absence is computed from per-item roll calls, not from the attendance roll call.

## Phase A — explore (one session; EXECUTE)
1. **Ask the user for the fetch scope** before any download: which bodies (all committees / standing only
   / plus joint and sub), since when (term start), and whether to try a sample of ~20 meetings first. Rate
   limit and resume logic already in `fetch_elms.py` — reuse `fetch_meeting_details`, with the body filter
   as a new named constant (e.g. `MEETING_DETAIL_BODIES`), not by editing `COUNCIL_BODY_NAME`.
2. Save to a separate folder (e.g. `data/raw/elms/meetings_committees/`) so the scheduled workflow and
   snapshot are untouched until the user decides.
3. New notebook section (tables_review §1.x style, raw first):
   - How many committee meetings have an attendance record; what one looks like (raw JSON).
   - Attendance vs. committee membership on that date: members present/absent, non-members present
     (alders often attend other committees), joint-committee rosters.
   - Cancelled / recessed / deferred meetings (`status` values).
   - The 19 committee vote events: list with matter, body, date, counts, roster kind.
   - 2–3 Summary PDFs: what attendance information they carry, if any.
4. Handoff with the raw counts. **No metric yet.**

## Phase B — planning questions (after A)
- **What "absent from a committee meeting" means** (no per-item roll call there; attendance record only?
  late arrivals?). Named constant, user's choice.
- **Denominator**: meetings of committees the alder was a member of on that date / every meeting they're
  on the roster for / joint committees counted once or as each parent committee.
- **Non-members who attend**: count, show, or ignore.
- **Overall attendance formula**: total meetings attended ÷ total meetings (council and committee pooled)
  vs. an average of the two rates. Show both drawn; user picks.
- **Display**: hover card and table columns (overall %, council n and %, committee n and %); whether the
  map colors by overall or by a sub-toggle (overall / council / committee).
- **Scheduled workflow**: fetch committee details every run? Request cost (~820 meetings once, then a few
  per run), new hard/soft checks in `check_dashboard_data.py`, snapshot size.
- **Committee votes on the Votes tab**: `SPLIT_ACTION_BY = "City Council"` today. Options: a dropdown
  "Council / Committee / Both", or a separate list; only 5 divided committee votes now, and committee
  members only (so the map would show non-members as blank).

## Files that will change (Phase B execution, for reference)
`scripts/fetch_elms.py`, `scripts/build_tables.py` (meetings + attendance for committee bodies),
`scripts/council_metrics.py` (absence functions), `scripts/export_dashboard_data.py`,
`docs/dashboard/app.js` (absence view, hover, table, Votes tab), `scripts/check_dashboard_data.py`,
`notebooks/ward_views.ipynb` §3 (and §4 for votes), `.github/workflows/update-data.yml` if fetch scope grows.
