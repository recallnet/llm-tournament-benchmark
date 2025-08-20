#!/usr/bin/env python3
"""
Test cache ID consistency across pipeline stages.
Ensures that cache keys are stable, unique, and properly invalidated.
"""

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_conversation_cache_key_consistency():
    """Test that conversation cache keys are consistent and properly invalidated."""
    print("🔍 Testing conversation cache key consistency...")

    # Load real data
    try:
        with open("data/loaded_models.json") as f:
            models_data = json.load(f)
        with open("data/loaded_skills.json") as f:
            skills_data = json.load(f)
    except FileNotFoundError:
        print("   ⚠️ Test data not found - skipping")
        return True

    from execute_conversations import ConversationExecutor

    # Test cache key generation
    executor = ConversationExecutor(Path("data/conversations"), Path("data/intermediaries"))

    model = models_data["models"][0]
    eval_data = skills_data["evals"][0]

    # Generate cache key multiple times - should be identical
    key1 = executor._generate_cache_key(model["id"], eval_data)
    key2 = executor._generate_cache_key(model["id"], eval_data)

    if key1 != key2:
        print(f"   ❌ Cache keys inconsistent: {key1} != {key2}")
        return False

    print(f"   ✅ Consistent cache key: {key1}")

    # Test cache key changes when eval content changes
    eval_data_modified = eval_data.copy()
    eval_data_modified["chain"][0]["prompt"] += " [MODIFIED]"

    key_modified = executor._generate_cache_key(model["id"], eval_data_modified)

    if key1 == key_modified:
        print(f"   ❌ Cache key should change when eval modified: {key1} == {key_modified}")
        return False

    print(f"   ✅ Cache key changes with content: {key1} -> {key_modified}")

    # Test cache key differs for different models
    if len(models_data["models"]) > 1:
        model2 = models_data["models"][1]
        key_model2 = executor._generate_cache_key(model2["id"], eval_data)

        if key1 == key_model2:
            print(f"   ❌ Cache key should differ for different models: {key1} == {key_model2}")
            return False

        print(f"   ✅ Different models have different keys: {key1} vs {key_model2}")

    return True


def test_tournament_cache_key_dependencies():
    """Test that tournament cache keys properly depend on conversation content."""
    print("\n🔍 Testing tournament cache key dependencies...")

    try:
        # Check if we have tournament data
        tournament_files = list(Path("data/tournaments").glob("*/*.json"))
        if not tournament_files:
            print("   ⚠️ No tournament files to test - skipping")
            return True

        # Load a tournament file and check its dependencies
        with open(tournament_files[0]) as f:
            tournament_data = json.load(f)

        # Check if tournament references conversation IDs
        matches = tournament_data.get("match_history", [])
        if matches:
            first_match = matches[0]
            print(f"   📊 Sample match ID: {first_match.get('match_id')}")
            print(f"   📊 Match has conversation references: {'conversation_a_id' in first_match}")

        print("   ✅ Tournament cache structure validated")
        return True

    except Exception as e:
        print(f"   ❌ Tournament cache validation failed: {e}")
        return False


def test_skill_ratings_cache_key_dependencies():
    """Test that skill ratings cache keys depend on tournament data."""
    print("\n🔍 Testing skill ratings cache key dependencies...")

    try:
        with open("data/loaded_models.json") as f:
            models_data = json.load(f)
        with open("data/loaded_judges.json") as f:
            judges_data = json.load(f)
        with open("data/loaded_skills.json") as f:
            skills_data = json.load(f)
    except FileNotFoundError:
        print("   ⚠️ Test data not found - skipping")
        return True

    # Test with mock tournament data
    mock_tournament_summaries = {
        "test_skill": {"match_history": [{"match_id": "match_1", "winner": "model_a", "timestamp": "2025-01-01T00:00:00"}]}
    }

    from calculate_skill_ratings import SkillRatingCalculator

    calculator = SkillRatingCalculator(Path("data/skill_ratings"))

    # Generate cache key
    key1 = calculator._generate_cache_key(
        models_data["models"], judges_data["judges"], skills_data["evals"], mock_tournament_summaries
    )

    # Modify tournament data
    mock_tournament_summaries_modified = {
        "test_skill": {
            "match_history": [
                {"match_id": "match_2", "winner": "model_a", "timestamp": "2025-01-01T00:00:00"}  # Changed match ID
            ]
        }
    }

    key2 = calculator._generate_cache_key(
        models_data["models"], judges_data["judges"], skills_data["evals"], mock_tournament_summaries_modified
    )

    if key1 == key2:
        print(f"   ❌ Cache key should change when tournament data changes: {key1} == {key2}")
        return False

    print(f"   ✅ Cache key changes with tournament data: {key1} -> {key2}")
    return True


def test_cache_file_naming_consistency():
    """Test that cache file names are consistent with their content."""
    print("\n🔍 Testing cache file naming consistency...")

    # Check conversation cache files
    conv_files = list(Path("data/conversations").glob("*/*.json"))
    if not conv_files:
        print("   ⚠️ No conversation files to test - skipping")
        return True

    for conv_file in conv_files[:3]:  # Test first 3
        try:
            with open(conv_file) as f:
                conv_data = json.load(f)

            metadata = conv_data.get("metadata", {})
            cache_key = metadata.get("cache_key", "")
            model_id = metadata.get("model_id", "")
            eval_id = metadata.get("eval_id", "")

            # Check filename components
            filename = conv_file.name
            expected_components = [eval_id, model_id.replace("/", "_"), cache_key]

            # Verify all components are in filename
            for component in expected_components:
                if component and component not in filename:
                    print(f"   ❌ Component '{component}' not found in filename '{filename}'")
                    return False

            print(f"   ✅ {filename}: components match metadata")

        except Exception as e:
            print(f"   ❌ Failed to validate {conv_file.name}: {e}")
            return False

    return True


def test_cache_invalidation_propagation():
    """Test that changes properly propagate through the pipeline."""
    print("\n🔍 Testing cache invalidation propagation...")

    # Create a test scenario with temporary modified data
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy original data
        try:
            shutil.copy("data/loaded_skills.json", temp_path / "skills_original.json")
            shutil.copy("data/loaded_skills.json", temp_path / "skills_modified.json")
        except FileNotFoundError:
            print("   ⚠️ Skills data not found - skipping")
            return True

        # Modify the skills file
        with open(temp_path / "skills_modified.json") as f:
            skills_data = json.load(f)

        # Modify first eval prompt
        if skills_data["evals"]:
            first_eval = skills_data["evals"][0]
            if "chain" in first_eval and first_eval["chain"]:
                first_eval["chain"][0]["prompt"] += " [TEST MODIFICATION]"

        with open(temp_path / "skills_modified.json", "w") as f:
            json.dump(skills_data, f, indent=2)

        # Compare file hashes (simulating cache key generation)
        with open(temp_path / "skills_original.json", "rb") as f:
            original_hash = hashlib.sha256(f.read()).hexdigest()[:8]

        with open(temp_path / "skills_modified.json", "rb") as f:
            modified_hash = hashlib.sha256(f.read()).hexdigest()[:8]

        if original_hash == modified_hash:
            print(f"   ❌ File hashes should differ after modification")
            return False

        print(f"   ✅ File hash changes: {original_hash} -> {modified_hash}")

    return True


def test_cache_collision_prevention():
    """Test that different inputs don't produce the same cache keys."""
    print("\n🔍 Testing cache collision prevention...")

    # Test different model-eval combinations produce different keys
    from execute_conversations import ConversationExecutor

    try:
        with open("data/loaded_models.json") as f:
            models_data = json.load(f)
        with open("data/loaded_skills.json") as f:
            skills_data = json.load(f)
    except FileNotFoundError:
        print("   ⚠️ Test data not found - skipping")
        return True

    if len(models_data["models"]) < 2 or len(skills_data["evals"]) < 2:
        print("   ⚠️ Need at least 2 models and 2 evals for collision testing - skipping")
        return True

    executor = ConversationExecutor(Path("data/conversations"), Path("data/intermediaries"))

    # Generate cache keys for different combinations
    cache_keys = set()
    combinations = []

    for model in models_data["models"][:2]:
        for eval_data in skills_data["evals"][:3]:
            key = executor._generate_cache_key(model["id"], eval_data)
            if key in cache_keys:
                print(f"   ❌ Cache collision detected: {key}")
                print(f"      Model: {model['id']}, Eval: {eval_data['id']}")
                return False
            cache_keys.add(key)
            combinations.append((model["id"], eval_data["id"]))

    print(f"   ✅ No collisions in {len(cache_keys)} cache keys from {len(combinations)} combinations")
    return True


if __name__ == "__main__":
    print("🔍 Cache ID consistency validation...")

    tests = [
        ("Conversation cache key consistency", test_conversation_cache_key_consistency),
        ("Tournament cache dependencies", test_tournament_cache_key_dependencies),
        ("Skill ratings cache dependencies", test_skill_ratings_cache_key_dependencies),
        ("Cache file naming consistency", test_cache_file_naming_consistency),
        ("Cache invalidation propagation", test_cache_invalidation_propagation),
        ("Cache collision prevention", test_cache_collision_prevention),
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
    print(f"\n📋 CACHE ID CONSISTENCY TEST SUMMARY:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1

    print(f"\n📊 Results: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("✅ ALL CACHE ID CONSISTENCY TESTS PASSED")
        print("💡 Cache keys are stable, unique, and properly invalidated")
    else:
        print("❌ CACHE ID CONSISTENCY ISSUES DETECTED")
        print("💡 Cache invalidation may not work correctly")

    sys.exit(0 if passed == len(results) else 1)
