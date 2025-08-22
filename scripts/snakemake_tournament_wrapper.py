#!/usr/bin/env python3
"""
Data-driven tournament wrapper that fixes the restart loop bug.

Instead of being config-driven (only processing skills in loaded_skills.json),
this wrapper is data-driven (processes any skills with conversations but no tournaments).

This fixes the restart loop where pipeline gets stuck after partial completion.
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from run_tournaments import main_with_cache_dir_data_driven
from tournament_restart_detector import detect_tournament_restart_work

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(
            "Usage: python snakemake_tournament_wrapper.py <conversations_dir> <models_file> <judges_file> <skills_file> <output_file>"
        )
        sys.exit(1)

    conversations_dir = sys.argv[1]
    models_file = sys.argv[2]
    judges_file = sys.argv[3]
    skills_file = sys.argv[4]
    output_file = sys.argv[5]

    # CRITICAL FIX: Detect unprocessed tournament work from data, not config
    print("🔍 Detecting tournament restart requirements...")
    restart_status = detect_tournament_restart_work(conversations_dir, output_file)

    if not restart_status["should_run_tournaments"]:
        print("✅ All skills with conversations have completed tournaments")
        print(f"   Skills processed: {restart_status['tournament_skills']}")
        # Still need to call main function to generate output file if missing
        if not Path(output_file).exists():
            main_with_cache_dir_data_driven(
                conversations_dir, models_file, judges_file, skills_file, output_file
            )
    else:
        print(
            f"⚠️  Tournament restart needed: {restart_status['total_unprocessed']} skills unprocessed"
        )
        print(f"   Unprocessed skills: {restart_status['unprocessed_skills']}")
        print("   Processing tournaments for all skills with conversations...")

        # Run data-driven tournament generation (processes all skills with conversations)
        main_with_cache_dir_data_driven(
            conversations_dir, models_file, judges_file, skills_file, output_file
        )
