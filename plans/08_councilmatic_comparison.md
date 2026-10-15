# 08 — Compare with Councilmatic; report errors upstream

**Kind: PLAN-TO-PLAN.** Item 8 of the 2026-10-15 list. Also queued in
`sessions/2026-10-15_auto_update_handoff.md` ("Next session" 2).

## Goal (user, 2026-10-15)
An in-depth comparison with https://chicago.councilmatic.org/; possibly open issues on DataMade's GitHub, or
fork and offer fixes. Errors seen so far by the user: **incorrect years in office**; **double-counted
meetings in attendance**.

## Start from what's done
- `notebooks/source_comparison.ipynb` (2026-09-30): eLMS vs. the DataMade nightly database — coverage,
  agreement, record-number formats, substitutes. Councilmatic runs on the same scraper/database.
- Known differences: `KNOWN_DELETED_MATTER_IDS` (9 matters only in DataMade); roll calls eLMS removed later
  (O2026-0025202, O2026-0027938), which DataMade may still have.
- **Our tenure start dates come from DataMade memberships** (`reference/datamade_council_memberships.csv`,
  `scripts/extract_datamade_memberships.py`). If Councilmatic's years-in-office are wrong, check whether the
  same error is in our data before anything else.

## Sketch
1. Pick test cases: 3–5 alders (include Martin, 47th), 3 meetings, 3 matters.
2. For each: Councilmatic page value vs. eLMS raw vs. DataMade SQLite vs. our tables. One row per mismatch,
   raw values from every side, no conclusions yet.
3. For each mismatch, trace the cause in code (`datamade/chicago-council-scrapers`, the councilmatic app
   repo) before calling it a bug.
4. Draft issues (or a fork + PR) with the evidence; **the user reviews and posts** — nothing is posted by
   the agent.

## Questions for the planning session
- How many alders/meetings — sample vs. all 50.
- Scrape Councilmatic pages, or use its API / the nightly DB only?
- Issue etiquette: one issue per error class; check existing issues first.
