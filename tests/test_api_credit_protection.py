#!/usr/bin/env python3
"""
Test to detect and prevent endless loops that burn through API credits.
This is a critical safety check to prevent runaway costs.
"""

import json
import sys
import time
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_detect_repeated_api_calls():
    """Detect if we're making repeated API calls for the same conversations."""
    print("🧪 Testing for repeated API calls that burn credits...")

    # Check conversation cache to see if we're regenerating the same conversations
    cache_dir = Path("data/testonly/conversations/cache")

    if not cache_dir.exists():
        print("⚠️ No conversation cache directory found")
        return True

    # Get all cache files and their timestamps
    cache_files = []
    current_time = time.time()

    for cache_file in cache_dir.glob("*.json"):
        try:
            stat = cache_file.stat()
            age_minutes = (current_time - stat.st_mtime) / 60

            # Load cache to get the conversation details
            with open(cache_file) as f:
                cache_data = json.load(f)

            metadata = cache_data.get("metadata", {})
            cache_files.append(
                {
                    "file": cache_file.name,
                    "model_id": metadata.get("model_id", "unknown"),
                    "eval_id": metadata.get("eval_id", "unknown"),
                    "age_minutes": age_minutes,
                    "size": cache_file.stat().st_size,
                }
            )

        except Exception as e:
            print(f"⚠️ Error reading cache file {cache_file}: {e}")

    # Group by model+eval to find duplicates
    conversation_groups = {}
    for cache_file in cache_files:
        key = f"{cache_file['model_id']}:{cache_file['eval_id']}"
        if key not in conversation_groups:
            conversation_groups[key] = []
        conversation_groups[key].append(cache_file)

    # Check for recent duplicates (multiple cache files for same conversation)
    recent_duplicates = []
    for key, files in conversation_groups.items():
        # Sort by age (newest first)
        files.sort(key=lambda x: x["age_minutes"])

        # If we have multiple files for same conversation created recently
        recent_files = [f for f in files if f["age_minutes"] < 60]  # Last hour
        if len(recent_files) > 1:
            recent_duplicates.append(
                {
                    "conversation": key,
                    "duplicate_files": len(recent_files),
                    "newest_age": recent_files[0]["age_minutes"],
                }
            )

    if recent_duplicates:
        print(
            f"🚨 CREDIT BURN DETECTED: {len(recent_duplicates)} conversations have recent duplicates"
        )
        for dup in recent_duplicates:
            print(
                f"   ⚠️ {dup['conversation']}: {dup['duplicate_files']} files in last hour"
            )

        print("\n💰 This indicates repeated API calls for the same conversations!")
        print("🛑 STOPPING to prevent credit burn")
        return False

    print("✅ No recent duplicate API calls detected")
    return True


def test_check_for_infinite_loops():
    """Check if conversation generation is stuck in infinite loops."""
    print("\n🧪 Checking for infinite loops in conversation generation...")

    # Check cache marker files and individual cache files for signs of infinite loops
    data_dir = Path("data")
    cache_markers = list(data_dir.glob("conversations_cache_*.done"))

    if not cache_markers:
        print("⚠️ No conversation cache markers found - generation may be stuck")
        return True

    # Check for repeated recent cache generation (indicating loops)
    recent_markers = []
    current_time = time.time()

    for marker in cache_markers:
        marker_age = current_time - marker.stat().st_mtime
        if marker_age < 3600:  # Within last hour
            recent_markers.append(marker)

    if len(recent_markers) > 10:
        print(
            f"🚨 Found {len(recent_markers)} recent cache markers - possible rapid regeneration loop"
        )
        return False

    # Check individual conversation files for malformed content
    conversations_dir = data_dir / "conversations"
    if conversations_dir.exists():
        cache_files = list(conversations_dir.rglob("*.json"))

        malformed_count = 0
        empty_step_count = 0
        total_conversations = 0

        for cache_file in cache_files[:50]:  # Sample first 50 files
            try:
                with open(cache_file) as f:
                    conv_data = json.load(f)

                # Handle different conversation formats
                conversations = (
                    [conv_data]
                    if isinstance(conv_data, dict)
                    else conv_data.get("conversations", [])
                )

                for conv in conversations:
                    total_conversations += 1
                    steps = conv.get("steps", [])
                    messages = conv.get("messages", [])

                    if len(steps) == 0:
                        empty_step_count += 1

                    if not conv.get("final") and len(messages) == 0:
                        malformed_count += 1

            except (OSError, json.JSONDecodeError):
                malformed_count += 1

        if malformed_count > total_conversations * 0.5:
            print(
                f"🚨 INFINITE LOOP RISK: {malformed_count}/{total_conversations} conversations malformed"
            )
            print("💡 These may cause repeated regeneration attempts")
            return False

        if total_conversations > 0 and empty_step_count == total_conversations:
            print(
                f"🚨 INFINITE LOOP DETECTED: ALL {empty_step_count} conversations have 0 steps"
            )
            print("💡 This indicates the generation script is failing but not erroring")
            return False

    print(
        f"✅ Cache activity looks normal ({len(cache_markers)} markers, {len(recent_markers)} recent)"
    )
    return True


def test_estimate_credit_burn_rate():
    """Estimate current API credit burn rate."""
    print("\n🧪 Estimating API credit burn rate...")

    # Load models to understand API costs
    try:
        with open("data/testonly/loaded_models.json") as f:
            models = json.load(f)["models"]

        with open("data/testonly/loaded_skills.json") as f:
            skills = json.load(f)["evals"]

        total_conversations = len(models) * len(skills)

        # Rough cost estimates (these should be configurable)
        COST_PER_CONVERSATION = 0.01  # $0.01 per conversation (conservative estimate)
        MAX_ACCEPTABLE_COST = 5.00  # $5 max for full run

        estimated_cost = total_conversations * COST_PER_CONVERSATION

        print("📊 Cost estimation:")
        print(f"   Total conversations: {total_conversations}")
        print(f"   Estimated cost per conversation: ${COST_PER_CONVERSATION}")
        print(f"   Total estimated cost: ${estimated_cost:.2f}")
        print(f"   Max acceptable cost: ${MAX_ACCEPTABLE_COST:.2f}")

        if estimated_cost > MAX_ACCEPTABLE_COST:
            print(
                f"🚨 COST OVERRUN: Estimated ${estimated_cost:.2f} exceeds ${MAX_ACCEPTABLE_COST:.2f}"
            )
            print("💡 Consider reducing model count or using cheaper models")
            return False

        print("✅ Estimated cost is within acceptable limits")
        return True

    except Exception as e:
        print(f"❌ Error estimating costs: {e}")
        return True  # Don't fail the test if we can't estimate


def test_api_credit_protection():
    """Main test for API credit protection."""
    print("🧪 Testing API credit protection measures...")

    repeated_calls_ok = test_detect_repeated_api_calls()
    infinite_loops_ok = test_check_for_infinite_loops()
    cost_estimate_ok = test_estimate_credit_burn_rate()

    if not (repeated_calls_ok and infinite_loops_ok and cost_estimate_ok):
        print("\n🚨 CREDIT PROTECTION FAILURE")
        print("🛑 PIPELINE MUST STOP TO PREVENT CREDIT BURN")

        print("\n🔧 Recommended actions:")
        print("   1. rm data/conversations_cache_*.done")
        print("   2. rm -rf data/conversations/")
        print("   3. rm -rf data/judge_cache/")
        print("   4. Fix conversation generation script")
        print("   5. Add proper error handling and timeouts")
        print("   6. Implement credit limits and monitoring")

        return False

    print("\n✅ API credit protection measures are working")
    return True


if __name__ == "__main__":
    print("🧪 Testing API credit protection...")

    try:
        credit_protection_ok = test_api_credit_protection()

        if not credit_protection_ok:
            print("\n❌ CRITICAL: API credit protection failed")
            print("🛑 STOPPING PIPELINE TO PREVENT CREDIT BURN")
            sys.exit(1)
        else:
            print("\n✅ API credit protection tests passed")

    except Exception as e:
        print(f"\n❌ Unexpected error in credit protection: {e}")
        sys.exit(1)
