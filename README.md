# Riyadh Capital Circle — Real-Estate Tracker

Automated build + deploy of the Riyadh land/property price dashboard.

- **Live site:** https://riyadh-capital-circle-tracker.netlify.app
- **Refresh:** GitHub Actions runs hourly (`.github/workflows/refresh-tracker.yml`) — no local computer required.

## What each run does

1. `_tracker_build/collect_land.py` — pulls newest vacant-plot (raw-land) deals from SREM's public API, rotating through districts, deduped into `raw_land_deals.csv`.
2. `_tracker_build/build_tracker.py` — rebuilds `riyadh-real-estate-tracker.html` from MOJ Sales + GASTAT REPI (cloned from the public `civillizard/Saudi-Real-Estate-Data` repo) plus the raw-land feed and local district boundaries.
3. Deploys the HTML to Netlify via the file-digest API (content-type `text/html`).
4. Commits the refreshed data files back to the repo so state persists between runs.

## Secret required

- `NETLIFY_TOKEN` — Netlify personal access token, stored as a GitHub Actions repository secret (Settings -> Secrets and variables -> Actions).

## Notes

- Do **not** hand-edit `riyadh-real-estate-tracker.html`; it is generated.
- The Netlify site id is `ad0b6dda-b6fb-45d5-adfe-1ebb8afaef6f`.
