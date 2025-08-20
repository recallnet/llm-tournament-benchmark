"""
AFBench Snakemake workflow

A modular data processing pipeline with rigorous QA standards.
"""

import pandas as pd
from pathlib import Path

# Configuration
configfile: "config/config.yaml"

# Define output directories
OUTPUT_DIR = Path("output")
DATA_DIR = Path("data")
RESULTS_DIR = OUTPUT_DIR / "results"
PLOTS_DIR = OUTPUT_DIR / "plots"

# Ensure directories exist
Path.mkdir(OUTPUT_DIR, exist_ok=True)
Path.mkdir(DATA_DIR, exist_ok=True)
Path.mkdir(RESULTS_DIR, exist_ok=True)
Path.mkdir(PLOTS_DIR, exist_ok=True)

# Define final outputs
rule all:
    input:
        DATA_DIR / "skill_ratings.json"

# AFBench tournament pipeline
rule afbench:
    input:
        DATA_DIR / "skill_ratings.json"
    shell:
        "python scripts/print_results_table.py"

# Load model pool (first stage)
rule load_models:
    output:
        DATA_DIR / "loaded_models.json"
    params:
        pool_name=config.get("model_pool", {}).get("default_pool", "test"),
        pools_dir=config.get("model_pool", {}).get("pools_dir", "model_pools")
    script:
        "scripts/load_models.py"

# Load judge pool
rule load_judges:
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
    return glob.glob("skills/*/*.json")

rule load_skills:
    input:
        # Dynamically find all skill JSON files to trigger reload when they change
        get_all_skill_files()
    output:
        DATA_DIR / "loaded_skills.json"
    params:
        skills_dir=config.get("skills", {}).get("skills_dir", "skills"),
        selected_skills=config.get("skills", {}).get("selected_skills", None)
    script:
        "scripts/load_skills.py"

# Execute conversations between models and evals
rule execute_conversations:
    input:
        models=DATA_DIR / "loaded_models.json",
        skills=DATA_DIR / "loaded_skills.json",
        judges=DATA_DIR / "loaded_judges.json"
    output:
        DATA_DIR / "conversations.json"
    script:
        "scripts/execute_conversations.py"

# Run Swiss tournaments for model evaluation
rule run_tournaments:
    input:
        conversations=DATA_DIR / "conversations.json",
        models=DATA_DIR / "loaded_models.json",
        judges=DATA_DIR / "loaded_judges.json",
        skills=DATA_DIR / "loaded_skills.json"
    output:
        DATA_DIR / "tournaments.json"
    script:
        "scripts/run_tournaments.py"

# Summarize tournaments with match history and rankings
rule summarize_tournaments:
    input:
        tournaments=DATA_DIR / "tournaments.json",
        models=DATA_DIR / "loaded_models.json",
        judges=DATA_DIR / "loaded_judges.json",
        skills=DATA_DIR / "loaded_skills.json"
    output:
        DATA_DIR / "tournament_summaries.json"
    script:
        "scripts/summarize_tournaments.py"

# Calculate skill ratings using OpenSkill Bradley-Terry system
rule calculate_skill_ratings:
    input:
        summaries=DATA_DIR / "tournament_summaries.json",
        models=DATA_DIR / "loaded_models.json",
        judges=DATA_DIR / "loaded_judges.json",
        skills=DATA_DIR / "loaded_skills.json"
    output:
        DATA_DIR / "skill_ratings.json"
    script:
        "scripts/calculate_skill_ratings.py"

# Print final results table
rule print_results:
    input:
        DATA_DIR / "skill_ratings.json"
    shell:
        "python scripts/print_results_table.py"


# Clean intermediate files
rule clean:
    shell:
        "rm -rf data/ output/"