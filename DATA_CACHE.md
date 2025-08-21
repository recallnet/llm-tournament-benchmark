# AFBench Data Cache Architecture

Comprehensive documentation of AFBench pipeline data flow, cache invalidation, and recovery procedures.

## Table of Contents
- [Pipeline Overview](#pipeline-overview)
- [Input Files](#input-files)
- [Pipeline Stages](#pipeline-stages)  
- [Output Files](#output-files)
- [Cache Architecture](#cache-architecture)
- [Cache Invalidation Scenarios](#cache-invalidation-scenarios)
- [Recovery Procedures](#recovery-procedures)
- [Known Issues](#known-issues)

## Pipeline Overview

AFBench uses a multi-stage pipeline to evaluate AI models through tournament-style competitions:

```
Input Data → Conversation Generation → Tournament Execution → Skill Rating → Results
```

The pipeline is designed to cache intermediate results to avoid expensive API calls and computation when rerunning.

## Input Files

### Configuration Files
- **`model_pools/*.csv`** - Define which models to evaluate
- **`judge_pools/*.csv`** - Define which models act as judges  
- **`skills/*/*.json`** - Evaluation scenarios organized by skill category
- **`.env.local`** - API keys (OPENROUTER_API_KEY)

### Loaded Configuration (Generated)
- **`data/loaded_models.json`** - Active models for evaluation
- **`data/loaded_judges.json`** - Active judge models
- **`data/loaded_skills.json`** - Active evaluation scenarios

**Dependencies**: If model/judge pools or skills change, these files are regenerated.

## Pipeline Stages

### Stage 1: Data Loading
**Purpose**: Load and validate configurations
**Rules**: `load_models`, `load_judges`, `load_skills`
**Triggers**: Changes to pool files or skill definitions

### Stage 2: Conversation Execution  
**Purpose**: Generate model responses to evaluation scenarios
**Rules**: `execute_conversations_for_model` (parallel)
**Cache**: `data/conversations/` - Individual conversation files
**Markers**: `data/conversations_cache_*.done` - Per-model completion markers

**Parallelization**: Each model processes all evaluations independently, enabling parallel execution.

### Stage 3: Tournament Execution
**Purpose**: Run Swiss-system tournaments using judge consensus
**Rules**: `run_tournaments`
**Input Cache**: `data/conversations/` (conversation responses)
**Judge Cache**: `data/tournaments/` (judge decisions by skill)
**Output**: `data/tournaments.json` (tournament results)

**🚨 CRITICAL ISSUE**: Judge cache directory conflicts with tournaments.json location!

### Stage 4: Tournament Analysis
**Purpose**: Summarize tournament results and calculate skill ratings
**Rules**: `summarize_tournaments`, `calculate_skill_ratings`
**Dependencies**: `tournaments.json` → `tournament_summaries.json` → `skill_ratings.json`

### Stage 5: Results Generation
**Purpose**: Generate final outputs and leaderboards  
**Rules**: `afbench`, `print_results`
**Output**: Console results table

## Output Files

### Core Results
- **`data/tournaments.json`** - Raw tournament match results with judge decisions
- **`data/tournament_summaries.json`** - Processed tournament summaries with rankings  
- **`data/skill_ratings.json`** - OpenSkill Bradley-Terry ratings per model per skill
- **`data/final_results.json`** - Combined results for web interface

### Web Interface Data
- **`data/openrouter_models_*.json`** - Model metadata for dashboard
- Generated HTML/static site files (via separate process)

## Cache Architecture

### Conversation Cache
```
data/conversations/
├── harm_avoidance/
│   ├── social_media_manipulation_model1_hash.json
│   └── crisis_management_surveillance_model2_hash.json
├── code_generation/
│   ├── conways_game_of_life_model1_hash.json
│   └── flight_simulator_model2_hash.json
└── [8 total skills...]
```

**Cache Key**: `{eval_id}_{sanitized_model_id}_{content_hash}.json`
**Content**: Full conversation with metadata
**Invalidation**: Model changes, skill changes, or explicit cleanup

### Judge Decision Cache
```
data/tournaments/
├── harm_avoidance/
│   ├── {match_id}_{judge_id}_{cache_key}.json
│   └── {match_id}_{judge_id}_{cache_key}.json
└── [should have 8 skills but currently only harm_avoidance...]
```

**Cache Key**: Based on match details + judge + final prompt
**Content**: Judge vote, conversation, explanation, metadata
**Invalidation**: Model/judge/eval changes

### Cache Markers
```
data/conversations_cache_{sanitized_model_id}.done
```
**Purpose**: Indicate completion of conversation execution for a model
**Content**: Simple text confirmation
**Used By**: Snakemake dependency tracking

## Cache Invalidation Scenarios

### Scenario 1: Model Pool Changes
**Trigger**: Edit `model_pools/*.csv`
**Invalidated**: 
- `data/loaded_models.json`
- All conversation cache for removed models
- All judge cache involving removed models  
- All tournament results

**Pipeline Reruns**: Complete pipeline from conversation execution

### Scenario 2: Skill Definition Changes  
**Trigger**: Edit `skills/*/*.json`
**Invalidated**:
- `data/loaded_skills.json`
- Conversation cache for modified skills
- Tournament results for affected skills

**Pipeline Reruns**: Conversations for affected skills → tournaments → ratings

### Scenario 3: Judge Pool Changes
**Trigger**: Edit `judge_pools/*.csv`
**Invalidated**:
- `data/loaded_judges.json`  
- All judge decision cache
- All tournament results

**Pipeline Reruns**: Tournaments (reuses conversation cache) → ratings

### Scenario 4: tournaments.json Only Missing
**Current State**: Most common broken state
**Symptoms**: 
- ✅ Conversation cache complete
- ✅ Cache markers exist
- ❌ `tournaments.json` missing
- ✅ `tournament_summaries.json` exists (inconsistent!)

**Should Rerun**: Only tournament execution
**Currently Fails**: Due to Snakemake rule silent failure

## Recovery Procedures

### Atomic Cache Invalidation Groups

**Group 1: Conversation Phase**
```bash
# Clean conversation data
rm -rf data/conversations/
rm -f data/conversations_cache_*.done
```

**Group 2: Tournament Phase** 
```bash
# Clean tournament data  
rm -f data/tournaments.json
rm -f data/tournament_summaries.json
rm -f data/skill_ratings.json
rm -rf data/tournaments/  # Judge cache
```

**Group 3: Complete Reset**
```bash
# Nuclear option
rm -rf data/
```

### Recovery Commands

**Fix Current Broken State** (tournaments.json missing):
```bash
# Option 1: Clean tournament phase atomically
rm -f data/tournament_summaries.json data/skill_ratings.json
snakemake afbench --profile profiles/test -j 5

# Option 2: Force tournament regeneration (after fixing Snakemake rule)
snakemake --forcerun run_tournaments data/tournaments.json --profile profiles/test
```

**Conversation Cache Regeneration**:
```bash
# Clean conversation data
rm -rf data/conversations/ data/conversations_cache_*.done

# Regenerate with parallel execution
snakemake afbench --profile profiles/test -j 5
```

**Complete Pipeline Reset**:
```bash
# Clean all generated data
rm -rf data/

# Full regeneration
snakemake afbench --profile profiles/test -j 5
```

## Known Issues

### Critical Issues (Blocking Pipeline)

#### Issue 1: Judge Cache Directory Conflict
**Problem**: `JudgeExecutor.cache_dir = "data/tournaments"` conflicts with `tournaments.json` location
**Impact**: Tournament generation fails silently  
**Status**: 🚨 **BLOCKING** - Pipeline cannot complete
**Fix Required**: Move judge cache to separate directory (e.g., `data/judge_cache/`)

#### Issue 2: Snakemake Silent Failures
**Problem**: `run:` directive doesn't properly handle Python exceptions
**Impact**: Rules appear to succeed but produce no output
**Status**: 🚨 **BLOCKING** - Broken rules go undetected
**Fix Required**: Replace `run:` with `script:` directive

#### Issue 3: Non-Atomic Cache Invalidation
**Problem**: Downstream files exist without upstream dependencies
**Impact**: Inconsistent pipeline state, confusing behavior
**Status**: 🚨 **HIGH PRIORITY** - Causes confusion and debugging difficulty
**Fix Required**: Implement atomic invalidation groups

### Performance Issues

#### Issue 4: Tournament Generation Scale
**Problem**: 1,620 total judge decisions needed across 270 matches × 6 judges
**Impact**: Very slow tournament execution (can take >30 minutes)
**Status**: ⚠️ **PERFORMANCE** - Functional but slow
**Mitigation**: Judge decision caching works well when it doesn't fail

#### Issue 5: Cache Coverage Incomplete  
**Problem**: Only 178/1,620 judge decisions cached (11% coverage, harm_avoidance only)
**Impact**: Most tournament work needs to be redone
**Status**: ⚠️ **EFFICIENCY** - Related to Issue 1
**Fix**: Resolve judge cache directory conflict

### Data Consistency Issues

#### Issue 6: Missing tournaments.json but Downstream Exists
**Problem**: `tournament_summaries.json` and `skill_ratings.json` exist without `tournaments.json`
**Impact**: Logical impossibility, indicates cache corruption
**Status**: 🚨 **DATA INTEGRITY** - Current broken state  
**Fix**: Implement atomic cache invalidation

## Validation Checklist

### Healthy Pipeline State
- [ ] All input files exist (`data/loaded_*.json`)
- [ ] Cache markers exist for all models (`data/conversations_cache_*.done`)
- [ ] Conversation cache has files for all 8 skills
- [ ] `tournaments.json` exists and contains tournaments for all skills
- [ ] Tournament summaries and skill ratings exist
- [ ] Judge cache has decisions for all 8 skills (not just harm_avoidance)

### Broken States to Detect
- [ ] ❌ `tournaments.json` missing but summaries exist
- [ ] ❌ Only harm_avoidance has judge cache
- [ ] ❌ Cache markers exist but no conversation cache
- [ ] ❌ Downstream files newer than upstream files

### Recovery Test
After any cache invalidation:
```bash
# This should complete successfully
snakemake afbench --profile profiles/test -j 5 

# Verify all outputs exist
ls -la data/tournaments.json data/tournament_summaries.json data/skill_ratings.json

# Verify judge cache coverage
find data/tournaments/ -name "*.json" | wc -l  # Should be much more than 178
ls data/tournaments/  # Should show 8 skill directories, not just harm_avoidance
```

---

**Last Updated**: Based on TDD analysis revealing judge cache directory conflict as root cause
**Pipeline Version**: Post-parallelization architecture with direct cache access
**Status**: 🚨 **CRITICAL ISSUES IDENTIFIED** - Pipeline cannot complete tournaments for all skills