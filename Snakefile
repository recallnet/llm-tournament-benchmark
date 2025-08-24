"""
AFBench Snakemake workflow - Proper file-based dependencies

Uses the existing conversation execution system with native Snakemake caching.
Snakemake automatically handles incremental updates based on file timestamps.
"""

import sys
import pandas as pd
from pathlib import Path

# Configuration
configfile: "config/config.yaml"

# Define output directories  
OUTPUT_DIR = Path("output")
DATA_DIR = Path(config.get("data_dir", "tests/data"))
RESULTS_DIR = OUTPUT_DIR / "results"
PLOTS_DIR = OUTPUT_DIR / "plots"

# Ensure directories exist
try:
    Path.mkdir(OUTPUT_DIR, exist_ok=True)
    Path.mkdir(DATA_DIR, exist_ok=True)
    Path.mkdir(RESULTS_DIR, exist_ok=True)
    Path.mkdir(PLOTS_DIR, exist_ok=True)
except FileNotFoundError:
    # During dry runs or parsing, parent dirs might not exist - that's OK
    pass

# Define final outputs
rule all:
    input:
        DATA_DIR / "final_results.json",
        DATA_DIR / "benchmarks.json"

# AFBench tournament pipeline
rule afbench:
    input:
        DATA_DIR / "skill_ratings.json"
    shell:
        "python scripts/print_results_table.py {DATA_DIR}"

# Load model pool
rule load_models:
    input:
        lambda wildcards: f"{config.get('model_pool', {}).get('pools_dir', 'model_pools')}/{config.get('model_pool', {}).get('default_pool', 'test')}.csv"
    output:
        DATA_DIR / "loaded_models.json"
    params:
        pool_name=config.get("model_pool", {}).get("default_pool", "test"),
        pools_dir=config.get("model_pool", {}).get("pools_dir", "model_pools")
    script:
        "scripts/load_models.py"

# Load judge pool
rule load_judges:
    input:
        lambda wildcards: f"{config.get('judge_pool', {}).get('pools_dir', 'judge_pools')}/{config.get('judge_pool', {}).get('default_pool', 'test')}.csv"
    output:
        DATA_DIR / "loaded_judges.json"
    params:
        pool_name=config.get("judge_pool", {}).get("default_pool", "test"),
        pools_dir=config.get("judge_pool", {}).get("pools_dir", "judge_pools")
    script:
        "scripts/load_judges.py"

# Load skills and evals
def get_all_skill_files():
    """Dynamically find all skill JSON files."""
    import glob
    skills_dir = config.get("skills", {}).get("skills_dir", "skills")
    return glob.glob(f"{skills_dir}/*/*.json")

rule load_skills:
    input:
        get_all_skill_files()
    output:
        DATA_DIR / "loaded_skills.json"
    params:
        skills_dir=config.get("skills", {}).get("skills_dir", "skills"),
        selected_skills=config.get("skills", {}).get("selected_skills", None)
    script:
        "scripts/load_skills.py"

# Helper function to get model IDs for parallel execution  
def get_model_ids():
    """Get sanitized model IDs from model pool CSV file."""
    # Read directly from CSV to avoid chicken-and-egg problem
    pool_file = f"{config.get('model_pool', {}).get('pools_dir', 'model_pools')}/{config.get('model_pool', {}).get('default_pool', 'test')}.csv"
    
    try:
        import pandas as pd
        df = pd.read_csv(pool_file)
        model_ids = df['id'].tolist()
        # Sanitize for filenames
        return [model_id.replace("/", "_").replace(":", "_") for model_id in model_ids]
    except (FileNotFoundError, KeyError, ImportError):
        # Fallback to empty list if CSV doesn't exist or has issues
        return []

# Helper function to get skill names for parallel tournament execution
def get_skills():
    """Get skill names from loaded_skills.json for parallel tournament wildcards."""
    skills_file = DATA_DIR / "loaded_skills.json"
    
    try:
        import json
        with open(skills_file) as f:
            skills_data = json.load(f)
        # Extract skill names from the skills section
        skill_names = list(skills_data.get("skills", {}).keys())
        return skill_names
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Fallback: try to infer from conversations directory
        try:
            conversations_dir = DATA_DIR / "conversations"
            if conversations_dir.exists():
                # Get skill names from subdirectories
                return [d.name for d in conversations_dir.iterdir() if d.is_dir()]
        except:
            pass
        # Final fallback to common skills
        return ["code_generation", "harm_avoidance", "empathy", "hidden_messages"]

# Execute conversations for each model in parallel with per-model serialization
rule execute_conversations_for_model:
    input:
        models=DATA_DIR / "loaded_models.json",
        skills=DATA_DIR / "loaded_skills.json", 
        judges=DATA_DIR / "loaded_judges.json"
    output:
        DATA_DIR / "model_conversations_{model_id}.completed"
    params:
        original_model_id=lambda wildcards: wildcards.model_id.replace('_', '/', 1).replace('_', ':', 1)
    resources:
        # CRITICAL: Enforce per-model serialization - only one conversation generation per model at a time
        # This creates a dynamic resource constraint based on the model_id
        model_lock=lambda wildcards: f"model_{wildcards.model_id}"
    threads: 1  # Single-threaded per model to prevent internal concurrency
    shell:
        "python scripts/execute_conversations_standalone.py {input.models} {input.skills} {input.judges} {params.original_model_id} {DATA_DIR}/conversations {DATA_DIR}/intermediaries && touch {output}"

# Aggregate all model completions into single flag
rule execute_conversations:
    input:
        # Depend on all per-model completion markers
        lambda wildcards: [DATA_DIR / f"model_conversations_{model_id}.completed" 
                          for model_id in get_model_ids()]
    output:
        DATA_DIR / "conversations_completed.flag"
    shell:
        "touch {output}"

# Run Swiss tournaments per skill in parallel - depends on conversations being completed
rule run_tournament_per_skill:
    input:
        flag=DATA_DIR / "conversations_completed.flag",
        models=DATA_DIR / "loaded_models.json",
        judges=DATA_DIR / "loaded_judges.json", 
        skills=DATA_DIR / "loaded_skills.json"
    params:
        conversations_dir=DATA_DIR / "conversations"
    output:
        DATA_DIR / "tournament_{skill}.json"
    wildcard_constraints:
        skill="[a-z_]+"
    shell:
        "python scripts/run_single_skill_tournament.py {wildcards.skill} {params.conversations_dir} {input.models} {input.judges} {input.skills} {output}"

# Aggregate per-skill tournament results into single tournaments.json
rule aggregate_tournaments:
    input:
        lambda wildcards: [DATA_DIR / f"tournament_{skill}.json" for skill in get_skills()]
    output:
        DATA_DIR / "tournaments.json"
    shell:
        "python scripts/aggregate_tournament_results.py {input} {output}"

# Summarize tournaments
rule summarize_tournaments:
    input:
        tournaments=DATA_DIR / "tournaments.json",
        models=DATA_DIR / "loaded_models.json",
        judges=DATA_DIR / "loaded_judges.json",
        skills=DATA_DIR / "loaded_skills.json"
    output:
        DATA_DIR / "tournament_summaries.json"
    shell:
        "python scripts/snakemake_summarize_wrapper.py {input.tournaments} {output}"

# Calculate skill ratings
rule calculate_skill_ratings:
    input:
        summaries=DATA_DIR / "tournament_summaries.json",
        models=DATA_DIR / "loaded_models.json",
        judges=DATA_DIR / "loaded_judges.json",
        skills=DATA_DIR / "loaded_skills.json"
    output:
        DATA_DIR / "skill_ratings.json"
    shell:
        "{sys.executable} scripts/snakemake_ratings_wrapper.py {input.summaries} {input.models} {input.judges} {input.skills} {output}"

# Generate final results - always run (never cached)
rule generate_final_results:
    input:
        skills=DATA_DIR / "loaded_skills.json",
        ratings=DATA_DIR / "skill_ratings.json"  # Ensure this runs after ratings
    output:
        DATA_DIR / "final_results.json"
    params:
        data_dir=DATA_DIR
    shell:
        "AFBENCH_DATA_DIR={params.data_dir} python scripts/generate_final_results.py"

# Generate benchmarks leaderboard - always run (never cached)
rule generate_benchmarks:
    input:
        skills=DATA_DIR / "loaded_skills.json",
        ratings=DATA_DIR / "skill_ratings.json",
        summaries=DATA_DIR / "tournament_summaries.json",
        models=DATA_DIR / "loaded_models.json",
        judges=DATA_DIR / "loaded_judges.json"
    output:
        DATA_DIR / "benchmarks.json"
    params:
        data_dir=DATA_DIR
    shell:
        "AFBENCH_DATA_DIR={params.data_dir} python scripts/generate_benchmarks.py"

# Clean intermediate files
rule clean:
    shell:
        "rm -rf data/ output/"