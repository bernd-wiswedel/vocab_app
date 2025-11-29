# Quick Test Guide

## Installation

```bash
pip install -r requirements-dev.txt
```

## Run Tests

### Basic

```bash
# All tests
pytest

# Fast tests (skip Google Sheets API)
pytest -m "not slow"

# Specific module
pytest tests/test_level.py
pytest tests/test_google_sheet_io.py
pytest tests/test_app.py
```

### With Coverage

```bash
pytest --cov --cov-report=html
# Open htmlcov/index.html in browser
```

### Using Test Runner

```bash
chmod +x run_tests.sh

./run_tests.sh          # All tests
./run_tests.sh fast     # Skip slow tests
./run_tests.sh coverage # With coverage report
./run_tests.sh help     # See all options
```

## Test Organization

- **`test_level.py`**: Level system & spaced repetition (65+ tests)
- **`test_google_sheet_io.py`**: Data layer & Google Sheets (45+ tests)
- **`test_app.py`**: Flask routes & sessions (50+ tests)

**Total: 150+ tests**

## Key Features

✅ Real Google Sheets reads (marked as slow, can be skipped)  
✅ Mocked Google Sheets writes (for safety)  
✅ Complete test flow coverage  
✅ Session management testing  
✅ Guest mode vs authenticated mode  
✅ Boundary condition testing  
✅ Date-dependent logic testing  

## Coverage Goals

- `level.py`: 90%+
- `google_sheet_io.py`: 80%+
- `app.py`: 70%+

Check current: `pytest --cov`

## More Info

See `TESTING.md` for comprehensive documentation.
