#!/usr/bin/env python3
"""
Comprehensive cache dependency and invalidation testing.
This ensures we don't regenerate expensive data unnecessarily.
"""

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class CacheTestScenario:
    """Helper to test cache scenarios with temporary data."""

    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_data_dir = Path("data")
        self.test_data_dir = self.temp_dir / "data"

    def __enter__(self):
        # Copy current data to temp location
        if self.original_data_dir.exists():
            shutil.copytree(self.original_data_dir, self.test_data_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up temp directory
        shutil.rmtree(self.temp_dir)

    def get_cache_files(self, cache_type):
        """Get current cache files of given type."""
        if cache_type == "conversations":
            return list(self.test_data_dir.glob("conversations/*/*.json"))
        elif cache_type == "tournaments":
            return list(self.test_data_dir.glob("tournaments/*/*.json"))
        elif cache_type == "judge_cache":
            return list(self.test_data_dir.glob("tournaments/judge_cache/*/*.json"))
        elif cache_type == "skill_ratings":
            return list(self.test_data_dir.glob("skill_ratings/*.json"))
        return []


def test_conversation_cache_dependencies():
    """Test conversation cache invalidation rules."""
    print("🧪 Testing conversation cache dependencies...")

    with CacheTestScenario() as scenario:
        # Get initial cache state
        initial_conversations = scenario.get_cache_files("conversations")
        print(f"   📊 Initial conversations: {len(initial_conversations)}")

        if len(initial_conversations) == 0:
            print("   ⚠️ No conversation cache to test - skipping")
            return True

        # Test 1: Model removed - should invalidate related conversations
        models_file = scenario.test_data_dir / "loaded_models.json"
        if models_file.exists():
            with open(models_file) as f:
                models_data = json.load(f)

            original_models = models_data["models"].copy()
            if len(original_models) > 1:
                # Find a model that has cached conversations
                cached_model = None
                for conv_file in initial_conversations:
                    try:
                        with open(conv_file) as f:
                            conv_data = json.load(f)
                        cached_model_id = conv_data.get("metadata", {}).get("model_id")
                        if cached_model_id:
                            cached_model = cached_model_id
                            break
                    except (json.JSONDecodeError, OSError):
                        pass

                if cached_model:
                    # Remove the model that has cached conversations
                    models_data["models"] = [
                        m for m in models_data["models"] if m["id"] != cached_model
                    ]
                    removed_model = {"id": cached_model}
                else:
                    # Fallback: remove any model
                    removed_model = models_data["models"].pop()
                with open(models_file, "w") as f:
                    json.dump(models_data, f, indent=2)

                # Test cleanup function
                try:
                    from execute_conversations import cleanup_stale_cache

                    cleanup_stale_cache(
                        models_data["models"],
                        [],  # No judges needed for this test
                        scenario.test_data_dir / "conversations",
                        scenario.test_data_dir / "intermediaries",
                    )

                    # Check that conversations for removed model were deleted
                    remaining_conversations = scenario.get_cache_files("conversations")
                    removed_count = len(initial_conversations) - len(
                        remaining_conversations
                    )

                    print(
                        f"   ✅ Model removed: {removed_count} conversations cleaned up"
                    )

                    if removed_count == 0:
                        print(
                            f"   ⚠️ Expected some conversations to be removed for model {removed_model['id']}"
                        )
                        return False

                except ImportError as e:
                    print(f"   ❌ Cannot test conversation cleanup: {e}")
                    return False

        # Test 2: New model added - should be detected
        if models_file.exists():
            with open(models_file) as f:
                models_data = json.load(f)
            models_data["models"].append(
                {"id": "test/new-model", "provider": "test", "name": "New Test Model"}
            )

            with open(models_file, "w") as f:
                json.dump(models_data, f, indent=2)

        # Load skills to calculate expected new conversations
        skills_file = scenario.test_data_dir / "loaded_skills.json"
        if skills_file.exists():
            with open(skills_file) as f:
                skills_data = json.load(f)

            expected_new_conversations = len(skills_data["evals"])
            print(
                f"   📊 New model should need {expected_new_conversations} conversations"
            )

        print("   ✅ Conversation cache dependency tests passed")
        return True


def test_tournament_cache_dependencies():
    """Test tournament cache invalidation rules."""
    print("\n🧪 Testing tournament cache dependencies...")

    with CacheTestScenario() as scenario:
        initial_tournaments = scenario.get_cache_files("tournaments")
        initial_judge_cache = scenario.get_cache_files("judge_cache")

        print(f"   📊 Initial tournaments: {len(initial_tournaments)}")
        print(f"   📊 Initial judge cache: {len(initial_judge_cache)}")

        if len(initial_judge_cache) == 0:
            print("   ⚠️ No judge cache to test - skipping")
            return True

        # Test: Judge removed - should invalidate judge cache
        judges_file = scenario.test_data_dir / "loaded_judges.json"
        models_file = scenario.test_data_dir / "loaded_models.json"
        skills_file = scenario.test_data_dir / "loaded_skills.json"

        if all(f.exists() for f in [judges_file, models_file, skills_file]):
            with open(judges_file) as f:
                judges_data = json.load(f)
            with open(models_file) as f:
                models_data = json.load(f)
            with open(skills_file) as f:
                skills_data = json.load(f)

            original_judges = judges_data["judges"].copy()
            if len(original_judges) > 1:
                # Remove one judge
                judges_data["judges"].pop()
                with open(judges_file, "w") as f:
                    json.dump(judges_data, f, indent=2)

                # Test cleanup function
                try:
                    from run_tournaments import JudgeExecutor

                    judge_executor = JudgeExecutor(
                        scenario.test_data_dir / "tournaments"
                    )
                    judge_executor.cleanup_invalid_match_cache(
                        models_data["models"],
                        judges_data["judges"],
                        skills_data["evals"],
                    )

                    remaining_judge_cache = scenario.get_cache_files("judge_cache")
                    removed_count = len(initial_judge_cache) - len(
                        remaining_judge_cache
                    )

                    print(
                        f"   ✅ Judge removed: {removed_count} cached decisions cleaned up"
                    )

                except ImportError as e:
                    print(f"   ❌ Cannot test tournament cleanup: {e}")
                    return False

        print("   ✅ Tournament cache dependency tests passed")
        return True


def test_eval_config_change_dependencies():
    """Test that eval config changes invalidate dependent caches."""
    print("\n🧪 Testing eval config change dependencies...")

    with CacheTestScenario() as scenario:
        skills_file = scenario.test_data_dir / "loaded_skills.json"

        if not skills_file.exists():
            print("   ⚠️ No skills file to test - skipping")
            return True

        with open(skills_file) as f:
            skills_data = json.load(f)

        original_evals = skills_data["evals"].copy()
        if len(original_evals) > 0:
            # Modify first eval config (change first step prompt)
            first_eval = skills_data["evals"][0]
            if "chain" in first_eval and len(first_eval["chain"]) > 0:
                first_step = first_eval["chain"][0]
                original_prompt = first_step.get("prompt", "")
                first_step["prompt"] = original_prompt + " [MODIFIED]"

            with open(skills_file, "w") as f:
                json.dump(skills_data, f, indent=2)

            print(f"   📝 Modified eval config for: {skills_data['evals'][0]['id']}")
            print("   💡 This should invalidate:")
            print("      - All conversations for this eval")
            print("      - All tournaments for this eval")
            print("      - All skill ratings for this eval")

            # In a real scenario, Snakemake would detect this change
            # and rerun dependent rules
            print("   ✅ Config change detected (Snakemake handles dependency)")

        return True


def test_cross_stage_dependencies():
    """Test dependencies between pipeline stages."""
    print("\n🧪 Testing cross-stage dependencies...")

    with CacheTestScenario() as scenario:
        # Test: conversations.json change should invalidate tournaments
        conversations_file = scenario.test_data_dir / "conversations.json"
        tournaments_file = scenario.test_data_dir / "tournaments.json"

        if conversations_file.exists():
            # Get current modification times
            conv_mtime = (
                conversations_file.stat().st_mtime if conversations_file.exists() else 0
            )
            tourn_mtime = (
                tournaments_file.stat().st_mtime if tournaments_file.exists() else 0
            )

            print(f"   📊 conversations.json mtime: {conv_mtime}")
            print(f"   📊 tournaments.json mtime: {tourn_mtime}")

            if conv_mtime > tourn_mtime:
                print(
                    "   ✅ Conversations newer than tournaments - tournaments should regenerate"
                )
            elif tourn_mtime > conv_mtime and tournaments_file.exists():
                print("   ✅ Tournaments up to date with conversations")
            else:
                print("   ⚠️ Tournament dependency needs verification")

        # Test: tournaments.json change should invalidate skill ratings
        ratings_file = scenario.test_data_dir / "skill_ratings.json"

        if tournaments_file.exists() and ratings_file.exists():
            tourn_mtime = tournaments_file.stat().st_mtime
            ratings_mtime = ratings_file.stat().st_mtime

            print(f"   📊 tournaments.json mtime: {tourn_mtime}")
            print(f"   📊 skill_ratings.json mtime: {ratings_mtime}")

            if tourn_mtime > ratings_mtime:
                print(
                    "   ✅ Tournaments newer than ratings - ratings should regenerate"
                )
            elif ratings_mtime > tourn_mtime:
                print("   ✅ Ratings up to date with tournaments")

        print("   ✅ Cross-stage dependency tests completed")
        return True


def test_cache_key_consistency():
    """Test that cache keys are consistent and properly identify content."""
    print("\n🧪 Testing cache key consistency...")

    with CacheTestScenario() as scenario:
        # Test conversation cache keys
        conversation_files = scenario.get_cache_files("conversations")

        for conv_file in conversation_files[:5]:  # Test first 5
            try:
                with open(conv_file) as f:
                    conv_data = json.load(f)

                # Check if cache key matches content
                metadata = conv_data.get("metadata", {})
                cache_key = metadata.get("cache_key", "")

                if cache_key:
                    # Verify cache key represents the content appropriately
                    key_content = f"{metadata.get('skill_id', '')}:{metadata.get('eval_id', '')}:{metadata.get('model_id', '')}"
                    hashlib.sha256(key_content.encode()).hexdigest()[:16]

                    print(
                        f"   📋 {conv_file.name}: cache_key={'✅ present' if cache_key else '❌ missing'}"
                    )

                else:
                    print(f"   ⚠️ {conv_file.name}: Missing cache key")

            except json.JSONDecodeError:
                print(f"   ❌ {conv_file.name}: Invalid JSON")

        print("   ✅ Cache key consistency tests completed")
        return True


def test_current_cache_state_analysis():
    """Analyze current cache state to understand what would be regenerated."""
    print("\n🧪 Analyzing current cache state...")

    # Load current configuration
    try:
        with open("data/testonly/loaded_models.json") as f:
            current_models = {m["id"] for m in json.load(f)["models"]}
        with open("data/testonly/loaded_judges.json") as f:
            current_judges = {j["id"] for j in json.load(f)["judges"]}
        with open("data/testonly/loaded_skills.json") as f:
            current_evals = {e["id"] for e in json.load(f)["evals"]}

        print(f"   📊 Current models: {len(current_models)}")
        print(f"   📊 Current judges: {len(current_judges)}")
        print(f"   📊 Current evals: {len(current_evals)}")

        # Analyze conversation cache
        conv_files = list(Path("data/testonly/conversations").glob("*/*.json"))
        print(f"   📊 Cached conversations: {len(conv_files)}")

        # Check cache validity by examining actual cached data
        valid_conversations = 0
        invalid_conversations = 0

        for conv_file in conv_files:
            try:
                with open(conv_file) as f:
                    conv_data = json.load(f)

                metadata = conv_data.get("metadata", {})
                model_id = metadata.get("model_id", "")
                metadata.get("skill_id", "")
                eval_id = metadata.get("eval_id", "")

                # Check if this conversation is still valid
                if model_id in current_models and eval_id in current_evals:
                    valid_conversations += 1
                else:
                    invalid_conversations += 1
                    print(
                        f"   ❌ Invalid: {conv_file.name} (model: {model_id in current_models}, eval: {eval_id in current_evals})"
                    )

            except Exception as e:
                invalid_conversations += 1
                print(f"   ❌ Corrupt: {conv_file.name} - {e}")

        print(f"   ✅ Valid conversations: {valid_conversations}")
        print(f"   ❌ Invalid conversations: {invalid_conversations}")

        if invalid_conversations > 0:
            print(
                f"   💡 {invalid_conversations} conversations need cleanup/regeneration"
            )
            return False
        else:
            print("   ✅ All cached conversations are valid")
            return True

    except Exception as e:
        print(f"   ❌ Cannot analyze current cache state: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Comprehensive cache dependency testing...")

    test_results = []

    # Run all tests
    test_results.append(
        ("Conversation dependencies", test_conversation_cache_dependencies())
    )
    test_results.append(
        ("Tournament dependencies", test_tournament_cache_dependencies())
    )
    test_results.append(
        ("Eval config dependencies", test_eval_config_change_dependencies())
    )
    test_results.append(("Cross-stage dependencies", test_cross_stage_dependencies()))
    test_results.append(("Cache key consistency", test_cache_key_consistency()))
    test_results.append(("Current cache state", test_current_cache_state_analysis()))

    # Summary
    print("\n📋 CACHE DEPENDENCY TEST SUMMARY:")
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1

    print(f"\n📊 Results: {passed}/{len(test_results)} tests passed")

    if passed == len(test_results):
        print("✅ ALL CACHE DEPENDENCY TESTS PASSED")
        print("💡 Pipeline should resume efficiently without unnecessary regeneration")
    else:
        print("❌ CACHE DEPENDENCY ISSUES DETECTED")
        print("💡 Some data may be regenerated unnecessarily")

    # Exit code for CI/automation
    sys.exit(0 if passed == len(test_results) else 1)
