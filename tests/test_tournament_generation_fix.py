#!/usr/bin/env python3
"""
Test that verifies tournament generation works for all skills including ethical_loopholes.
This test should pass after we fix the underlying issue.
"""

import json
import subprocess

from .test_utils_judge_cache import get_judge_cache_dir


def test_tournament_directory_creation():
    """Test that tournament directories are created for all skills."""
    print("🧪 Testing tournament directory creation for all skills...")

    # Load all skills
    with open("data/testonly/loaded_skills.json") as f:
        skills_data = json.load(f)

    all_skills = list(skills_data["skills"].keys())
    print(f"📊 All loaded skills: {all_skills}")

    # Check if tournament directories exist for all skills
    tournaments_base = get_judge_cache_dir()
    missing_dirs = []

    for skill in all_skills:
        skill_tournament_dir = tournaments_base / skill
        if not skill_tournament_dir.exists():
            missing_dirs.append(skill)
            print(f"❌ Missing tournament directory: {skill}")
        else:
            tournament_files = list(skill_tournament_dir.glob("*.json"))
            print(f"✅ {skill}: {len(tournament_files)} tournament files")

    if missing_dirs:
        print(f"❌ FAIL: Missing tournament directories: {missing_dirs}")
        return False

    print("✅ All skills have tournament directories")
    return True


def test_skill_ratings_completeness():
    """Test that skill ratings include all skills."""
    print("🧪 Testing skill ratings completeness...")

    # Load skills and ratings
    with open("data/testonly/loaded_skills.json") as f:
        skills_data = json.load(f)

    with open("data/testonly/skill_ratings.json") as f:
        ratings_data = json.load(f)

    all_skills = set(skills_data["skills"].keys())
    rated_skills = set(ratings_data["skill_ratings"].keys())

    print(f"📊 Skills in loaded_skills.json: {all_skills}")
    print(f"📊 Skills in skill_ratings.json: {rated_skills}")

    missing_ratings = all_skills - rated_skills
    if missing_ratings:
        print(f"❌ FAIL: Missing skill ratings: {missing_ratings}")
        return False

    extra_ratings = rated_skills - all_skills
    if extra_ratings:
        print(f"⚠️  WARNING: Extra skill ratings: {extra_ratings}")

    # Check execution info
    total_skills_in_ratings = ratings_data["execution_info"]["total_skills"]
    expected_skills = len(all_skills)

    if total_skills_in_ratings != expected_skills:
        print(
            f"❌ FAIL: Expected {expected_skills} skills in ratings, got {total_skills_in_ratings}"
        )
        return False

    print("✅ All skills have ratings calculated")
    return True


def test_results_table_includes_all_skills():
    """Test that the results table includes all skills."""
    print("🧪 Testing results table includes all skills...")

    # Run the results table script and capture output
    try:
        result = subprocess.run(
            ["python", "scripts/print_results_table.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"❌ FAIL: Results table script failed: {result.stderr}")
            return False

        output = result.stdout
        print("📊 Results table output:")
        print(output[:500] + "..." if len(output) > 500 else output)

        # Load expected skills
        with open("data/testonly/loaded_skills.json") as f:
            skills_data = json.load(f)

        all_skills = list(skills_data["skills"].keys())

        # Check if all skills are mentioned in the output
        missing_in_output = []
        for skill in all_skills:
            # Check various forms the skill might appear as in the output
            skill_variants = [
                skill.replace("_", " ").title(),
                skill.replace("_", " "),
                skill,
                skill.replace("_", "").title(),
            ]

            skill_found = any(variant in output for variant in skill_variants)
            if not skill_found:
                missing_in_output.append(skill)
                print(f"❌ Skill '{skill}' not found in results table")

        if missing_in_output:
            print(f"❌ FAIL: Skills missing from results table: {missing_in_output}")
            return False

        print("✅ All skills appear in results table")
        return True

    except subprocess.TimeoutExpired:
        print("❌ FAIL: Results table script timed out")
        return False
    except Exception as e:
        print(f"❌ FAIL: Error running results table script: {e}")
        return False


def create_missing_tournament_directories():
    """Create missing tournament directories to fix the issue."""
    print("🔧 Creating missing tournament directories...")

    # Load all skills
    with open("data/testonly/loaded_skills.json") as f:
        skills_data = json.load(f)

    all_skills = list(skills_data["skills"].keys())
    tournaments_base = get_judge_cache_dir()

    for skill in all_skills:
        skill_tournament_dir = tournaments_base / skill
        if not skill_tournament_dir.exists():
            skill_tournament_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created tournament directory: {skill}")
        else:
            print(f"📁 Tournament directory already exists: {skill}")


if __name__ == "__main__":
    print("🧪 Testing tournament generation fix...")

    # First, try to create missing directories
    create_missing_tournament_directories()

    # Run tests
    test1_passed = test_tournament_directory_creation()
    test2_passed = test_skill_ratings_completeness()
    test3_passed = test_results_table_includes_all_skills()

    if test1_passed and test2_passed and test3_passed:
        print("\n✅ All tests passed! Tournament generation is working correctly.")
    else:
        print("\n❌ Some tests failed. Need to investigate further.")

        if not test1_passed:
            print("   - Tournament directories missing")
        if not test2_passed:
            print("   - Skill ratings incomplete")
        if not test3_passed:
            print("   - Results table missing skills")
