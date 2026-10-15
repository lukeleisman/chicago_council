# 04 — Context for votes: coverage, supporters, reasons

**Kind: PLAN-TO-PLAN (big; several sessions).** Item 4 of the 2026-10-15 list.

## Goal (user, 2026-10-15)
Give the votes more context: what news outlets wrote (Sun-Times, Block Club Chicago, Streetsblog, …), which
groups support or oppose, why alders voted as they did. Tools (scrapers, searches, link collection, NLP)
plus room for the user's own manual research. Councilmatic's short AI summaries of bill contents exist but
don't explain *why* people vote the way they do.

## Sketch of tool layers (cheapest first)
1. **Link collection per matter.** Search by record number (e.g. O2026-0027938) and title keywords across:
   Chicago Sun-Times, Block Club Chicago, Streetsblog Chicago, WBEZ, WTTW, Chicago Tribune, The Daily Line,
   Chicago Reader, Crain's, South Side Weekly, Hyde Park Herald, Borderless, and **City Bureau Documenters**
   (meeting notes for council and committee meetings — likely the richest per-meeting source).
   Methods to evaluate: each site's RSS / sitemap, site search, a web search API, GDELT, Media Cloud.
   Store in a reviewable table: matter, url, outlet, date, headline, how found (query), reviewed (y/n),
   relevant (y/n, by the user).
2. **Primary sources already in eLMS.** Matter attachments (substitutes, committee reports — the
   `attachments` table), meeting video and transcript links (`videoLink`, `transcriptLink` in the meeting
   list), committee Summary PDFs (see 01), public comment.
3. **Statements by alders.** Ward newsletters and websites (`site` in `person_list.json`), social posts,
   floor speeches (transcripts / video).
4. **Supporters and opponents.** Public-comment sign-ups; organizations' letters and press releases;
   lobbyist activity (Board of Ethics lobbyist data on the Data Portal); sponsors and co-sponsors (09);
   campaign contributions (Illinois Sunshine) — sensitive, needs careful framing and the user's decision.
   Check: does Chicago have anything like Illinois General Assembly witness slips? (Probably not.)
5. **NLP / AI.** Summarize a matter's collected articles; extract alder quotes and stance; always link the
   source; never present generated text as fact; label it. Compare with Councilmatic's summaries.

## Questions for the planning session
- Scope: all ~17k roll calls, split votes only (224), or a hand-picked "votes of interest" list.
- Manual research workflow: a sheet / form the user fills, merged into the same table.
- Copyright: links + short quotes only.
- Where it shows: Votes tab event detail panel (links grouped by outlet), maybe a per-event page.
- Refresh: one-off backfill vs. part of the scheduled workflow.
- Which first experiment: e.g. 10 recent split votes × 3 outlets, measure hits and false hits.
