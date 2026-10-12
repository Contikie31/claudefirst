# Acquisitions Tracker

Collects recent company acquisitions, mergers, take-privates and PE buyouts from public news feeds and SEC filings, classifies them, and shows them on a filterable web page that works on a phone.

## What it does

- Fetches ~23 public RSS/Atom feeds every hour (Google News queries for US/UK/EU/India/Australia, TechCrunch M&A, GlobeNewswire, PR Newswire, SEC EDGAR tender offers / merger proxies / going-private filings). Feeds are listed in `acqtracker/sources.py`.
- Drops non-deal items ("customer acquisition", "buy rating", buybacks).
- Extracts acquirer, target, deal value (converted to USD at fixed approximate rates), deal type, status, sectors, region, and private-equity involvement.
- Merges the same deal reported by several outlets into one record.
- Keeps 120 days of history.

Filters: search text, sector (Technology, Digital & Media, Private Equity, Financial Services, Healthcare, Industrials, Energy, Consumer & Retail, Telecom, Real Estate, Other), deal type, status, region, period, minimum value, news vs. SEC filings, sort, and CSV export. Filter state is kept in the URL, so a filtered view can be bookmarked.

Limitations: classification is keyword-based, so some records will have a missing or wrong acquirer/target or sector. Each record links to its source.

## Setup (GitHub Pages, no server needed)

1. Merge this code into the `main` branch.
2. Repository **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions** tab → "Update deals and publish site" → **Run workflow** (the first run; it then runs hourly).
4. Open `https://<your-username>.github.io/<repo-name>/` on your phone. In Safari: Share → Add to Home Screen.

The repository must be public for free GitHub Pages.

## Run locally (optional)

Requires Python 3.10+, no extra packages.

```
python -m acqtracker fetch     # fetch feeds into web/data/deals.json
python -m acqtracker serve     # http://localhost:8000, with a "Refresh now" button
python -m unittest discover -s tests
```
