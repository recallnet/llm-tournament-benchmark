#!/usr/bin/env python3
"""Snakemake wrapper script for tournament summarization."""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from summarize_tournaments import main

if __name__ == "__main__":
    # Check if command line arguments were provided (from snakemake shell command)
    if len(sys.argv) >= 3:
        tournaments_file = Path(sys.argv[1])  # {input.tournaments}
        output_file = Path(sys.argv[2])  # {output}

        # Judge cache is in profile-specific data directory - derive from output path
        output_data_dir = output_file.parent
        tournaments_dir = output_data_dir / "judge_cache"

        main(tournaments_dir=tournaments_dir, output_file=output_file)
    elif "snakemake" in globals():
        # Fallback to snakemake context (though this shouldn't be reached with shell commands)
        tournaments_file = Path(snakemake.input.tournaments)
        output_file = Path(snakemake.output[0])

        output_data_dir = output_file.parent
        tournaments_dir = output_data_dir / "judge_cache"

        main(tournaments_dir=tournaments_dir, output_file=output_file)
    else:
        # Fallback for direct execution
        main()
