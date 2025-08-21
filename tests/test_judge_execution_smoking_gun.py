"""
TDD investigation of the judge execution smoking gun.

Judges decide tournament match outcomes, so any issues with judge execution
or caching will break the entire tournament system.
"""

import json
from pathlib import Path

import pytest


class TestJudgeExecutionSmokingGun:
    """Investigate judge execution as the smoking gun for tournament failures."""

    def test_judge_cache_directory_architecture(self):
        """Test the judge cache directory architecture for conflicts."""
        print("\n🔍 TESTING: Judge cache directory architecture")

        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor()
        judge_cache_dir = judge_executor.cache_dir

        print(f"   JudgeExecutor.cache_dir: {judge_cache_dir}")

        # This is the smoking gun - where does judge cache live vs where tournaments.json should be?
        expected_tournaments_location = Path("data/testonly/tournaments.json")
        actual_judge_cache_location = Path(judge_cache_dir)

        print(f"   Expected tournaments.json: {expected_tournaments_location}")
        print(f"   Actual judge cache dir: {actual_judge_cache_location}")

        # Check for the conflict
        if str(judge_cache_dir) == "data/testonly/tournaments":
            print("   🚨 SMOKING GUN CONFIRMED!")
            print("   Judge cache directory IS the tournaments directory!")
            print("   This means:")
            print("   - Judge decisions cache to: data/tournaments/harm_avoidance/*.json")
            print("   - tournaments.json should be at: data/tournaments.json")
            print("   - But judge cleanup targets: data/tournaments/ (same as tournaments.json parent!)")

            # Check what's actually in the judge cache directory
            if actual_judge_cache_location.exists():
                subdirs = [d for d in actual_judge_cache_location.iterdir() if d.is_dir()]
                files = [f for f in actual_judge_cache_location.iterdir() if f.is_file()]

                print("   Judge cache contents:")
                print(f"   - Subdirectories: {[d.name for d in subdirs]}")
                print(f"   - Files in root: {[f.name for f in files]}")

                # Look for tournaments.json in the judge cache directory
                tournaments_in_cache = actual_judge_cache_location / "tournaments.json"
                if tournaments_in_cache.exists():
                    print("   🎯 FOUND tournaments.json in judge cache directory!")
                    with open(tournaments_in_cache) as f:
                        content = json.load(f)
                    tournament_count = len(content.get("tournaments", []))
                    print(f"   tournaments.json has {tournament_count} tournaments")

                    pytest.fail(
                        "tournaments.json written to wrong location: data/tournaments/tournaments.json instead of data/tournaments.json"
                    )
                else:
                    print("   ❌ tournaments.json not found in judge cache directory either")

            pytest.fail("Judge cache directory conflicts with tournaments.json location")

    def test_judge_decision_execution_flow(self):
        """Test the judge decision execution flow for bottlenecks."""
        print("\n🔍 TESTING: Judge decision execution flow")

        # Load actual skills to see what judges need to process
        skills_file = Path("data/testonly/loaded_skills.json")
        if skills_file.exists():
            with open(skills_file) as f:
                skills_data = json.load(f)

            evals = skills_data.get("evals", [])
            models_file = Path("data/testonly/loaded_models.json")

            if models_file.exists():
                with open(models_file) as f:
                    models_data = json.load(f)
                models = models_data.get("models", [])

                print("   Pipeline needs to process:")
                print(f"   - Models: {len(models)}")
                print(f"   - Evals: {len(evals)}")

                # Calculate tournament workload
                model_pairs_per_eval = (len(models) * (len(models) - 1)) // 2  # Combinations of 2 models
                total_matches = model_pairs_per_eval * len(evals)

                print(f"   - Model pairs per eval: {model_pairs_per_eval}")
                print(f"   - Total tournament matches: {total_matches}")

                # Check how many judges per match
                judges_file = Path("data/testonly/loaded_judges.json")
                if judges_file.exists():
                    with open(judges_file) as f:
                        judges_data = json.load(f)
                    judges = judges_data.get("judges", [])

                    total_judge_decisions = total_matches * len(judges)
                    print(f"   - Judges per match: {len(judges)}")
                    print(f"   - Total judge decisions needed: {total_judge_decisions}")

                    # Check existing judge cache
                    judge_cache_dir = Path("data/testonly/tournaments")
                    if judge_cache_dir.exists():
                        cached_decisions = list(judge_cache_dir.rglob("*.json"))
                        print(f"   - Cached judge decisions: {len(cached_decisions)}")

                        coverage_percent = (
                            (len(cached_decisions) / total_judge_decisions) * 100 if total_judge_decisions > 0 else 0
                        )
                        print(f"   - Cache coverage: {coverage_percent:.1f}%")

                        # Check which skills have judge cache
                        skills_with_cache = set()
                        for cache_file in cached_decisions:
                            if cache_file.parent != judge_cache_dir:  # Skip root level files
                                skills_with_cache.add(cache_file.parent.name)

                        print(f"   - Skills with judge cache: {sorted(skills_with_cache)}")

                        expected_skills = {eval_data["_metadata"]["skill"] for eval_data in evals}
                        missing_skills = expected_skills - skills_with_cache

                        if missing_skills:
                            print(f"   🚨 Skills missing judge cache: {sorted(missing_skills)}")
                            print("   This confirms tournament generation stops after processing some skills")
                        else:
                            print("   ✅ All skills have judge cache")

    def test_judge_execution_error_detection(self):
        """Test if we can detect where judge execution is failing."""
        print("\n🔍 TESTING: Judge execution error detection")

        # Check if we can identify the failure point in judge execution
        judge_cache_dir = Path("data/testonly/tournaments")

        if judge_cache_dir.exists():
            # Group judge cache files by skill
            skill_cache_counts = {}
            for cache_file in judge_cache_dir.rglob("*.json"):
                if cache_file.parent != judge_cache_dir:  # Skip root files
                    skill = cache_file.parent.name
                    skill_cache_counts[skill] = skill_cache_counts.get(skill, 0) + 1

            print("   Judge cache by skill:")
            for skill, count in sorted(skill_cache_counts.items()):
                print(f"   - {skill}: {count} cached decisions")

            # If only harm_avoidance has cache, that's the smoking gun
            if len(skill_cache_counts) == 1 and "harm_avoidance" in skill_cache_counts:
                print("   🚨 SMOKING GUN: Only harm_avoidance has judge cache!")
                print("   This means tournament generation processes harm_avoidance then fails/stops")

                # Check what specific error might cause this
                print("   Possible causes:")
                print("   1. Exception thrown after processing first skill")
                print("   2. Judge execution timeout after first skill")
                print("   3. API rate limiting after processing harm_avoidance")
                print("   4. Cache directory conflict causing write failures")

                pytest.fail("Tournament generation fails after processing only harm_avoidance skill")
            elif len(skill_cache_counts) == 0:
                print("   ❌ No judge cache found at all")
            else:
                print(f"   ✅ Multiple skills have judge cache: {sorted(skill_cache_counts.keys())}")

    def test_judge_cache_vs_tournaments_json_relationship(self):
        """Test the relationship between judge cache and tournaments.json generation."""
        print("\n🔍 TESTING: Judge cache vs tournaments.json relationship")

        judge_cache_dir = Path("data/testonly/tournaments")
        tournaments_file = Path("data/testonly/tournaments.json")

        judge_cache_exists = judge_cache_dir.exists()
        tournaments_exists = tournaments_file.exists()

        print(f"   Judge cache directory exists: {judge_cache_exists}")
        print(f"   tournaments.json exists: {tournaments_exists}")

        if judge_cache_exists and not tournaments_exists:
            print("   🎯 ANALYSIS: Judge cache exists but tournaments.json missing")

            # Count judge decisions
            if judge_cache_dir.exists():
                judge_files = list(judge_cache_dir.rglob("*.json"))
                print(f"   Judge cache files: {len(judge_files)}")

                if len(judge_files) > 0:
                    print("   🚨 CRITICAL FINDING:")
                    print(f"   - Judges have made {len(judge_files)} decisions")
                    print("   - But tournaments.json was never created from these decisions")
                    print("   - This means main_with_cache_dir() failed after judge execution")

                    # This is the key insight - judge execution works but tournament compilation fails
                    print("   💡 ROOT CAUSE:")
                    print("   Judge execution succeeds (we have cached decisions)")
                    print("   But tournament results compilation/writing fails")
                    print("   The failure is in creating tournaments.json from judge decisions")

                    pytest.fail("Judge decisions exist but tournaments.json compilation failed")

        elif not judge_cache_exists and not tournaments_exists:
            print("   ❌ Both judge cache and tournaments.json missing")
            print("   This indicates tournament generation never started successfully")

        elif tournaments_exists:
            print("   ✅ tournaments.json exists")
            with open(tournaments_file) as f:
                content = json.load(f)
            tournament_count = len(content.get("tournaments", []))
            print(f"   tournaments.json has {tournament_count} tournaments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
