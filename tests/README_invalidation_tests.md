# AFBench Invalidation Test Suite

This directory contains comprehensive tests for **Section 2: Correct invalidation (minimal rebuilds)** from `TESTS.md`.

## Overview

The test suite verifies that AFBench follows the **Single-Command Contract (SCC)**:

```bash
snakemake --unlock && snakemake --profile profiles/testonly -j <k>
```

And ensures that:
- Only affected scopes rebuild when configurations change
- Unaffected work is properly reused
- The pipeline maintains deterministic behavior

## Test Files

### Core Test Implementation

- **`test_invalidation_minimal_rebuilds.py`** - Main pytest test suite implementing all I1-I6 tests
- **`run_invalidation_test_suite.py`** - CI test matrix runner implementing the full test sequence

### Test Categories

#### Individual Tests (I1-I6)

1. **I1: Add model** - Verify new conversations only for added model, tournaments recomputed, prior conversations reused
2. **I2: Remove model** - Verify no stale artifacts consumed, tournaments reflect smaller set  
3. **I3: Change judges** - Verify matches re-evaluated, conversations reused
4. **I4: Change eval configuration** - Verify only affected eval rebuilds
5. **I5: Add/remove eval** - Verify only that eval's scope changes
6. **I6: Tournament changes** - Verify scores recompute when tournament parameters change

#### Test Matrix Sequence

1. **Clean baseline** - Fresh workspace, both `-j 1` and `-j 5` succeed
2. **No-op repeat** - Identical inputs produce no work  
3. **Mutation battery** - Apply I1-I6 mutations systematically
4. **Fault handling** - Introduce failures, verify halt and resume
5. **Interrupt/resume** - Kill mid-run, resume completes cleanly
6. **Partial artifact loss** - Delete random files, regenerate only missing
7. **Concurrency safety** - Verify per-model serialization under `-j 5`
8. **Observability** - Verify reasons for rebuilds are visible
9. **Summary freshness** - Verify summaries regenerate on upstream changes

## Usage

### Run Individual Test Categories

```bash
# Run the core invalidation tests with pytest
pytest tests/test_invalidation_minimal_rebuilds.py -v

# Run specific test
pytest tests/test_invalidation_minimal_rebuilds.py::TestInvalidationMinimalRebuilds::test_i1_add_model_minimal_rebuild -v
```

### Run Full CI Test Matrix

```bash
# Run complete test suite
python tests/run_invalidation_test_suite.py --verbose

# Run specific test from the matrix
python tests/run_invalidation_test_suite.py --test clean_baseline --verbose

# Run in custom directory
python tests/run_invalidation_test_suite.py --working-dir /tmp/afbench_test
```

### Available Test Matrix Tests

```bash
--test clean_baseline       # Test 1: Clean baseline runs
--test no_op_repeat         # Test 2: No-op repeat behavior  
--test mutation_battery     # Test 3: All I1-I6 mutations
--test fault_handling       # Test 4: Failure injection/recovery
--test interrupt_resume     # Test 5: Mid-run interruption
--test partial_artifact_loss # Test 6: Random file deletion
--test concurrency_safety   # Test 7: Parallel execution safety
--test observability        # Test 8: Diagnostic visibility
--test summary_freshness    # Test 9: Summary regeneration
```

## Test Framework Features

### `SnakemakeTestFramework` Class

- **Isolated testing** - Each test runs in temporary directory
- **File tracking** - Snapshots track what files change between runs
- **SCC enforcement** - All tests use the Single-Command Contract
- **Configuration management** - Modify pools, skills, configs for testing
- **Safety guards** - Production data protection (from `conftest.py`)

### Key Verification Methods

- `snapshot_files()` - Capture file modification times
- `compare_snapshots()` - Identify created/modified/deleted files  
- `run_snakemake_scc()` - Execute the Single-Command Contract
- `modify_model_pool()` - Add/remove models for testing
- `modify_judge_pool()` - Add/remove judges for testing
- `modify_skills()` - Add/remove evaluations for testing

## Test Configuration

### Test Profile: `profiles/testonly`

The tests use the `testonly` profile which provides:

- **Isolated data** - Uses `data/testonly` directory
- **Minimal fixtures** - Small model/judge pools for fast execution
- **Deterministic seeds** - Fixed random seed (12345) for reproducible results
- **Mock endpoints** - No external API calls during testing

### Test Fixtures

- **Models**: `test/model-alpha`, `test/model-beta` (mock endpoints)
- **Judges**: `test/judge-gamma`, `test/judge-delta` (mock endpoints)  
- **Skills**: `testonly/skills/test_skill/` with `eval_one.json`, `eval_two.json`

## Expected Behavior

### Minimal Rebuild Patterns

When you **add a model**:
- ✅ New model conversation files created
- ✅ Tournaments and ratings recomputed  
- ❌ Existing model conversations NOT modified

When you **remove a model**:
- ✅ Tournaments and ratings recomputed
- ✅ Removed model absent from loaded_models.json
- ❌ No references to removed model in tournaments

When you **change judges**:  
- ✅ Tournaments and ratings recomputed
- ❌ Conversations NOT modified (reused)

When you **change eval configuration**:
- ✅ Affected eval scope rebuilds
- ❌ Unaffected evals remain cached

### File Change Tracking

The test framework tracks these file types:

```
data/testonly/
├── loaded_models.json          # Modified when model pool changes
├── loaded_judges.json          # Modified when judge pool changes  
├── loaded_skills.json          # Modified when skills change
├── model_conversations_*.completed  # Created per model
├── tournaments.json            # Modified when tournaments recompute
├── tournament_summaries.json   # Modified when summaries regenerate  
├── skill_ratings.json          # Modified when ratings recompute
└── conversations/              # Conversation content files
    └── intermediaries/         # Intermediate processing files
```

## Integration with CI

### Prerequisites

```bash
# Install test dependencies
pip install pytest pandas

# Ensure Snakemake is available
snakemake --version
```

### CI Test Matrix

The full test matrix covers:

| Dimension   | Values                                              |
|-------------|-----------------------------------------------------|
| Profile     | `profiles/testonly`                                 |  
| Parallelism | `-j 1`, `-j 5`                                      |
| Run type    | clean, repeat, mutated, interrupted, partial-delete |

### Exit Codes

- **0** - All tests passed
- **1** - One or more tests failed

## Troubleshooting

### Common Issues

**Tests fail with "Production data safety"**
- The test framework includes safety guards to prevent accidental production data access
- Tests should only touch `data/testonly/` directory
- Check `conftest.py` for safety guard configuration

**Snakemake command not found**
- Ensure Snakemake is installed and in PATH
- Tests require Snakemake to be available as CLI command

**Permission errors on temp directories** 
- Tests create temporary directories for isolation
- Check write permissions in system temp directory

**Tests hang during execution**
- Check for any processes holding file locks
- Verify mock endpoints in testonly pools don't make real API calls

### Debug Mode

Enable verbose logging:

```bash
python tests/run_invalidation_test_suite.py --verbose
pytest tests/test_invalidation_minimal_rebuilds.py -v -s
```

### Manual Verification

You can manually verify invalidation behavior:

```bash
# 1. Clean run
snakemake --unlock && snakemake --profile profiles/testonly -j 1

# 2. No-op (should do nothing)  
snakemake --unlock && snakemake --profile profiles/testonly -j 1

# 3. Add model and re-run
echo "test/new-model,TestCorp,new-model,4096,input:0.0001,mock,1000" >> model_pools/testonly.csv
snakemake --unlock && snakemake --profile profiles/testonly -j 1

# 4. Check what files changed
git status  # or compare timestamps
```

## Contract Compliance

These tests verify compliance with the **Single-Command Contract**:

> At any time, the pipeline must correctly rebuild with:
> ```bash
> snakemake --unlock && snakemake --profile profiles/<p> -j <k>
> ```
> All tests only call that. No targeted rule runs. If SCC fails under any mutation, it's a pipeline bug.

The test suite serves as both **specification** and **verification** that AFBench maintains proper invalidation semantics under all configuration changes.