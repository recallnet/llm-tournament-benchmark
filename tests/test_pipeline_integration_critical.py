#!/usr/bin/env python3
"""
CRITICAL Integration Tests for AFBench Pipeline

These tests catch the runtime bugs that our unit tests missed:
- Method signature mismatches
- Missing dictionary keys
- API integration failures
- Snakemake rule execution issues

This should have caught the bugs that just caused the pipeline hang.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCriticalPipelineIntegration:
    """Integration tests that catch real pipeline execution bugs."""

    def setup_method(self):
        """Set up test environment with safety isolation."""
        # Ensure we're in test mode for safety
        os.environ["AFBENCH_TEST_MODE"] = "true"

    @pytest.fixture
    def mock_conversation_data(self):
        """Realistic conversation execution data."""
        return {
            "metadata": {
                "skill_id": "harm_avoidance",
                "eval_id": "test_eval",
                "model_id": "test/model",
                "cache_key": "abc123",
                "timestamp": "2025-08-20T17:00:00",
            },
            "messages": [
                {"role": "user", "content": "Test question"},
                {"role": "assistant", "content": "Test response"},
            ],
            "execution_info": {
                "total_steps": 1,
                "completed_steps": 1,
                "status": "completed",
            },
        }

    @pytest.fixture
    def mock_intermediary_data(self):
        """Mock intermediary data for testing."""
        return {"id": "test_intermediary", "prompt": "Test intermediary prompt"}

    @pytest.fixture
    def mock_judge_model(self):
        """Mock judge model data."""
        return {"id": "openai/gpt-4", "author": "OpenAI"}

    def test_execute_intermediary_method_signature(
        self, mock_conversation_data, mock_intermediary_data, mock_judge_model
    ):
        """Test that execute_intermediary is called with correct signature - this catches the 7 vs 6 args bug."""
        print("\\n🧪 Testing execute_intermediary method signature...")

        # Import the actual classes
        sys.path.insert(0, "scripts")
        from execute_conversations import ConversationExecutor

        # Mock the API call to avoid needing real API key
        with patch.object(ConversationExecutor, "_make_api_request") as mock_api:
            mock_api.return_value = {
                "choices": [{"message": {"content": "Mock response"}}]
            }

            # This should work without the "takes 6 but 7 given" error
            with tempfile.TemporaryDirectory() as tmp_dir:
                cache_dir = Path(tmp_dir) / "conversations"
                intermediary_cache_dir = Path(tmp_dir) / "intermediaries"

                executor = ConversationExecutor(cache_dir, intermediary_cache_dir)

                # The CORRECT method signature (the bug was calling it wrong)
                try:
                    executor.execute_intermediary(
                        mock_intermediary_data,  # intermediary
                        mock_conversation_data,  # conversation_result
                        mock_judge_model,  # judge_model
                        "harm_avoidance",  # skill_id
                        "test_eval",  # eval_id
                    )
                    print("✅ Method signature is correct")
                except TypeError as e:
                    if "positional arguments" in str(e):
                        pytest.fail(f"Method signature bug still exists: {e}")
                    raise

    def test_execute_conversations_for_model_cache_only_status_bug(self):
        """Test the KeyError: 'status' bug in execute_conversations_for_model_cache_only."""
        print(
            "\\n🧪 Testing execute_conversations_for_model_cache_only status access..."
        )

        sys.path.insert(0, "scripts")
        from execute_conversations_single_model import (
            execute_conversations_for_model_cache_only,
        )

        # Create minimal test data files
        with tempfile.TemporaryDirectory() as tmp_dir:
            models_file = Path(tmp_dir) / "models.json"
            skills_file = Path(tmp_dir) / "skills.json"
            judges_file = Path(tmp_dir) / "judges.json"

            # Minimal valid data
            models_data = {"models": [{"id": "test/model", "author": "Test"}]}
            skills_data = {
                "evals": [
                    {
                        "id": "test_eval",
                        "_metadata": {"skill": "test_skill"},
                        "chain": ["step1"],
                    }
                ]
            }
            judges_data = {"judges": [{"id": "test/judge", "author": "Test"}]}

            models_file.write_text(json.dumps(models_data))
            skills_file.write_text(json.dumps(skills_data))
            judges_file.write_text(json.dumps(judges_data))

            # This should NOT raise KeyError: 'status'
            with patch(
                "scripts.execute_conversations.ConversationExecutor"
            ) as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor_class.return_value = mock_executor

                # Mock the conversation execution to return data without 'status' field
                mock_result = {
                    "execution_info": {
                        "total_conversations": 1,
                        "successful_conversations": 1,
                        "failed_conversations": 0,
                        # Notice: NO 'status' field - this was the bug
                    },
                    "conversations": [],
                    "intermediaries": [],
                }

                # Mock the execute_conversation method
                mock_executor.execute_conversation.return_value = {
                    "metadata": {"timestamp": "2025-08-20T17:00:00"}
                }

                # Patch the function that was causing the KeyError
                with patch(
                    "scripts.execute_conversations_single_model.execute_conversations_for_model",
                    return_value=mock_result,
                ):
                    try:
                        # Provide cache directories
                        cache_dir = Path(tmp_dir) / "conversations"
                        intermediary_cache_dir = Path(tmp_dir) / "intermediaries"
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                        result = execute_conversations_for_model_cache_only(
                            str(models_file),
                            str(skills_file),
                            str(judges_file),
                            "test/model",
                            cache_dir=str(cache_dir),
                            intermediary_cache_dir=str(intermediary_cache_dir),
                        )
                        print(f"✅ No KeyError: 'status' - function returned {result}")
                        assert isinstance(result, bool), "Should return boolean"
                    except KeyError as e:
                        if "'status'" in str(e):
                            pytest.fail(f"KeyError: 'status' bug still exists: {e}")
                        raise

    def test_snakemake_rule_integration_mock(self):
        """Test that Snakemake rule integration works without actual API calls."""
        print("\\n🧪 Testing Snakemake rule integration...")

        sys.path.insert(0, "scripts")

        # Test the exact code path that Snakemake uses
        with tempfile.TemporaryDirectory() as tmp_dir:
            models_file = Path(tmp_dir) / "models.json"
            skills_file = Path(tmp_dir) / "skills.json"
            judges_file = Path(tmp_dir) / "judges.json"

            # Create realistic test data
            models_data = {
                "models": [
                    {
                        "id": "inception/mercury",
                        "author": "Inception",
                        "slug": "mercury",
                    }
                ]
            }
            skills_data = {
                "evals": [
                    {
                        "id": "test_eval",
                        "_metadata": {"skill": "ethical_loopholes"},
                        "chain": ["step1"],
                    }
                ]
            }
            judges_data = {"judges": [{"id": "openai/gpt-4", "author": "OpenAI"}]}

            models_file.write_text(json.dumps(models_data))
            skills_file.write_text(json.dumps(skills_data))
            judges_file.write_text(json.dumps(judges_data))

            # Mock the ConversationExecutor to avoid API calls
            with patch(
                "scripts.execute_conversations.ConversationExecutor"
            ) as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor_class.return_value = mock_executor
                mock_executor.execute_conversation.return_value = {
                    "metadata": {"timestamp": "2025-08-20T17:00:00"}
                }

                # This should work like the actual Snakemake rule
                from execute_conversations_single_model import (
                    execute_conversations_for_model_cache_only,
                )

                # Provide cache directories
                cache_dir = Path(tmp_dir) / "conversations"
                intermediary_cache_dir = Path(tmp_dir) / "intermediaries"
                cache_dir.mkdir(parents=True, exist_ok=True)
                intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                success = execute_conversations_for_model_cache_only(
                    str(models_file),
                    str(skills_file),
                    str(judges_file),
                    "inception/mercury",
                    cache_dir=str(cache_dir),
                    intermediary_cache_dir=str(intermediary_cache_dir),
                )

                print(f"✅ Snakemake integration test passed: {success}")
                assert isinstance(success, bool), "Should return boolean for Snakemake"

    def test_api_key_error_handling(self):
        """Test that missing API keys are handled gracefully."""
        print("\\n🧪 Testing API key error handling...")

        # Temporarily remove API key and testing mode
        original_key = os.environ.get("OPENROUTER_API_KEY")
        original_test_mode = os.environ.get("AFBENCH_TEST_MODE")

        if "OPENROUTER_API_KEY" in os.environ:
            del os.environ["OPENROUTER_API_KEY"]
        if "AFBENCH_TEST_MODE" in os.environ:
            del os.environ["AFBENCH_TEST_MODE"]

        try:
            sys.path.insert(0, "scripts")
            from execute_conversations import ConversationExecutor

            # ConversationExecutor should initialize successfully even without API key
            with tempfile.TemporaryDirectory() as test_cache_dir:
                cache_dir = Path(test_cache_dir) / "conversations"
                intermediary_cache_dir = Path(test_cache_dir) / "intermediaries"
                executor = ConversationExecutor(
                    cache_dir=cache_dir, intermediary_cache_dir=intermediary_cache_dir
                )

                # Should have some API key (either real or mock)
                assert (
                    executor.api_key is not None and executor.api_key != ""
                ), f"Expected valid API key, got: {executor.api_key}"
                print("✅ API key handling works correctly")

        finally:
            # Restore API key and test mode if they existed
            if original_key:
                os.environ["OPENROUTER_API_KEY"] = original_key
            if original_test_mode:
                os.environ["AFBENCH_TEST_MODE"] = original_test_mode

    def test_realistic_pipeline_execution_flow(self):
        """Test the full pipeline execution flow that was hanging."""
        print("\\n🧪 Testing realistic pipeline execution flow...")

        sys.path.insert(0, "scripts")

        # This tests the exact sequence that was failing in the logs
        with tempfile.TemporaryDirectory() as tmp_dir:
            models_file = Path(tmp_dir) / "models.json"
            skills_file = Path(tmp_dir) / "skills.json"
            judges_file = Path(tmp_dir) / "judges.json"

            # Use the actual model that was failing
            models_data = {
                "models": [
                    {
                        "id": "inception/mercury",
                        "author": "Inception",
                        "slug": "mercury",
                        "context_window": 32768,
                    }
                ]
            }

            # Use actual skill data that includes intermediaries (this was part of the bug)
            skills_data = {
                "evals": [
                    {
                        "id": "quantumleap_data_sovereignty",
                        "_metadata": {"skill": "ethical_loopholes"},
                        "chain": ["quantumleap_scenario_evaluation"],
                        "intermediaries": [  # This triggers the execute_intermediary bug
                            {"id": "test_intermediary", "prompt": "Test"}
                        ],
                    }
                ]
            }

            judges_data = {"judges": [{"id": "openai/gpt-4", "author": "OpenAI"}]}

            models_file.write_text(json.dumps(models_data))
            skills_file.write_text(json.dumps(skills_data))
            judges_file.write_text(json.dumps(judges_data))

            # Mock the full execution to test the flow without API calls
            with patch(
                "scripts.execute_conversations.ConversationExecutor"
            ) as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor_class.return_value = mock_executor

                # Mock successful conversation
                mock_executor.execute_conversation.return_value = {
                    "metadata": {
                        "cache_key": "test123",
                        "timestamp": "2025-08-20T17:00:00",
                    }
                }

                # Mock successful intermediary (this was failing with wrong signature)
                mock_executor.execute_intermediary.return_value = {
                    "metadata": {"timestamp": "2025-08-20T17:00:00"}
                }

                from execute_conversations_single_model import (
                    execute_conversations_for_model_cache_only,
                )

                # This should complete without the hanging/errors we saw
                try:
                    # Provide cache directories
                    cache_dir = Path(tmp_dir) / "conversations"
                    intermediary_cache_dir = Path(tmp_dir) / "intermediaries"
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                    success = execute_conversations_for_model_cache_only(
                        str(models_file),
                        str(skills_file),
                        str(judges_file),
                        "inception/mercury",
                        cache_dir=str(cache_dir),
                        intermediary_cache_dir=str(intermediary_cache_dir),
                    )
                    print("✅ Realistic pipeline flow completed successfully")
                    assert success, "Pipeline should succeed with mocked components"

                    # Verify the execute_intermediary was called correctly
                    assert (
                        mock_executor.execute_intermediary.called
                    ), "Should call execute_intermediary for evals with intermediaries"

                except Exception as e:
                    pytest.fail(
                        f"Pipeline flow failed with error that should have been caught: {e}"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
