#!/usr/bin/env python3
"""
Test conversation performance and identify bottlenecks.
"""

import json
from pathlib import Path


def test_conversation_complexity():
    """Calculate the total number of API calls needed."""
    print("🔍 Calculating conversation complexity...")

    # Load the data
    with open("data/testonly/loaded_skills.json") as f:
        skills_data = json.load(f)

    with open("data/testonly/loaded_models.json") as f:
        models_data = json.load(f)

    with open("data/testonly/loaded_judges.json") as f:
        judges_data = json.load(f)

    evals = skills_data.get("evals", [])
    models = models_data.get("models", [])
    judges = judges_data.get("judges", [])

    print(
        f"📊 {len(evals)} evals × {len(models)} models = {len(evals) * len(models)} conversations"
    )

    # Calculate API calls per conversation
    api_calls_per_conversation = 0
    intermediary_calls = 0

    # Check if any evals need intermediary processing
    for eval_data in evals:
        chain = eval_data.get("chain", [])
        steps = len(chain)

        # Each step is one API call
        api_calls_per_conversation += steps

        # Check for intermediary requirements
        for step in chain:
            if "intermediary" in step.get("prompt", "").lower():
                intermediary_calls += len(judges)  # One call per judge for intermediary

    print(
        f"📊 ~{api_calls_per_conversation / len(evals):.1f} API calls per conversation on average"
    )

    if intermediary_calls > 0:
        print(f"📊 +{intermediary_calls} additional intermediary API calls")

    total_api_calls = (
        len(evals) * len(models) * (api_calls_per_conversation / len(evals))
    )
    if intermediary_calls > 0:
        total_api_calls += intermediary_calls * len(models)  # Intermediary per model

    print(f"📊 Total estimated API calls: ~{total_api_calls:.0f}")

    # Calculate time with rate limiting
    rate_limit_delay = 0.1  # 100ms per call
    total_sleep_time = total_api_calls * rate_limit_delay

    print(
        f"⏱️ Rate limiting sleep time: {total_sleep_time:.1f} seconds ({total_sleep_time/60:.1f} minutes)"
    )

    # Check ethical_loopholes specifically
    ethical_evals = [
        e for e in evals if e.get("_metadata", {}).get("skill") == "ethical_loopholes"
    ]
    ethical_api_calls = len(ethical_evals) * len(models)
    ethical_sleep_time = ethical_api_calls * rate_limit_delay

    print(
        f"📊 ethical_loopholes: {len(ethical_evals)} evals × {len(models)} models = {ethical_api_calls} conversations"
    )
    print(f"⏱️ ethical_loopholes sleep time: {ethical_sleep_time:.1f} seconds")

    return total_sleep_time < 300  # Should complete within 5 minutes


def test_cache_efficiency():
    """Check if conversations are being cached properly."""
    print("🔍 Testing cache efficiency...")

    # Check conversation cache directory
    cache_dir = Path("data/testonly/conversations")
    if not cache_dir.exists():
        print("❌ No conversation cache directory found")
        return False

    cache_files = list(cache_dir.rglob("*.json"))
    print(f"📊 Found {len(cache_files)} cached conversation files")

    # Check if ethical_loopholes has any cache files
    ethical_cache_files = [f for f in cache_files if "ethical_loopholes" in str(f)]
    print(f"📊 Found {len(ethical_cache_files)} ethical_loopholes cache files")

    if len(ethical_cache_files) == 0:
        print("⚠️ No ethical_loopholes conversations cached - they need to be generated")

        # This means the script will need to make API calls for ethical_loopholes
        with open("data/testonly/loaded_skills.json") as f:
            skills_data = json.load(f)

        ethical_evals = [
            e
            for e in skills_data.get("evals", [])
            if e.get("_metadata", {}).get("skill") == "ethical_loopholes"
        ]

        models_count = len(
            json.load(open("data/testonly/loaded_models.json"))["models"]
        )

        missing_conversations = len(ethical_evals) * models_count
        print(
            f"📊 Need to generate {missing_conversations} ethical_loopholes conversations"
        )

        # With rate limiting, this will take time
        estimated_time = missing_conversations * 0.1  # 100ms per conversation
        print(f"⏱️ Estimated time for ethical_loopholes: {estimated_time:.1f} seconds")

    return len(cache_files) > 0


if __name__ == "__main__":
    print("🧪 Testing conversation performance issues...")

    test1_passed = test_conversation_complexity()
    test2_passed = test_cache_efficiency()

    if test1_passed and test2_passed:
        print("✅ Performance should be acceptable")
    else:
        print("❌ Performance issues detected")
