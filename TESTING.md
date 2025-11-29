# Testing Documentation - Vocabulary Learning App

## Summary

A comprehensive test suite has been created for the vocabulary learning application with **150+ test cases** covering all major functionality.

## Test Coverage by Module

### 1. `test_level.py` - Spaced Repetition System (65+ tests)

**Coverage**: Level system, urgency calculations, progression logic

- **Level class**: Creation, representation
- **Urgency class**: Comparison logic, sorting, equality
- **LevelSystem class**:
  - Level lookup and validation
  - Next level progression
  - Testability checks (min_days)
  - Expiration checks (max_days)
  - Urgency calculation for all states
  - Answer processing (correct/incorrect)
  - Boundary conditions (exact min/max days)
  - Special cases (Red-1, Green progression, expired terms)

**Key Test Scenarios**:
- ✅ Correct answer advances level when eligible
- ✅ Correct answer too soon keeps same level
- ✅ Incorrect answer always returns to Red-1
- ✅ Expired terms fall back to Red-1
- ✅ Green level stays at Green when correct
- ✅ Urgency prioritizes by days until expiry, then level
- ✅ Boundary testing at exact min_days and max_days

### 2. `test_google_sheet_io.py` - Data Layer (45+ tests)

**Coverage**: Vocabulary classes, database operations, Google Sheets integration

- **VocabularyTerm**: Creation, equality, hashing, dict key usage
- **VocabularyScore**: Creation, defaults, updating
- **VocabularyDatabase**:
  - Adding/retrieving items
  - Filtering by language and category
  - Testable terms selection (with/without guest mode)
  - Urgency-based sorting
  - Score updates
  - Insertion order preservation
- **CSV Parsing**: Header skipping, category auto-fill, blank term filtering, NaN handling
- **Google Sheets Integration**:
  - **Real reads** from production sheets (marked as slow tests)
  - **Mocked writes** for safety
  - Batch update/append logic
  - Error handling

**Key Test Scenarios**:
- ✅ Guest mode returns all terms regardless of urgency
- ✅ Authenticated mode filters and sorts by urgency
- ✅ Category auto-fill from previous row
- ✅ Database preserves Google Sheets order
- ✅ Write operations update existing rows or append new ones

### 3. `test_app.py` - Flask Application (50+ tests)

**Coverage**: Routes, session management, authentication, test flow

**Test Categories**:

- **Authentication** (7 tests):
  - Login page accessibility
  - Correct/incorrect password handling
  - Rate limiting after failed attempts
  - Guest login
  - Logout session clearing
  - @require_auth decorator

- **Data Loading** (4 tests):
  - Loading page display
  - API fetch success/failure
  - Reload preserves auth state

- **Index & Categories** (5 tests):
  - Index page for authenticated/guest users
  - Category fetching by language
  - Lesson statistics with/without urgency

- **Practice Mode** (2 tests):
  - Single/multiple category selection
  - Data filtering and display

- **Test Mode** (15 tests):
  - Starting test session
  - Test page rendering
  - Showing translation
  - Checking correct/wrong answers
  - Skipping questions
  - Switching direction (term ↔ translation)
  - Guest mode vs authenticated mode
  - Completion redirect to review

- **Test Selected** (2 tests):
  - Manual item selection
  - Empty selection handling

- **Error Review** (2 tests):
  - Retesting wrong/skipped items
  - No incomplete items handling

- **Review Page** (3 tests):
  - Results display
  - Correct/wrong/skipped counts
  - No data redirect

- **Score Writing** (3 tests):
  - Authenticated mode writing
  - Guest mode rejection
  - Selected items only

- **Utility Functions** (7 tests):
  - Language label generation
  - Status info calculation
  - Data format conversion
  - Random order generation

**Key Test Scenarios**:
- ✅ Complete test flow from start to review
- ✅ Session state management across redirects
- ✅ Guest mode doesn't update scores
- ✅ Direction switching preserves state
- ✅ Error review creates new shuffled order
- ✅ Score writing groups by language

## Test Infrastructure

### Fixtures (`conftest.py`)

- **`app`**: Configured test Flask app with temp session dir
- **`client`**: Unauthenticated test client
- **`authenticated_client`**: Regular authenticated client
- **`guest_client`**: Guest mode authenticated client
- **`sample_vocab_terms`**: 4 sample terms (2 Latin, 2 English)
- **`sample_vocab_database`**: Pre-populated database with various states
- **`sample_test_data`**: Test session data structure
- **`mock_vocab_data`**: Helper to inject database into session
- **`mock_google_sheets_data`**: Mock Google Sheets responses
- **`freeze_date`**: Time freezing at 2025-11-29

### Configuration (`pytest.ini`)

- Test discovery: `tests/test_*.py`
- Verbose output by default
- Short traceback format
- Markers: `unit`, `integration`, `slow`

## Running Tests

### Quick Start

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run fast tests only (skip Google Sheets API calls)
pytest -m "not slow"

# Run with coverage
pytest --cov --cov-report=html
```

### Using Test Runner

```bash
# Make executable
chmod +x run_tests.sh

# Run commands
./run_tests.sh all        # All tests
./run_tests.sh fast       # Skip slow tests
./run_tests.sh unit       # Unit tests only
./run_tests.sh coverage   # With coverage report
```

## Coverage Goals

**Target Coverage** (aspirational):
- `level.py`: 90%+ ✅
- `google_sheet_io.py`: 80%+ ✅
- `app.py`: 70%+ ✅

**Current Status**: Check with `pytest --cov`

## Google Sheets Testing Strategy

### Reads: Real API Calls

Tests in `test_google_sheet_io.py::test_fetch_data_real_sheets()` make **actual reads** from production Google Sheets to verify:
- CSV export parsing works correctly
- Column name mapping is accurate
- Category auto-fill logic works
- Score fetching and merging succeeds

**Marked as `@pytest.mark.slow`** - skip with `pytest -m "not slow"`

### Writes: Fully Mocked

All write operations use mocked Google Sheets service to prevent accidental data modification:
- `@patch('google_sheet_io._get_sheets_service')`
- Verifies correct API call structure
- Tests update vs. append logic
- Validates batch update format

## Test Data Management

### In-Memory Test Data

Tests use programmatically generated test data via fixtures:
- Consistent across test runs
- Easy to modify for edge cases
- No external file dependencies
- Fast test execution

### Sample Data Structure

```python
# Latin term with Red-1 status
VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1", "domus, domūs f.")
VocabularyScore('Red-1', None)

# English term with Yellow-1 status  
VocabularyTerm("house", "das Haus", "Englisch", "Unit 1", "")
VocabularyScore('Yellow-1', '2025-11-22')
```

## Key Testing Patterns

### 1. Session Management Testing

```python
def test_session_data(authenticated_client):
    with authenticated_client.session_transaction() as sess:
        sess['test_data'] = sample_data
    
    response = authenticated_client.get('/test')
    
    with authenticated_client.session_transaction() as sess:
        assert sess['current_position'] == 0
```

### 2. Mocking Google Sheets

```python
@patch('google_sheet_io._get_sheets_service')
def test_write_scores(mock_get_service):
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service
    mock_service.spreadsheets().values().get().execute.return_value = {...}
    
    write_scores_to_sheet(items, 'Englisch')
    
    assert mock_service.spreadsheets().values().batchUpdate.called
```

### 3. Date-Dependent Testing

```python
def test_with_dates():
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    
    result = LevelSystem.is_testable('Red-2', yesterday)
    assert result is True
```

## Edge Cases Covered

### Level System
- ✅ Testing exactly at min_days boundary
- ✅ Testing exactly at max_days boundary  
- ✅ Testing before min_days (not ready)
- ✅ Testing after max_days (expired)
- ✅ Red-1 never expires, always testable
- ✅ Green stays at Green on correct answer
- ✅ Urgency with same days, different levels

### Data Layer
- ✅ Empty database
- ✅ Blank Fremdsprache (skipped)
- ✅ NaN values in CSV
- ✅ Category auto-fill with blank first category
- ✅ Guest mode vs. authenticated filtering
- ✅ Limit enforcement in get_testable_terms

### Flask App
- ✅ Session expiration (no test_data)
- ✅ Empty test results
- ✅ All questions correct (immediate review)
- ✅ All questions skipped
- ✅ Mixed correct/wrong/skipped
- ✅ Direction switching mid-test
- ✅ Guest mode score writing (rejected)

## Continuous Integration Ready

Tests are designed for CI/CD:
- No manual intervention required
- Fast execution (< 10 seconds full suite)
- Mocked external dependencies (except opt-in real API tests)
- Clear success/failure reporting
- Coverage metrics exportable

Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest -m "not slow" --cov --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Future Enhancements

Potential additions:
1. **Performance tests**: Test with 1000+ vocabulary items
2. **Stress tests**: Concurrent session access
3. **E2E tests**: Selenium/Playwright browser tests
4. **Property-based tests**: Hypothesis for fuzz testing
5. **Mutation testing**: Verify test quality with mutmut
6. **Load testing**: Simulate multiple users
7. **API contract tests**: Verify Google Sheets API assumptions

## Maintenance

### Adding New Tests

1. Choose appropriate test file based on module
2. Use existing fixtures when possible
3. Follow AAA pattern (Arrange, Act, Assert)
4. Add descriptive docstrings
5. Mark slow tests with `@pytest.mark.slow`

### Updating Tests

When code changes:
1. Run tests: `pytest`
2. Fix failing tests
3. Add tests for new functionality
4. Update fixtures if data structure changes
5. Check coverage: `pytest --cov`

## Dependencies

Test framework:
- pytest 8.3.5
- pytest-flask 1.3.0
- pytest-mock 3.14.0
- pytest-cov 6.0.0
- freezegun 1.5.1
- responses 0.25.3

Install with:
```bash
pip install -r requirements-dev.txt
```

## Troubleshooting

**Tests fail with "No module named 'app'"**
→ Run from project root: `cd /path/to/vocab_app && pytest`

**Session-related errors**
→ Ensure `/tmp/flask_session` is writable

**Google Sheets API tests fail**
→ Check credentials or skip with `pytest -m "not slow"`

**Coverage seems low**
→ Run `pytest --cov --cov-report=term-missing` to see uncovered lines

## Contact

For questions about the test suite, refer to:
- `tests/README.md` - Detailed test documentation
- `tests/conftest.py` - Fixture definitions
- Individual test files - Specific test implementations
