# AI Coding Instructions - Jakobs WortSpaß

## Project Overview
Flask-based vocabulary learning app for Latin and English practice. Data is sourced from public Google Sheets and cached in Flask session. The app provides practice/test modes with authentication.

## Core Architecture

### Data Flow
- **fetch_data.py**: Downloads vocabulary from Google Sheets (2 sheets: Latin & English)
- **app.py**: Main Flask app with session-based data caching and authentication
- **Templates**: Three views - index (selection), practice (display), test (interactive quiz)

### Key Data Structure
Vocabulary items are dictionaries with standardized column names:
```python
COL_NAME_TERM = 'Fremdsprache'        # Foreign language term
COL_NAME_COMMENT = 'Zusatz'           # Additional info (grammar notes)
COL_NAME_TRANSLATION = 'Deutsch'      # German translation
COL_NAME_CATEGORY = 'Kategorie'       # Lesson/chapter grouping
COL_NAME_LANGUAGE = 'Sprache'         # 'Latein' or 'Englisch'
```

## Critical Patterns

### Authentication & Session Management
- Password-protected with rate limiting (progressive delays on failed attempts)
- Session data persists test state, wrong answers, and vocab cache
- Use `@require_auth` decorator for protected routes
- Session clears on logout and data reload

### Language-Specific Logic
The `_get_language_labels()` function handles display differences:
- Latin shows comments (grammar info), English doesn't
- Label mapping changes based on test direction (term→translation or reverse)
- Always use this utility when rendering test/practice templates

### Data Processing Patterns
1. **Category filtering**: Filter by language first, then category
2. **Unnamed column removal**: Strip keys starting with 'Unnamed' from Google Sheets data
3. **Category grouping**: Transform flat list to `{category: [items]}` dict for templates
4. **Session state**: Test progress tracked via `correct_answers`, `wrong_answers`, `show_term`

## Development Workflows

### Local Development
```bash
python app.py  # Runs on localhost:5000
```

### Data Reload
- `/reload_data` endpoint clears session and re-fetches from Google Sheets
- Useful during development when sheet data changes

### Deployment
- Configured for Heroku/Koyeb with `Procfile` (gunicorn)
- Environment variables: `FLASK_SECRET_KEY`, `LOGIN_PASSWORD`
- Google Sheets API key in `/keys/vocab-app-*.json` (not committed)

## File Conventions

### Templates
- Use `col_name_*` variables for column references (not hardcoded strings)
- `is_error_review` flag enables error-specific UI in practice.html
- JavaScript in index.html handles category cascading and form persistence

### Error Handling
- Wrong answers stored in `session['list_of_wrong_answers']` for review
- Test direction toggling preserves current question state
- Position tracking uses modulo arithmetic for circular navigation

## Integration Points

### Google Sheets API
- Public sheets accessed via CSV export URLs (no auth required)
- Two sheet GIDs: 0 (Latin), 897548588 (English)
- Data structure assumes first row is ignored, categories auto-fill down

### Session Storage
- Flask-Session with filesystem backend (`/tmp/flask_session`)
- 10-hour session lifetime
- Critical for test state persistence and vocab caching

## Testing Patterns
When adding features:
1. Test with both languages (different comment visibility)
2. Verify session state persistence across redirects
3. Check category filtering logic with multiple selections
4. Test authentication flow including rate limiting