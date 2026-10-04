# Who's still in?

A responsive navy-blue-and-gold website for U.S. Naval Academy graduates to explore **estimated** still-serving versus out percentages by commissioning class. It shows aggregate counts, service breakdowns, a model reference date, confidence, and citations. No official logos or crests are used, and no individual names are published.

**Live site:** https://coltonkawamura.github.io/whos-still-in/

## Enable GitHub Pages

1. Open **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Push to `main`, or run **Actions → Build and deploy GitHub Pages → Run workflow** on `main`.
3. If prompted, allow the `github-pages` environment to deploy from `main`.

The workflow uses Python 3.12 to test and regenerate data, stages only the frontend and aggregate JSON, and uses `actions/configure-pages`, `actions/upload-pages-artifact`, and `actions/deploy-pages`. The deployment job has `pages: write` and `id-token: write`; repository access is read-only. There is no automatic data scraping or scheduled date advancement: rebuilding does not make an old estimate current.

## Run locally

Requires Python 3.12 (standard library only). There is no package installation or frontend build step. Chart.js 4.5.1 is loaded from jsDelivr; if it is unavailable, the numerical summary and table still work.

```sh
python scripts/build_data.py
python -m unittest discover -s tests -v
python -m http.server 8000
```

Open http://localhost:8000/ rather than opening the HTML as a file, since the app fetches JSON. If Node is installed, check JavaScript syntax with `node --check app.js`.

## Data and methodology

`data/sources/2012.json` is the documented input: commissioning totals, explicit per-service retention assumptions, model date, coverage, limitations, and source URLs. `scripts/build_data.py` generates `data/2012.json` and `data/index.json` deterministically. It rejects invalid rates, negative counts, invalid dates/years, duplicate years, and totals that do not match the service breakdown.

### Class of 2012 starting point

- Official [Navy/DVIDS captions](https://www.dvidshub.net/image/591206/us-naval-academy-class-2012) report **810 Navy ensigns + 267 Marine Corps second lieutenants = 1,077 documented commissions**.
- [Contemporary CBS reporting](https://www.cbsnews.com/baltimore/news/about-1000-to-graduate-from-naval-academy/) counted **1,099 graduates**. The **22 remaining graduates** are not automatically other U.S. commissions. Local reporting mentions international and other-service graduates, but the full exact breakdown is unresolved here.
- Therefore `commissioned_total` for this input is the **documented subtotal modeled**, not the verified total of all U.S. commissions or the whole graduating class. Other services are **unavailable, not zero**, and are excluded from the percentages. The UI prominently discloses this partial coverage.
- Assumed retention of **40% USN / 35% USMC** produces **417 modeled still in / 660 modeled out (38.7% / 61.3%)**. These are editorial scenarios, not rates extracted from the linked studies. Changing both assumptions to 30% or 50% would change the result accordingly; these are not statistical uncertainty bounds.
- Commissioning evidence was available through public search excerpts; direct full-text retrieval failed during implementation. The source input records that verification limitation for follow-up.

**The initial 2012 result is a low-confidence illustrative model, not an observed retention rate.** Public commissioning counts can be documented; a current, complete list of serving graduates has not been established. The service-specific assumptions are editorial modeling choices, not published USNA retention statistics. The model date is not a verified personnel-status date. Do not use this site to claim that a specific percentage of the class is known to be serving.

### Best available public-source approach

- **Denominator:** USNA class profiles and commissioning press releases, including official military reporting archived on DVIDS. Distinguish all graduates from those commissioned into U.S. services; exclude international graduates and non-commissioning graduates. Preserve Navy/Marine Corps/other service counts where published.
- **Serving evidence:** Navy **NAVADMIN** and Marine Corps **MARADMIN** officer promotion results, especially O-4/LCDR/major and above. The 2012 commissioning cohort broadly reached first O-4 consideration around the ten-year mark, but timing varies by service, specialty, component, and promotion zone. A board fiscal year is not a commissioning year and does not prove USNA affiliation.
- **Necessary matching work:** verify both academy class and commissioning year before counting a promotion-list entry; distinguish selection from actual promotion; deduplicate repeated listings; account for reserves, transfers, and subsequent exits. Recent promotion is evidence at that date, not a guarantee of current service. Absence from a list is **not** evidence of separation. No matching or promotion-list extraction has yet been performed for this initial model.
- **Fallback/cross-check:** DoD actuarial officer continuation tables give service-wide context, not a USNA-specific cohort count. Annual continuation probabilities, survival after the five-year minimum obligation, and cumulative retention roughly fourteen years after commissioning are not interchangeable. A later evidence-based model should calculate cohort survival from applicable longitudinal rates and document coverage rather than substitute a single annual rate.
- **Current calculation:** multiply each commissioning service's count by its documented assumed retention rate, round to the nearest whole officer (half up), and sum. “Out” is the remaining denominator; percentages are rounded to one decimal and complement to 100%. The residual may include deaths and other losses, not just voluntary separation or retirement. The intended still-serving scope includes active and reserve service in any U.S. service, but the current model does not verify that coverage.

The website's expandable **How does this work?** section explains these limitations. Public source links and their roles are included in the source input and generated JSON.

## Add or update a class

1. Copy `data/sources/2012.json` to `data/sources/<year>.json`.
2. Change `year`, the commissioned total and service counts, model `as_of` date, explicitly justified `assumed_retention_rate` values (0–1), `method`, `confidence`, `coverage_note`, and cited `sources`. Include exclusions, provenance, and limitations in the input documentation. The filename alone does not set the year.
3. Run `python scripts/build_data.py` and `python -m unittest discover -s tests -v`.
4. Commit the source file and generated class JSON/index. The dropdown reads `data/index.json`; no HTML/JavaScript change is needed. Class of 2012 is selected by default when available.

Additional service keys can be used under `by_service`; the UI falls back to the key as its label. Services are original commissioning services, not claimed present-day assignments. Only aggregate source inputs belong in this repository—do not add rosters or individual identifiers.

## Disclaimer

This is an unofficial estimate built from public sources and could be wrong or out of date. Not affiliated with or endorsed by the U.S. Naval Academy, the Department of the Navy, or the DoD.
