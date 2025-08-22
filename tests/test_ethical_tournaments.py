#!/usr/bin/env python3
"""
Test that identifies why ethical_loopholes tournaments are not being run.
This test should isolate the root cause and verify our fix.
"""

import json
from pathlib import Path

from .test_utils_judge_cache import get_judge_cache_dir


def test_ethical_tournaments_missing():
    """Test that ethical_loopholes tournaments should be generated but aren't."""
    print("🧪 Testing ethical_loopholes tournament generation issue...")

    # 1. Verify ethical_loopholes conversations exist
    ethical_convs_path = Path("data/testonly/conversations/ethical_loopholes")
    if not ethical_convs_path.exists():
        print("❌ FAIL: ethical_loopholes conversations directory doesn't exist")
        return False

    ethical_conv_files = list(ethical_convs_path.glob("*.json"))
    print(f"📊 Found {len(ethical_conv_files)} ethical_loopholes conversation files")

    if len(ethical_conv_files) == 0:
        print("❌ FAIL: No ethical_loopholes conversation files exist")
        return False

    # 2. Check expected count (3 evals × 4 models = 12 conversations)
    expected_conversations = 3 * 4  # 3 ethical_loopholes evals, 4 models
    if len(ethical_conv_files) < expected_conversations:
        print(
            f"⚠️  WARNING: Expected {expected_conversations} conversations, found {len(ethical_conv_files)}"
        )

    # 3. Verify ethical_loopholes skill is in loaded skills
    with open("data/testonly/loaded_skills.json") as f:
        skills_data = json.load(f)

    if "ethical_loopholes" not in skills_data["skills"]:
        print("❌ FAIL: ethical_loopholes skill not in loaded_skills.json")
        return False

    ethical_skill = skills_data["skills"]["ethical_loopholes"]
    print(f"✅ ethical_loopholes skill has {ethical_skill['eval_count']} evals")

    # 4. Check if tournaments exist
    tournaments_path = get_judge_cache_dir() / "ethical_loopholes"
    if not tournaments_path.exists():
        print("❌ FAIL: ethical_loopholes tournaments directory doesn't exist")
        return False

    tournament_files = list(tournaments_path.glob("*.json"))
    print(f"📊 Found {len(tournament_files)} ethical_loopholes tournament files")

    # Should have tournaments for 3 evals
    if len(tournament_files) == 0:
        print("❌ FAIL: No ethical_loopholes tournament files exist")
        return False

    # 5. Check if skill ratings include ethical_loopholes
    with open("data/testonly/skill_ratings.json") as f:
        ratings_data = json.load(f)

    if "ethical_loopholes" not in ratings_data["skill_ratings"]:
        print("❌ FAIL: ethical_loopholes not in skill_ratings.json")
        print(
            f"📊 Available skills in ratings: {list(ratings_data['skill_ratings'].keys())}"
        )
        return False

    print("✅ All ethical_loopholes tournament components exist")
    return True


def test_tournament_script_parameter_handling():
    """Test if the tournament script properly handles skill filtering."""
    print("🧪 Testing tournament script skill parameter handling...")

    # Read tournament script to check for skill filtering logic
    try:
        with open("scripts/run_tournaments.py") as f:
            script_content = f.read()

        # Check if script has skill filtering capability
        if "--skill" not in script_content and "skill" not in script_content.lower():
            print(
                "❌ FAIL: Tournament script doesn't appear to support skill filtering"
            )
            return False

        # Check for proper argument parsing
        if "argparse" in script_content or "sys.argv" in script_content:
            print("✅ Tournament script has argument parsing")
        else:
            print("⚠️  WARNING: Tournament script may not properly parse arguments")

        print("✅ Tournament script appears to support skill filtering")
        return True

    except Exception as e:
        print(f"❌ FAIL: Error reading tournament script: {e}")
        return False


def test_snakemake_rule_coverage():
    """Test if Snakemake rules properly include all skills."""
    print("🧪 Testing Snakemake rule coverage for all skills...")

    try:
        with open("Snakefile") as f:
            snakefile_content = f.read()

        # Check if ethical_loopholes is properly handled in rules
        if "ethical_loopholes" in snakefile_content:
            print("✅ ethical_loopholes mentioned in Snakefile")
        else:
            print("⚠️  WARNING: ethical_loopholes not explicitly mentioned in Snakefile")

        # Check for dynamic skill handling
        if "glob_wildcards" in snakefile_content or "expand" in snakefile_content:
            print("✅ Snakefile uses dynamic patterns for skills")
        else:
            print("⚠️  WARNING: Snakefile may not dynamically handle all skills")

        # Load skills and check if all are represented
        with open("data/testonly/loaded_skills.json") as f:
            skills_data = json.load(f)

        all_skills = list(skills_data["skills"].keys())
        print(f"📊 All skills: {all_skills}")

        # Check tournament output files
        tournament_files = list(get_judge_cache_dir().iterdir())
        existing_skills = [p.name for p in tournament_files if p.is_dir()]
        print(f"📊 Skills with tournament directories: {existing_skills}")

        missing_skills = set(all_skills) - set(existing_skills)
        if missing_skills:
            print(
                f"❌ FAIL: Missing tournament directories for skills: {missing_skills}"
            )
            return False

        print("✅ All skills have tournament directories")
        return True

    except Exception as e:
        print(f"❌ FAIL: Error analyzing Snakemake rules: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Testing ethical_loopholes tournament generation issues...")

    test1_passed = test_ethical_tournaments_missing()
    test2_passed = test_tournament_script_parameter_handling()
    test3_passed = test_snakemake_rule_coverage()

    if not test1_passed:
        print("\n❌ ROOT CAUSE IDENTIFIED: ethical_loopholes tournaments are missing")
        print("   - Conversations exist but tournaments weren't generated")
        print("   - This suggests the tournament generation process skipped this skill")

    if not test2_passed:
        print("\n❌ ISSUE: Tournament script may not properly handle skill parameters")

    if not test3_passed:
        print("\n❌ ISSUE: Snakemake rules may not cover all skills properly")

    if test1_passed and test2_passed and test3_passed:
        print("\n✅ All tests passed - tournaments should be working")
    else:
        print("\n❌ Issues found - need to fix tournament generation process")
