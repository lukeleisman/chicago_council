# 07 — Landing page / intro text

**Kind: PLAN-TO-PLAN. Do last** (it describes everything else). Item 7 of the 2026-10-15 list.

## Goal (user, 2026-10-15)
Text that says what the app is for and helps people find what they're looking for. Link to Councilmatic
and highlight how this app complements it.

## Sketch of content
- Purpose: who represents each ward, how they vote, how often they attend; map-first.
- "I want to…" links: find my alder (by address → ward), see how my alder voted on divided votes, see
  attendance, see committee roles, see what's in my ward (Wards tab layers).
- How this complements Councilmatic (https://chicago.councilmatic.org/): Councilmatic = every bill,
  meeting and person with search and summaries; this app = ward map views, comparisons across alders,
  every counting rule shown (absence rule, split-vote rule), data checks. Link to Councilmatic's alder
  and matter pages from the hover card / event detail.
- Data sources and update schedule (meta.json already has "Data checked …; last changed …; includes
  council meetings through …").
- Known limits (e.g. committee votes mostly voice votes; tenure source).

## Questions for the planning session
- In-app intro panel (collapsible) vs. the WordPress page text around the embed vs. both.
- Address lookup: which geocoder (City of Chicago, Census, Esri), privacy, rate limits.
- Councilmatic URL pattern for alders / matters (stable slugs?).
- Tone and length; who writes it (user drafts, agent edits?).
