#!/usr/bin/env python3
"""
Single-skill tournament execution script for parallel tournament processing.

This script runs tournaments for a specific skill, enabling parallel execution
of multiple skills simultaneously while maintaining full cache compatibility.

Usage:
    python run_single_skill_tournament.py <skill> <conversations_dir> <models_file> <judges_file> <skills_file> <output_file>
"""

import sys
import json
import os
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from run_tournaments import main_with_cache_dir_data_driven
from tournament_restart_detector import detect_tournament_restart_work


def filter_skills_for_single_skill(skills_data, target_skill):
    """
    Filter skills data to contain only the target skill.
    This ensures tournaments only run for the specified skill.
    """
    filtered_skills = {
        "load_info": skills_data["load_info"],
        "skills": {
            target_skill: skills_data["skills"][target_skill]
        } if target_skill in skills_data["skills"] else {},
        "evals": [
            eval_data for eval_data in skills_data["evals"]
            if eval_data.get("_metadata", {}).get("skill") == target_skill
        ]
    }
    return filtered_skills


def main():
    if len(sys.argv) != 7:
        print("Usage: python run_single_skill_tournament.py <skill> <conversations_dir> <models_file> <judges_file> <skills_file> <output_file>")
        sys.exit(1)

    target_skill = sys.argv[1]
    conversations_dir = sys.argv[2]
    models_file = sys.argv[3]
    judges_file = sys.argv[4]
    skills_file = sys.argv[5]
    output_file = sys.argv[6]

    print(f"🏟️  Running tournaments for skill: {target_skill}")

    # Load original skills data
    with open(skills_file) as f:
        skills_data = json.load(f)

    # Check if target skill exists
    if target_skill not in skills_data.get("skills", {}):
        print(f"❌ Skill '{target_skill}' not found in loaded skills")
        # Create empty output file to satisfy Snakemake
        with open(output_file, 'w') as f:
            json.dump({"tournaments": {}}, f, indent=2)
        return

    # Filter skills to only include the target skill
    filtered_skills = filter_skills_for_single_skill(skills_data, target_skill)

    # Create temporary filtered skills file
    temp_skills_file = f"{skills_file}.{target_skill}.tmp"
    with open(temp_skills_file, 'w') as f:
        json.dump(filtered_skills, f, indent=2)

    try:
        # Check if this skill needs tournament processing
        print(f"🔍 Checking tournament restart requirements for {target_skill}...")
        restart_status = detect_tournament_restart_work(conversations_dir, output_file)

        # Filter restart status to only our target skill
        skill_needs_processing = target_skill in restart_status.get("unprocessed_skills", [])

        if not skill_needs_processing:
            print(f"✅ Skill '{target_skill}' tournaments already complete")
            # Check if output file exists, create if missing
            if not Path(output_file).exists():
                print(f"📋 Creating output file for completed skill: {target_skill}")
                # Run the tournament processor to generate the output file
                main_with_cache_dir_data_driven(
                    conversations_dir, models_file, judges_file, temp_skills_file, output_file
                )
        else:
            print(f"⚠️  Running tournaments for skill: {target_skill}")
            # Run tournaments for this specific skill
            main_with_cache_dir_data_driven(
                conversations_dir, models_file, judges_file, temp_skills_file, output_file
            )

        print(f"🎉 Tournament processing complete for skill: {target_skill}")

    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_skills_file)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()