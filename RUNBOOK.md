# AFBench Runbook

Comprehensive guide to running the AFBench AI evaluation pipeline with Snakemake.

## Quick Start

```bash
# Development workflow (recommended)
snakemake --profile profiles/quick -j5 > pipeline_run.log 2>&1 &

# Production workflow
snakemake --profile profiles/production -j5 > pipeline_run.log 2>&1 &

# Monitor progress
tail -f pipeline_run.log
```

## Pipeline Overview

AFBench uses Snakemake to orchestrate a multi-stage AI model evaluation pipeline:

1. **Setup**: Load models, judges, and skills
2. **Execution**: Run conversations between models and evaluators (parallel by model)
3. **Tournament**: Conduct Swiss-system tournaments (parallel by skill)
4. **Analysis**: Calculate skill ratings and generate summaries
5. **Reporting**: Create visualizations and final reports

## Profile-Based Execution

### Quick Profile (Development)
```bash
# Start pipeline in background
snakemake --profile profiles/quick -j5 > pipeline_run.log 2>&1 &

# Monitor progress
tail -f pipeline_run.log

# Check status
ps aux | grep snakemake
```

**Configuration:**
- Uses lightweight models and judges for fast testing
- Parallel execution with 4 cores
- Verbose output for debugging
- Continues on errors for development iteration

### Production Profile (Full Evaluation)
```bash
# Start production pipeline in background
snakemake --profile profiles/production -j5 > pipeline_run.log 2>&1 &

# Monitor progress
tail -f pipeline_run.log

# Check cache growth (judge decisions)
find data/production/judge_cache -name "*.json" | wc -l
```

**Configuration:**
- Uses comprehensive model and judge pools (51 models, 3 judges)
- Parallel execution with 5 jobs max (be respectful of APIs)
- Stops on first error for production safety
- High-quality analysis parameters

## Pipeline Management

### Starting and Stopping

```bash
# Start pipeline
snakemake --profile profiles/production -j5 > pipeline_run.log 2>&1 &

# Find pipeline process
ps aux | grep snakemake

# Stop pipeline gracefully (if needed)
kill [PID]

# Emergency stop (if process is stuck)
kill -9 [PID]

# Unlock workflow after interruption
snakemake --unlock --profile profiles/production
```

### Monitoring Progress

```bash
# Monitor live output
tail -f pipeline_run.log

# Check recent tournament activity
tail -50 pipeline_run.log | grep -E "(🏟️|🎉|✅|❌)"

# Count completed tournaments
grep -c "🎉.*complete" pipeline_run.log

# Check cache growth over time
watch "find data/production/judge_cache -name '*.json' | wc -l"
```

### Restarting Safely

```bash
# Safe restart procedure
kill $(ps aux | grep snakemake | grep -v grep | awk '{print $2}')
snakemake --unlock --profile profiles/production
snakemake --profile profiles/production -j5 > pipeline_run.log 2>&1 &
```

The pipeline is designed for safe restarts - it will resume from where it left off using cached data.

## Parallel Execution

### Conversation Generation
- **Per-model parallelization**: Each model processes all evaluations independently
- **Automatic aggregation**: Results combined into unified format
- **Cache preservation**: Existing conversation cache files remain valid

### Tournament System
- **Per-skill parallelization**: Each skill runs tournaments independently  
- **Race condition safety**: Cache cleanup uses exclusive locking
- **Swiss tournaments**: Head-to-head model competitions with judge consensus

### Resource Management

```bash
# Recommended: Limit concurrent jobs to be respectful of APIs
snakemake --profile profiles/production -j5

# Conservative: Use fewer jobs if experiencing rate limits
snakemake --profile profiles/production -j2

# Check active processes
ps aux | grep "run_single_skill_tournament\|run_tournament_per_skill"
```

## Output Structure

```
data/[profile]/
├── conversations/                  # Individual conversations by skill
├── conversations.json             # Aggregated conversation data
├── judge_cache/                   # Cached judge decisions (critical!)
├── loaded_models.json            # Model configurations
├── loaded_judges.json            # Judge configurations
├── loaded_skills.json            # Skill definitions
├── tournament_[skill].json       # Per-skill tournament files
├── tournaments.json              # Aggregated tournament results
├── tournament_summaries.json     # Processed results
└── skill_ratings.json           # Final OpenSkill ratings
```

## Troubleshooting

### Common Issues

**Pipeline Won't Start**
```bash
# Check for locks
snakemake --unlock --profile profiles/production

# Validate configuration
snakemake --profile profiles/production --dry-run
```

**API Rate Limiting**
```bash
# Reduce parallelism
snakemake --profile profiles/production -j2

# Check OpenRouter API limits in your account
```

**Cache Issues**
```bash
# Check cache integrity
ls -la data/production/judge_cache/*/

# Never delete judge cache manually - it contains thousands of expensive API calls!
```

**Stale Processes**
```bash
# Find tournament processes
ps aux | grep "tournament"

# Kill specific stuck process (be careful!)
kill [PID]
```

### Performance Monitoring

```bash
# Check judge cache growth (should increase during tournaments)
watch "find data/production/judge_cache -name '*.json' | wc -l"

# Monitor active tournament processes
watch "ps aux | grep 'tournament' | wc -l"

# Check completed tournaments
grep "🎉.*complete" pipeline_run.log
```

### Data Safety

**Critical Files - Never Delete:**
- `data/[profile]/judge_cache/` - Contains thousands of expensive judge decisions
- `data/[profile]/conversations/` - Contains expensive conversation data

**Safe to Delete:**
- `pipeline_run.log` - Log files
- `data/[profile]/tournament_*.json` - Will regenerate from cache
- `data/[profile]/tournaments.json` - Will regenerate from cache

## Admin UI

View results in a web interface:

```bash
cd site

# Quick profile results
./run.sh

# Production profile results  
AFBENCH_ADMIN_DATA_DIR=data/production ./run.sh
```

Access at http://localhost:8501

## Profile Comparison

| Feature | Quick Profile | Production Profile |
|---------|---------------|-------------------|
| Models | 4 lightweight | 51 comprehensive |
| Judges | 3 fast | 3 high-quality |
| Execution | Fast iteration | Rigorous evaluation |
| Cost | Low | High |
| Use Case | Development | Final results |

## Best Practices

1. **Always use job limits** (`-j5`) to respect API services
2. **Monitor cache growth** to ensure tournaments are progressing
3. **Run in background** with log redirection for long evaluations
4. **Never delete judge cache** - it represents significant API costs
5. **Use quick profile** for development, production for final results
6. **Safe restart** by unlocking workflow after interruptions