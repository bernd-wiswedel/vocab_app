# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"WortSpaß" — a small Flask app for practicing Latin and English vocabulary, with a
spaced-repetition level system. Vocabulary and progress live in Google Sheets — one spreadsheet
per learner, all copies of the same template; the app has no database of its own. Learners
(name, spreadsheet ID) are configured in the committed `configuration.ini`, never in code;
passwords come from `LOGIN_PASSWORD_<NAME>` env vars (`config.py`). `VOCAB_APP_CONFIG` can
replace the file with inline INI text — the tests use that. The learner is picked on the login
page and stored in `session['user']`. UI text, column names, and form values are German (`Richtig`/`Falsch`,
`Latein`/`Englisch`, `Fremdsprache`/`Deutsch`/`Zusatz`/`Kategorie`/`Sprache`).

## Commands

```bash
source venv/bin/activate                 # Python 3.13+ required
pip install -r requirements.txt -r requirements-dev.txt

python app.py                            # dev server on 0.0.0.0:5000

pytest -m "not slow and not browser"     # the normal test run (CI runs this)
pytest -m browser                        # the round in a real browser (CI runs this too)
pytest -m sheets                         # against the real Google Sheet — run by hand
pytest tests/test_level.py::TestLevelSystem::test_is_expired_respects_max_days  # single test
pytest --cov=level --cov=google_sheet_io --cov=app --cov-report=term-missing -m "not slow and not browser"
./run_tests.sh help                      # wrapper with presets (fast/unit/app/coverage/...)
```

The markers matter. `browser` drives headless Chrome through Playwright and is the only cover the
round's JavaScript has; it skips without a browser. `sheets` talks to the real Sheets API and is
the only cover the Google boundary has — tab names, gids, the A:C layout, `values.batchUpdate`,
auth; it skips without credentials.

**Please run `pytest -m sheets` by hand after touching `google_sheet_io.py` or anything about the
sheet layout.** It is deliberately not automated: it needs the service-account key, which is not
worth handing to CI, and it writes to a shared fixture spreadsheet. It takes about ten seconds and
puts the sheet back as it found it.

Dependency helpers (mirroring the weekly GitHub Actions jobs): `python check_dependencies.py`,
`python update_dependencies.py [--security-only|--interactive]`, `python check_python_version.py`.

## Architecture

Three modules, strictly layered: `level.py` (no I/O) ← `google_sheet_io.py` ← `app.py`, plus
`config.py` (learner registry `LEARNERS`, loaded once at import) which the latter two read.

**`level.py`** — the spaced-repetition engine. `LevelSystem.LEVELS` is an ordered list
Red-1 → Red-2 → Red-3 → Red-4 → Yellow-1 → Yellow-2 → Green, each with `min_days` (earliest retest)
and `max_days` (after which the term expires back to Red-1). `Urgency` sorts *ascending* = most
urgent first, by `days_until_expiry` then by higher level. Two sentinels encode "not selectable":
`NOT_EXPIRED_LOW_URGENCY` (too soon to retest — filtered out of tests entirely) and
`RED_1_LOW_URGENCY` (Red-1, always testable but lowest priority). `process_answer()` is the single
place level transitions happen: wrong → Red-1; expired → Red-1; correct and past `min_days` →
next level; correct but too soon → same level, date refreshed.

**`google_sheet_io.py`** — data layer plus the Google Sheets boundary. `UserSheet` holds one
learner's spreadsheet ID and derives the CSV URLs and score-tab names (`Scores <Sprache> (<Name>)`);
`fetch_data(user_name)` and `write_scores_to_sheet(items, language, user_name)` require the
learner — there is deliberately no default, because the worst failure of this app is silently
touching the wrong child's sheet. Reads use two different mechanisms:
- *Vocabulary* comes from public CSV export URLs (`.../export?format=csv&gid=...`, gid 0 = Latein,
  897548588 = Englisch — identical in every learner's copy), no auth. The first data row is skipped,
  blank `Fremdsprache` rows dropped, and a blank `Kategorie` inherits the previous row's value
  (categories are only written once per lesson block in the sheet).
- *Scores* use the authenticated Sheets API v4 against two score tabs, and writing scores
  (`write_scores_to_sheet`) is the app's only mutation: it reads columns A:C, maps term → row, and
  sends one `values.batchUpdate` per language, updating existing rows or appending new ones.

`fetch_data()` joins the two into a `VocabularyDatabase` — an `OrderedDict` mapping
`VocabularyTerm` → `VocabularyScore` that preserves sheet order (the UI relies on this; categories
are just reversed for the dropdown). Two sharp edges: `VocabularyTerm.__hash__` covers all five
fields, so any lookup must reconstruct the term exactly; and the score map is keyed by the term
string alone across both languages, so identical Latin and English terms share a score row.

**`app.py`** — routes, session state, and rendering. There is no persistence layer: the whole
`VocabularyDatabase` is pickled into the Flask filesystem session (10 h lifetime) at login and
re-fetched on `/reload_data`. `get_vocab_data()` raises if it is missing. `current_user()` reads
`session['user']`; every call into the sheet layer goes through it, and `/reload_data` must carry
it across its `session.clear()`. `is_authenticated()` also requires `session['user']` to be a
configured learner, so a stale or user-less session is simply logged out. Passwords are per
learner (`LOGIN_PASSWORDS`, `None` = guest-only); a login POST without a valid `user` is rejected.

`SESSION_REFRESH_EACH_REQUEST` is off, so the session is written only by requests that changed
it. That is deliberate: Flask-Session writes the whole session back from the snapshot the request
read, so with it on, any request — a stylesheet, a favicon — could undo a concurrent one that did
change something. The cost is that a route mutating data *inside* the session (`test_data`
entries, the `VocabularyDatabase`) has to set `session.modified = True` itself, because that
mutation is invisible from the outside; `/finish_test` and `/write_scores` do.

The session directory is `FLASK_SESSION_DIR`, defaulting to `<tempdir>/flask_session` where
`tempdir` honors `TMPDIR` — that is what lets the app and the tests run inside a sandbox whose
`/tmp` is read-only. `Session(app)` binds the directory at import time, so it can only be changed
through the env var *before* `app` is imported (conftest does this), not via `app.config`.

Credentials resolve in this order: `GOOGLE_SERVICE_ACCOUNT_JSON` env var (production) →
`keys/vocab-app-*.json` (local, gitignored).

### Test-round state machine

A test is three session keys, and most bugs in this area come from treating them
independently:

- `test_data` — flat list of dicts (built by `_new_test_data` from `(term, score)` tuples), each
  carrying `test_result` ∈ `correct`/`wrong`/`skipped`, initialized to `skipped`. Its
  `score_status`/`score_date` are the level the term had when the test started (or was last
  saved, see below); answering does not move them.
- `order` — list of *indices into `test_data`* for the current round, shuffled. Non-empty exactly
  while a round is in progress (`_begin_round` / `_end_round`). `/test_errors` rebuilds it from
  the wrong and skipped indices (wrong first) instead of building a new `test_data`.
- `round_id` — random token set together with `order`. The browser has to echo it, so a stale tab
  cannot report positions against a different round.

The browser runs the round. `GET /test` embeds every term of `order` as JSON in `#round-data`
(keys `term`/`translation`/`comment`/`language`/`result`, plus `labels` from
`_get_language_labels()` for both directions and `base` counts of the terms outside the round)
and one pre-rendered `_status_display.html` block per position. The script in
`templates/test.html` does reveal, skip, switch-direction and grading in memory and keeps its
cursor in `sessionStorage`, so a reload resumes. It reports once: `POST /finish_test` with
`round_id` and `answers`, a JSON list of `{"position": <index into the round>, "answer":
"Richtig"|"Falsch"}`. The server maps positions through `order`, sets `test_result`, empties
`order` and redirects to `/review`. "Auswertung" posts the answers so far the same way.

Levels move only when saving. `_projected_score()` runs `LevelSystem.process_answer` on the
original level and the final `test_result`; `/review` shows that projection, `/write_scores`
writes it and then copies it into `test_data` and the `VocabularyDatabase` and flags the item
`saved`, so a second save writes nothing and a later projection starts from what the sheet now
says. `/finish_test` clears `saved` when a term is answered again.

A wrong answer is sticky: `/finish_test` will not overwrite a `wrong` result with a `correct` one,
so getting a term right on the retest round does not undo the miss. Saving lifts that — the sheet
records the miss, and from there the term can be earned back.

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
- Selected rows travel through forms as indices, never as term strings: `/test_selected` gets
  comma-separated indices into the practice page's row list and re-derives that list with
  `_practice_rows()` from the `language` and `categories` fields the page carries along;
  `/write_scores` gets indices into `test_data`; `/finish_test` gets positions into the round.

## Deployment

Koyeb/Heroku-style: `Procfile` runs `gunicorn --bind :$PORT app:app`, `.python-version` pins the
Python minor version (`3.13`, the newest Koyeb offers; patch releases float). Env vars:
`FLASK_SECRET_KEY`, `LOGIN_PASSWORD_<NAME>` for every learner in
`configuration.ini`, `GOOGLE_SERVICE_ACCOUNT_JSON`; optional `VOCAB_APP_CONFIG` and
`FLASK_SESSION_DIR`. The service account must be shared on every learner's spreadsheet. Locally,
`python app.py` alone gives guest-only logins — export the password vars for password logins.

Tests never see the real learners: conftest sets `VOCAB_APP_CONFIG` to two made-up ones (Alice,
Bob) before importing `app`.
