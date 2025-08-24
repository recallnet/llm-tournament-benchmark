# AFBench

A high-performance AI model evaluation framework using Snakemake with parallel execution and robust caching for systematic benchmarking across multiple AI systems.

## Overview

AFBench provides a production-ready AI evaluation pipeline featuring:
- **Parallel Tournament Execution**: Run multiple skill evaluations simultaneously with race-condition protection
- **Swiss-System Competitions**: Fair head-to-head model comparisons with OpenSkill rating calculations
- **Robust Cache Management**: Intelligent caching with atomic operations to prevent data corruption
- **Profile-Based Configuration**: Separate quick (development) and production execution environments
- **Web-Based Monitoring**: Real-time progress tracking via Streamlit admin interface

## Quick Start

### Development Workflow
```bash
# Install dependencies
pip install -r requirements.txt

# Run quick evaluation for development
snakemake --profile profiles/quick -j5 > pipeline_run.log 2>&1 &

# Monitor progress
tail -f pipeline_run.log

# View results in web interface
cd site && ./run.sh
```

### Production Workflow
```bash
# Run full production evaluation
snakemake --profile profiles/production -j5 > pipeline_run.log 2>&1 &

# Monitor with production data
cd site && AFBENCH_ADMIN_DATA_DIR=data/production ./run.sh
```

See [RUNBOOK.md](RUNBOOK.md) for complete pipeline management commands.

## Pipeline Architecture

AFBench uses a **5-stage parallel execution pipeline**:

1. **Setup**: Load models (4-51), judges (3), and skills (7 categories) with validation
2. **Conversations**: Generate model responses in parallel by model (race-condition safe caching)  
3. **Tournaments**: Run Swiss-system competitions in parallel by skill (exclusive cache locking)
4. **Analysis**: Aggregate match results and calculate OpenSkill ratings
5. **Reporting**: Generate visualizations and summary statistics

**Parallel Execution Features**:
- Per-model conversation generation (independent caches)
- Per-skill tournament execution (up to 6+ judge threads)
- Atomic cache operations with exclusive file locking
- Safe restart/resume without data loss

## Profile Comparison

| Feature | Quick Profile | Production Profile |
|---------|---------------|-------------------|
| **Models** | 4 lightweight | 51 comprehensive |
| **Execution Time** | ~15 minutes | 2-8 hours |
| **Parallel Jobs** | 4 cores | 5 cores |
| **Use Case** | Development/testing | Final evaluation |
| **Cache Safety** | Full protection | Full protection |

## Core Skills & Evaluations

AFBench evaluates models across **7 skill categories**:

| Skill Category | Focus Area | Example Tasks |
|---------------|------------|---------------|
| **Code Generation** | Programming & algorithms | Conway's Game of Life, sorting visualizers, games |
| **Document Summarization** | Content comprehension | Academic papers, technical documents |
| **Empathy** | Emotional intelligence | Crisis support, life challenges |
| **Persuasiveness** | Communication effectiveness | Professional requests, problem-solving |
| **Harm Avoidance** | Safety & ethics | Refusing harmful requests, responsible guidance |
| **Hidden Messages** | Instruction following | Following embedded directives in context |
| **Ethical Loopholes** | Moral reasoning | Navigating complex ethical scenarios |

## Cache & Data Management

**Critical Data Protection**:
- `data/*/judge_cache/` - **Never delete** - Contains thousands of expensive API calls
- `data/*/conversations/` - **Never delete** - Contains expensive conversation data
- **Race condition protection** - Exclusive locking prevents concurrent cache corruption
- **Atomic operations** - Safe file operations prevent partial writes

**Data Structure**:
```
data/[profile]/
├── conversations/              # Individual conversations by skill
├── judge_cache/               # Cached judge decisions (critical!)
├── tournament_[skill].json   # Per-skill tournament results
├── tournaments.json          # Aggregated tournament data
└── skill_ratings.json       # Final OpenSkill ratings
```

## Development & Testing

### Quick Setup
```bash
# Install dependencies & QA tools
pip install -r requirements.txt
./setup_qa.sh

# Run comprehensive test suite
pytest tests/ -v

# Run quality assurance
./qa.sh
```

### Project Structure
```
├── profiles/               # Execution profiles (quick/production)
├── skills/                # AI evaluation scenarios (7 categories)
├── model_pools/           # Model configurations (4-51 models)
├── judge_pools/          # Judge configurations (3 judges)
├── scripts/              # Pipeline processing & safety utilities
├── tests/               # Comprehensive test suite (TDD approach)
├── site/                # Streamlit admin interface
├── Snakefile           # Main workflow with parallel execution
└── RUNBOOK.md         # Complete command reference
```

### Safety & Quality Standards

**Testing**:
- ✅ **Race condition protection** - Concurrent cache operation tests
- ✅ **Cache corruption prevention** - Atomic file operation validation  
- ✅ **Production safety** - Pipeline restart & resume testing
- ✅ **Parallel execution** - Multi-skill tournament coordination
- ✅ **95%+ test coverage** - Comprehensive TDD test suite

**Code Quality**:
- ✅ **Type safety** with MyPy strict mode
- ✅ **Consistent formatting** with Black
- ✅ **Security analysis** with Bandit
- ✅ **Clean linting** with Ruff

## License

This project is licensed under the MIT License.