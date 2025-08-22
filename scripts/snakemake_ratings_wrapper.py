#!/usr/bin/env python3
"""Snakemake wrapper script for skill ratings calculation."""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from calculate_skill_ratings import main, main_with_data_dir

if __name__ == "__main__":
    # Check if command line arguments were provided (from snakemake shell command)
    if len(sys.argv) >= 6:
        summaries_file = Path(sys.argv[1])  # {input.summaries}
        models_file = Path(sys.argv[2])  # {input.models}
        judges_file = Path(sys.argv[3])  # {input.judges}
        skills_file = Path(sys.argv[4])  # {input.skills}
        output_file = Path(sys.argv[5])  # {output}

        # Data directory is parent of input files
        data_dir = summaries_file.parent

        main_with_data_dir(
            data_dir, summaries_file, models_file, judges_file, skills_file, output_file
        )
    elif "snakemake" in globals():
        # Fallback to snakemake context
        summaries_file = Path(snakemake.input.summaries)
        models_file = Path(snakemake.input.models)
        judges_file = Path(snakemake.input.judges)
        skills_file = Path(snakemake.input.skills)
        output_file = Path(snakemake.output[0])

        data_dir = summaries_file.parent

        main_with_data_dir(
            data_dir, summaries_file, models_file, judges_file, skills_file, output_file
        )
    else:
        # Fallback for direct execution
        main()
