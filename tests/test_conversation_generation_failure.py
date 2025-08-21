#!/usr/bin/env python3
"""
Test to identify why conversation generation is failing and taking too long.
This should expose the root cause and suggest fixes.
"""

import json
import os
import sys
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_api_key_configuration():
    """Test if API keys are properly configured."""
    print("🧪 Testing API key configuration...")

    # Check for OpenRouter API key
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in environment")
        print("💡 Check .env.local file or environment variables")
        return False

    if api_key.startswith("sk-"):
        print("✅ OpenRouter API key found and looks valid")
        return True
    else:
        print("⚠️ API key doesn't look like a valid OpenRouter key")
        return False


def test_conversation_script_imports():
    """Test if conversation script can be imported without errors."""
    print("\n🧪 Testing conversation script imports...")

    try:
        import execute_conversations

        print("✅ execute_conversations imported successfully")

        # Check required functions exist
        required_functions = ["execute_single_conversation", "main"]

        for func_name in required_functions:
            if hasattr(execute_conversations, func_name):
                print(f"✅ Function {func_name} exists")
            else:
                print(f"❌ Function {func_name} missing")
                return False

        return True

    except ImportError as e:
        print(f"❌ Cannot import execute_conversations: {e}")
        return False
    except Exception as e:
        print(f"❌ Error importing execute_conversations: {e}")
        return False


def test_input_data_validity():
    """Test if input data files are valid and complete."""
    print("\n🧪 Testing input data validity...")

    required_files = [
        "data/testonly/loaded_models.json",
        "data/testonly/loaded_skills.json",
        "data/testonly/loaded_judges.json",
    ]

    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ Missing required file: {file_path}")
            return False

        try:
            with open(file_path) as f:
                data = json.load(f)
            print(f"✅ {file_path} is valid JSON")

            # Check content
            if file_path.endswith("models.json"):
                models = data.get("models", [])
                if len(models) == 0:
                    print("❌ No models found in loaded_models.json")
                    return False
                print(f"   📊 {len(models)} models loaded")

            elif file_path.endswith("skills.json"):
                evals = data.get("evals", [])
                if len(evals) == 0:
                    print("❌ No evals found in loaded_skills.json")
                    return False
                print(f"   📊 {len(evals)} evals loaded")

            elif file_path.endswith("judges.json"):
                judges = data.get("judges", [])
                if len(judges) == 0:
                    print("❌ No judges found in loaded_judges.json")
                    return False
                print(f"   📊 {len(judges)} judges loaded")

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {file_path}: {e}")
            return False
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            return False

    return True


def test_snakemake_execution_context():
    """Test if we're running in the correct Snakemake context."""
    print("\n🧪 Testing Snakemake execution context...")

    # Check if we have the right Python environment
    try:
        import requests

        print("✅ requests library available")
    except ImportError:
        print("❌ requests library missing (required for API calls)")
        return False

    try:
        from dotenv import load_dotenv

        print("✅ python-dotenv available")
    except ImportError:
        print("❌ python-dotenv missing (required for .env.local)")
        return False

    # Check if .env.local exists
    env_file = Path(".env.local")
    if env_file.exists():
        print("✅ .env.local file found")
    else:
        print("⚠️ .env.local file missing")

    return True


def test_conversation_generation_failure_modes():
    """Test for common conversation generation failure modes."""
    print("\n🧪 Testing conversation generation failure modes...")

    issues_found = []

    # Test 1: API key issues
    if not test_api_key_configuration():
        issues_found.append("api_key_missing")

    # Test 2: Import issues
    if not test_conversation_script_imports():
        issues_found.append("import_failures")

    # Test 3: Data issues
    if not test_input_data_validity():
        issues_found.append("invalid_input_data")

    # Test 4: Environment issues
    if not test_snakemake_execution_context():
        issues_found.append("environment_issues")

    if issues_found:
        print(f"\n❌ CONVERSATION GENERATION ISSUES FOUND: {', '.join(issues_found)}")

        print("\n🔧 Recommended fixes:")
        if "api_key_missing" in issues_found:
            print("   1. Set OPENROUTER_API_KEY in .env.local")
        if "import_failures" in issues_found:
            print("   2. Check execute_conversations.py for syntax errors")
        if "invalid_input_data" in issues_found:
            print("   3. Regenerate input data files")
        if "environment_issues" in issues_found:
            print("   4. Install missing Python packages")

        return False

    print("\n✅ No obvious failure modes detected")
    return True


def test_should_conversation_generation_be_skipped():
    """Test if conversation generation should be skipped entirely."""
    print("\n🧪 Testing if conversation generation should be skipped...")

    # Check for cache marker files that indicate completed conversation generation
    data_dir = Path("data")
    cache_markers = list(data_dir.glob("conversations_cache_*.done"))

    if not cache_markers:
        print("⚠️ No conversation cache markers found - generation needed")
        return False

    print(f"✅ Found {len(cache_markers)} conversation cache markers:")
    for marker in cache_markers:
        print(f"   📄 {marker.name}")

        # Verify marker file has content
        if marker.stat().st_size == 0:
            print(f"   ⚠️ {marker.name} is empty - may need regeneration")
            return False

    # Also check if individual conversation cache files exist
    conversations_dir = data_dir / "conversations"
    if conversations_dir.exists():
        cache_files = list(conversations_dir.rglob("*.json"))
        if cache_files:
            print(f"✅ Found {len(cache_files)} individual conversation cache files")
            print("💡 Conversation generation should be skipped")
            return True
        else:
            print("⚠️ No individual conversation cache files found despite markers")
            return False
    else:
        print("⚠️ Conversations cache directory doesn't exist")
    return False


if __name__ == "__main__":
    print("🧪 Testing conversation generation failures...")

    # Check if generation should be skipped
    should_skip = test_should_conversation_generation_be_skipped()

    if should_skip:
        print("\n✅ Conversation generation not needed")
    else:
        # Run failure mode tests
        generation_ok = test_conversation_generation_failure_modes()

        if not generation_ok:
            print("\n❌ CRITICAL: Conversation generation will fail")
            print("🛑 Fix these issues before running pipeline")
            sys.exit(1)
        else:
            print("\n✅ Conversation generation should work")
            print("💡 But it's taking too long - check for performance issues")
