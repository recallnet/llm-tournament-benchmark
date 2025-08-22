#!/usr/bin/env python3
"""
Snakemake wrapper script for tournament generation.
Properly handles exceptions and provides error reporting.
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from run_tournaments import main_with_cache_dir


def main():
    """Main function for Snakemake script execution."""
    try:
        # Get parameters from Snakemake
        conversations_cache_dir = str(snakemake.params.conversations_dir)
        models_file = str(snakemake.input.models)
        judges_file = str(snakemake.input.judges)
        skills_file = str(snakemake.input.skills)
        output_file = str(snakemake.output[0])

        print("🏁 Starting tournament generation...")
        print(f"   Conversations cache: {conversations_cache_dir}")
        print(f"   Models file: {models_file}")
        print(f"   Judges file: {judges_file}")
        print(f"   Skills file: {skills_file}")
        print(f"   Output file: {output_file}")

        # Run tournament generation
        main_with_cache_dir(
            conversations_cache_dir, models_file, judges_file, skills_file, output_file
        )

        # Verify output was created
        output_path = Path(output_file)
        if not output_path.exists():
            raise RuntimeError(
                f"Tournament generation failed - output file not created: {output_file}"
            )

        # Verify output has content
        if output_path.stat().st_size == 0:
            raise RuntimeError(
                f"Tournament generation failed - output file is empty: {output_file}"
            )

        print(f"✅ Tournament generation completed successfully: {output_file}")

    except Exception as e:
        print(f"❌ Tournament generation failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
