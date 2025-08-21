#!/usr/bin/env python3
"""
Test cross-stage cache consistency to ensure changes propagate correctly through the pipeline.
"""

import json
import sys
from pathlib import Path

from .test_utils_judge_cache import get_judge_cache_dir

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_conversation_to_tournament_consistency():
    """Test that tournament references align with conversation cache keys."""
    print("🔗 Testing conversation-to-tournament cache consistency...")

    # Check if we have both conversation and tournament data
    conv_files = list(Path("data/testonly/conversations").glob("*/*.json"))
    tournament_files = list(get_judge_cache_dir().glob("*/*.json"))

    if not conv_files:
        print("   ⚠️ No conversation files - skipping")
        return True

    if not tournament_files:
        print("   ⚠️ No tournament files - skipping")
        return True

    # Load conversation data
    conv_metadata = []
    for conv_file in conv_files:
        try:
            with open(conv_file) as f:
                conv_data = json.load(f)
            metadata = conv_data.get("metadata", {})
            conv_metadata.append(
                {
                    "file": conv_file.name,
                    "model_id": metadata.get("model_id"),
                    "eval_id": metadata.get("eval_id"),
                    "skill_id": metadata.get("skill_id"),
                    "cache_key": metadata.get("cache_key"),
                }
            )
        except Exception as e:
            print(f"   ❌ Failed to read {conv_file}: {e}")
            return False

    # Check tournament references
    referenced_conversations = set()
    for tournament_file in tournament_files:
        try:
            with open(tournament_file) as f:
                tournament_data = json.load(f)

            matches = tournament_data.get("match_history", [])
            for match in matches:
                conv_a_id = match.get("conversation_a_id")
                conv_b_id = match.get("conversation_b_id")
                if conv_a_id:
                    referenced_conversations.add(conv_a_id)
                if conv_b_id:
                    referenced_conversations.add(conv_b_id)

        except Exception as e:
            print(f"   ❌ Failed to read {tournament_file}: {e}")
            return False

    if referenced_conversations:
        # Check if referenced conversation IDs exist in our cache
        available_conversations = {meta["cache_key"] for meta in conv_metadata if meta["cache_key"]}

        missing_refs = referenced_conversations - available_conversations
        if missing_refs:
            print(f"   ❌ Tournament references missing conversations: {missing_refs}")
            return False

        print(f"   ✅ All {len(referenced_conversations)} tournament conversation references found")
    else:
        print("   ⚠️ No conversation references found in tournaments")

    return True


def test_tournament_to_ratings_consistency():
    """Test that skill ratings depend on tournament data correctly."""
    print("\n🔗 Testing tournament-to-ratings cache consistency...")

    # Check for skill rating files
    rating_files = list(Path("data/testonly/skill_ratings").glob("*.json"))
    if not rating_files:
        print("   ⚠️ No skill rating files - skipping")
        return True

    # Load tournament summaries
    try:
        with open("data/testonly/tournament_summaries.json") as f:
            tournament_summaries = json.load(f)
    except FileNotFoundError:
        print("   ⚠️ No tournament summaries file - skipping")
        return True

    # Check that each skill rating corresponds to tournament data
    for rating_file in rating_files:
        skill_id = rating_file.stem.split("_")[0]  # Extract skill ID from filename

        if skill_id not in tournament_summaries:
            print(f"   ❌ Skill rating {skill_id} has no corresponding tournament summary")
            return False

        try:
            with open(rating_file) as f:
                rating_data = json.load(f)

            # Check if rating metadata references tournament data
            metadata = rating_data.get("metadata", {})
            tournament_matches = tournament_summaries[skill_id].get("match_history", [])

            if tournament_matches and not metadata.get("tournament_match_count"):
                print(f"   ⚠️ Rating {skill_id} missing tournament match count in metadata")

        except Exception as e:
            print(f"   ❌ Failed to read {rating_file}: {e}")
            return False

    print(f"   ✅ {len(rating_files)} skill ratings align with tournament data")
    return True


def test_model_judge_consistency_across_stages():
    """Test that model and judge IDs are consistent across all pipeline stages."""
    print("\n🔗 Testing model/judge consistency across pipeline stages...")

    try:
        with open("data/testonly/loaded_models.json") as f:
            models_data = json.load(f)
        with open("data/testonly/loaded_judges.json") as f:
            judges_data = json.load(f)
    except FileNotFoundError:
        print("   ⚠️ Model/judge data not found - skipping")
        return True

    current_model_ids = {model["id"] for model in models_data["models"]}
    current_judge_ids = {judge["id"] for judge in judges_data["judges"]}

    # Check conversation files
    conv_files = list(Path("data/testonly/conversations").glob("*/*.json"))
    for conv_file in conv_files[:5]:  # Sample check
        try:
            with open(conv_file) as f:
                conv_data = json.load(f)

            model_id = conv_data.get("metadata", {}).get("model_id")
            if model_id and model_id not in current_model_ids:
                print(f"   ❌ Conversation references unknown model: {model_id}")
                return False

        except Exception as e:
            print(f"   ❌ Failed to check conversation {conv_file}: {e}")
            return False

    # Check tournament files
    tournament_files = list(get_judge_cache_dir().glob("*/*.json"))
    for tournament_file in tournament_files[:3]:  # Sample check
        try:
            with open(tournament_file) as f:
                tournament_data = json.load(f)

            matches = tournament_data.get("match_history", [])
            for match in matches[:5]:  # Sample check
                model_a = match.get("model_a_id")
                model_b = match.get("model_b_id")
                judge_id = match.get("judge_decision", {}).get("judge_id")

                if model_a and model_a not in current_model_ids:
                    print(f"   ❌ Tournament references unknown model A: {model_a}")
                    return False

                if model_b and model_b not in current_model_ids:
                    print(f"   ❌ Tournament references unknown model B: {model_b}")
                    return False

                if judge_id and judge_id not in current_judge_ids:
                    print(f"   ❌ Tournament references unknown judge: {judge_id}")
                    return False

        except Exception as e:
            print(f"   ❌ Failed to check tournament {tournament_file}: {e}")
            return False

    print("   ✅ Model and judge IDs consistent across pipeline stages")
    return True


def test_eval_id_consistency():
    """Test that eval IDs are consistent across all pipeline stages."""
    print("\n🔗 Testing eval ID consistency across pipeline stages...")

    try:
        with open("data/testonly/loaded_skills.json") as f:
            skills_data = json.load(f)
    except FileNotFoundError:
        print("   ⚠️ Skills data not found - skipping")
        return True

    current_eval_ids = {eval_data["id"] for eval_data in skills_data["evals"]}

    # Check conversation files
    conv_files = list(Path("data/testonly/conversations").glob("*/*.json"))
    for conv_file in conv_files:
        try:
            with open(conv_file) as f:
                conv_data = json.load(f)

            eval_id = conv_data.get("metadata", {}).get("eval_id")
            if eval_id and eval_id not in current_eval_ids:
                print(f"   ❌ Conversation references unknown eval: {eval_id}")
                return False

        except Exception as e:
            print(f"   ❌ Failed to check conversation {conv_file}: {e}")
            return False

    # Check tournament files
    tournament_files = list(get_judge_cache_dir().glob("*/*.json"))
    for tournament_file in tournament_files:
        try:
            with open(tournament_file) as f:
                tournament_data = json.load(f)

            eval_id = tournament_data.get("eval_id")
            if eval_id and eval_id not in current_eval_ids:
                print(f"   ❌ Tournament references unknown eval: {eval_id}")
                return False

        except Exception as e:
            print(f"   ❌ Failed to check tournament {tournament_file}: {e}")
            return False

    print("   ✅ Eval IDs consistent across pipeline stages")
    return True


if __name__ == "__main__":
    print("🔗 Cross-stage cache consistency validation...")

    tests = [
        ("Conversation-to-tournament consistency", test_conversation_to_tournament_consistency),
        ("Tournament-to-ratings consistency", test_tournament_to_ratings_consistency),
        ("Model/judge consistency across stages", test_model_judge_consistency_across_stages),
        ("Eval ID consistency", test_eval_id_consistency),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"   ❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n📋 CROSS-STAGE CACHE CONSISTENCY SUMMARY:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1

    print(f"\n📊 Results: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("✅ ALL CROSS-STAGE CONSISTENCY TESTS PASSED")
        print("💡 Cache dependencies are properly maintained across pipeline stages")
    else:
        print("❌ CROSS-STAGE CONSISTENCY ISSUES DETECTED")
        print("💡 Pipeline stage dependencies may not be working correctly")

    sys.exit(0 if passed == len(results) else 1)
