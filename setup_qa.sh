#!/bin/bash
set -e

echo "🔧 Setting up QA environment..."

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $required_version or higher is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install -r requirements-dev.txt

# Setup pre-commit hooks
echo "🪝 Setting up pre-commit hooks..."
pre-commit install

# Create qa.sh if it doesn't exist
if [ ! -f qa.sh ]; then
    echo "📝 Creating qa.sh script..."
    cat > qa.sh << 'EOF'
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
EOF
    chmod +x qa.sh
fi

# Create directories
mkdir -p src tests config

echo "✅ QA tools installed successfully!"
echo "📋 Next steps:"
echo "   1. Run './qa.sh' to perform full QA check"
echo "   2. Use 'pre-commit run --all-files' to run pre-commit hooks"
echo "   3. Start implementing your pipeline in src/"