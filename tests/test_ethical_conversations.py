#!/usr/bin/env python3
"""
Test just the ethical_loopholes conversation generation.
"""

import json
import sys
import time

# Add scripts to path
sys.path.insert(0, "scripts")


def test_ethical_conversation_generation():
    """Test generating one ethical_loopholes conversation."""
    print("🔍 Testing ethical_loopholes conversation generation...")

    try:
        # Import the conversation classes
        from execute_conversations import ConversationExecutor

        print("✅ Successfully imported conversation classes")

        # Load data
        with open("data/testonly/loaded_models.json") as f:
            models_data = json.load(f)

        with open("data/testonly/loaded_judges.json") as f:
            judges_data = json.load(f)

        with open("data/testonly/loaded_skills.json") as f:
            skills_data = json.load(f)

        models = models_data["models"]
        judges = judges_data["judges"]
        evals = skills_data["evals"]

        # Find one ethical_loopholes eval
        ethical_evals = [
            e
            for e in evals
            if e.get("_metadata", {}).get("skill") == "ethical_loopholes"
        ]

        if not ethical_evals:
            print("❌ No ethical_loopholes evals found")
            return False

        test_eval = ethical_evals[0]
        test_model = models[0]

        print(f"🧪 Testing eval: {test_eval['id']}")
        print(f"🧪 Testing model: {test_model['id']}")

        # Create executor
        executor = ConversationExecutor()

        # Try to execute one conversation with timeout
        print("⏱️ Attempting conversation execution (10 second timeout)...")

        start_time = time.time()

        # Set a timeout using signal
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError("Conversation execution timed out")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10 second timeout

        try:
            result = executor._execute_conversation_for_model(
                test_model, test_eval, judges
            )
            signal.alarm(0)  # Cancel timeout

            execution_time = time.time() - start_time
            print(f"✅ Conversation completed in {execution_time:.2f} seconds")

            if result:
                print(f"✅ Result keys: {list(result.keys())}")
                return True
            else:
                print("❌ No result returned")
                return False

        except TimeoutError:
            print("❌ Conversation execution timed out after 10 seconds")
            return False
        except Exception as e:
            signal.alarm(0)  # Cancel timeout
            print(f"❌ Error during execution: {e}")
            return False

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Setup error: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Testing ethical_loopholes conversation generation...")

    success = test_ethical_conversation_generation()

    if success:
        print("✅ Ethical conversations should work")
    else:
        print("❌ Issue found with ethical conversations")
