# 03 — Caucuses: who belongs, and how often they break with their caucus

**Kind: PLAN-TO-PLAN.** Item 3 of the 2026-10-15 list.

## Goal (user, 2026-10-15)
Caucus membership (Black Caucus, LGBTQ Caucus, Progressive Caucus, …), and how often / when members break
with their caucus. Presentation to be designed. Also feeds 06b (agreement matrix ordered or colored by
caucus, caucus cohesion).

## Known (2026-10-15)
- **Lead from the user: Councilmatic shows caucus information and says its data comes from eLMS.**
  Check this first.
- What our raw eLMS data has: `data/raw/elms/body_list.json` is the whole `/body` list (fetched unfiltered
  by `fetch_elms.fetch_lists`, `scripts/fetch_elms.py:275`) and has **no caucus bodies**. Body types:
  Joint Committee 99, Committee 33, Executive Office 2, Sub-Committee 2, plus one each of "962870059",
  "" and "Journal Preparation" (all three inactive joint committees with odd type values).
  `person_list.json` has no caucus field. Our list was fetched 2026-09-30 (and by each scheduled run).
- The Councilmatic council-members index page shows no caucus labels (WebFetch, 2026-10-15). A person page
  was not checked.
- Web search (unverified): active caucuses include Black, Latino, LGBT, Progressive Reform, Democratic
  Socialist, Women's. The Daily Line lists counts (undated): Black 20, Progressive Reform 19, Women's 15,
  Latino 15, LGBT 9, Democratic Socialist 6. Wikipedia has a page for the LGBT Caucus (chair listed:
  Lamont Robinson).

## Step 1 for the planning session: trace the Councilmatic lead
1. Find where Councilmatic shows caucuses (alder pages? an organizations/bodies page?). Screenshot / quote.
2. Trace the source: the councilmatic code and `datamade/chicago-council-scrapers` (people/organizations
   scraper); the DataMade SQLite `data/raw/chicago_council.db` (organization and membership tables —
   query for names containing "Caucus").
3. If it's eLMS: which endpoint/field, and why our `/body` list lacks it (other endpoint? person detail
   `/person/{id}`? inactive filter on the API side?). Fetch one example raw.
4. If it's hand-kept by DataMade: note their source and date.
Only then fall back to manual sources.

## Questions for the planning session
- Which caucuses to include.
- Source per caucus if not in eLMS: caucus press releases and websites, alder websites, The Daily Line,
  WTTW, Sun-Times, Block Club, Wikipedia (as a lead only), asking caucus offices directly.
- Membership over time: people join and leave mid-term; dates per row.
- Storage: hand-curated `reference/caucus_memberships.csv`, one row per person × caucus × date range, each
  with a citation URL and retrieval date (same idea as `TENURE_START_OVERRIDES` citations).
- Alders in several caucuses (common): how to show.

## Sketch: "breaks with caucus"
- Per split event and caucus: the caucus position = a named rule (e.g. majority of Yea/Nay among members
  who voted; ties → no position; Absent / Not Voting excluded). User picks.
- Per member: share of split events where they voted against their caucus position; the list of those
  events (with links).
- Per caucus: cohesion (e.g. mean share agreeing with the caucus position).
- Which events: all split roll calls (224 as of 2026-10-04), or only events where the caucus itself was
  split, or a hand-picked "votes of interest" list (memory: all votes of interest, not just divided).

## Presentation candidates (draw each before choosing)
- Alders dropdown "Caucuses", like Committees: one caucus at a time, or all (stripes for several).
- Votes tab: color/outline each ward by caucus; hover shows "broke with caucus".
- Hover card / table: caucuses + break rate.
- 06b: agreement matrix ordered by caucus.
