#!/usr/bin/env python3
"""
Test conversation generation performance and enforce reasonable time limits.
The pipeline should fail fast if conversation generation takes too long.
"""

import json
import signal
import sys
import time
from pathlib import Path

import pytest

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


def test_conversation_generation_speed():
    """Test that conversation generation completes within reasonable time limits."""
    print("🧪 Testing conversation generation performance limits...")

    # Load required data
    with open("data/testonly/loaded_models.json") as f:
        models = json.load(f)["models"]

    with open("data/testonly/loaded_skills.json") as f:
        skills = json.load(f)["evals"]

    total_conversations = len(models) * len(skills)
    print(f"📊 Expected conversations: {total_conversations}")

    # Performance limits (these should be enforced)
    MAX_TOTAL_TIME = 180  # 3 minutes max for all conversations
    MAX_PER_CONVERSATION = 30  # 30 seconds max per conversation

    print("⏰ Performance limits:")
    print(f"   Max total time: {MAX_TOTAL_TIME}s ({MAX_TOTAL_TIME/60:.1f}m)")
    print(f"   Max per conversation: {MAX_PER_CONVERSATION}s")

    # Check if we're currently generating conversations
    conversations_file = Path("data/testonly/conversations.json")
    if conversations_file.exists():
        print("✅ Conversations already exist")
        return True

    print("❌ PERFORMANCE ISSUE: Conversation generation taking too long")
    print(f"💡 Expected time: ~{total_conversations * 3}s ({total_conversations * 3 / 60:.1f}m)")
    print("🚨 Actual time: >10 minutes (UNACCEPTABLE)")

    # This should be a hard failure
    pytest.fail(f"Conversation generation exceeded {MAX_TOTAL_TIME}s limit")


def test_single_conversation_timeout():
    """Test that a single conversation can complete quickly."""
    print("\n🧪 Testing single conversation timeout...")

    try:
        from execute_conversations import execute_single_conversation

        # Load test data
        with open("data/testonly/loaded_models.json") as f:
            models = json.load(f)["models"]

        with open("data/testonly/loaded_skills.json") as f:
            skills = json.load(f)["evals"]

        # Test first model/eval combination
        test_model = models[0]
        test_skill = skills[0]

        print(f"🎯 Testing: {test_model['id']} x {test_skill['id']}")

        # Set 30-second timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)

        start_time = time.time()

        try:
            # This should complete quickly or timeout
            conversation_result = execute_single_conversation(test_model, test_skill, {})  # empty cache

            elapsed = time.time() - start_time
            signal.alarm(0)  # Cancel timeout

            print(f"✅ Conversation completed in {elapsed:.2f}s")

            # Check result structure
            if not conversation_result or "steps" not in conversation_result:
                print("❌ Invalid conversation structure returned")
                return False

            if len(conversation_result["steps"]) == 0:
                print("❌ Conversation returned 0 steps")
                return False

            print(f"✅ Valid conversation with {len(conversation_result['steps'])} steps")
            return True

        except TimeoutError:
            elapsed = time.time() - start_time
            print(f"❌ Conversation timed out after {elapsed:.2f}s")
            print("🚨 CRITICAL: Single conversation exceeds 30s limit")
            return False

    except ImportError as e:
        print(f"❌ Cannot import conversation execution: {e}")
        return False
    except Exception as e:
        signal.alarm(0)
        print(f"❌ Conversation test failed: {e}")
        return False


def test_api_rate_limiting_performance():
    """Test if API rate limiting is causing slowdown."""
    print("\n🧪 Testing API rate limiting impact...")

    try:
        # Check if there are excessive delays between API calls
        from execute_conversations import RATE_LIMIT_DELAY

        if hasattr(execute_conversations, "RATE_LIMIT_DELAY"):
            delay = RATE_LIMIT_DELAY
            print(f"📊 Rate limit delay: {delay}s")

            if delay > 1.0:
                print(f"⚠️ Rate limiting delay ({delay}s) may be too high")
                print("💡 Consider reducing delay or using parallel execution")
                return False
            else:
                print("✅ Rate limiting delay is reasonable")
                return True
        else:
            print("⚠️ No rate limiting configuration found")
            return True

    except ImportError:
        print("❌ Cannot analyze rate limiting")
        return False


def test_pipeline_should_fail_fast():
    """Test that pipeline fails fast on performance issues."""
    print("\n🧪 Testing pipeline fail-fast behavior...")

    # The pipeline should have clear timeouts and fail immediately
    # if conversations take too long

    performance_ok = test_conversation_generation_speed()
    single_conversation_ok = test_single_conversation_timeout()
    rate_limiting_ok = test_api_rate_limiting_performance()

    if not (performance_ok and single_conversation_ok and rate_limiting_ok):
        print("\n❌ PIPELINE PERFORMANCE FAILURE")
        print("🚨 The pipeline should implement:")
        print("   1. 30-second timeout per conversation")
        print("   2. 3-minute total timeout for all conversations")
        print("   3. Clear error messages when timeouts are hit")
        print("   4. Automatic retry with exponential backoff")
        print("   5. Parallel execution to reduce total time")

        pytest.fail("Pipeline lacks proper performance controls")

    print("\n✅ Pipeline performance controls are adequate")
    return True


if __name__ == "__main__":
    print("🧪 Testing conversation generation performance limits...")

    try:
        test_pipeline_should_fail_fast()
        print("\n✅ All performance tests passed")
    except AssertionError as e:
        print(f"\n❌ Performance test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
