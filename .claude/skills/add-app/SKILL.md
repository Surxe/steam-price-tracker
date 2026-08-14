---
name: add-app
description: Search Steam by game/product name and register the chosen app id into the tracker's tracked-apps file. Use when the user runs "/add-app <game name>" or asks to add/track a new Steam game by name.
---

# add-app

Resolve a game name to a Steam app id and register it for price tracking.

Arguments: the game/product name to search for (everything after `/add-app`).

All commands run from the repo root (`/srv/dev/repos/steam-price-tracker`) using
the project venv (`.venv/bin/python`). The heavy lifting lives in the package —
do not reimplement search or config editing inline.

## Steps

1. **Search.** Run the search CLI with the user's term:

   ```bash
   .venv/bin/python -m steam_price_tracker.search "<game name>" --limit 10
   ```

   It prints a Markdown table of candidates (`#`, App ID, Type, Name). If it
   prints `_No matching apps found._` (exit code 2), tell the user and ask them
   to refine the name — do not guess an id.

2. **Present & ask.** Put the Markdown table directly into chat and ask the user
   to pick one by number or app id. Do not auto-select, even if there is a clear
   top hit — the user confirms. (Note `type`: `app` is a game/software; `dlc`,
   `bundle`, `music` etc. may not be what they want.)

3. **Ask about a price alert (optional).** After they pick, share the app's
   **SteamDB price-history page** so they can review historical lows and pick a
   sensible target before deciding:

   ```
   https://steamdb.info/app/<app_id>/
   ```

   Post that link in chat (e.g. for ARK: `https://steamdb.info/app/2399830/`). Do
   NOT fetch or scrape the page — just provide the link for the user to open.
   Then ask whether they want a price-alert threshold for this app, in USD — e.g.
   "alert me when it's at or below $30". This per-app threshold is the whole point
   of using this over a Steam wishlist. It is optional; if they decline, skip it.

4. **Register the confirmed choice.** The tracked-apps file is **owned by
   my-system** (its source of truth is version-controlled there and deployed to
   `~/.config/steam-price-tracker/` by `install.sh`), so edit that source copy —
   not the tracker repo's gitignored `data/`. Point the registry at it via
   `STEAM_TRACKER_APPS_PATH`. Pass the exact product name; include
   `--threshold <usd>` only if the user gave one:

   ```bash
   APPS=/srv/dev/repos/my-system/users/ethan/.config/steam-price-tracker/tracked_apps.json

   # without an alert
   STEAM_TRACKER_APPS_PATH="$APPS" \
     .venv/bin/python -m steam_price_tracker.registry add <app_id> --name "<full product name>"

   # with an alert threshold in USD
   STEAM_TRACKER_APPS_PATH="$APPS" \
     .venv/bin/python -m steam_price_tracker.registry add <app_id> --name "<full product name>" --threshold <usd>
   ```

   This adds the id (and, if given, its threshold) to the my-system source file.
   It is idempotent: if the id is already present it reports "already registered"
   and changes nothing. Report the outcome. To add or change a threshold later,
   use the same `STEAM_TRACKER_APPS_PATH` prefix with:

   ```bash
   STEAM_TRACKER_APPS_PATH="$APPS" \
     .venv/bin/python -m steam_price_tracker.registry set-threshold <app_id> <usd>
   ```

   Because it edited a my-system source file, **remind the user to commit it in
   my-system and re-run `install.sh`** — that deploys the updated list to
   `~/.config/steam-price-tracker/`, where the refresh service reads it. Until
   then the change is staged in the repo but not live. (Do not commit for them.)

5. **Offer a first price fetch (optional).** Ask whether to pull an initial
   price now. If yes:

   ```bash
   .venv/bin/python -m steam_price_tracker <app_id>
   ```

   This also fetches and stores the product name the first time the app is
   priced.

## Notes

- The Steam search endpoint is US-scoped (`cc=us`), matching the tracker's
  US-only pricing.
- If the user already gave an exact app id (not a name), skip search and go
  straight to the alert question (step 3) and registration (step 4).
- For machine-readable output (e.g. to script a pick), add `--format json` to
  the search command.
