# Who's still in?

A responsive navy-blue-and-gold website for U.S. Naval Academy graduates to see **self-reported** still-in, out, and unreported shares of each commissioning class's documented commissions, voluntarily report their status, and see current pay-grade percentages among still-in respondents. Nothing is estimated or modeled. The website and its maintained CSV contain only aggregate data, not individual names. Voluntary GitHub submissions and usernames are public. No official logos or crests are used.

**Live site:** https://coltonkawamura.github.io/whos-still-in/

## Enable GitHub Pages

1. Open **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Push to `main`, or run **Actions → Build and deploy GitHub Pages → Run workflow** on `main`.
3. If prompted, allow the `github-pages` environment to deploy from `main`.

The workflow uses Python 3.12 to regenerate and test data, stages only the frontend, aggregate CSV, and derived JSON, and uses `actions/configure-pages`, `actions/upload-pages-artifact`, and `actions/deploy-pages`. The deployment job has `pages: write` and `id-token: write`; repository access is read-only. There is no automatic data scraping.

## Run locally

Requires Python 3.12 (standard library only). There is no package installation or frontend build step. Chart.js 4.5.1 is loaded from jsDelivr; if it is unavailable, the numerical summary and table still work.

```sh
python scripts/build_data.py
python -m unittest discover -s tests -v
python -m http.server 8000
```

Open http://localhost:8000/ rather than opening the HTML as a file, since the app fetches JSON. If Node is installed, check JavaScript syntax with `node --check app.js`.

## Data and methodology

**`data/cohorts.csv` is the single maintained source of truth** for all classes, documented commissioning counts, public-source citations, and accepted voluntary aggregates. There are no separately maintained per-class source files. `scripts/build_data.py` derives the browser's `data/<year>.json` and `data/index.json` deterministically; do not edit the derived JSON by hand. The CSV is also downloadable from the website.

The builder rejects negative counts, invalid dates/years, duplicate metadata/service/report aggregates, invalid report status/rank combinations, and commissioning totals that do not match the service breakdown. No personal identifiers belong in the CSV.

### CSV rows

The CSV header is `year,kind,service,status,rank,community,industry,separation_year,count,as_of,title,url,notes`. Each row has one `kind`; unused fields stay blank. Use a CSV-aware editor or Python's standard `csv` module to preserve quoting of commas in notes.

| Kind | Required fields and meaning |
| --- | --- |
| `class` | One per year: `count` = documented commissioning denominator, `as_of` = date the denominator was compiled, `notes` = coverage caveat. |
| `service` | One per original commissioning service: `service` and integer commissioned `count`. |
| `source` | Public-source `title`, HTTPS `url`, and provenance/role in `notes`; at least one per year. |
| `voluntary` | One aggregate per current/last service + status + rank + community combination + industry + separation year: `service`, `status` (`still_in` or `out`), `rank`, `community`, `industry` (out only), `separation_year` (out only), integer respondent `count`, and aggregate review `as_of` date. |

For `still_in` voluntary rows, `rank` is the current pay grade—`O-1` through `O-10`, `W-1` through `W-5`, `Other`, or `Not disclosed`—and `industry` and `separation_year` must be blank. For `out` rows, `rank` is the **pay grade at separation** (the grade held when leaving the service, same values; earlier reports asked for highest grade held) and `industry` is required: one of `Self-employed / entrepreneur`, `Tech / software`, `Law`, `Civil service / government`, `Defense / aerospace / government contracting`, `Construction / trades / real estate`, `Engineering / manufacturing`, `Finance / banking / insurance`, `Consulting / business services`, `Healthcare / medicine`, `Education / academia`, `Energy / utilities`, `Transportation / aviation / maritime / logistics`, `Sales / marketing / retail`, `Media / entertainment / arts`, `Nonprofit / ministry`, `Politics / public policy`, `Law enforcement / first responder`, `Student / graduate school`, `Not working / retired / caregiving`, `Other`, or `Not disclosed`. `separation_year` is also required on `out` rows: the four-digit year the respondents separated or retired (no earlier than the class year and not in the future) or `Not disclosed`. Out rows accepted before this field existed were set to `2023`. `community` is required on every voluntary row and lists every warfare community the respondents served in, joined with `; ` (semicolon + space) in the canonical order of `COMMUNITIES` in `scripts/build_data.py`—for example `Surface; Foreign Area Officer` for a lateral transfer. Values are `Surface`, `Submarine`, `Aviation`, `Special Warfare (SEAL)`, `Special Operations (EOD)`, `Nuclear Power (Naval Reactors / Instructor)`, `Intelligence`, `Cryptologic Warfare`, `Information Professional`, `Oceanography (METOC)`, `Maritime Space`, `Foreign Area Officer`, `Engineering Duty`, `Aerospace Engineering Duty`, `Aviation Maintenance Duty`, `Human Resources`, `Public Affairs`, `Medical`, `Supply`, `Civil Engineer Corps`, `JAG`, `Chaplain`, `Infantry`, `Artillery`, `Armor / Assault Amphibian`, `Combat Engineer`, `Logistics`, `Communications`, `Military Police`, `Air Command and Control`, `Other service (Army / Air Force / Space Force / Coast Guard)`, `Other`, or `Not disclosed` (which must stand alone). Community names must not contain commas or semicolons. Suggested `service` keys are `USN`, `USMC`, `USA`, `USAF`, `USSF`, `USCG`, and `Not disclosed`. These lists are defined in `scripts/build_data.py` and must match the issue form's options (a test checks the community list). No voluntary rows have been seeded with invented responses.

### Class of 2012 starting point

- Official [Navy/DVIDS captions](https://www.dvidshub.net/image/591206/us-naval-academy-class-2012) report **810 Navy ensigns + 267 Marine Corps second lieutenants = 1,077 documented commissions**.
- [Contemporary CBS reporting](https://www.cbsnews.com/baltimore/news/about-1000-to-graduate-from-naval-academy/) counted **1,099 graduates**. The **22 remaining graduates** are not automatically other U.S. commissions. Local reporting mentions international and other-service graduates, but the full exact breakdown is unresolved here.
- Therefore `commissioned_total` for this input is the **documented subtotal**, not the verified total of all U.S. commissions or the whole graduating class. Other services are **unavailable, not zero**, and are excluded from the denominator.
- Commissioning evidence was available through public search excerpts; direct full-text retrieval failed during implementation. The source input records that verification limitation for follow-up.

### What the site shows

For each class the headline chart shows **reported still in**, **reported out**, and **unreported** (documented commissions minus accepted reports) as shares of `commissioned_total`. Nothing is estimated or extrapolated: unreported classmates are not assumed to be in or out. Earlier versions applied editorial retention assumptions (40% USN / 35% USMC); those assumptions and their outputs have been removed.

The CSV still cites Navy NAVADMIN and Marine Corps MARADMIN promotion messages as public evidence for possible future matching work. No names or counts have been extracted from them, they do not identify USNA class years, and absence from a list is **not** evidence of separation.

## Voluntary submissions and rank distribution

The site links to `.github/ISSUE_TEMPLATE/voluntary-report.yml`, a GitHub issue form for a graduate's own class year, current serving status, current/last service, current pay grade, warfare community or communities (multi-select, for lateral transfers), and status date. Respondents who are out can optionally add their pay grade at separation, year of separation, and a broad current-industry category (for example self-employed, tech, law, civil service, or construction). **Enable Issues in Settings → General → Features**, and merge the form into the default branch so GitHub can display it.

Participation is optional. A GitHub account is required, and usernames and submissions are public—not an anonymous survey. The form requires consent and prohibits names, contact details, units, duty stations, deployment information, and documents. Users should update their existing issue rather than submit duplicates. Do not upload personnel records or someone else's information.

### Automated pull requests (approve to publish)

Each voluntary report becomes a pull request automatically; **approving that PR publishes it**.

1. A user submits the issue form, which applies the `voluntary-report` label. `.github/workflows/voluntary-report-pr.yml` runs `scripts/voluntary_pr.sh sync`, which parses the issue with `scripts/add_report.py`, updates the matching aggregate row in `data/cohorts.csv`, rebuilds the JSON, runs the tests, and opens (or updates) a PR from branch `voluntary-report/issue-<n>`. The PR shows the parsed answers in a table.
2. If the answers are invalid (missing consent, out-of-list value, future date, still-in answer with an out-only field, class without cited class rows, …) the bot comments on the issue instead and closes any existing PR for it. Editing the issue re-runs the check.
3. Review the PR and the issue (consent, plausibility, obvious duplicates), then **approve** the PR. `.github/workflows/voluntary-report-merge.yml` confirms that the reviewer has write access, squash-merges exactly the approved commit, dispatches the Pages deploy, comments on the issue with the counted answers, labels it `counted`, closes it, and rebuilds every other open report PR on the new `main` so they still merge cleanly. Merging a report PR by hand also records it, and the normal push-to-`main` deploy runs. To reject a report, close the PR.
4. **Updates:** when a counted issue is edited, the bot opens an *Update* PR that subtracts the previously counted answers (read only from its own `github-actions[bot]` comment) and adds the new ones; if the answers are unchanged, no PR is opened. A second issue from an account that already has a `counted` report gets a comment asking the user to edit the original instead, and it is not counted.

No usernames or issue numbers are written to the CSV or JSON. Issue text is untrusted: the workflows check out scripts from `main`, read the body into a file, and only accept allow-listed values; it is never interpolated into a shell command.

**One-time setup:** in **Settings → Actions → General → Workflow permissions**, check **Allow GitHub Actions to create and approve pull requests** (the PRs are opened by `github-actions[bot]`, so you can approve them yourself). The workflows create the `voluntary-report` and `counted` labels the first time they run; create `voluntary-report` yourself before the first submission so the form can apply it. If branch protection on `main` requires status checks or blocks `github-actions[bot]` from merging, approval will not merge automatically; merge the approved PR by hand instead. PRs opened and branches pushed with `GITHUB_TOKEN` do not trigger other workflows, which is why the sync step runs the tests itself. To re-process an issue manually, run **Actions → Voluntary report pull request → Run workflow** with its number.

If GitHub denies PR creation because that setting is disabled, sync saves the validated branch, emits a workflow warning, and posts a prefilled **open the prepared pull request** link on the issue (updating the same notice on later runs). The report is **not counted** until the PR is reviewed and merged. A maintainer can use that link to create the PR manually, or enable the setting and re-process the issue. If an organization policy locks the setting, an organization administrator must enable it. Other PR-creation errors still fail the workflow.

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

The helper checks consent boxes, status/service, rank/industry consistency with status, the community list, a non-future status date, and that the class already has cited class rows; it then increments (or with `--subtract`, decrements and removes empty) the matching aggregate row, sets its `as_of` to the review date (`--as-of`, default today), and validates the whole CSV before writing. It never writes usernames or issue numbers. The rules it applies are:

1. Review a voluntary issue for consent, supported class year, plausible status/pay grade, and a valid non-future date. Ask the submitter to correct invalid or contradictory answers; do not count them yet. Reports remain **unverified self-reports** even after review.
2. Check that account's previous accepted submissions/updates in the issue history. Count only the latest accepted response once. When status, service, or grade changes, decrement its previous aggregate before incrementing the new one. Do not add GitHub usernames or issue identifiers to the CSV.
3. Add or adjust the applicable `voluntary` aggregate row in `data/cohorts.csv`, using the aggregate review date in `as_of`. Use `Not disclosed` for respondents who select no community, for still-in respondents who omit their grade, and use `Not disclosed` for out respondents who omit their pay grade at separation, year of separation, or industry (the form's “Not disclosed / not applicable” or a blank optional answer). Current/last service in these rows is separate from original commissioning service in `service` rows.
4. Rebuild and test, then commit the CSV and derived JSON. A push to `main` deploys the update. Unsupported classes need cited class/service/source rows before reports can be published.

The rank denominator is **all accepted still-in respondents**, including `Not disclosed`/`Other`, not commissioned graduates or all survey respondents. For example, two O-4s, one O-5, and one undisclosed rank yield 50%, 25%, and 25%; out reports do not enter that calculation. Rounding may prevent exactly 100%. Zero responses show no percentages, not fabricated zero-percent rank estimates.

The site also shows **pay grade at separation** and **current industry** among out respondents. Their denominator is **all accepted out respondents**, including `Not disclosed`; still-in reports do not enter those calculations. For example, two O-3s in tech, one O-4 in law, and one undisclosed grade/industry yield O-3 50%, O-4 25%, Not disclosed 25% and Tech 50%, Law 25%, Not disclosed 25%.

The **Explore voluntary responses** panel uses the aggregate `responses` rows in each class JSON to filter by any combination of status, service, community, current pay grade (still in), pay grade at separation (out), year of separation (out), and industry; break down by any of those; split bars by a second dimension; and show counts or percentages. Clicking a bar drills into that group. Grade and industry breakdowns use only the respondents they apply to as the denominator. Community shares use all filtered respondents as the denominator and count a respondent once in each community reported, so they can total more than 100%.

Respondents are self-selected and may be inaccurate or stale; their rank distribution is **not representative of the whole class**. Respondent aggregates have their own date, separate from the class denominator's date.

## Add or update a class

1. Add a new year's `class`, `service`, and `source` rows to `data/cohorts.csv`, following the existing 2012 rows.
2. Supply cited commissioning totals, the compilation date, and coverage caveats. Do not treat unknown other-service counts as zero, guess a total, or invent voluntary reports.
3. Run `python scripts/build_data.py` and `python -m unittest discover -s tests -v`.
4. Commit the CSV and generated class JSON/index. The dropdown reads `data/index.json`; no HTML/JavaScript change is needed. Class of 2012 is selected by default when available.

Additional commissioning service keys can be used in `service` rows; the UI falls back to the key as its label. Only aggregate data belongs in the CSV—do not add rosters or individual identifiers.

## Disclaimer

Unofficial and self-reported; could be wrong or out of date. Not affiliated with or endorsed by the U.S. Naval Academy, the Department of the Navy, or the DoD.
