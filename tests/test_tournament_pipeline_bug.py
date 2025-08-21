"""
TDD tests to investigate the tournament pipeline bug.

These tests investigate why the pipeline reports being "done" when
tournaments.json doesn't exist and tournaments aren't being generated.
"""

import json
from pathlib import Path

import pytest


class TestTournamentPipelineBug:
    """Test why pipeline reports done when tournaments aren't generated."""

    def test_tournaments_json_file_actually_missing(self):
        """Confirm that tournaments.json is actually missing."""
        print("\n🔍 TESTING: tournaments.json file existence")

        tournaments_file = Path("data/testonly/tournaments.json")

        exists = tournaments_file.exists()
        print(f"   tournaments.json exists: {exists}")

        if exists:
            size = tournaments_file.stat().st_size
            print(f"   File size: {size} bytes")

            # Check if it's empty or has content
            if size == 0:
                print("   ❌ File exists but is EMPTY")
                pytest.fail("tournaments.json exists but is empty")
            else:
                # File exists and has content - let's see what's in it
                with open(tournaments_file) as f:
                    content = json.load(f)
                tournaments_count = len(content.get("tournaments", []))
                print(f"   File has {tournaments_count} tournaments")

                if tournaments_count == 0:
                    print("   ❌ File exists but has NO tournaments")
                    pytest.fail("tournaments.json exists but contains no tournaments")
                else:
                    print("   ✅ File exists and has tournaments - this is not the bug")
        else:
            print("   ❌ tournaments.json does NOT exist")
            pytest.fail("tournaments.json file is missing")

    def test_snakemake_thinks_tournaments_exist(self):
        """Test why Snakemake thinks tournaments are up to date."""
        print("\n🔍 TESTING: Why Snakemake thinks tournaments are done")

        # Check if the tournaments rule dependencies exist
        dependencies = [
            "data/testonly/conversations_cache_thedrummer_unslopnemo-12b.done",
            "data/testonly/conversations_cache_openai_gpt-oss-120b.done",
            "data/testonly/conversations_cache_inception_mercury.done",
            "data/testonly/conversations_cache_openai_gpt-oss-20b.done",
            "data/testonly/loaded_models.json",
            "data/testonly/loaded_judges.json",
            "data/testonly/loaded_skills.json",
        ]

        missing_deps = []
        for dep in dependencies:
            if not Path(dep).exists():
                missing_deps.append(dep)

        print(f"   Missing dependencies: {missing_deps}")

        tournaments_file = Path("data/testonly/tournaments.json")
        output_exists = tournaments_file.exists()

        print(f"   Output file exists: {output_exists}")

        if not output_exists and not missing_deps:
            print("   🚨 BUG: All dependencies exist but output is missing")
            print("   This means the run_tournaments rule FAILED but Snakemake didn't detect it")
            pytest.fail("Snakemake dependency bug: dependencies exist but output missing")

    def test_tournament_rule_execution_tracking(self):
        """Test if we can track what happens when tournament rule runs."""
        print("\n🔍 TESTING: Tournament rule execution tracking")

        # Check if there are any error logs
        snakemake_log_dir = Path(".snakemake/log")
        if snakemake_log_dir.exists():
            log_files = list(snakemake_log_dir.glob("*.snakemake.log"))
            if log_files:
                latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                print(f"   Latest Snakemake log: {latest_log}")

                with open(latest_log) as f:
                    log_content = f.read()

                if "run_tournaments" in log_content:
                    print("   ✅ Found run_tournaments in log")
                    # Look for error patterns
                    if "Error" in log_content or "Exception" in log_content:
                        print("   🚨 Found errors in log:")
                        lines = log_content.split("\n")
                        for i, line in enumerate(lines):
                            if "run_tournaments" in line or "Error" in line or "Exception" in line:
                                print(f"      {line}")
                else:
                    print("   ❌ No run_tournaments found in log")
            else:
                print("   ❌ No Snakemake log files found")
        else:
            print("   ❌ No .snakemake/log directory found")

    def test_tournament_judge_cache_pattern(self):
        """Test the pattern of judge cache files to understand what's happening."""
        print("\n🔍 TESTING: Tournament judge cache pattern analysis")

        tournaments_dir = Path("data/testonly/tournaments")

        if not tournaments_dir.exists():
            print("   ❌ No tournaments cache directory exists")
            return

        skill_dirs = []
        for item in tournaments_dir.iterdir():
            if item.is_dir():
                skill_dirs.append(item.name)
                judge_files = list(item.glob("*.json"))
                print(f"   📁 {item.name}: {len(judge_files)} judge cache files")

                if judge_files:
                    # Check timestamps of judge files
                    latest_file = max(judge_files, key=lambda f: f.stat().st_mtime)
                    import datetime

                    timestamp = datetime.datetime.fromtimestamp(latest_file.stat().st_mtime)
                    print(f"      Latest judge cache: {timestamp}")

        print(f"   Skills with judge cache: {sorted(skill_dirs)}")

        missing_skills = [
            "code_generation",
            "document_summarization",
            "empathy",
            "ethical_loopholes",
            "hidden_messages",
            "persuasiveness",
            "respect_no_em_dash_requests",
        ]

        actually_missing = [s for s in missing_skills if s not in skill_dirs]
        print(f"   Skills with NO judge cache: {actually_missing}")

        if len(skill_dirs) == 1 and "harm_avoidance" in skill_dirs:
            print("   🚨 BUG CONFIRMED: Only harm_avoidance has judge cache files")
            print("   This means tournament generation stops after first skill")

    def test_main_with_cache_dir_first_skill_bug(self):
        """Test if main_with_cache_dir stops after processing first skill."""
        print("\n🔍 TESTING: main_with_cache_dir execution flow")

        # We can't easily test the full function due to API calls,
        # but we can test the setup logic

        # Load the actual data to see what it contains
        skills_file = Path("data/testonly/loaded_skills.json")
        if skills_file.exists():
            with open(skills_file) as f:
                skills_data = json.load(f)

            evals = skills_data.get("evals", [])

            # Group by skill to see the distribution
            skills_distribution = {}
            for eval_data in evals:
                skill_id = eval_data.get("_metadata", {}).get("skill")
                if skill_id:
                    if skill_id not in skills_distribution:
                        skills_distribution[skill_id] = 0
                    skills_distribution[skill_id] += 1

            print(f"   Eval distribution by skill: {skills_distribution}")
            print(f"   Total evals to process: {len(evals)}")

            # The function should process ALL evals, not just harm_avoidance ones
            harm_avoidance_count = skills_distribution.get("harm_avoidance", 0)
            other_skills_count = len(evals) - harm_avoidance_count

            print(f"   harm_avoidance evals: {harm_avoidance_count}")
            print(f"   Other skill evals: {other_skills_count}")

            if other_skills_count > 0:
                print("   🎯 The function SHOULD process more than just harm_avoidance")
                print("   🚨 BUG: Function is stopping early or hitting an error")

    def test_pipeline_state_consistency(self):
        """Test if the pipeline state is consistent."""
        print("\n🔍 TESTING: Pipeline state consistency check")

        # Key files that should exist
        key_files = {
            "data/testonly/tournaments.json": "Tournament results",
            "data/testonly/tournament_summaries.json": "Tournament summaries",
            "data/testonly/skill_ratings.json": "Skill ratings",
        }

        file_states = {}
        for file_path, description in key_files.items():
            path = Path(file_path)
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            file_states[file_path] = {"exists": exists, "size": size, "desc": description}
            print(f"   {description}: {'✅' if exists else '❌'} ({size} bytes)")

        # Check the logical dependency chain
        tournaments_exist = file_states["data/testonly/tournaments.json"]["exists"]
        summaries_exist = file_states["data/testonly/tournament_summaries.json"]["exists"]
        ratings_exist = file_states["data/testonly/skill_ratings.json"]["exists"]

        print("\n   Dependency chain:")
        print("   tournaments.json → tournament_summaries.json → skill_ratings.json")
        print(f"   {tournaments_exist} → {summaries_exist} → {ratings_exist}")

        if not tournaments_exist and (summaries_exist or ratings_exist):
            print("   🚨 INCONSISTENT STATE: Downstream files exist without tournaments.json")
            print("   This indicates tournaments.json was created but then disappeared or failed")

        if ratings_exist:
            # Check the content of ratings to see what skills are included
            with open("data/testonly/skill_ratings.json") as f:
                ratings_data = json.load(f)

            skill_keys = list(ratings_data.keys()) if isinstance(ratings_data, dict) else []
            print(f"   Skills in skill_ratings.json: {skill_keys}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
