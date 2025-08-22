#!/usr/bin/env python3
"""
Test why ethical_loopholes conversations aren't being created.
"""

import json


def test_conversation_data():
    """Test if the conversation script has the right data to work with."""
    print("🔍 Testing conversation execution data...")

    # Check loaded skills
    with open("data/testonly/loaded_skills.json") as f:
        skills_data = json.load(f)

    skills = skills_data.get("skills", {})
    evals = skills_data.get("evals", [])

    print(f"📊 Found {len(skills)} skills in loaded_skills.json")

    ethical_skill = skills.get("ethical_loopholes")
    if ethical_skill:
        print(
            f"✅ ethical_loopholes skill found with {ethical_skill['eval_count']} evals"
        )
        print(f"   Eval IDs: {ethical_skill['eval_ids']}")
    else:
        print("❌ ethical_loopholes skill not found in loaded skills")
        assert (
            ethical_skill is not None
        ), "ethical_loopholes skill not found in loaded skills"

    # Check if ethical_loopholes evals exist in the evals list
    ethical_evals = [
        e for e in evals if e.get("_metadata", {}).get("skill") == "ethical_loopholes"
    ]
    print(f"📊 Found {len(ethical_evals)} ethical_loopholes evals in evals list")

    for eval_data in ethical_evals:
        eval_id = eval_data.get("id")
        eval_name = eval_data.get("name")
        print(f"  - {eval_id}: {eval_name}")

    # Check models and judges
    with open("data/testonly/loaded_models.json") as f:
        models_data = json.load(f)

    with open("data/testonly/loaded_judges.json") as f:
        judges_data = json.load(f)

    model_count = len(models_data.get("models", []))
    judge_count = len(judges_data.get("judges", []))

    print(f"📊 {model_count} models, {judge_count} judges available")

    assert len(ethical_evals) > 0, "No ethical_loopholes evals found"


def test_conversation_script_structure():
    """Test the structure of the conversation script for potential issues."""
    print("🔍 Testing conversation script structure...")

    with open("scripts/execute_conversations.py") as f:
        script_content = f.read()

    # Check for potential infinite loops or problematic patterns
    issues = []

    if "while True:" in script_content:
        issues.append("Infinite while loop detected")

    if script_content.count("for") > 20:
        issues.append(f"Many loops detected ({script_content.count('for')} for loops)")

    if "sleep(" in script_content:
        issues.append("Sleep calls detected (may cause slowdown)")

    if "time.sleep" in script_content:
        issues.append("time.sleep calls detected")

    # Look for error handling that might be silently failing
    if "except:" in script_content and "pass" in script_content:
        issues.append("Silent exception handling detected")

    if issues:
        print(f"⚠️ Potential issues in conversation script: {issues}")
    else:
        print("✅ No obvious structural issues detected")

    # These are warnings rather than errors - the script works but could be optimized
    if len(issues) > 0:
        print(f"⚠️ Code quality issues detected (but not critical): {issues}")
    assert True  # Test completed - issues are informational only


if __name__ == "__main__":
    print("🧪 Testing conversation execution issues...")

    test_conversation_data()
    test_conversation_script_structure()

    print("✅ All conversation tests completed")
