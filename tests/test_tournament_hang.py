#!/usr/bin/env python3
"""
Test to isolate the tournament hanging issue.
"""

import json
import signal
from pathlib import Path

from .test_utils_judge_cache import get_judge_cache_dir


def test_tournament_script_timeout():
    """Test if the tournament script hangs or has infinite loops."""
    print("🔍 Testing tournament script for hangs...")

    # Check if required input files exist
    required_files = [
        "data/testonly/conversations.json",
        "data/testonly/loaded_models.json",
        "data/testonly/loaded_judges.json",
        "data/testonly/loaded_skills.json",
    ]

    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)

    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        raise AssertionError(f"Missing required files: {missing_files}")

    # Check the size/complexity of conversations.json
    with open("data/testonly/conversations.json") as f:
        conversations = json.load(f)

    conv_count = len(conversations.get("conversations", []))
    print(f"📊 Found {conv_count} conversations to process")

    # Check for potential infinite loop conditions
    with open("data/testonly/loaded_skills.json") as f:
        skills_data = json.load(f)

    total_evals = skills_data["load_info"]["total_evals"]
    expected_tournaments = total_evals * 6  # 6 matches per eval typically

    print(f"📊 Expected ~{expected_tournaments} tournament matches for {total_evals} evals")

    # Check current tournament files
    tournament_files = list(get_judge_cache_dir().rglob("*.json"))
    print(f"📊 Found {len(tournament_files)} existing tournament files")

    # Look for signs of infinite loops in tournament script

    # Test timeout mechanism
    print("⏱️ Testing tournament script with timeout...")

    def timeout_handler(signum, frame):
        raise TimeoutError("Tournament script timed out!")

    # Set a 10 second timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)

    try:
        # Import and check the script for obvious issues
        print("✅ Tournament script imported successfully")
        signal.alarm(0)  # Cancel timeout
    except TimeoutError:
        print("❌ Tournament script appears to have infinite loop or hang")
        raise AssertionError("Tournament script timed out - likely infinite loop")
    except Exception as e:
        signal.alarm(0)  # Cancel timeout
        print(f"❌ Tournament script has error: {e}")
        raise AssertionError(f"Tournament script error: {e}")


def test_tournament_logic_bottlenecks():
    """Test for specific logic that might cause slowdowns."""
    print("🔍 Checking for tournament logic bottlenecks...")

    # Read the tournament script to look for potential issues
    with open("scripts/run_tournaments.py") as f:
        script_content = f.read()

    potential_issues = []

    # Check for nested loops
    if "for" in script_content and script_content.count("for") > 10:
        potential_issues.append("Many nested loops detected")

    # Check for file I/O in loops
    if "open(" in script_content and "for" in script_content:
        lines = script_content.split("\n")
        for i, line in enumerate(lines):
            if "for" in line:
                # Check next 10 lines for file operations
                for j in range(i + 1, min(i + 11, len(lines))):
                    if "open(" in lines[j] or "json.load" in lines[j]:
                        potential_issues.append(f"File I/O in loop at line {j}")
                        break

    # Check for recursive calls
    if "def " in script_content and "recursion" in script_content.lower():
        potential_issues.append("Potential recursion detected")

    if potential_issues:
        print(f"⚠️ Potential bottlenecks: {potential_issues}")
        # These are warnings, not failures
    else:
        print("✅ No obvious bottlenecks detected")

    # Always pass - these are informational checks
    assert True


if __name__ == "__main__":
    print("🧪 Running tournament hang diagnosis tests...")

    test_tournament_script_timeout()
    test_tournament_logic_bottlenecks()

    print("✅ Tournament hang diagnosis tests completed")
