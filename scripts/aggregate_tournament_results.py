#!/usr/bin/env python3
"""
Tournament results aggregation script for parallel tournament processing.

This script combines per-skill tournament JSON files into a single tournaments.json
file with the exact same structure as the original monolithic tournament processing.

Usage:
    python aggregate_tournament_results.py <tournament_skill_1.json> [tournament_skill_2.json ...] <output_file>
"""

import sys
import json
from pathlib import Path


def aggregate_tournament_files(input_files, output_file):
    """
    Aggregate multiple per-skill tournament JSON files into single tournaments.json.
    
    Maintains exact compatibility with existing tournaments.json structure.
    """
    aggregated_tournaments = {}
    aggregated_metadata = {}

    for input_file in input_files:
        if not Path(input_file).exists():
            print(f"⚠️  Warning: Tournament file not found: {input_file}")
            continue

        try:
            with open(input_file) as f:
                tournament_data = json.load(f)

            # Extract tournaments section
            tournaments = tournament_data.get("tournaments", [])
            
            # Handle both list and dict formats
            if isinstance(tournaments, list):
                # Convert list format to dict format by skill_id
                for tournament in tournaments:
                    skill = tournament.get("skill_id")
                    if skill:
                        if skill in aggregated_tournaments:
                            print(f"⚠️  Warning: Duplicate skill found: {skill}")
                        aggregated_tournaments[skill] = tournament
            elif isinstance(tournaments, dict):
                # Merge tournaments (original dict format)
                for skill, skill_tournaments in tournaments.items():
                    if skill in aggregated_tournaments:
                        print(f"⚠️  Warning: Duplicate skill found: {skill}")
                    aggregated_tournaments[skill] = skill_tournaments

            # Preserve metadata if present
            for key, value in tournament_data.items():
                if key != "tournaments":
                    aggregated_metadata[key] = value

        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ Error processing {input_file}: {e}")
            continue

    # Create final aggregated structure
    final_output = {
        "tournaments": aggregated_tournaments,
        **aggregated_metadata
    }

    # Write aggregated results
    with open(output_file, 'w') as f:
        json.dump(final_output, f, indent=2)

    print(f"✅ Aggregated {len(aggregated_tournaments)} skills into {output_file}")
    return final_output


def main():
    if len(sys.argv) < 3:
        print("Usage: python aggregate_tournament_results.py <tournament_file1.json> [tournament_file2.json ...] <output_file>")
        sys.exit(1)

    # Last argument is output file, all others are input files
    input_files = sys.argv[1:-1]
    output_file = sys.argv[-1]

    print(f"🔄 Aggregating {len(input_files)} tournament files...")
    print(f"📁 Output: {output_file}")

    result = aggregate_tournament_files(input_files, output_file)

    skills_processed = list(result["tournaments"].keys())
    print(f"🏆 Processed skills: {', '.join(skills_processed)}")


if __name__ == "__main__":
    main()