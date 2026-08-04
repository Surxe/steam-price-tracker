---
name: add-app
description: Search Steam by game/product name and register the chosen app id into the tracker's TRACKED_APP_IDS list. Use when the user runs "/add-app <game name>" or asks to add/track a new Steam game by name.
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

3. **Register the confirmed choice.** Once the user picks, register it, passing
   the exact product name so it is stored as an inline comment:

   ```bash
   .venv/bin/python -m steam_price_tracker.registry add <app_id> --name "<full product name>"
   ```

   This appends to `TRACKED_APP_IDS` in `steam_price_tracker/config.py`. It is
   idempotent: if the id is already present it reports "already registered" and
   changes nothing. Report the outcome to the user.

4. **Offer a first price fetch (optional).** Ask whether to pull an initial
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
  straight to step 3.
- For machine-readable output (e.g. to script a pick), add `--format json` to
  the search command.
