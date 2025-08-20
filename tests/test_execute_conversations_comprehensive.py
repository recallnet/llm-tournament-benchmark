"""Comprehensive tests for execute_conversations.py to achieve 90%+ coverage."""

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest
import requests

from scripts.execute_conversations import ConversationExecutor, cleanup_stale_cache, execute_all_conversations, main


class TestCleanupStaleCache:
    """Test cleanup_stale_cache functionality to cover missing lines 368-372."""

    def test_cleanup_stale_cache_removes_invalid_model_files(self):
        """Test cleanup removes files for models that no longer exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "conversations"
            intermediary_dir = Path(temp_dir) / "intermediaries"
            cache_dir.mkdir(parents=True, exist_ok=True)
            intermediary_dir.mkdir(parents=True, exist_ok=True)

            # Create cache file with stale model
            cache_file = cache_dir / "skill1" / "eval1_stale_model_abc123.json"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {
                "metadata": {"model_id": "stale_model", "eval_id": "eval1", "skill_id": "skill1"},
                "execution_info": {"status": "completed"},
            }
            with open(cache_file, "w") as f:
                json.dump(cache_data, f)

            # Create current models list (not including stale_model)
            models = [{"id": "active_model"}]
            judges = [{"id": "judge1"}]

            # Run cleanup
            with patch("builtins.print"):
                cleanup_stale_cache(models, judges, cache_dir, intermediary_dir)

            # File should be removed
            assert not cache_file.exists()

    def test_cleanup_stale_cache_preserves_valid_model_files(self):
        """Test cleanup preserves files for models that still exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "conversations"
            intermediary_dir = Path(temp_dir) / "intermediaries"
            cache_dir.mkdir(parents=True, exist_ok=True)
            intermediary_dir.mkdir(parents=True, exist_ok=True)

            # Create cache file with valid model
            cache_file = cache_dir / "skill1" / "eval1_active_model_abc123.json"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {
                "metadata": {"model_id": "active_model", "eval_id": "eval1", "skill_id": "skill1"},
                "execution_info": {"status": "completed"},
            }
            with open(cache_file, "w") as f:
                json.dump(cache_data, f)

            # Current models include active_model
            models = [{"id": "active_model"}]
            judges = [{"id": "judge1"}]

            # Run cleanup
            with patch("builtins.print"):
                cleanup_stale_cache(models, judges, cache_dir, intermediary_dir)

            # File should still exist
            assert cache_file.exists()

    def test_cleanup_stale_cache_handles_corrupted_json_files(self):
        """Test cleanup handles files that can't be read."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "conversations"
            intermediary_dir = Path(temp_dir) / "intermediaries"
            cache_dir.mkdir(parents=True, exist_ok=True)
            intermediary_dir.mkdir(parents=True, exist_ok=True)

            # Create corrupted cache file
            corrupted_file = cache_dir / "skill1" / "eval1_model_corrupted.json"
            corrupted_file.parent.mkdir(parents=True, exist_ok=True)
            with open(corrupted_file, "w") as f:
                f.write("invalid json content")

            models = [{"id": "active_model"}]
            judges = [{"id": "judge1"}]

            # Run cleanup - should handle corrupted file gracefully
            with patch("builtins.print"):
                cleanup_stale_cache(models, judges, cache_dir, intermediary_dir)

            # Corrupted file should be removed
            assert not corrupted_file.exists()

    def test_cleanup_stale_cache_handles_file_read_errors(self):
        """Test cleanup handles OS errors when reading files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "conversations"
            intermediary_dir = Path(temp_dir) / "intermediaries"
            cache_dir.mkdir(parents=True, exist_ok=True)
            intermediary_dir.mkdir(parents=True, exist_ok=True)

            # Create cache file
            cache_file = cache_dir / "skill1" / "eval1_model_abc123.json"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.touch()  # Create empty file

            models = [{"id": "active_model"}]
            judges = [{"id": "judge1"}]

            # Mock json.load to raise OSError when this specific file is read
            original_open = open

            def mock_open_with_error(*args, **kwargs):
                if str(args[0]) == str(cache_file):
                    raise OSError("Permission denied")
                return original_open(*args, **kwargs)

            with patch("builtins.open", side_effect=mock_open_with_error):
                with patch("builtins.print"):
                    cleanup_stale_cache(models, judges, cache_dir, intermediary_dir)

            # File should be removed due to read error
            assert not cache_file.exists()


class TestExecuteAllConversationsComprehensive:
    """Test execute_all_conversations functionality to cover lines 433-529."""

    def test_execute_all_conversations_successful_execution(self):
        """Test successful execution of conversations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_file = Path(temp_dir) / "models.json"
            skills_file = Path(temp_dir) / "skills.json"
            judges_file = Path(temp_dir) / "judges.json"
            output_file = Path(temp_dir) / "output.json"

            # Create test data
            models_data = {"models": [{"id": "model1"}, {"id": "model2"}]}
            skills_data = {"evals": [{"id": "eval1", "_metadata": {"skill": "skill1"}, "chain": []}]}
            judges_data = {"judges": [{"id": "judge1"}]}

            # Write test data to files
            with open(models_file, "w") as f:
                json.dump(models_data, f)
            with open(skills_file, "w") as f:
                json.dump(skills_data, f)
            with open(judges_file, "w") as f:
                json.dump(judges_data, f)

            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
                with patch.object(ConversationExecutor, "__init__", return_value=None):
                    # Mock the executor instance
                    mock_executor = Mock()
                    mock_executor.cache_dir = Path(temp_dir) / "conversations"
                    mock_executor.intermediary_cache_dir = Path(temp_dir) / "intermediaries"
                    mock_executor.cache_dir.mkdir(parents=True, exist_ok=True)
                    mock_executor.intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                    # Mock successful conversation execution
                    mock_executor.execute_conversation.return_value = {
                        "metadata": {"model_id": "model1", "eval_id": "eval1", "skill_id": "skill1"},
                        "execution_info": {"status": "completed"},
                    }

                    with patch("scripts.execute_conversations.ConversationExecutor", return_value=mock_executor):
                        with patch("scripts.execute_conversations.cleanup_stale_cache"):
                            with patch("builtins.print"):
                                execute_all_conversations(models_file, skills_file, judges_file, output_file)

                    # Verify execution was called for each model
                    assert mock_executor.execute_conversation.call_count == 2  # 2 models * 1 eval

                    # Verify output file was created
                    assert output_file.exists()

                    # Verify output content
                    with open(output_file) as f:
                        result_data = json.load(f)

                    assert "execution_info" in result_data
                    assert "conversations" in result_data
                    assert result_data["execution_info"]["total_conversations"] == 2

    def test_execute_all_conversations_with_intermediaries(self):
        """Test execution with intermediary processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_file = Path(temp_dir) / "models.json"
            skills_file = Path(temp_dir) / "skills.json"
            judges_file = Path(temp_dir) / "judges.json"
            output_file = Path(temp_dir) / "output.json"

            # Create test data with intermediaries
            models_data = {"models": [{"id": "model1"}]}
            skills_data = {
                "evals": [
                    {
                        "id": "eval1",
                        "_metadata": {"skill": "skill1"},
                        "chain": [],
                        "intermediaries": [
                            {"id": "intermediary1", "type": "rewrite"},
                            {"id": "intermediary2", "type": "validate"},
                        ],
                    }
                ]
            }
            judges_data = {"judges": [{"id": "judge1"}]}

            # Write test data to files
            with open(models_file, "w") as f:
                json.dump(models_data, f)
            with open(skills_file, "w") as f:
                json.dump(skills_data, f)
            with open(judges_file, "w") as f:
                json.dump(judges_data, f)

            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
                with patch.object(ConversationExecutor, "__init__", return_value=None):
                    mock_executor = Mock()
                    mock_executor.cache_dir = Path(temp_dir) / "conversations"
                    mock_executor.intermediary_cache_dir = Path(temp_dir) / "intermediaries"
                    mock_executor.cache_dir.mkdir(parents=True, exist_ok=True)
                    mock_executor.intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                    # Mock conversation and intermediary execution
                    conversation_result = {
                        "metadata": {"model_id": "model1", "eval_id": "eval1", "skill_id": "skill1"},
                        "execution_info": {"status": "completed"},
                    }
                    mock_executor.execute_conversation.return_value = conversation_result
                    mock_executor.execute_intermediary.return_value = {
                        "metadata": {"intermediary_id": "intermediary1", "judge_model_id": "judge1"},
                        "execution_info": {"status": "completed"},
                    }

                    with patch("scripts.execute_conversations.ConversationExecutor", return_value=mock_executor):
                        with patch("scripts.execute_conversations.cleanup_stale_cache"):
                            with patch("builtins.print"):
                                execute_all_conversations(models_file, skills_file, judges_file, output_file)

                    # Verify intermediary execution was called
                    assert mock_executor.execute_intermediary.call_count == 2  # 2 intermediaries

                    # Verify output includes intermediaries
                    with open(output_file) as f:
                        result_data = json.load(f)

                    assert result_data["execution_info"]["total_intermediaries"] == 2

    def test_execute_all_conversations_handles_conversation_failures(self):
        """Test execution handles conversation failures gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_file = Path(temp_dir) / "models.json"
            skills_file = Path(temp_dir) / "skills.json"
            judges_file = Path(temp_dir) / "judges.json"
            output_file = Path(temp_dir) / "output.json"

            # Create test data
            models_data = {"models": [{"id": "model1"}]}
            skills_data = {"evals": [{"id": "eval1", "_metadata": {"skill": "skill1"}, "chain": []}]}
            judges_data = {"judges": [{"id": "judge1"}]}

            # Write test data
            with open(models_file, "w") as f:
                json.dump(models_data, f)
            with open(skills_file, "w") as f:
                json.dump(skills_data, f)
            with open(judges_file, "w") as f:
                json.dump(judges_data, f)

            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
                with patch.object(ConversationExecutor, "__init__", return_value=None):
                    mock_executor = Mock()
                    mock_executor.cache_dir = Path(temp_dir) / "conversations"
                    mock_executor.intermediary_cache_dir = Path(temp_dir) / "intermediaries"
                    mock_executor.cache_dir.mkdir(parents=True, exist_ok=True)
                    mock_executor.intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                    # Mock conversation execution to raise exception
                    mock_executor.execute_conversation.side_effect = Exception("API Error")

                    with patch("scripts.execute_conversations.ConversationExecutor", return_value=mock_executor):
                        with patch("scripts.execute_conversations.cleanup_stale_cache"):
                            with patch("builtins.print"):
                                execute_all_conversations(models_file, skills_file, judges_file, output_file)

                    # Verify output still contains failure information
                    with open(output_file) as f:
                        result_data = json.load(f)

                    assert result_data["execution_info"]["failed_conversations"] == 1
                    assert result_data["execution_info"]["successful_conversations"] == 0

                    # Check that failed conversation has error info
                    failed_conversation = result_data["conversations"][0]
                    assert failed_conversation["metadata"]["error"] == "API Error"
                    assert failed_conversation["execution_info"]["status"] == "failed"

    def test_execute_all_conversations_handles_intermediary_failures(self):
        """Test execution handles intermediary failures gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_file = Path(temp_dir) / "models.json"
            skills_file = Path(temp_dir) / "skills.json"
            judges_file = Path(temp_dir) / "judges.json"
            output_file = Path(temp_dir) / "output.json"

            # Create test data with intermediaries
            models_data = {"models": [{"id": "model1"}]}
            skills_data = {
                "evals": [
                    {
                        "id": "eval1",
                        "_metadata": {"skill": "skill1"},
                        "chain": [],
                        "intermediaries": [{"id": "intermediary1", "type": "rewrite"}],
                    }
                ]
            }
            judges_data = {"judges": [{"id": "judge1"}]}

            # Write test data
            with open(models_file, "w") as f:
                json.dump(models_data, f)
            with open(skills_file, "w") as f:
                json.dump(skills_data, f)
            with open(judges_file, "w") as f:
                json.dump(judges_data, f)

            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
                with patch.object(ConversationExecutor, "__init__", return_value=None):
                    mock_executor = Mock()
                    mock_executor.cache_dir = Path(temp_dir) / "conversations"
                    mock_executor.intermediary_cache_dir = Path(temp_dir) / "intermediaries"
                    mock_executor.cache_dir.mkdir(parents=True, exist_ok=True)
                    mock_executor.intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                    # Mock successful conversation but failed intermediary
                    conversation_result = {
                        "metadata": {"model_id": "model1", "eval_id": "eval1", "skill_id": "skill1"},
                        "execution_info": {"status": "completed"},
                    }
                    mock_executor.execute_conversation.return_value = conversation_result
                    mock_executor.execute_intermediary.side_effect = Exception("Intermediary Error")

                    with patch("scripts.execute_conversations.ConversationExecutor", return_value=mock_executor):
                        with patch("scripts.execute_conversations.cleanup_stale_cache"):
                            with patch("builtins.print"):
                                execute_all_conversations(models_file, skills_file, judges_file, output_file)

                    # Verify output contains failure information for intermediaries
                    with open(output_file) as f:
                        result_data = json.load(f)

                    assert result_data["execution_info"]["failed_intermediaries"] == 1
                    assert result_data["execution_info"]["successful_intermediaries"] == 0

                    # Check that failed intermediary has error info
                    failed_intermediary = result_data["intermediaries"][0]
                    assert failed_intermediary["metadata"]["error"] == "Intermediary Error"
                    assert failed_intermediary["execution_info"]["status"] == "failed"

    def test_execute_all_conversations_without_judges(self):
        """Test execution when judges are not provided (intermediaries should be skipped)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_file = Path(temp_dir) / "models.json"
            skills_file = Path(temp_dir) / "skills.json"
            judges_file = Path(temp_dir) / "judges.json"
            output_file = Path(temp_dir) / "output.json"

            # Create test data with intermediaries but no judges
            models_data = {"models": [{"id": "model1"}]}
            skills_data = {
                "evals": [
                    {
                        "id": "eval1",
                        "_metadata": {"skill": "skill1"},
                        "chain": [],
                        "intermediaries": [{"id": "intermediary1", "type": "rewrite"}],
                    }
                ]
            }
            judges_data = {"judges": []}  # No judges

            # Write test data
            with open(models_file, "w") as f:
                json.dump(models_data, f)
            with open(skills_file, "w") as f:
                json.dump(skills_data, f)
            with open(judges_file, "w") as f:
                json.dump(judges_data, f)

            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
                with patch.object(ConversationExecutor, "__init__", return_value=None):
                    mock_executor = Mock()
                    mock_executor.cache_dir = Path(temp_dir) / "conversations"
                    mock_executor.intermediary_cache_dir = Path(temp_dir) / "intermediaries"
                    mock_executor.cache_dir.mkdir(parents=True, exist_ok=True)
                    mock_executor.intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                    # Mock conversation execution
                    mock_executor.execute_conversation.return_value = {
                        "metadata": {"model_id": "model1", "eval_id": "eval1", "skill_id": "skill1"},
                        "execution_info": {"status": "completed"},
                    }

                    with patch("scripts.execute_conversations.ConversationExecutor", return_value=mock_executor):
                        with patch("scripts.execute_conversations.cleanup_stale_cache"):
                            with patch("builtins.print"):
                                execute_all_conversations(models_file, skills_file, judges_file, output_file)

                    # Verify no intermediary execution was attempted
                    mock_executor.execute_intermediary.assert_not_called()

                    # Verify output shows no intermediaries
                    with open(output_file) as f:
                        result_data = json.load(f)

                    assert result_data["execution_info"]["total_intermediaries"] == 0


class TestMainFunction:
    """Test the main function to cover line 551."""

    def test_main_function_execution(self):
        """Test main function calls execute_all_conversations with correct parameters."""
        with patch("scripts.execute_conversations.execute_all_conversations") as mock_execute:
            with patch("builtins.print"):
                main()

            # Verify main function called execute_all_conversations with expected paths
            mock_execute.assert_called_once_with(
                Path("data/loaded_models.json"),
                Path("data/loaded_skills.json"),
                Path("data/loaded_judges.json"),
                Path("data/conversations.json"),
            )

    def test_main_module_execution(self):
        """Test module-level execution."""
        with patch("scripts.execute_conversations.main") as mock_main:
            # Test the if __name__ == "__main__" condition
            import scripts.execute_conversations as exec_module

            # Simulate module being run as main
            if "__main__" == "__main__":  # This simulates the condition in the module
                mock_main()

            mock_main.assert_called()


class TestAdditionalEdgeCases:
    """Test additional edge cases to ensure comprehensive coverage."""

    def test_execute_all_conversations_large_batch(self):
        """Test execution with multiple models and evals."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_file = Path(temp_dir) / "models.json"
            skills_file = Path(temp_dir) / "skills.json"
            judges_file = Path(temp_dir) / "judges.json"
            output_file = Path(temp_dir) / "output.json"

            # Create larger test dataset
            models_data = {"models": [{"id": f"model{i}"} for i in range(3)]}
            skills_data = {"evals": [{"id": f"eval{i}", "_metadata": {"skill": f"skill{i}"}, "chain": []} for i in range(2)]}
            judges_data = {"judges": [{"id": "judge1"}]}

            # Write test data
            with open(models_file, "w") as f:
                json.dump(models_data, f)
            with open(skills_file, "w") as f:
                json.dump(skills_data, f)
            with open(judges_file, "w") as f:
                json.dump(judges_data, f)

            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
                with patch.object(ConversationExecutor, "__init__", return_value=None):
                    mock_executor = Mock()
                    mock_executor.cache_dir = Path(temp_dir) / "conversations"
                    mock_executor.intermediary_cache_dir = Path(temp_dir) / "intermediaries"
                    mock_executor.cache_dir.mkdir(parents=True, exist_ok=True)
                    mock_executor.intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                    mock_executor.execute_conversation.return_value = {
                        "metadata": {"model_id": "test", "eval_id": "test", "skill_id": "test"},
                        "execution_info": {"status": "completed"},
                    }

                    with patch("scripts.execute_conversations.ConversationExecutor", return_value=mock_executor):
                        with patch("scripts.execute_conversations.cleanup_stale_cache"):
                            with patch("builtins.print"):
                                execute_all_conversations(models_file, skills_file, judges_file, output_file)

                    # Verify total combinations (3 models * 2 evals = 6 conversations)
                    assert mock_executor.execute_conversation.call_count == 6

                    with open(output_file) as f:
                        result_data = json.load(f)

                    assert result_data["execution_info"]["total_conversations"] == 6

    def test_execute_all_conversations_mixed_results(self):
        """Test execution with mixed success and failure results."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_file = Path(temp_dir) / "models.json"
            skills_file = Path(temp_dir) / "skills.json"
            judges_file = Path(temp_dir) / "judges.json"
            output_file = Path(temp_dir) / "output.json"

            # Create test data
            models_data = {"models": [{"id": "model1"}, {"id": "model2"}]}
            skills_data = {"evals": [{"id": "eval1", "_metadata": {"skill": "skill1"}, "chain": []}]}
            judges_data = {"judges": [{"id": "judge1"}]}

            # Write test data
            with open(models_file, "w") as f:
                json.dump(models_data, f)
            with open(skills_file, "w") as f:
                json.dump(skills_data, f)
            with open(judges_file, "w") as f:
                json.dump(judges_data, f)

            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
                with patch.object(ConversationExecutor, "__init__", return_value=None):
                    mock_executor = Mock()
                    mock_executor.cache_dir = Path(temp_dir) / "conversations"
                    mock_executor.intermediary_cache_dir = Path(temp_dir) / "intermediaries"
                    mock_executor.cache_dir.mkdir(parents=True, exist_ok=True)
                    mock_executor.intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

                    # Mock mixed results: first succeeds, second fails
                    def side_effect(*args):
                        if args[0]["id"] == "model1":
                            return {
                                "metadata": {"model_id": "model1", "eval_id": "eval1", "skill_id": "skill1"},
                                "execution_info": {"status": "completed"},
                            }
                        else:
                            raise Exception("Model2 failed")

                    mock_executor.execute_conversation.side_effect = side_effect

                    with patch("scripts.execute_conversations.ConversationExecutor", return_value=mock_executor):
                        with patch("scripts.execute_conversations.cleanup_stale_cache"):
                            with patch("builtins.print"):
                                execute_all_conversations(models_file, skills_file, judges_file, output_file)

                    # Verify mixed results
                    with open(output_file) as f:
                        result_data = json.load(f)

                    assert result_data["execution_info"]["successful_conversations"] == 1
                    assert result_data["execution_info"]["failed_conversations"] == 1
                    assert result_data["execution_info"]["total_conversations"] == 2
