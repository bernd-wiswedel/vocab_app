# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Jakobs WortSpaß" — a small Flask app for practicing Latin and English vocabulary, with a
spaced-repetition level system. Vocabulary and progress both live in one Google Sheet; the app has
no database of its own. UI text, column names, and form values are German (`Richtig`/`Falsch`,
`Latein`/`Englisch`, `Fremdsprache`/`Deutsch`/`Zusatz`/`Kategorie`/`Sprache`).

## Commands

```bash
source venv/bin/activate                 # Python 3.12+ required
pip install -r requirements.txt -r requirements-dev.txt

python app.py                            # dev server on 0.0.0.0:5000

pytest -m "not slow"                     # the normal test run (CI runs this)
pytest tests/test_level.py::TestLevelSystem::test_is_expired_respects_max_days  # single test
pytest --cov=level --cov=google_sheet_io --cov=app --cov-report=term-missing -m "not slow"
./run_tests.sh help                      # wrapper with presets (fast/unit/app/coverage/...)
```

`-m "not slow"` matters: the one `@pytest.mark.slow` test (`test_fetch_data_real_sheets`) calls the
live Google Sheets API and needs real service-account credentials. Everything else is mocked.

Dependency helpers (mirroring the weekly GitHub Actions jobs): `python check_dependencies.py`,
`python update_dependencies.py [--security-only|--interactive]`, `python check_python_version.py`.

## Architecture

Three modules, strictly layered: `level.py` (no I/O) ← `google_sheet_io.py` ← `app.py`.

**`level.py`** — the spaced-repetition engine. `LevelSystem.LEVELS` is an ordered list
Red-1 → Red-2 → Red-3 → Red-4 → Yellow-1 → Yellow-2 → Green, each with `min_days` (earliest retest)
and `max_days` (after which the term expires back to Red-1). `Urgency` sorts *ascending* = most
urgent first, by `days_until_expiry` then by higher level. Two sentinels encode "not selectable":
`NOT_EXPIRED_LOW_URGENCY` (too soon to retest — filtered out of tests entirely) and
`RED_1_LOW_URGENCY` (Red-1, always testable but lowest priority). `process_answer()` is the single
place level transitions happen: wrong → Red-1; expired → Red-1; correct and past `min_days` →
next level; correct but too soon → same level, date refreshed.

**`google_sheet_io.py`** — data layer plus the Google Sheets boundary. Reads use two different
mechanisms:
- *Vocabulary* comes from public CSV export URLs (`.../export?format=csv&gid=...`, gid 0 = Latein,
  897548588 = Englisch), no auth. The first data row is skipped, blank `Fremdsprache` rows dropped,
  and a blank `Kategorie` inherits the previous row's value (categories are only written once per
  lesson block in the sheet).
- *Scores* use the authenticated Sheets API v4 against two score tabs, and writing scores
  (`write_scores_to_sheet`) is the app's only mutation: it reads columns A:C, maps term → row, and
  sends one `values.batchUpdate` per language, updating existing rows or appending new ones.

`fetch_data()` joins the two into a `VocabularyDatabase` — an `OrderedDict` mapping
`VocabularyTerm` → `VocabularyScore` that preserves sheet order (the UI relies on this; categories
are just reversed for the dropdown). Two sharp edges: `VocabularyTerm.__hash__` covers all five
fields, so any lookup must reconstruct the term exactly; and the score map is keyed by the term
string alone across both languages, so identical Latin and English terms share a score row.

**`app.py`** — routes, session state, and rendering. There is no persistence layer: the whole
`VocabularyDatabase` is pickled into the Flask filesystem session (`/tmp/flask_session`, 10 h
lifetime) at login and re-fetched on `/reload_data`. `get_vocab_data()` raises if it is missing.

Credentials resolve in this order: `GOOGLE_SERVICE_ACCOUNT_JSON` env var (production) →
`keys/vocab-app-*.json` (local, gitignored).

### Test-session state machine

A running test is four session keys, and most bugs in this area come from treating them
independently:

- `test_data` — flat list of dicts (converted from `(term, score)` tuples by
  `_convert_vocab_tuples_to_dict`), each carrying `test_result` ∈ `correct`/`wrong`/`skipped`,
  initialized to `skipped`.
- `order` — list of *indices into `test_data`*, shuffled. `/test_errors` rebuilds `order` from the
  wrong and skipped indices (wrong first) instead of building a new `test_data`.
- `current_position` — cursor into `order`, advanced by `/check_answer` and `/skip_question`.
  `_get_position_in_test()` walks forward past already-correct terms and returns `-1` when done,
  which is what redirects to `/review`.
- `show_term` — test direction; `/switch_direction` toggles it and re-renders the *same* question.

Score changes are applied twice on each answer — into `test_data[position]` and into the
`VocabularyDatabase` in the session — and only flushed to Sheets when the user saves from
`/review` (`/write_scores`, grouped per language).

### Guest mode

`session['guest_mode']` is the second axis through almost every route: guests get *all* terms
regardless of urgency (`get_testable_terms(guest_mode=True)`), no status/urgency info in the UI,
and `/write_scores` refuses them. Any change to test selection, stats, or rendering needs to be
considered for both modes.

## Conventions

- Reference columns through the `COL_NAME_*` constants, never the German literals, in Python and
  as template variables (`col_name_term`, …) in Jinja.
- `_get_language_labels()` is the only place that decides which side is "term" vs "translation" for
  a given language and direction — use it rather than branching on language inline.
- `_add_status_info_to_data()` adds `current_status` / `days_until_retest` / `days_until_expire`;
  `templates/_status_display.html` is included by practice, test, and review and expects exactly
  those keys.
- Selected items travel through forms as `term|translation|language`, joined with `||`
  (`/test_selected`, `/write_scores`).

## Deployment

Koyeb/Heroku-style: `Procfile` runs `gunicorn --bind :$PORT app:app`, `runtime.txt` pins the Python
version. Env vars: `FLASK_SECRET_KEY`, `LOGIN_PASSWORD`, `GOOGLE_SERVICE_ACCOUNT_JSON`.
