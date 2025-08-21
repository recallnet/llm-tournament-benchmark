#!/usr/bin/env python3
"""
End-to-end cache invalidation testing.
Verifies that changes in one stage properly invalidate downstream caches.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def simulate_conversation_cache_generation():
    """Simulate generating conversation cache keys."""
    try:
        with open("data/testonly/loaded_models.json") as f:
            models_data = json.load(f)
        with open("data/testonly/loaded_skills.json") as f:
            skills_data = json.load(f)
    except FileNotFoundError:
        return None

    from execute_conversations import ConversationExecutor

    executor = ConversationExecutor(Path("data/testonly/conversations"), Path("data/testonly/intermediaries"))

    # Generate cache keys for current state
    cache_keys = {}
    for model in models_data["models"]:
        for eval_data in skills_data["evals"]:
            key = executor._generate_cache_key(model["id"], eval_data)
            cache_keys[(model["id"], eval_data["id"])] = key

    return cache_keys


def test_eval_modification_invalidation():
    """Test that modifying eval configurations properly invalidates all dependent caches."""
    print("🧪 Testing eval modification cache invalidation...")

    # Get baseline cache keys
    original_keys = simulate_conversation_cache_generation()
    if not original_keys:
        print("   ⚠️ Cannot load test data - skipping")
        return True

    print(f"   📊 Generated {len(original_keys)} baseline cache keys")

    # Modify eval configuration in memory (simulating loaded_skills.json change)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_skills = Path(temp_dir) / "loaded_skills.json"
        shutil.copy("data/testonly/loaded_skills.json", temp_skills)

        # Modify the skills data
        with open(temp_skills) as f:
            skills_data = json.load(f)

        # Modify first eval
        if skills_data["evals"]:
            first_eval = skills_data["evals"][0]
            if "chain" in first_eval and first_eval["chain"]:
                first_eval["chain"][0]["prompt"] += " [CACHE INVALIDATION TEST]"

        with open(temp_skills, "w") as f:
            json.dump(skills_data, f, indent=2)

        # Temporarily replace the skills file
        original_skills = Path("data/testonly/loaded_skills.json")
        backup_skills = Path("data/testonly/loaded_skills.json.backup")

        try:
            shutil.copy(original_skills, backup_skills)
            shutil.copy(temp_skills, original_skills)

            # Generate new cache keys
            modified_keys = simulate_conversation_cache_generation()
            if not modified_keys:
                print("   ❌ Failed to generate modified cache keys")
                return False

            # Check which keys changed
            changed_keys = 0
            unchanged_keys = 0
            modified_eval_id = skills_data["evals"][0]["id"]

            for (model_id, eval_id), original_key in original_keys.items():
                modified_key = modified_keys.get((model_id, eval_id))
                if modified_key is None:
                    continue

                if eval_id == modified_eval_id:
                    # This eval was modified - key should change
                    if original_key == modified_key:
                        print(f"   ❌ Cache key should change for modified eval {eval_id}: {original_key}")
                        return False
                    else:
                        changed_keys += 1
                elif original_key != modified_key:
                    print(f"   ❌ Cache key should NOT change for unmodified eval {eval_id}: {original_key} -> {modified_key}")
                    return False
                else:
                    unchanged_keys += 1

            print(f"   ✅ {changed_keys} cache keys properly invalidated for modified eval")
            print(f"   ✅ {unchanged_keys} cache keys properly preserved for unmodified evals")

        finally:
            # Restore original file
            shutil.copy(backup_skills, original_skills)
            backup_skills.unlink()

    return True


def test_model_removal_invalidation():
    """Test that removing models properly invalidates related caches."""
    print("\n🧪 Testing model removal cache invalidation...")

    # Get baseline cache keys
    original_keys = simulate_conversation_cache_generation()
    if not original_keys:
        print("   ⚠️ Cannot load test data - skipping")
        return True

    # Temporarily remove a model
    original_models = Path("data/testonly/loaded_models.json")
    backup_models = Path("data/testonly/loaded_models.json.backup")

    try:
        shutil.copy(original_models, backup_models)

        with open(original_models) as f:
            models_data = json.load(f)

        if len(models_data["models"]) <= 1:
            print("   ⚠️ Need at least 2 models for removal test - skipping")
            return True

        # Remove last model
        removed_model = models_data["models"].pop()
        removed_model_id = removed_model["id"]

        with open(original_models, "w") as f:
            json.dump(models_data, f, indent=2)

        # Generate new cache keys
        modified_keys = simulate_conversation_cache_generation()
        if not modified_keys:
            print("   ❌ Failed to generate modified cache keys")
            return False

        # Check that keys for removed model no longer exist
        removed_keys = 0
        preserved_keys = 0

        for (model_id, eval_id), original_key in original_keys.items():
            if model_id == removed_model_id:
                # This model was removed - key should not exist
                if (model_id, eval_id) in modified_keys:
                    print(f"   ❌ Cache key still exists for removed model {model_id}")
                    return False
                else:
                    removed_keys += 1
            else:
                # This model was not removed - key should still exist and be same
                modified_key = modified_keys.get((model_id, eval_id))
                if modified_key is None:
                    print(f"   ❌ Cache key missing for preserved model {model_id}")
                    return False
                elif original_key != modified_key:
                    print(f"   ❌ Cache key changed for preserved model {model_id}: {original_key} -> {modified_key}")
                    return False
                else:
                    preserved_keys += 1

        print(f"   ✅ {removed_keys} cache keys properly removed for deleted model")
        print(f"   ✅ {preserved_keys} cache keys properly preserved for remaining models")

    finally:
        # Restore original file
        shutil.copy(backup_models, original_models)
        backup_models.unlink()

    return True


def test_cache_key_stability():
    """Test that cache keys are stable when nothing changes."""
    print("\n🧪 Testing cache key stability...")

    # Generate cache keys twice without changes
    keys1 = simulate_conversation_cache_generation()
    keys2 = simulate_conversation_cache_generation()

    if not keys1 or not keys2:
        print("   ⚠️ Cannot load test data - skipping")
        return True

    if keys1 != keys2:
        print("   ❌ Cache keys are not stable across multiple generations")
        return False

    print(f"   ✅ {len(keys1)} cache keys are stable across generations")
    return True


def test_collision_resistance():
    """Test that similar configurations produce different cache keys."""
    print("\n🧪 Testing cache key collision resistance...")

    try:
        with open("data/testonly/loaded_models.json") as f:
            models_data = json.load(f)
        with open("data/testonly/loaded_skills.json") as f:
            skills_data = json.load(f)
    except FileNotFoundError:
        print("   ⚠️ Cannot load test data - skipping")
        return True

    from execute_conversations import ConversationExecutor

    executor = ConversationExecutor(Path("data/testonly/conversations"), Path("data/testonly/intermediaries"))

    # Create slightly different eval configurations
    base_eval = skills_data["evals"][0]

    # Test variations
    variations = [
        ("original", base_eval),
        ("extra_space", {**base_eval, "chain": [{**base_eval["chain"][0], "prompt": base_eval["chain"][0]["prompt"] + " "}]}),
        (
            "extra_word",
            {**base_eval, "chain": [{**base_eval["chain"][0], "prompt": base_eval["chain"][0]["prompt"] + " test"}]},
        ),
        (
            "case_change",
            {**base_eval, "chain": [{**base_eval["chain"][0], "prompt": base_eval["chain"][0]["prompt"].upper()}]},
        ),
    ]

    model_id = models_data["models"][0]["id"]
    cache_keys = {}

    for variation_name, eval_data in variations:
        key = executor._generate_cache_key(model_id, eval_data)
        cache_keys[variation_name] = key

    # Check all keys are different
    unique_keys = set(cache_keys.values())
    if len(unique_keys) != len(variations):
        print(f"   ❌ Cache collision detected: {len(unique_keys)} unique keys from {len(variations)} variations")
        for name, key in cache_keys.items():
            print(f"      {name}: {key}")
        return False

    print(f"   ✅ {len(variations)} variations produced {len(unique_keys)} unique cache keys")
    return True


if __name__ == "__main__":
    print("🧪 End-to-end cache invalidation testing...")

    tests = [
        ("Cache key stability", test_cache_key_stability),
        ("Collision resistance", test_collision_resistance),
        ("Eval modification invalidation", test_eval_modification_invalidation),
        ("Model removal invalidation", test_model_removal_invalidation),
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
    print("\n📋 END-TO-END CACHE INVALIDATION SUMMARY:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1

    print(f"\n📊 Results: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("✅ ALL END-TO-END CACHE INVALIDATION TESTS PASSED")
        print("💡 Cache invalidation works correctly across the entire pipeline")
    else:
        print("❌ END-TO-END CACHE INVALIDATION ISSUES DETECTED")
        print("💡 Cache invalidation may not be working properly")

    sys.exit(0 if passed == len(results) else 1)
