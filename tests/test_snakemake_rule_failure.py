"""
Test to identify the exact failure point in the Snakemake run_tournaments rule.
"""

from pathlib import Path

import pytest


class TestSnakemakeRuleFailure:
    """Test Snakemake rule failure detection."""

    def test_run_tournaments_rule_silent_failure(self):
        """Test that the run_tournaments rule is failing silently."""
        print("\n🔍 TESTING: Snakemake rule failure detection")

        # The smoking gun: tournaments.json should exist after running pipeline
        tournaments_file = Path("data/testonly/tournaments.json")

        print(f"   tournaments.json exists: {tournaments_file.exists()}")

        # If it doesn't exist, the rule failed
        if not tournaments_file.exists():
            print("   🚨 BUG CONFIRMED: run_tournaments rule failed silently")
            print(
                "   Snakemake 'run:' directive doesn't properly handle Python exceptions"
            )

            # Check if we can find evidence of the failure
            cache_markers = [
                "data/testonly/conversations_cache_thedrummer_unslopnemo-12b.done",
                "data/testonly/conversations_cache_openai_gpt-oss-120b.done",
                "data/testonly/conversations_cache_inception_mercury.done",
                "data/testonly/conversations_cache_openai_gpt-oss-20b.done",
            ]

            all_markers_exist = all(Path(marker).exists() for marker in cache_markers)
            print(f"   All input dependencies exist: {all_markers_exist}")

            if all_markers_exist:
                print(
                    "   🎯 SOLUTION: Replace 'run:' directive with 'script:' directive"
                )
                print(
                    "   This will properly handle Python exceptions and fail the rule"
                )

                pytest.fail(
                    "run_tournaments rule has silent failure - use script: instead of run:"
                )
        else:
            print("   ✅ Rule succeeded - tournaments.json exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
