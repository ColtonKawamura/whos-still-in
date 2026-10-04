# Who's still in?

A responsive navy-blue-and-gold website for U.S. Naval Academy graduates to explore **estimated** still-serving versus out percentages by commissioning class, voluntarily report their status, and see current pay-grade percentages among still-in respondents. The website and its maintained CSV contain only aggregate data, not individual names. Voluntary GitHub submissions and usernames are public. No official logos or crests are used.

**Live site:** https://coltonkawamura.github.io/whos-still-in/

## Enable GitHub Pages

1. Open **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Push to `main`, or run **Actions → Build and deploy GitHub Pages → Run workflow** on `main`.
3. If prompted, allow the `github-pages` environment to deploy from `main`.

The workflow uses Python 3.12 to regenerate and test data, stages only the frontend, aggregate CSV, and derived JSON, and uses `actions/configure-pages`, `actions/upload-pages-artifact`, and `actions/deploy-pages`. The deployment job has `pages: write` and `id-token: write`; repository access is read-only. There is no automatic data scraping or scheduled date advancement: rebuilding does not make an old estimate current.

## Run locally

Requires Python 3.12 (standard library only). There is no package installation or frontend build step. Chart.js 4.5.1 is loaded from jsDelivr; if it is unavailable, the numerical summary and table still work.

```sh
python scripts/build_data.py
python -m unittest discover -s tests -v
python -m http.server 8000
```

Open http://localhost:8000/ rather than opening the HTML as a file, since the app fetches JSON. If Node is installed, check JavaScript syntax with `node --check app.js`.

## Data and methodology

**`data/cohorts.csv` is the single maintained source of truth** for all classes, public-source citations, modeling assumptions, and accepted voluntary aggregates. There are no separately maintained per-class source files. `scripts/build_data.py` derives the browser's `data/<year>.json` and `data/index.json` deterministically; do not edit the derived JSON by hand. The CSV is also downloadable from the website.

The builder rejects invalid rates, negative counts, invalid dates/years, duplicate metadata/service/report aggregates, invalid report status/rank combinations, and commissioning totals that do not match the service breakdown. No personal identifiers belong in the CSV.

### CSV rows

The CSV header is `year,kind,service,status,rank,community,industry,count,retention_rate,as_of,title,url,notes`. Each row has one `kind`; unused fields stay blank. Use a CSV-aware editor or Python's standard `csv` module to preserve quoting of commas in notes.

| Kind | Required fields and meaning |
| --- | --- |
| `class` | One per year: `count` = modeled commissioning denominator, `as_of` = model reference date, `title` = confidence label, `notes` = coverage caveat. |
| `service` | One per original commissioning service: `service`, integer commissioned `count`, and explicit `retention_rate` assumption (0–1). |
| `method` | One per year: `notes` explaining derivation and limitations. |
| `source` | Public-source `title`, HTTPS `url`, and provenance/role in `notes`; at least one per year. |
| `voluntary` | One aggregate per current/last service + status + rank + community combination + industry: `service`, `status` (`still_in` or `out`), `rank`, `community`, `industry` (out only), integer respondent `count`, and aggregate review `as_of` date. |

For `still_in` voluntary rows, `rank` is the current pay grade—`O-1` through `O-10`, `W-1` through `W-5`, `Other`, or `Not disclosed`—and `industry` must be blank. For `out` rows, `rank` is the **pay grade at separation** (the grade held when leaving the service, same values; earlier reports asked for highest grade held) and `industry` is required: one of `Self-employed / entrepreneur`, `Tech / software`, `Law`, `Civil service / government`, `Defense / aerospace / government contracting`, `Construction / trades / real estate`, `Engineering / manufacturing`, `Finance / banking / insurance`, `Consulting / business services`, `Healthcare / medicine`, `Education / academia`, `Energy / utilities`, `Transportation / aviation / maritime / logistics`, `Sales / marketing / retail`, `Media / entertainment / arts`, `Nonprofit / ministry`, `Politics / public policy`, `Law enforcement / first responder`, `Student / graduate school`, `Not working / retired / caregiving`, `Other`, or `Not disclosed`. `community` is required on every voluntary row and lists every warfare community the respondents served in, joined with `; ` (semicolon + space) in the canonical order of `COMMUNITIES` in `scripts/build_data.py`—for example `Surface; Foreign Area Officer` for a lateral transfer. Values are `Surface`, `Submarine`, `Aviation`, `Special Warfare (SEAL)`, `Special Operations (EOD)`, `Nuclear Power (Naval Reactors / Instructor)`, `Intelligence`, `Cryptologic Warfare`, `Information Professional`, `Oceanography (METOC)`, `Maritime Space`, `Foreign Area Officer`, `Engineering Duty`, `Aerospace Engineering Duty`, `Aviation Maintenance Duty`, `Human Resources`, `Public Affairs`, `Medical`, `Supply`, `Civil Engineer Corps`, `JAG`, `Chaplain`, `Infantry`, `Artillery`, `Armor / Assault Amphibian`, `Combat Engineer`, `Logistics`, `Communications`, `Military Police`, `Air Command and Control`, `Other service (Army / Air Force / Space Force / Coast Guard)`, `Other`, or `Not disclosed` (which must stand alone). Community names must not contain commas or semicolons. Suggested `service` keys are `USN`, `USMC`, `USA`, `USAF`, `USSF`, `USCG`, and `Not disclosed`. These lists are defined in `scripts/build_data.py` and must match the issue form's options (a test checks the community list). No voluntary rows have been seeded with invented responses; the initial respondent panel correctly displays “no reports.”

### Class of 2012 starting point

- Official [Navy/DVIDS captions](https://www.dvidshub.net/image/591206/us-naval-academy-class-2012) report **810 Navy ensigns + 267 Marine Corps second lieutenants = 1,077 documented commissions**.
- [Contemporary CBS reporting](https://www.cbsnews.com/baltimore/news/about-1000-to-graduate-from-naval-academy/) counted **1,099 graduates**. The **22 remaining graduates** are not automatically other U.S. commissions. Local reporting mentions international and other-service graduates, but the full exact breakdown is unresolved here.
- Therefore `commissioned_total` for this input is the **documented subtotal modeled**, not the verified total of all U.S. commissions or the whole graduating class. Other services are **unavailable, not zero**, and are excluded from the percentages. The UI prominently discloses this partial coverage.
- Assumed retention of **40% USN / 35% USMC** produces **417 modeled still in / 660 modeled out (38.7% / 61.3%)**. These are editorial scenarios, not rates extracted from the linked studies. Changing both assumptions to 30% or 50% would change the result accordingly; these are not statistical uncertainty bounds.
- Commissioning evidence was available through public search excerpts; direct full-text retrieval failed during implementation. The source input records that verification limitation for follow-up.

**The initial 2012 result is a low-confidence illustrative model, not an observed retention rate.** Public commissioning counts can be documented; a current, complete list of serving graduates has not been established. The service-specific assumptions are editorial modeling choices, not published USNA retention statistics. The model date is not a verified personnel-status date. Do not use this site to claim that a specific percentage of the class is known to be serving.

### Best available public-source approach

- **Denominator:** USNA class profiles and commissioning press releases, including official military reporting archived on DVIDS. Distinguish all graduates from those commissioned into U.S. services; exclude international graduates and non-commissioning graduates. Preserve Navy/Marine Corps/other service counts where published.
- **Serving evidence:** [MyNavy HR NAVADMIN archive](https://www.mynavyhr.navy.mil/References/Messages/NAVADMIN-2025/), including the [official NAVADMIN 202/25 active-duty promotion message](https://www.mynavyhr.navy.mil/Portals/55/Messages/NAVADMIN/NAV2025/NAV25202.pdf), and Marine Corps **MARADMIN** officer promotion results. These publish officer promotion events/grades, not USNA class years or complete cohort retention. The 2012 commissioning cohort broadly reached first O-4 consideration around the ten-year mark, but timing varies by service, specialty, component, and promotion zone. A board fiscal year is not a commissioning year and does not prove USNA affiliation. The CSV cites these public sources without republishing names or claiming their grade totals represent this class.
- **Necessary matching work:** verify both academy class and commissioning year before counting a promotion-list entry; distinguish selection from actual promotion; deduplicate repeated listings; account for reserves, transfers, and subsequent exits. Recent promotion is evidence at that date, not a guarantee of current service. Absence from a list is **not** evidence of separation. No matching or promotion-list extraction has yet been performed for this initial model.
- **Fallback/cross-check:** DoD actuarial officer continuation tables give service-wide context, not a USNA-specific cohort count. Annual continuation probabilities, survival after the five-year minimum obligation, and cumulative retention roughly fourteen years after commissioning are not interchangeable. A later evidence-based model should calculate cohort survival from applicable longitudinal rates and document coverage rather than substitute a single annual rate.
- **Current calculation:** multiply each commissioning service's count by its documented assumed retention rate, round to the nearest whole officer (half up), and sum. “Out” is the remaining denominator; percentages are rounded to one decimal and complement to 100%. The residual may include deaths and other losses, not just voluntary separation or retirement. The intended still-serving scope includes active and reserve service in any U.S. service, but the current model does not verify that coverage.

The website's expandable **How does this work?** section explains these limitations. Public source links and their roles are documented in the CSV; source titles and URLs also appear in the derived JSON and UI. Direct MyNavy HR retrieval failed during implementation; the source's coverage was checked through web-search-accessible official content, not independently retrieved full text.

## Voluntary submissions and rank distribution

The site links to `.github/ISSUE_TEMPLATE/voluntary-report.yml`, a GitHub issue form for a graduate's own class year, current serving status, current/last service, current pay grade, warfare community or communities (multi-select, for lateral transfers), and status date. Respondents who are out can optionally add their pay grade at separation and a broad current-industry category (for example self-employed, tech, law, civil service, or construction). **Enable Issues in Settings → General → Features**, and merge the form into the default branch so GitHub can display it.

Participation is optional. A GitHub account is required, and usernames and submissions are public—not an anonymous survey. The form requires consent and prohibits names, contact details, units, duty stations, deployment information, and documents. Users should update their existing issue rather than submit duplicates. Do not upload personnel records or someone else's information.

### Automated pull requests (approve to publish)

Each voluntary report becomes a pull request automatically; **approving that PR publishes it**.

1. A user submits the issue form, which applies the `voluntary-report` label. `.github/workflows/voluntary-report-pr.yml` runs `scripts/voluntary_pr.sh sync`, which parses the issue with `scripts/add_report.py`, updates the matching aggregate row in `data/cohorts.csv`, rebuilds the JSON, runs the tests, and opens (or updates) a PR from branch `voluntary-report/issue-<n>`. The PR shows the parsed answers in a table.
2. If the answers are invalid (missing consent, out-of-list value, future date, still-in answer with an out-only field, class without model rows, …) the bot comments on the issue instead and closes any existing PR for it. Editing the issue re-runs the check.
3. Review the PR and the issue (consent, plausibility, obvious duplicates), then **approve** the PR. `.github/workflows/voluntary-report-merge.yml` confirms that the reviewer has write access, squash-merges exactly the approved commit, dispatches the Pages deploy, comments on the issue with the counted answers, labels it `counted`, closes it, and rebuilds every other open report PR on the new `main` so they still merge cleanly. Merging a report PR by hand also records it, and the normal push-to-`main` deploy runs. To reject a report, close the PR.
4. **Updates:** when a counted issue is edited, the bot opens an *Update* PR that subtracts the previously counted answers (read only from its own `github-actions[bot]` comment) and adds the new ones; if the answers are unchanged, no PR is opened. A second issue from an account that already has a `counted` report gets a comment asking the user to edit the original instead, and it is not counted.

No usernames or issue numbers are written to the CSV or JSON. Issue text is untrusted: the workflows check out scripts from `main`, read the body into a file, and only accept allow-listed values; it is never interpolated into a shell command.

**One-time setup:** in **Settings → Actions → General → Workflow permissions**, check **Allow GitHub Actions to create and approve pull requests** (the PRs are opened by `github-actions[bot]`, so you can approve them yourself). The workflows create the `voluntary-report` and `counted` labels the first time they run; create `voluntary-report` yourself before the first submission so the form can apply it. If branch protection on `main` requires status checks or blocks `github-actions[bot]` from merging, approval will not merge automatically; merge the approved PR by hand instead. PRs opened and branches pushed with `GITHUB_TOKEN` do not trigger other workflows, which is why the sync step runs the tests itself. To re-process an issue manually, run **Actions → Voluntary report pull request → Run workflow** with its number.

### Manual update process

`scripts/add_report.py` can also be run locally to turn one issue-form body into the matching aggregate CSV change:

```sh
# Requires the GitHub CLI (or paste the issue body into a file and pass its path).
gh issue view 12 --json body -q .body | python scripts/add_report.py -
# Replace previously counted answers in one step (row JSON from the bot's issue comment):
gh issue view 12 --json body -q .body | python scripts/add_report.py - --previous-json '{"year": "2012", ...}'
# Or remove an old answer from a saved issue body:
python scripts/add_report.py --subtract /tmp/old.md
python scripts/build_data.py && python -m unittest discover -s tests -v
git commit -am "Add voluntary report aggregate" && git push   # or open a PR; merging to main deploys
```

The helper checks consent boxes, status/service, rank/industry consistency with status, the community list, a non-future status date, and that the class already has model rows; it then increments (or with `--subtract`, decrements and removes empty) the matching aggregate row, sets its `as_of` to the review date (`--as-of`, default today), and validates the whole CSV before writing. It never writes usernames or issue numbers. The rules it applies are:

1. Review a voluntary issue for consent, supported class year, plausible status/pay grade, and a valid non-future date. Ask the submitter to correct invalid or contradictory answers; do not count them yet. Reports remain **unverified self-reports** even after review.
2. Check that account's previous accepted submissions/updates in the issue history. Count only the latest accepted response once. When status, service, or grade changes, decrement its previous aggregate before incrementing the new one. Do not add GitHub usernames or issue identifiers to the CSV.
3. Add or adjust the applicable `voluntary` aggregate row in `data/cohorts.csv`, using the aggregate review date in `as_of`. Use `Not disclosed` for respondents who select no community, for still-in respondents who omit their grade, and use `Not disclosed` for out respondents who omit their pay grade at separation or industry (the form's “Not disclosed / not applicable” or a blank optional answer). Current/last service in these rows is separate from original commissioning service in model rows.
4. Rebuild and test, then commit the CSV and derived JSON. A push to `main` deploys the update. Unsupported classes need cited class/service/model rows before reports can be published.

The rank denominator is **all accepted still-in respondents**, including `Not disclosed`/`Other`, not commissioned graduates, modeled still-in counts, or all survey respondents. For example, two O-4s, one O-5, and one undisclosed rank yield 50%, 25%, and 25%; out reports do not enter that calculation. Rounding may prevent exactly 100%. Zero responses show no percentages, not fabricated zero-percent rank estimates.

The site also shows **pay grade at separation** and **current industry** among out respondents. Their denominator is **all accepted out respondents**, including `Not disclosed`; still-in reports do not enter those calculations. For example, two O-3s in tech, one O-4 in law, and one undisclosed grade/industry yield O-3 50%, O-4 25%, Not disclosed 25% and Tech 50%, Law 25%, Not disclosed 25%.

The **Explore voluntary responses** panel uses the aggregate `responses` rows in each class JSON to filter by any combination of status, service, community, current pay grade (still in), pay grade at separation (out), and industry; break down by any of those; split bars by a second dimension; and show counts or percentages. Clicking a bar drills into that group. Grade and industry breakdowns use only the respondents they apply to as the denominator. Community shares use all filtered respondents as the denominator and count a respondent once in each community reported, so they can total more than 100%.

Respondents are self-selected and may be inaccurate or stale; their rank distribution is **not representative of the whole class**. Voluntary counts never silently replace modeled counts. Keep the model reference date unchanged unless the model itself is updated; respondent aggregates have their own date.

## Add or update a class

1. Add a new year's `class`, `service`, `method`, and `source` rows to `data/cohorts.csv`, following the existing 2012 rows.
2. Supply cited commissioning totals, explicit retention assumptions, model reference date, confidence, coverage caveats, and limitations. Do not treat unknown other-service counts as zero, guess a total, or invent voluntary reports.
3. Run `python scripts/build_data.py` and `python -m unittest discover -s tests -v`.
4. Commit the CSV and generated class JSON/index. The dropdown reads `data/index.json`; no HTML/JavaScript change is needed. Class of 2012 is selected by default when available.

Additional commissioning service keys can be used in `service` rows; the UI falls back to the key as its label. Only aggregate data belongs in the CSV—do not add rosters or individual identifiers.

## Disclaimer

This is an unofficial estimate built from public sources and could be wrong or out of date. Not affiliated with or endorsed by the U.S. Naval Academy, the Department of the Navy, or the DoD.
