# AFBench

A comprehensive AI model evaluation framework using Snakemake for systematic benchmarking and skill assessment across multiple AI systems.

## Overview

AFBench is an advanced AI model evaluation pipeline that:
- Evaluates multiple AI models across diverse skill categories
- Conducts systematic tournaments between models using Swiss-system pairing
- Calculates skill ratings using OpenSkill Bradley-Terry system
- Generates comprehensive reports and visualizations
- Maintains rigorous quality assurance standards

## Core Components

- **Model & Judge Pools**: Configurable sets of AI models and evaluation judges
- **Skills & Evaluations**: Structured test scenarios across categories like:
  - Code Generation (algorithm optimization, game development)
  - Document Summarization (academic papers, technical content)
  - Persuasiveness (communication effectiveness)
  - Ethical Compliance (respect for constraints, harm avoidance)
- **Tournament System**: Swiss-system tournaments for fair model comparison
- **Skill Rating**: OpenSkill-based rating system for model capabilities
- **Static Site Generation**: Web interface for results review

## Pipeline Data Flow

AFBench follows a multi-stage pipeline architecture:

1. **Configuration Loading**: Load model pools, judge pools, and skill definitions
   - Input: `model_pools/*.csv`, `judge_pools/*.csv`, `skills/*/*.json`
   - Output: `data/loaded_models.json`, `data/loaded_judges.json`, `data/loaded_skills.json`

2. **Parallel Conversation Execution**: Generate model conversations with evaluation scenarios
   - Input: Configuration data from stage 1
   - Output: `data/conversations/skill/eval_model_hash.json` (cached individual files)
   - Markers: `data/conversations_cache_model.done`

3. **Tournament Execution**: Run Swiss-system tournaments between models
   - Input: Conversation cache files and configuration data
   - Output: `data/tournaments.json`

4. **Tournament Summarization**: Aggregate match results and rankings
   - Input: `data/tournaments.json` and configuration data 
   - Output: `data/tournament_summaries.json`

5. **Skill Rating Calculation**: Compute OpenSkill Bradley-Terry ratings
   - Input: `data/tournament_summaries.json` and configuration data
   - Output: `data/skill_ratings.json`

**Cache Management**: The pipeline maintains sophisticated caching:
- `data/conversations/`: Individual conversation results (prevents re-execution)
- `data/judge_cache/`: Judge decision cache (prevents re-evaluation)  
- `data/skill_ratings/`: Rating calculation cache (prevents re-computation)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the complete AI evaluation pipeline
snakemake --cores 4

# Run with custom configuration
snakemake --cores 4 --configfile config/config.yaml

# View planned execution without running
snakemake --dry-run

# Visualize workflow dependency graph
snakemake --dag | dot -Tpng > workflow_dag.png

# Generate static site for results review
cd site && ./run.sh
```

For detailed command explanations and expected outputs, see [RUNBOOK.md](RUNBOOK.md).

## Quality Assurance

This project maintains high code quality through comprehensive tooling:

### Quick Setup
```bash
./setup_qa.sh
```

### Run Full QA Suite
```bash
./qa.sh
```

### Individual QA Tools

- **Type Checking**: `mypy src/ --strict --show-error-codes`
- **Code Formatting**: `black --check --diff src/ tests/`
- **Linting**: `ruff check src/ tests/ --show-fixes`
- **Import Sorting**: `isort --check-only --diff src/ tests/`
- **Security**: `bandit -r src/ -f json -ll`
- **Dependencies**: `safety check --json`
- **Testing**: `pytest tests/ --cov=src --cov-fail-under=95`

### Pre-commit Hooks

Pre-commit hooks run automatically on each commit:
```bash
pre-commit install  # One-time setup (included in setup_qa.sh)
```

## Development

### Requirements
- Python >= 3.11
- All dev dependencies installed via `requirements-dev.txt`

### Project Structure
```
├── config/                  # Pipeline configuration
│   └── config.yaml         # Main configuration file
├── skills/                  # AI evaluation scenarios
│   ├── code_generation/    # Programming tasks
│   ├── document_summarization/ # Summarization tasks  
│   ├── persuasiveness/     # Communication tasks
│   ├── empathy/            # Empathy assessment tasks
│   ├── harm_avoidance/     # Safety evaluation tasks
│   ├── hidden_messages/    # Hidden message detection
│   └── ethical_loopholes/  # Ethical reasoning tasks
├── model_pools/            # AI model configurations
├── judge_pools/            # Judge model configurations
├── scripts/                # Pipeline processing scripts
├── data/                   # Generated evaluation data and cache
│   ├── conversations/      # Individual conversation cache files
│   ├── intermediaries/     # Intermediate processing cache
│   ├── judge_cache/        # Judge decision cache
│   ├── skill_ratings/      # Skill rating calculation cache
│   ├── loaded_*.json       # Pipeline configuration data
│   ├── tournaments.json    # Tournament results
│   ├── tournament_summaries.json  # Match history and rankings
│   └── skill_ratings.json # Final model skill ratings
├── output/                 # Analysis results and plots
├── site/                   # Static site for results review
├── tests/                  # Test suite with safety guards
├── pyproject.toml          # Project configuration and QA settings
├── Snakefile              # Main workflow definition
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Development dependencies
├── setup_qa.sh            # QA environment setup
├── qa.sh                  # Full QA suite runner
└── RUNBOOK.md             # Detailed command reference
```

### Development Workflow

1. Add skills or modify configurations in respective directories
2. Create tests in `tests/` for new functionality
3. Run QA suite: `./qa.sh`  
4. Test pipeline: `snakemake --dry-run`
5. Commit changes

### Adding New Skills

1. Create skill JSON files in appropriate `skills/` subdirectories
2. Update `config/config.yaml` if needed
3. Run pipeline to generate new evaluation data

### QA Standards

All code must pass:
- ✅ **100% type coverage** with MyPy strict mode
- ✅ **Consistent formatting** with Black
- ✅ **Clean linting** with Ruff
- ✅ **Sorted imports** with isort
- ✅ **Security analysis** with Bandit
- ✅ **Dependency security** with Safety
- ✅ **95%+ test coverage** with pytest

## License

This project is licensed under the MIT License.