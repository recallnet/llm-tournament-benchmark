"""
TDD tests to investigate what causes tournaments.json to be deleted
and ensure proper cache invalidation without silent failures.
"""

from pathlib import Path

import pytest


class TestTournamentsJsonDeletion:
    """Test what causes tournaments.json deletion and cache invalidation issues."""

    def test_identify_tournaments_json_deletion_points(self):
        """Identify all code that could delete tournaments.json."""
        print("\n🔍 TESTING: Code that could delete tournaments.json")

        # Search for code that deletes or cleans tournament files
        import re
        from pathlib import Path

        # Search through key scripts for deletion patterns
        scripts_to_check = [
            "scripts/run_tournaments.py",
            "Snakefile",
            "scripts/execute_conversations.py",
            "scripts/execute_conversations_single_model.py",
        ]

        deletion_patterns = [
            r"\.unlink\(",
            r"os\.remove",
            r"rm.*tournament",
            r"clean.*tournament",
            r"delete.*tournament",
            r"shutil\.rmtree",
            r"Path.*\.unlink",
        ]

        potential_deletions = []

        for script_path in scripts_to_check:
            script = Path(script_path)
            if script.exists():
                with open(script) as f:
                    content = f.read()

                for i, line in enumerate(content.split("\n"), 1):
                    for pattern in deletion_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            potential_deletions.append(
                                {
                                    "file": script_path,
                                    "line": i,
                                    "content": line.strip(),
                                    "pattern": pattern,
                                }
                            )

        print(f"   Found {len(potential_deletions)} potential deletion points:")
        for deletion in potential_deletions:
            print(
                f"   📁 {deletion['file']}:{deletion['line']} - {deletion['content']}"
            )

        # Check if tournaments.json is explicitly mentioned
        tournaments_deletions = [
            d for d in potential_deletions if "tournament" in d["content"].lower()
        ]
        if tournaments_deletions:
            print(
                f"   🚨 Found {len(tournaments_deletions)} tournament-specific deletions"
            )
            for td in tournaments_deletions:
                print(f"      ⚠️  {td['file']}:{td['line']} - {td['content']}")

    def test_cache_invalidation_consistency(self):
        """Test that cache invalidation is consistent across all related files."""
        print("\n🔍 TESTING: Cache invalidation consistency")

        # Check current state of tournament-related files
        tournament_files = {
            "tournaments.json": Path("data/testonly/tournaments.json"),
            "tournament_summaries.json": Path(
                "data/testonly/tournament_summaries.json"
            ),
            "skill_ratings.json": Path("data/testonly/skill_ratings.json"),
            "tournaments_cache_dir": Path("data/testonly/tournaments/"),
        }

        current_state = {}
        for name, path in tournament_files.items():
            exists = path.exists()
            if exists and path.is_file():
                mtime = path.stat().st_mtime
                size = path.stat().st_size
            elif exists and path.is_dir():
                mtime = (
                    max(f.stat().st_mtime for f in path.rglob("*") if f.is_file())
                    if any(path.rglob("*"))
                    else 0
                )
                size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            else:
                mtime = 0
                size = 0

            current_state[name] = {"exists": exists, "mtime": mtime, "size": size}

            print(
                f"   {name}: {'✅' if exists else '❌'} (size: {size}, mtime: {mtime})"
            )

        # Check for inconsistent state
        tournaments_exists = current_state["tournaments.json"]["exists"]
        summaries_exists = current_state["tournament_summaries.json"]["exists"]
        ratings_exists = current_state["skill_ratings.json"]["exists"]
        cache_exists = current_state["tournaments_cache_dir"]["exists"]

        inconsistencies = []

        # tournaments.json should exist if summaries exist (dependency chain)
        if summaries_exists and not tournaments_exists:
            inconsistencies.append(
                "tournament_summaries.json exists but tournaments.json is missing"
            )

        # skill_ratings.json should not exist if tournaments.json is missing
        if ratings_exists and not tournaments_exists:
            inconsistencies.append(
                "skill_ratings.json exists but tournaments.json is missing"
            )

        # If judge cache exists, tournaments.json should exist
        if cache_exists and not tournaments_exists:
            cache_files = list(Path("data/testonly/tournaments/").rglob("*.json"))
            if cache_files:
                inconsistencies.append(
                    f"Judge cache has {len(cache_files)} files but tournaments.json is missing"
                )

        if inconsistencies:
            print("   🚨 INCONSISTENT STATE DETECTED:")
            for inconsistency in inconsistencies:
                print(f"      ⚠️  {inconsistency}")

            print("   🎯 SOLUTION: Need atomic cache invalidation - delete ALL or NONE")
            pytest.fail(f"Cache invalidation inconsistency: {inconsistencies}")

    def test_cleanup_functions_side_effects(self):
        """Test if cleanup functions have unexpected side effects."""
        print("\n🔍 TESTING: Cleanup function side effects")

        # Check if there are cleanup functions that might delete tournaments.json
        from scripts.run_tournaments import JudgeExecutor

        print("   Testing JudgeExecutor.cleanup_invalid_match_cache...")

        # Create a test instance
        judge_executor = JudgeExecutor()

        # Mock current data to see what it would delete

        # Check if this function could affect tournaments.json
        tournaments_path = Path("data/testonly/tournaments.json")
        tournaments_existed_before = tournaments_path.exists()

        print(f"      tournaments.json before cleanup: {tournaments_existed_before}")

        # Don't actually run cleanup (could be destructive), but check what it targets
        cache_dir = judge_executor.cache_dir
        print(f"      Cleanup targets directory: {cache_dir}")

        if cache_dir == Path("data/testonly/tournaments"):
            print(
                "      🚨 WARNING: Cleanup function targets same directory as tournaments cache!"
            )
            print("      This could explain why tournaments.json gets deleted")

        # Check if cleanup could remove the wrong files
        if cache_dir.exists():
            all_files = list(cache_dir.rglob("*"))
            json_files = [f for f in all_files if f.suffix == ".json"]
            print(
                f"      Files in cache directory: {len(all_files)} total, {len(json_files)} JSON files"
            )

            # Look for files that could be confused with tournaments.json
            suspicious_files = [
                f
                for f in json_files
                if "tournament" in f.name
                and not any(
                    skill in str(f.parent)
                    for skill in ["harm_avoidance", "code_generation", "empathy"]
                )
            ]
            if suspicious_files:
                print(
                    f"      🚨 Suspicious files that could be mistakenly deleted: {suspicious_files}"
                )

    def test_snakemake_rule_output_deletion(self):
        """Test if Snakemake rules delete their own outputs on failure."""
        print("\n🔍 TESTING: Snakemake rule output deletion behavior")

        # Check if Snakemake could be deleting tournaments.json on rule failure
        tournaments_path = Path("data/testonly/tournaments.json")

        print(f"   tournaments.json currently exists: {tournaments_path.exists()}")

        # Check Snakemake logs for evidence of deletion
        snakemake_log_dir = Path(".snakemake/log")
        if snakemake_log_dir.exists():
            log_files = list(snakemake_log_dir.glob("*.snakemake.log"))
            if log_files:
                # Check recent logs for deletion patterns
                recent_logs = sorted(log_files, key=lambda f: f.stat().st_mtime)[
                    -3:
                ]  # Last 3 logs

                deletion_evidence = []
                for log_file in recent_logs:
                    with open(log_file) as f:
                        log_content = f.read()

                    deletion_keywords = [
                        "removing",
                        "deleting",
                        "unlink",
                        "tournaments.json",
                    ]
                    for keyword in deletion_keywords:
                        if keyword in log_content.lower():
                            lines = log_content.split("\n")
                            matching_lines = [
                                line
                                for line in lines
                                if keyword.lower() in line.lower()
                            ]
                            for line in matching_lines:
                                deletion_evidence.append(
                                    {
                                        "log_file": log_file.name,
                                        "keyword": keyword,
                                        "line": line.strip(),
                                    }
                                )

                if deletion_evidence:
                    print("   🚨 Found deletion evidence in logs:")
                    for evidence in deletion_evidence:
                        print(f"      {evidence['log_file']}: {evidence['line']}")
                else:
                    print("   ✅ No deletion evidence found in recent logs")
            else:
                print("   ❌ No Snakemake log files found")

        # Test hypothesis: Snakemake deletes output files when rules fail
        print("   💡 HYPOTHESIS: Snakemake may delete output files on rule failure")
        print(
            "   This would explain why tournaments.json disappears but dependencies remain"
        )

    def test_prevent_silent_tournament_failures(self):
        """Test that tournament generation failures are not silent."""
        print("\n🔍 TESTING: Preventing silent tournament failures")

        # Check if we can detect when tournament generation fails
        tournaments_path = Path("data/testonly/tournaments.json")

        if not tournaments_path.exists():
            print("   🚨 tournaments.json is missing - this indicates a failure")

            # Check if we have the inputs needed to regenerate it
            required_inputs = [
                "data/testonly/loaded_models.json",
                "data/testonly/loaded_judges.json",
                "data/testonly/loaded_skills.json",
            ]

            missing_inputs = [inp for inp in required_inputs if not Path(inp).exists()]

            if not missing_inputs:
                print("   📋 All inputs available for tournament generation")
                print("   🎯 SOLUTION: Tournament generation should be re-triggered")

                # Test if we can detect the specific failure point
                from scripts.run_tournaments import main_with_cache_dir

                print("   Testing main_with_cache_dir with minimal timeout...")

                # We won't actually run it (could take forever), but we can test the setup
                try:
                    # Just test if the function exists and is callable
                    assert callable(
                        main_with_cache_dir
                    ), "main_with_cache_dir should be callable"
                    print("   ✅ main_with_cache_dir function is available")
                except Exception as e:
                    print(f"   ❌ main_with_cache_dir has issues: {e}")

                pytest.fail(
                    "tournaments.json is missing but inputs exist - should regenerate"
                )
            else:
                print(f"   ❌ Missing required inputs: {missing_inputs}")
        else:
            print("   ✅ tournaments.json exists - no silent failure detected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
