#!/bin/bash
set -e

echo "🧪 Running full QA suite..."

# Type checking
echo "🔍 Running mypy..."
mypy src/ --strict --show-error-codes

# Code formatting check
echo "🎨 Checking code formatting with black..."
black --check --diff src/ tests/

# Linting
echo "🔧 Running ruff linter..."
ruff check src/ tests/ --show-fixes

# Import sorting check
echo "📦 Checking import sorting with isort..."
isort --check-only --diff src/ tests/

# Security scanning
echo "🔒 Running security analysis with bandit..."
bandit -r src/ -f json -ll

# Dependency security check
echo "🛡️ Checking dependencies with safety..."
safety check --json

# Run tests with coverage
echo "🧪 Running tests with coverage..."
pytest tests/ --cov=src --cov-fail-under=95

echo "✅ All QA checks passed!"