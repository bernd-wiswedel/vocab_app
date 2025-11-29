#!/bin/bash

# Test runner script for vocabulary app
# Provides convenient commands for running different test configurations

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Vocabulary App Test Suite ===${NC}\n"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found${NC}"
    echo "Install test dependencies with: pip install -r requirements-dev.txt"
    exit 1
fi

# Parse command line arguments
case "${1:-all}" in
    all)
        echo -e "${YELLOW}Running all tests...${NC}"
        pytest -v
        ;;
    
    fast)
        echo -e "${YELLOW}Running fast tests (skipping slow tests)...${NC}"
        pytest -v -m "not slow"
        ;;
    
    unit)
        echo -e "${YELLOW}Running unit tests only...${NC}"
        pytest -v tests/test_level.py tests/test_google_sheet_io.py -m "not slow"
        ;;
    
    integration)
        echo -e "${YELLOW}Running integration tests only...${NC}"
        pytest -v tests/test_app.py
        ;;
    
    level)
        echo -e "${YELLOW}Running level system tests...${NC}"
        pytest -v tests/test_level.py
        ;;
    
    sheets)
        echo -e "${YELLOW}Running Google Sheets tests...${NC}"
        pytest -v tests/test_google_sheet_io.py
        ;;
    
    app)
        echo -e "${YELLOW}Running Flask app tests...${NC}"
        pytest -v tests/test_app.py
        ;;
    
    coverage)
        echo -e "${YELLOW}Running tests with coverage report...${NC}"
        pytest --cov=level --cov=google_sheet_io --cov=app \
               --cov-report=html --cov-report=term-missing \
               -v
        echo -e "\n${GREEN}Coverage report generated in htmlcov/index.html${NC}"
        ;;
    
    quick)
        echo -e "${YELLOW}Running quick smoke test...${NC}"
        pytest -v -x -m "not slow"  # Exit on first failure
        ;;
    
    watch)
        echo -e "${YELLOW}Running tests in watch mode...${NC}"
        if command -v pytest-watch &> /dev/null; then
            pytest-watch -v -m "not slow"
        else
            echo -e "${RED}Error: pytest-watch not installed${NC}"
            echo "Install with: pip install pytest-watch"
            exit 1
        fi
        ;;
    
    help)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  all         Run all tests (default)"
        echo "  fast        Run all tests except slow ones"
        echo "  unit        Run unit tests only"
        echo "  integration Run integration tests only"
        echo "  level       Run level system tests"
        echo "  sheets      Run Google Sheets tests"
        echo "  app         Run Flask app tests"
        echo "  coverage    Run tests with coverage report"
        echo "  quick       Run fast tests, exit on first failure"
        echo "  watch       Run tests in watch mode (requires pytest-watch)"
        echo "  help        Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0              # Run all tests"
        echo "  $0 fast         # Run tests quickly"
        echo "  $0 coverage     # Generate coverage report"
        ;;
    
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac

# Exit with pytest's exit code
exit $?
