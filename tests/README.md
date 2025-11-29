# Test Suite for Jakobs WortSpaß Vocabulary App

## Overview

This test suite provides comprehensive coverage for the vocabulary learning application, including unit tests for the spaced repetition system, integration tests for the Flask application, and tests for Google Sheets data integration.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and configuration
├── test_level.py            # Unit tests for spaced repetition system
├── test_google_sheet_io.py  # Tests for data layer and Google Sheets
└── test_app.py              # Integration tests for Flask routes
```

## Test Organization

Tests are organized by module:

- **`test_level.py`**: Unit tests for the spaced repetition algorithm (level.py)
  - Level configuration and validation
  - Urgency calculation and comparison
  - Answer processing and level progression
  - Boundary conditions and edge cases

- **`test_google_sheet_io.py`**: Tests for data layer (google_sheet_io.py)
  - VocabularyTerm and VocabularyScore classes
  - VocabularyDatabase filtering and sorting
  - CSV parsing and data transformation
  - Google Sheets integration (includes real API tests)
  - Score writing (mocked for safety)

- **`test_app.py`**: Integration tests for Flask application (app.py)
  - Authentication flow and rate limiting
  - Session management
  - Practice and test modes
  - Error review functionality
  - Score persistence

## Installation

### Install Test Dependencies

```bash
pip install -r requirements-dev.txt
```

This includes:
- pytest: Test framework
- pytest-flask: Flask testing utilities
- pytest-mock: Mocking support
- pytest-cov: Coverage reporting
- freezegun: Time freezing for date-dependent tests
- responses: HTTP mocking

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Module

```bash
pytest tests/test_level.py
pytest tests/test_google_sheet_io.py
pytest tests/test_app.py
```

### Run Tests by Category

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests (like real Google Sheets API calls)
pytest -m "not slow"
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html --cov-report=term
```

This generates:
- Terminal coverage summary
- HTML coverage report in `htmlcov/index.html`

### Verbose Output

```bash
pytest -v
```

### Run Specific Test

```bash
pytest tests/test_level.py::TestLevelSystem::test_process_answer_correct_progression
```

## Test Coverage

The test suite aims for comprehensive coverage with the following targets:

- **level.py**: 90%+ (critical business logic)
- **google_sheet_io.py**: 80%+ (data layer)
- **app.py**: 70%+ (Flask routes, harder to test comprehensively)

Current coverage can be checked with:
```bash
pytest --cov=level --cov=google_sheet_io --cov=app --cov-report=term-missing
```

## Google Sheets Integration

### Real API Tests

Some tests in `test_google_sheet_io.py` make **actual calls** to Google Sheets:
- `test_fetch_data_real_sheets()`: Reads from production sheets to verify integration

These tests are marked with `@pytest.mark.slow` and can be skipped:
```bash
pytest -m "not slow"
```

### Mocked Write Operations

All **write operations** to Google Sheets are mocked to prevent accidental data modification during testing.

### Authentication

Real API tests require valid Google credentials. Ensure you have:
- Service account JSON key in `keys/` folder, OR
- `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable set

## Key Test Fixtures

Defined in `tests/conftest.py`:

- **`app`**: Configured Flask test application
- **`client`**: Unauthenticated test client
- **`authenticated_client`**: Authenticated test client (regular mode)
- **`guest_client`**: Authenticated test client (guest mode)
- **`sample_vocab_terms`**: Sample vocabulary terms for testing
- **`sample_vocab_database`**: Pre-populated VocabularyDatabase
- **`sample_test_data`**: Sample test session data
- **`mock_vocab_data`**: Helper to inject vocab database into session
- **`freeze_date`**: Time freezing utility for date-dependent tests

## Writing New Tests

### Example: Adding a Unit Test

```python
# tests/test_level.py
def test_my_new_feature():
    """Test description."""
    # Arrange
    level = LevelSystem.get_level('Red-2')
    
    # Act
    result = LevelSystem.is_testable('Red-2', '2025-11-28')
    
    # Assert
    assert result is True
```

### Example: Adding an Integration Test

```python
# tests/test_app.py
def test_my_route(authenticated_client, sample_vocab_database, mock_vocab_data):
    """Test a Flask route."""
    # Setup
    mock_vocab_data(authenticated_client)
    
    # Execute
    response = authenticated_client.get('/my-route')
    
    # Verify
    assert response.status_code == 200
    assert b'expected content' in response.data
```

## Test Data

### Sample Vocabulary

Tests use predefined sample data including:
- Latin terms: "domus", "templum" (Lektion 1)
- English terms: "house", "temple" (Unit 1)
- Various score states: Red-1, Red-2, Yellow-1, Green
- Different test dates for urgency testing

### Date Handling

Tests involving dates use `freezegun` to ensure consistency:

```python
@pytest.mark.usefixtures("freeze_date")
def test_with_frozen_time():
    # date.today() will always return 2025-11-29
    ...
```

## Continuous Integration

To set up CI/CD testing:

```yaml
# .github/workflows/test.yml
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
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Troubleshooting

### Tests Fail Due to Missing Dependencies

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Session-Related Test Failures

Ensure temporary session directory is writable:
```bash
mkdir -p /tmp/flask_session
chmod 777 /tmp/flask_session
```

### Google Sheets API Tests Fail

- Check credentials are properly configured
- Verify network connectivity
- Use `-m "not slow"` to skip real API tests

### Import Errors

Run tests from the project root directory:
```bash
cd /path/to/vocab_app
pytest
```

Or install the package in development mode:
```bash
pip install -e .
```

## Best Practices

1. **Run tests before committing**: `pytest`
2. **Check coverage regularly**: `pytest --cov`
3. **Write tests for new features**: Maintain high coverage
4. **Use fixtures**: Reuse common test setup
5. **Mock external services**: Except for integration verification
6. **Test edge cases**: Boundary conditions, errors, empty data
7. **Keep tests fast**: Mock slow operations, use fixtures efficiently

## Test Metrics

Expected test execution times:
- Unit tests (level.py): < 1 second
- Unit tests (google_sheet_io.py without real API): < 2 seconds
- Integration tests (app.py): < 5 seconds
- **Full suite (with real API)**: < 10 seconds
- **Full suite (without real API)**: < 5 seconds

Run quick tests only:
```bash
pytest -m "not slow" -x  # Exit on first failure
```
