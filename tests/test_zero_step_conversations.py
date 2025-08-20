#!/usr/bin/env python3
"""
Test to identify if zero-step conversations are causing the tournament hang.
This will check if conversations with 0 steps are causing issues in judge execution.
"""

import json
import sys
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_zero_step_conversations():
    """Test if conversations with 0 steps exist and could cause issues."""
    conversations_file = Path("data/conversations.json")
    if not conversations_file.exists():
        raise AssertionError("conversations.json not found")

    with open(conversations_file) as f:
        conversations_data = json.load(f)

    # Find all conversations with 0 steps
    zero_step_conversations = []
    ethical_zero_step = []

    for conv in conversations_data.get("conversations", []):
        steps = conv.get("steps", [])
        if len(steps) == 0:
            zero_step_conversations.append(conv)

            # Check if it's ethical_loopholes
            metadata = conv.get("metadata", {})
            if metadata.get("skill_id") == "ethical_loopholes":
                ethical_zero_step.append(conv)

    has_zero_steps = len(zero_step_conversations) > 0
    has_ethical_zero_steps = len(ethical_zero_step) > 0

    if has_zero_steps:
        print(f"Found {len(zero_step_conversations)} zero-step conversations")
        print(f"Found {len(ethical_zero_step)} ethical zero-step conversations")
        for conv in ethical_zero_step:
            print(f"  - {conv['metadata'].get('model_id')}: {conv['metadata'].get('eval_id')}")

    # Return for compatibility with other functions that check this
    return has_zero_steps, {
        "total_zero_step": len(zero_step_conversations),
        "ethical_zero_step": len(ethical_zero_step),
        "ethical_details": [
            {
                "model_id": conv["metadata"].get("model_id"),
                "eval_id": conv["metadata"].get("eval_id"),
                "has_messages": len(conv.get("messages", [])),
                "has_final": bool(conv.get("final")),
            }
            for conv in ethical_zero_step
        ],
    }


def test_judge_view_building_with_zero_steps():
    """Test if judge view building fails with zero-step conversations."""
    try:
        from run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor()

        # Load required data
        with open("data/conversations.json") as f:
            conversations_data = json.load(f)

        with open("data/loaded_skills.json") as f:
            skills_data = json.load(f)

        with open("data/loaded_models.json") as f:
            models = json.load(f)["models"]

        # Get an ethical eval
        ethical_evals = [e for e in skills_data["evals"] if e.get("_metadata", {}).get("skill") == "ethical_loopholes"]
        if not ethical_evals:
            raise AssertionError("No ethical evals found")

        test_eval = ethical_evals[0]
        eval_id = test_eval["id"]
        skill_id = test_eval["_metadata"]["skill"]

        judge_config = test_eval.get("judge", {})
        if "view" not in judge_config:
            return False, "No judge view config found"

        view_failures = []

        for model in models:
            model_id = model["id"]
            view_spec_a = judge_config["view"].get("A", [])

            try:
                view_content = judge_executor._build_view_content(
                    view_spec_a, conversations_data, conversations_data, model_id, skill_id, eval_id
                )

                # Check for error markers or problematic content
                issues = []
                if "[STEP_NOT_FOUND:" in view_content:
                    issues.append("step_not_found")
                if "[NO_FINAL_RESPONSE]" in view_content:
                    issues.append("no_final_response")
                if len(view_content) < 10:
                    issues.append(f"short_content_{len(view_content)}")

                if issues:
                    view_failures.append({"model_id": model_id, "issues": issues, "content_length": len(view_content)})

            except Exception as e:
                view_failures.append({"model_id": model_id, "error": str(e)})

        has_failures = len(view_failures) > 0
        if has_failures:
            print(f"View building failures: {len(view_failures)}")
            for failure in view_failures:
                print(f"  - {failure}")

        return has_failures, {"view_failures": view_failures}

    except Exception as e:
        print(f"Import error in judge view test: {e}")
        return True, {"import_error": str(e)}


def test_conversation_structure_issues():
    """Test if conversation structure has issues that could cause hangs."""
    conversations_file = Path("data/conversations.json")
    if not conversations_file.exists():
        raise AssertionError("conversations.json not found")

    with open(conversations_file) as f:
        conversations_data = json.load(f)

    # Check ethical conversations specifically
    ethical_conversations = []
    for conv in conversations_data.get("conversations", []):
        metadata = conv.get("metadata", {})
        if metadata.get("skill_id") == "ethical_loopholes":
            ethical_conversations.append(conv)

    structure_issues = []

    for conv in ethical_conversations:
        model_id = conv["metadata"]["model_id"]
        eval_id = conv["metadata"]["eval_id"]

        issues = []

        # Check structure
        if "steps" not in conv:
            issues.append("missing_steps_field")
        elif len(conv["steps"]) == 0:
            issues.append("zero_steps")

        if "messages" not in conv:
            issues.append("missing_messages_field")
        elif len(conv["messages"]) == 0:
            issues.append("zero_messages")

        if "final" not in conv:
            issues.append("missing_final_field")
        elif not conv["final"]:
            issues.append("empty_final")

        if issues:
            structure_issues.append({"model_id": model_id, "eval_id": eval_id, "issues": issues})

    has_issues = len(structure_issues) > 0
    if has_issues:
        print(f"Structure issues found: {len(structure_issues)}")
        for issue in structure_issues:
            print(f"  - {issue}")

    return has_issues, {"structure_issues": structure_issues, "total_ethical": len(ethical_conversations)}


def test_conversations_need_regeneration():
    """Test if conversations need regeneration due to structural problems."""
    zero_step_issue, zero_step_data = test_zero_step_conversations()
    view_issue, view_data = test_judge_view_building_with_zero_steps()
    structure_issue, structure_data = test_conversation_structure_issues()

    needs_regeneration = zero_step_issue or view_issue or structure_issue

    if needs_regeneration:
        print("Conversations need regeneration due to structural problems")
    else:
        print("Conversation structure appears healthy")

    return needs_regeneration, {
        "zero_step_issue": zero_step_issue,
        "zero_step_data": zero_step_data,
        "view_issue": view_issue,
        "view_data": view_data,
        "structure_issue": structure_issue,
        "structure_data": structure_data,
    }


if __name__ == "__main__":
    print("🧪 Testing zero-step conversation issues...")

    needs_regeneration, test_data = test_conversations_need_regeneration()

    if needs_regeneration:
        print("❌ ISSUE IDENTIFIED: Conversations have structural problems")
        print("💡 SOLUTION: Regenerate conversations for ethical_loopholes")
        print("\n🔧 To fix:")
        print("1. Remove conversations.json to force regeneration:")
        print("   rm data/conversations.json")
        print("2. Rerun the pipeline:")
        print("   snakemake --profile profiles/test")

        # Show specific issues
        if test_data["zero_step_issue"]:
            print(f"\n📊 Zero-step conversations: {test_data['zero_step_data']['total_zero_step']}")
            print(f"📊 Ethical zero-step: {test_data['zero_step_data']['ethical_zero_step']}")

        if test_data["view_issue"]:
            failures = test_data["view_data"]["view_failures"]
            print(f"\n⚠️ View building failures: {len(failures)}")

        if test_data["structure_issue"]:
            issues = test_data["structure_data"]["structure_issues"]
            print(f"\n⚠️ Structure issues: {len(issues)}")

        print("\n🎯 ROOT CAUSE: Malformed conversations causing judge execution issues")
    else:
        print("✅ Conversations structure looks OK - hang must be elsewhere")
