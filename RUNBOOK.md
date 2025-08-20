# AFBench Runbook

Comprehensive guide to running the AFBench AI evaluation pipeline with Snakemake.

## Table of Contents

- [Pipeline Overview](#pipeline-overview)
- [Basic Commands](#basic-commands)
- [Configuration](#configuration)
- [Pipeline Stages](#pipeline-stages)
- [Individual Rule Execution](#individual-rule-execution)
- [Troubleshooting](#troubleshooting)
- [Output Structure](#output-structure)

## Pipeline Overview

AFBench uses Snakemake to orchestrate a multi-stage AI model evaluation pipeline:

1. **Setup**: Load models, judges, and skills
2. **Execution**: Run conversations between models and evaluators
3. **Tournament**: Conduct Swiss-system tournaments
4. **Analysis**: Calculate skill ratings and generate summaries
5. **Reporting**: Create visualizations and final reports

## Basic Commands

### Profile-Based Execution (Recommended)

AFBench supports two execution profiles for different environments:

#### Test Profile
```bash
# Run with test profile (fast, lightweight models)
snakemake --profile profiles/test

# Development workflow: unlock and run AFBench tournament pipeline
snakemake --unlock && snakemake afbench --profile profiles/test
```

**Expected Output**: Complete evaluation pipeline using test model pools, single-core execution, and smaller samples for rapid testing. The `afbench` rule runs the tournament pipeline and prints results table.

#### Production Profile
```bash
# Run with production profile (comprehensive evaluation)
snakemake --profile profiles/production

# Production workflow: unlock and run AFBench tournament pipeline  
snakemake --unlock && snakemake afbench --profile profiles/production
```

**Expected Output**: Full-scale evaluation using production models, multi-core execution, and comprehensive analysis.

### Legacy Execution Methods

#### Manual Core Specification
```bash
# Run the complete pipeline with 4 cores (legacy method)
snakemake --cores 4
```

**Expected Output**: Complete evaluation pipeline generating all data files, tournament results, and final reports in `data/` and `output/` directories.

#### Dry Run (Preview)
```bash
# See what would be executed without running
snakemake --dry-run

# Or with specific profile
snakemake --profile profiles/test --dry-run
```

**Expected Output**: List of rules that would be executed with their dependencies, useful for validating pipeline structure.

#### Custom Configuration
```bash
# Run with specific configuration file (legacy method)
snakemake --cores 4 --configfile config/config.yaml

# Profile-based configuration (recommended)
snakemake --profile profiles/test --configfile config/custom_config.yaml
```

**Expected Output**: Same as full pipeline but using specified configuration parameters.

### Common Development Commands

#### AFBench Tournament Pipeline (Most Used)
```bash
# Development workflow - run tournament pipeline with test profile
snakemake --unlock && snakemake afbench --profile profiles/test

# Production workflow - run tournament pipeline with production profile
snakemake --unlock && snakemake afbench --profile profiles/production
```

**Expected Output**: Runs the complete AFBench tournament evaluation pipeline and prints final results table to console.

#### Unlock Workflow
```bash
# Unlock workflow (needed when previous runs were interrupted)
snakemake --unlock

# Then run any command
snakemake --profile profiles/test
```

**When to use `--unlock`**: 
- After interrupted pipeline runs
- When switching between profiles
- When Snakemake shows "WorkflowError: Directory cannot be locked"
- As standard practice before running AFBench rule

### Workflow Visualization

```bash
# Generate dependency graph (requires graphviz)
snakemake --dag | dot -Tpng > workflow_dag.png

# Alternative: Generate simpler rule graph
snakemake --rulegraph | dot -Tpng > rules_dag.png
```

**Expected Output**: PNG files showing pipeline dependencies and rule relationships.

## Configuration

### Profile Configuration

AFBench uses profile-based configuration for different environments:

#### Test Profile (`profiles/test/config.yaml`)
- **Single core execution** for fast development
- **Verbose output** with shell command printing
- **Keep-going enabled** to continue on errors
- **Uses test model/judge pools** with lightweight models

#### Production Profile (`profiles/production/config.yaml`) 
- **Multi-core execution (4 cores)** for performance
- **Quiet execution** without shell command printing
- **Stop on first error** for production safety
- **Uses production model/judge pools** with high-quality models

### Environment-Specific Configuration Files

#### Test Configuration (`config/test_config.yaml`)
```yaml
model_pool:
  default_pool: "test"
  pools_dir: "model_pools"

judge_pool:
  default_pool: "test"
  pools_dir: "judge_pools"

# Smaller samples for faster testing
n_samples: 100
processing:
  remove_outliers: true
  outlier_threshold: 3.0

# Faster analysis settings
analysis:
  significance_level: 0.05

# Lower resolution plots
plotting:
  dpi: 150
```

#### Production Configuration (`config/production_config.yaml`)
```yaml
model_pool:
  default_pool: "production"
  pools_dir: "model_pools"

judge_pool:
  default_pool: "production"
  pools_dir: "judge_pools"

# Full samples for comprehensive evaluation
n_samples: 10000
processing:
  remove_outliers: true
  outlier_threshold: 2.0

# Stricter analysis settings
analysis:
  significance_level: 0.01

# High resolution plots
plotting:
  dpi: 300
```

### Legacy Configuration (`config/config.yaml`)

For backwards compatibility, the main configuration file can still be used:

```yaml
model_pool:
  default_pool: "test"     # Options: test, production
  pools_dir: "model_pools"

judge_pool:
  default_pool: "test"     # Options: test, production
  pools_dir: "judge_pools"

skills:
  skills_dir: "skills"
  selected_skills: []      # Empty = all skills, or specify: ["skill1", "skill2"]
```

## Pipeline Stages

### Stage 1: Data Loading

Load models, judges, and skills from configuration files.

#### Profile-Based Loading (Recommended)
```bash
# Load models using test profile
snakemake --profile profiles/test data/loaded_models.json

# Load judges using production profile
snakemake --profile profiles/production data/loaded_judges.json

# Load skills (same across profiles)
snakemake --profile profiles/test data/loaded_skills.json
```

#### Legacy Loading
```bash
# Load just the models (legacy method)
snakemake --cores 1 data/loaded_models.json

# Load just the judges (legacy method)
snakemake --cores 1 data/loaded_judges.json

# Load just the skills (legacy method)
snakemake --cores 1 data/loaded_skills.json
```

**Expected Output**: 
- `data/loaded_models.json`: Available AI models with their configurations (different pools per profile)
- `data/loaded_judges.json`: Judge models for evaluation (different pools per profile)
- `data/loaded_skills.json`: Evaluation scenarios and prompts (consistent across profiles)

### Stage 2: Conversation Execution

Execute conversations between models and evaluation scenarios.

#### Profile-Based Execution
```bash
# Run conversation generation with test profile (faster)
snakemake --profile profiles/test data/conversations.json

# Run conversation generation with production profile (comprehensive)
snakemake --profile profiles/production data/conversations.json
```

#### Legacy Execution
```bash
# Run conversation generation (legacy method)
snakemake --cores 4 data/conversations.json
```

**Expected Output**: 
- `data/conversations.json`: Raw conversation data between models and skills
- `data/conversations/`: Individual conversation files organized by skill category

### Stage 3: Tournament System

Conduct Swiss-system tournaments between models.

#### Profile-Based Tournament Execution
```bash
# Run tournaments with test profile (small model pool)
snakemake --profile profiles/test data/tournaments.json

# Generate tournament summaries with production profile
snakemake --profile profiles/production data/tournament_summaries.json
```

#### Legacy Tournament Execution
```bash
# Run tournaments (legacy method)
snakemake --cores 4 data/tournaments.json

# Generate tournament summaries (legacy method)
snakemake --cores 4 data/tournament_summaries.json
```

**Expected Output**:
- `data/tournaments.json`: Raw tournament match data
- `data/tournaments/`: Individual tournament files by skill
- `data/tournament_summaries.json`: Processed tournament results with rankings

### Stage 4: Skill Rating Calculation

Calculate OpenSkill Bradley-Terry ratings for each model.

#### Profile-Based Rating Calculation
```bash
# Calculate skill ratings with test profile
snakemake --profile profiles/test data/skill_ratings.json

# Calculate skill ratings with production profile (stricter analysis)
snakemake --profile profiles/production data/skill_ratings.json
```

#### Legacy Rating Calculation
```bash
# Calculate skill ratings (legacy method)
snakemake --cores 4 data/skill_ratings.json
```

**Expected Output**:
- `data/skill_ratings.json`: Comprehensive skill ratings for all models
- `data/skill_ratings/`: Individual rating files by skill category

### Stage 5: Reporting and Visualization

Generate final analysis and visualizations.

#### Profile-Based Reporting
```bash
# Generate analysis with test profile (lower resolution, faster)
snakemake --profile profiles/test output/results/analysis_results.json

# Create high-resolution plots with production profile
snakemake --profile profiles/production output/plots/summary_plot.png

# Generate comprehensive final report
snakemake --profile profiles/production output/results/final_report.json
```

#### Legacy Reporting
```bash
# Generate analysis results (legacy method)
snakemake --cores 2 output/results/analysis_results.json

# Create plots (legacy method)
snakemake --cores 1 output/plots/summary_plot.png

# Generate final report (legacy method)
snakemake --cores 1 output/results/final_report.json
```

**Expected Output**:
- `output/results/analysis_results.json`: Statistical analysis of model performance
- `output/plots/summary_plot.png`: Visualization of results (resolution varies by profile)
- `output/results/final_report.json`: Comprehensive final report

## Individual Rule Execution

### Force Rerun Specific Rules

#### Profile-Based Force Rerun
```bash
# Force rerun model loading with test profile (when model pools change)
snakemake --profile profiles/test --forcerun load_models data/loaded_models.json

# Force rerun conversations with production profile (when skills change)
snakemake --profile profiles/production --forcerun execute_conversations data/conversations.json

# Force rerun tournaments with specific profile (for different tournament settings)
snakemake --profile profiles/test --forcerun run_tournaments data/tournaments.json
```

#### Legacy Force Rerun
```bash
# Force rerun model loading (useful when model pools change)
snakemake --cores 1 --forcerun load_models data/loaded_models.json

# Force rerun conversations (useful when skills change)  
snakemake --cores 4 --forcerun execute_conversations data/conversations.json

# Force rerun tournaments (useful for different tournament settings)
snakemake --cores 4 --forcerun run_tournaments data/tournaments.json
```

### Target Specific Outputs

#### Profile-Based Targeting
```bash
# Generate only tournament results with test profile
snakemake --profile profiles/test data/tournaments.json data/tournament_summaries.json

# Generate only skill ratings with production profile
snakemake --profile profiles/production data/skill_ratings.json

# Generate only high-resolution visualizations
snakemake --profile profiles/production output/plots/summary_plot.png
```

#### Legacy Targeting
```bash
# Generate only tournament results (legacy method)
snakemake --cores 4 data/tournaments.json data/tournament_summaries.json

# Generate only skill ratings (legacy method)
snakemake --cores 4 data/skill_ratings.json

# Generate only visualizations (legacy method)
snakemake --cores 2 output/plots/summary_plot.png
```

### Clean and Restart

```bash
# Clean all generated files
snakemake clean

# Or manually clean specific directories
rm -rf data/ output/
```

## Troubleshooting

### Common Issues

#### Missing Dependencies

```bash
# Install required Python packages
pip install -r requirements.txt
```

#### Configuration Errors

```bash
# Validate test profile configuration
snakemake --profile profiles/test --dry-run

# Validate production profile configuration
snakemake --profile profiles/production --dry-run

# Validate legacy configuration
snakemake --dry-run --configfile config/config.yaml
```

#### Workflow Validation

```bash
# Check for syntax errors
snakemake --lint

# Validate file existence with specific profile
snakemake --profile profiles/test --summary

# Validate file existence (legacy)
snakemake --summary
```

#### Debug Mode

```bash
# Run with verbose output using test profile (already includes printshellcmds)
snakemake --profile profiles/test --verbose

# Run with debugging information
snakemake --profile profiles/production --debug-dag

# Legacy debug mode
snakemake --cores 4 --verbose --debug-dag
```

### Performance Tuning

#### Profile-Based Performance
```bash
# Test profile is optimized for speed (1 core, continue on errors)
snakemake --profile profiles/test

# Production profile is optimized for thoroughness (4 cores, stop on errors)
snakemake --profile profiles/production

# Override production profile to use more cores
snakemake --profile profiles/production --cores 8
```

#### Legacy Performance Tuning
```bash
# Use more cores for parallel execution
snakemake --cores 8

# Limit resource usage
snakemake --cores 4 --resources mem_mb=4000

# Run specific compute-intensive rules with more resources
snakemake --cores 8 data/tournaments.json
```

### Profile-Specific Issues

#### Test Profile Issues
- **Faster execution** but may miss edge cases
- **Continues on errors** which may hide problems
- **Smaller sample sizes** may not be representative
- **Lower resolution plots** may miss details

#### Production Profile Issues  
- **Stops on first error** which is safer but may be frustrating during development
- **Higher resource usage** (4 cores, high-resolution plots)
- **Stricter analysis parameters** may be too conservative
- **Uses production model pools** which may be more expensive

## Output Structure

After successful pipeline execution:

```
data/
├── conversations.json              # Raw conversation data
├── conversations/                  # Individual conversations by skill
│   ├── code_generation/
│   ├── document_summarization/
│   ├── persuasiveness/
│   └── respect_no_em_dash_requests/
├── loaded_judges.json             # Judge configurations
├── loaded_models.json             # Model configurations  
├── loaded_skills.json             # Skill definitions
├── skill_ratings.json             # Final skill ratings
├── skill_ratings/                 # Individual rating files
├── tournament_summaries.json      # Tournament results
└── tournaments.json               # Raw tournament data

output/
├── plots/
│   └── summary_plot.png          # Performance visualization
└── results/
    ├── analysis_results.json     # Statistical analysis
    └── final_report.json         # Comprehensive report
```

## Static Site Generation

Generate a web interface for reviewing results:

```bash
cd site
./run.sh
```

**Expected Output**: Static site available for viewing evaluation results, typically served on localhost.

This creates a user-friendly interface for exploring model performance, tournament results, and skill ratings.

## Profile Usage Recommendations

### Development Workflow
1. **Start with test profile** for rapid iteration:
   ```bash
   # Most common development command
   snakemake --unlock && snakemake afbench --profile profiles/test
   ```

2. **Switch to production** for final evaluation:
   ```bash
   # Production tournament evaluation  
   snakemake --unlock && snakemake afbench --profile profiles/production
   ```

3. **Alternative: Full pipeline** (less common):
   ```bash
   # Complete pipeline including data generation and visualization
   snakemake --profile profiles/test
   ```

### When to Use Each Profile

#### Use Test Profile For:
- **Development and debugging** - fast feedback loop
- **Skill validation** - quickly test new evaluation scenarios
- **Pipeline testing** - verify workflow changes
- **Cost management** - use cheaper/faster models during development

#### Use Production Profile For:
- **Final evaluation** - comprehensive model assessment
- **Publication results** - high-quality, rigorous analysis
- **Benchmarking** - standardized evaluation conditions
- **Performance comparison** - consistent evaluation parameters

### Cache Isolation

Each profile maintains separate cache files since they use different model/judge pools, ensuring:
- **No cross-contamination** between test and production data
- **Reproducible results** within each environment
- **Independent execution** - can run both profiles simultaneously

### Current Model Pools

#### Test Pool (4 models, 3 judges)
**Models:**
- thedrummer/unslopnemo-12b
- openai/gpt-oss-120b  
- inception/mercury
- openai/gpt-oss-20b

**Judges:** Lightweight judge models for fast evaluation

#### Production Pool (2 models, 1 judge)  
**Models:**
- openai/gpt-4-turbo
- anthropic/claude-3-5-sonnet-20241022

**Judges:** High-quality judge models for rigorous evaluation

### Managing Model/Judge Pools

#### Adding Models to Test Environment
```bash
# Edit the test model pool
vim model_pools/test.csv

# Edit the test judge pool  
vim judge_pools/test.csv
```

#### Adding Models to Production Environment
```bash
# Edit the production model pool
vim model_pools/production.csv

# Edit the production judge pool
vim judge_pools/production.csv
```

**Note:** After editing pool files, run `snakemake --unlock` before your next execution to ensure proper cache invalidation.

### Mixed Profile Usage

```bash
# Develop with test profile
snakemake --profile profiles/test data/skill_ratings.json

# Generate production-quality plots from test data
snakemake --profile profiles/production output/plots/summary_plot.png

# Compare results between profiles
snakemake --profile profiles/test data/tournaments.json
snakemake --profile profiles/production data/tournaments.json
```