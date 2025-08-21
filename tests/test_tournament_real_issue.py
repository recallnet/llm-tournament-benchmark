#!/usr/bin/env python3
"""
Test the real tournament issue with actual data.
"""

import json
from pathlib import Path


def test_actual_tournament_bottleneck():
    """Test what's actually causing the tournament script to hang."""
    print("🔍 Analyzing actual tournament data...")

    # Check the size of conversations.json
    conv_file = Path("data/testonly/conversations.json")
    if not conv_file.exists():
        print("❌ conversations.json not found")
        return False

    with open(conv_file) as f:
        conversations = json.load(f)

    conv_count = len(conversations.get("conversations", []))
    print(f"📊 {conv_count} conversations to process")

    # Check skills data
    skills_file = Path("data/testonly/loaded_skills.json")
    with open(skills_file) as f:
        skills_data = json.load(f)

    total_evals = skills_data["load_info"]["total_evals"]
    skills = skills_data["skills"]

    print(f"📊 {total_evals} evals across {len(skills)} skills")
    for skill_name, skill_info in skills.items():
        eval_count = skill_info["eval_count"]
        print(f"  {skill_name}: {eval_count} evals")

    # Calculate expected tournament complexity
    models_file = Path("data/testonly/loaded_models.json")
    with open(models_file) as f:
        models_data = json.load(f)

    model_count = len(models_data["models"])
    judge_count = len(json.load(open("data/testonly/loaded_judges.json"))["judges"])

    print(f"📊 {model_count} models, {judge_count} judges")

    # For each eval: C(4,2) = 6 matches, 3 rounds, 3 judges per match = 18 judge decisions per eval
    expected_matches_per_eval = 6
    expected_judge_decisions_per_eval = expected_matches_per_eval * judge_count
    total_expected_decisions = total_evals * expected_judge_decisions_per_eval

    print(f"📊 Expected ~{total_expected_decisions} total judge decisions")
    print(f"📊 Expected ~{total_evals * expected_matches_per_eval} total matches")

    # Check current tournament files
    from .test_utils_judge_cache import get_judge_cache_dir

    judge_cache_dir = get_judge_cache_dir()
    tournament_files = list(judge_cache_dir.rglob("*.json"))
    print(f"📊 Found {len(tournament_files)} existing tournament files")

    # Check if we're missing the ethical_loopholes skill
    ethical_loopholes_dir = judge_cache_dir / "ethical_loopholes"
    ethical_files = list(ethical_loopholes_dir.glob("*.json")) if ethical_loopholes_dir.exists() else []
    print(f"📊 Found {len(ethical_files)} ethical_loopholes tournament files")

    if len(ethical_files) == 0:
        print("⚠️ No ethical_loopholes tournaments found - this may be where it's hanging!")

        # Check if the conversations exist for ethical_loopholes
        ethical_convs = [c for c in conversations.get("conversations", []) if c.get("skill_id") == "ethical_loopholes"]
        print(f"📊 Found {len(ethical_convs)} ethical_loopholes conversations")

        if len(ethical_convs) > 0:
            print("✅ Conversations exist, tournament should be runnable")
            return True
        else:
            print("❌ No conversations for ethical_loopholes - issue in conversation step")
            return False

    return True


def test_tournament_script_direct():
    """Test running a small portion of the tournament script directly."""
    print("🧪 Testing tournament script execution...")

    # Try to import and run just the setup part
    try:
        import sys

        sys.path.insert(0, "scripts")

        # Read the script to see what main function it has
        with open("scripts/run_tournaments.py") as f:
            script_content = f.read()

        if "def main(" in script_content:
            print("✅ Found main() function in tournament script")
        else:
            print("❌ No main() function found")

        if "if __name__ ==" in script_content:
            print("✅ Script has main execution block")
        else:
            print("❌ No main execution block")

        return True

    except Exception as e:
        print(f"❌ Error analyzing tournament script: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Running real tournament issue analysis...")

    test1_passed = test_actual_tournament_bottleneck()
    test2_passed = test_tournament_script_direct()

    if test1_passed and test2_passed:
        print("✅ Analysis complete - check output for bottlenecks")
    else:
        print("❌ Issues found in analysis")
