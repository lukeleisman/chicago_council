# Plan 10: Council and committee meetings calendar

Kind: **Phase A EXECUTE (survey, then stop and ask), then EXECUTE (B, C)**; phase D waits for the user's
Google service-account secret. Written 2026-11-11. No code yet.

**Next-session prompt:**
> Read `plans/10_meetings_calendar.md` and the newest `sessions/*handoff.md`. Run Phase A (`build_calendar.py survey`), show me the raw output, and stop to ask how to show the Recessed, Reconvened, Rescheduled, Revised, blank and None statuses. Then build Phases B and C. Phase D (the Google Calendar mirror) waits until I've made the service-account secret.

## Context
The goal is a calendar people can subscribe to in Google Calendar, Apple or Outlook. It lists every City Council meeting and committee meeting, updates automatically, and lets subscribers turn individual bodies on and off.

The repo already fetches everything needed. On every scheduled run, `scripts/fetch_elms.py` `fetch_lists()` writes `data/raw/elms/meeting_list.json`: all bodies, 3,656 meetings, each with a stable `meetingId` GUID, a UTC `date`, `status`, `location`, `comment`, and `files` (Notice/Agenda PDFs).

The link should eventually go on the landing page (`plans/07_landing_page.md`). Until then it goes in the dashboard footer and the README.

**User decisions (2026-11-11):**
- **Hosting: both.** `.ics` files on GitHub Pages, plus a mirror into public Google Calendars.
- **Feeds:** one combined feed, one for City Council, and one per committee.
- **Cancelled meetings:** keep them, with a `CANCELLED:` title prefix and `STATUS:CANCELLED`.
- **Refresh:** a step in the existing `update-data.yml` workflow, whose schedule changes to every weekday.

## Phase A: show the raw data, then stop and ask (standing rule)
New script `scripts/build_calendar.py` with subcommand `survey`. It prints, without changing anything:
- Every body: meeting count, first and last date, and the number of future meetings.
- Every `status` value with counts, including `""` and `None`, and how Recessed, Reconvened, Rescheduled and Revised meetings look in raw form, with 2–3 sample records each.
- All "Joint Committee: …" bodies.
- Distinct `location` values and `comment` samples.

**Already decided (user, 2026-11-11):**
- New packages are fine. Use `icalendar` (and the Google client libraries in phase D), added to `environment.yml`.
- `EVENT_DURATION_MINUTES = 120`.
- Joint committees appear in each parent committee's feed.
- Nothing before the start of the term (`TERM_START_DATE`). Committees with no meetings this term get no feed.
- New or renamed committees are picked up automatically. Any body that has a meeting this term gets a feed without a code change, and the build report lists newly appearing bodies so the user can see them.
- Joint committee parents are found by parsing the body name, "Joint Committee: X and Y". The survey prints how each joint body was parsed. A joint-body part that doesn't match a current committee name is reported loudly (it is never dropped silently), and `JOINT_COMMITTEE_PARENT_OVERRIDES` fixes it by hand.

**Still to ask after the survey:** how to show Recessed, Reconvened, Rescheduled, Revised, blank and None statuses.

## Phase B: build the .ics feeds
`scripts/build_calendar.py build` reads `data/raw/elms/meeting_list.json` and writes `docs/calendar/`.

**Constants at the top** (judgment calls, each dated "(user, 2026-11-11)"):
- `FEED_START_DATE = TERM_START_DATE`. Past meetings this term stay in the feed: if an event drops out of a subscribed feed, Google deletes it from subscribers' calendars. The apps open on today either way.
- `EVENT_DURATION_MINUTES = 120`
- `FEED_BODIES_RULE = "any_meeting_since_feed_start"` (decides which bodies get their own feed)
- `JOINT_COMMITTEE_PARENT_OVERRIDES = {}` (hand fixes for joint-body names that don't parse)
- `CANCELLED_STATUSES = {"Cancelled"}` and `CANCELLED_TITLE_PREFIX = "CANCELLED: "`
- `STATUS_TITLE_PREFIXES` (from the status question after the survey)
- `JOINT_COMMITTEE_FEED_RULE = "each_parent_feed"` (user, 2026-11-11)
- `FEED_SLUG_OVERRIDES` (a body name → stable file slug, so a renamed body keeps its subscription URL)
- `CALENDAR_TIMEZONE = "America/Chicago"`
- `REFRESH_INTERVAL_HOURS` (writes `REFRESH-INTERVAL` and `X-PUBLISHED-TTL`)
- `ATTACHMENT_TYPES_IN_DESCRIPTION` (which `files` links to list)

**Each event:**
- `UID = <meetingId>@chicago-council`
- `DTSTART` in UTC, taken straight from `date`
- `SUMMARY` = body name, with any status prefix
- `LOCATION`
- `DESCRIPTION` = status, `comment`, links to the Notice and Agenda PDFs, the eLMS meeting page link, and video/transcript links if present
- `SEQUENCE` and `LAST-MODIFIED` from `lastPublicationDate`, so calendar apps pick up changes

**Implementation details:**
- The ICS is written with the `icalendar` package, added to `environment.yml`.
- Strip the HTML entities seen in the data (`&amp;` in status) with `html.unescape`. Only decoding happens; no other cleaning.
- **Output:**
  - `docs/calendar/all.ics`
  - `docs/calendar/city-council.ics`
  - `docs/calendar/<committee-slug>.ics`
  - `docs/calendar/feeds.json`: the list of feeds, slug, body, event count and Google calendar ID if any, for the web page to read
- The script reports a per-feed event count and the totals it dropped, with reasons, so every exclusion is visible.

**Subscribe page:**
- A small `docs/calendar/index.html` lists every feed.
- Each feed has a "Copy URL" button, a `webcal://` link (Apple/Outlook), and an "Add to Google Calendar" link: `https://calendar.google.com/calendar/r?cid=<webcal or google id>`.
- Link it from the dashboard footer (`docs/dashboard/app.js`) and the README. It moves onto the landing page when plan 07 is done.

## Phase C: workflow
`.github/workflows/update-data.yml`:
- Change the cron from `0 9 * * 1,4` to every weekday: `0 9 * * 1-5`.
- After `fetch_elms.py update`, add a step `python -u scripts/build_calendar.py build`. Use if/else, never `exit` (see commit 4b46df4).
- Commit step: `git add docs/data docs/calendar`. The commit condition also has to fire when only the calendar changed. To do that, `build_calendar.py` writes `calendar_changed` into its own small result file (or `data/check/result.json` gets a new key). The code compares feeds without `DTSTAMP`, so an unchanged calendar does not cause a daily commit.
- Five runs a week instead of two raises eLMS requests. That is about 221 requests per run under `RATE_LIMIT_FLOOR`; report the real number after the first run.
- **Depends on** the open TODO check: does a push by the bot trigger the Pages build? If not, add a `workflow_dispatch` of `pages-build-deployment`, or a deploy step.

## Phase D: Google Calendar mirror (needs user setup first)
**User steps, which I can't do:**
1. Create a Google Cloud project, enable the Calendar API, and create a service account with a JSON key.
2. Add the key as the GitHub secret `GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON`.

**Then `scripts/sync_google_calendar.py`:**
- Creates one public calendar per feed if it doesn't exist (IDs stored in `docs/calendar/feeds.json`) and makes it public-read.
- Upserts events, using the `meetingId` (in hex) as the event id so it stays stable.
- Changes cancelled events in place and never deletes them, per the cancelled-meetings decision.
- New dependency: `google-api-python-client` + `google-auth`, added to `environment.yml` (the user approved new packages).
- Constants: `GOOGLE_SYNC_ENABLED` and a `GOOGLE_CALENDAR_OWNER_EMAIL` to share the calendars with. That email goes in the secret or config the user provides; I don't hard-code it.
- A workflow step runs it only when the secret is present.
- Subscribe page: Google's "Add" link uses the real calendar ID when one exists, and the URL-subscription link otherwise.

## Files
- New: `scripts/build_calendar.py`, `scripts/sync_google_calendar.py` (phase D), `docs/calendar/*`, `plans/10_meetings_calendar.md` (a copy of this plan, added to the `plans/README.md` table)
- Edit: `.github/workflows/update-data.yml`, `docs/dashboard/app.js` (footer link), `README.md`, `TODO.md`, `environment.yml` (phase D only)
- Reuse: `fetch_elms.py` `fetch_lists()` output, `TERM_START_DATE`, the `write_json` pattern (temp file, then replace), and the constants-block style

## Verification
1. `python -u scripts/build_calendar.py survey`: the user reviews the output (including how joint committees were parsed) and answers the status question.
2. `build`. Then:
   - Validate each `.ics` with `python -c "import icalendar"` in a scratch env, or with https://icalendar.org/validator.html (the user pastes it, since that sends data out).
   - Hand-check 3 events against the eLMS site (one future, one cancelled, one joint committee).
3. Open `docs/calendar/index.html` locally. After pushing, subscribe in Google Calendar to `all.ics` and one committee feed, and confirm the events and toggling work.
4. Run the workflow by hand (`workflow_dispatch`). Check that the calendar commit happens only when there is a change, and that the Pages URL serves the new file.
5. Phase D: dry-run mode prints the planned inserts and updates, then one real sync to a test calendar, then all.
6. End of session: README line, TODO ticks, `sessions/<date>_calendar_handoff.md`.
