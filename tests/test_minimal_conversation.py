#!/usr/bin/env python3
"""
Test minimal conversation generation to identify the real issue.
This should complete quickly and identify where the hang occurs.
"""

import json
import os
import signal
import sys
import time
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


def test_minimal_conversation_generation():
    """Test generating a single conversation with timeout."""
    print("🧪 Testing minimal conversation generation...")

    try:
        from execute_conversations import ConversationExecutor

        # Load test data
        with open("data/testonly/loaded_models.json") as f:
            models = json.load(f)["models"]

        with open("data/testonly/loaded_skills.json") as f:
            skills = json.load(f)["evals"]

        # Use first model and eval
        test_model = models[0]
        test_eval = skills[0]

        print(f"🎯 Testing: {test_model['id']} x {test_eval['id']}")

        # Create conversation executor
        executor = ConversationExecutor()
        print("✅ ConversationExecutor created")

        # Set 60-second timeout for single conversation
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(60)

        start_time = time.time()

        try:
            skill_id = test_eval["_metadata"]["skill"]
            conversation_result = executor.execute_conversation(
                test_model, skill_id, test_eval
            )

            elapsed = time.time() - start_time
            signal.alarm(0)  # Cancel timeout

            if conversation_result:
                steps = conversation_result.get("steps", [])
                messages = conversation_result.get("messages", [])
                print(f"✅ Conversation completed in {elapsed:.2f}s")
                print(f"   📊 {len(steps)} steps, {len(messages)} messages")

                if len(steps) == 0 and len(messages) == 0:
                    print("❌ ISSUE: Conversation has no steps or messages")
                    return False

                return True
            else:
                print("❌ Conversation returned None")
                return False

        except TimeoutError:
            elapsed = time.time() - start_time
            print(f"❌ Conversation timed out after {elapsed:.2f}s")
            print("🚨 CRITICAL: Single conversation exceeds 60s limit")

            # This is the real issue - individual conversations are hanging
            print("\n💡 DIAGNOSIS: Individual conversation generation is hanging")
            print("   This could be due to:")
            print("   1. API rate limiting issues")
            print("   2. Network connectivity problems")
            print("   3. Large prompt causing long response times")
            print("   4. Model-specific issues")

            return False

    except ImportError as e:
        print(f"❌ Cannot import ConversationExecutor: {e}")
        return False
    except Exception as e:
        signal.alarm(0)
        print(f"❌ Conversation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_api_connectivity():
    """Test basic API connectivity."""
    print("\n🧪 Testing API connectivity...")

    try:
        import requests
        from dotenv import load_dotenv

        load_dotenv(".env.local")
        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            print("❌ No API key found")
            return False

        # Test minimal API call with timeout
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Simple test payload
        payload = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }

        print("🌐 Testing OpenRouter API connectivity...")

        # Set 30-second timeout for API test
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)

        start_time = time.time()

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )

            elapsed = time.time() - start_time
            signal.alarm(0)

            print(f"📡 API response in {elapsed:.2f}s: {response.status_code}")

            if response.status_code == 200:
                print("✅ API connectivity working")
                return True
            else:
                print(f"❌ API error: {response.text}")
                return False

        except TimeoutError:
            elapsed = time.time() - start_time
            print(f"❌ API call timed out after {elapsed:.2f}s")
            print("🌐 Network connectivity issue detected")
            return False

    except Exception as e:
        signal.alarm(0)
        print(f"❌ API test failed: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Testing minimal conversation generation...")

    # Test API connectivity first
    api_ok = test_api_connectivity()

    if not api_ok:
        print("\n❌ CRITICAL: API connectivity failed")
        print("🛑 Cannot generate conversations without API access")
        sys.exit(1)

    # Test minimal conversation generation
    conversation_ok = test_minimal_conversation_generation()

    if not conversation_ok:
        print("\n❌ CRITICAL: Minimal conversation generation failed")
        print("🛑 Pipeline will hang on conversation generation")
        sys.exit(1)
    else:
        print("\n✅ Minimal conversation generation works")
        print(
            "💡 Issue may be with bulk processing or specific eval/model combinations"
        )
