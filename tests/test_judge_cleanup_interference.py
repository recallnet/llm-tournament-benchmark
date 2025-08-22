"""
Test to identify if JudgeExecutor cleanup is interfering with tournament generation.
"""

import json
from pathlib import Path

import pytest


class TestJudgeCleanupInterference:
    """Test if judge cleanup is causing tournament generation failures."""

    def test_judge_cleanup_directory_conflict(self):
        """Test if judge cleanup directory conflicts with tournaments.json location."""
        print("\n🔍 TESTING: Judge cleanup directory conflict")

        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor()
        cleanup_dir = judge_executor.cache_dir

        print(f"   JudgeExecutor cache_dir: {cleanup_dir}")
        print("   Expected tournaments.json location: data/tournaments.json")

        # Check if cleanup targets the wrong directory
        if str(cleanup_dir) == "data/testonly/tournaments":
            print(
                "   🚨 CRITICAL BUG: JudgeExecutor.cache_dir points to data/tournaments"
            )
            print(
                "   This means tournaments.json should be at data/tournaments/tournaments.json"
            )
            print(
                "   But tournament generation tries to write to data/tournaments.json"
            )

            # Check where tournaments.json should actually be written
            tournaments_in_cache_dir = cleanup_dir / "tournaments.json"
            tournaments_in_data_dir = Path("data/testonly/tournaments.json")

            print(
                f"   tournaments.json in cache dir exists: {tournaments_in_cache_dir.exists()}"
            )
            print(
                f"   tournaments.json in data dir exists: {tournaments_in_data_dir.exists()}"
            )

            if tournaments_in_cache_dir.exists():
                print(
                    "   🎯 FOUND IT! tournaments.json is being written to the wrong location!"
                )
                with open(tournaments_in_cache_dir) as f:
                    content = json.load(f)
                tournaments_count = len(content.get("tournaments", []))
                print(
                    f"   tournaments.json in cache dir has {tournaments_count} tournaments"
                )

                pytest.fail(
                    "tournaments.json is written to wrong location - should be data/tournaments.json not data/tournaments/tournaments.json"
                )
            else:
                print("   ❌ tournaments.json not found in either location")
                pytest.fail(
                    "JudgeExecutor cache_dir conflicts with expected tournaments.json location"
                )

    def test_snakemake_output_path_vs_actual_write_path(self):
        """Test if Snakemake output path matches where tournament generation actually writes."""
        print("\n🔍 TESTING: Snakemake output vs actual write path")

        # Check what Snakemake expects as output
        expected_output = Path("data/testonly/tournaments.json")

        # Check where main_with_cache_dir actually writes
        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor()
        actual_cache_dir = judge_executor.cache_dir

        print(f"   Snakemake expects output at: {expected_output}")
        print(f"   JudgeExecutor cache_dir: {actual_cache_dir}")

        # The tournament generation function receives output_file parameter
        # Let's check if it writes to the right place

        if str(actual_cache_dir) == "data/testonly/tournaments":
            print("   🚨 MISMATCH DETECTED!")
            print("   Snakemake expects: data/tournaments.json")
            print("   But judge cache dir is: data/tournaments/")
            print("   This creates a file vs directory conflict!")

            # Check if there's confusion between:
            # - data/tournaments.json (file) - what Snakemake expects
            # - data/tournaments/ (directory) - where judge cache lives

            tournaments_dir = Path("data/testonly/tournaments")
            if tournaments_dir.is_dir():
                files_in_dir = list(tournaments_dir.iterdir())
                print(f"   Files in data/tournaments/ directory: {len(files_in_dir)}")

                # Look for tournaments.json inside the directory
                tournaments_json_in_dir = tournaments_dir / "tournaments.json"
                if tournaments_json_in_dir.exists():
                    print("   🎯 FOUND THE BUG!")
                    print(
                        "   tournaments.json is being written INSIDE data/tournaments/ directory"
                    )
                    print("   But Snakemake expects it at data/tournaments.json")
                    pytest.fail(
                        "Output file path mismatch: written to data/tournaments/tournaments.json but expected at data/tournaments.json"
                    )

    def test_main_with_cache_dir_output_parameter(self):
        """Test what main_with_cache_dir does with the output_file parameter."""
        print("\n🔍 TESTING: main_with_cache_dir output parameter handling")

        # Check the function signature and implementation
        import inspect

        from scripts.run_tournaments import main_with_cache_dir

        signature = inspect.signature(main_with_cache_dir)
        print(f"   Function signature: {signature}")

        # Check if the function properly uses the output_file parameter
        # by examining the source code
        source = inspect.getsource(main_with_cache_dir)

        if "output_file" in source:
            print("   ✅ Function accepts output_file parameter")

            # Check if it actually uses it
            if "with open(output_file" in source:
                print("   ✅ Function writes to output_file parameter")
            else:
                print("   ❌ Function doesn't write to output_file parameter")
                print("   🚨 BUG: Function ignores output_file and writes elsewhere!")
                pytest.fail("main_with_cache_dir ignores output_file parameter")
        else:
            print("   ❌ Function doesn't accept output_file parameter")
            pytest.fail("main_with_cache_dir missing output_file parameter")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
