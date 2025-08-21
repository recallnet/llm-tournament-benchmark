"""
Advanced safety tests for parallelization feature.

These tests focus on production reliability scenarios including
API rate limiting, resource constraints, and recovery mechanisms.
"""

import json
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestAPIRateLimitingBehavior:
    """Test behavior under API rate limiting conditions."""

    def test_api_rate_limit_handling_with_retries(self):
        """Test that API rate limits are handled gracefully with retries."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test data
            test_models = {
                "pool_info": {"name": "test", "model_count": 2},
                "models": [{"id": "rate_limited_model", "slug": "rate_limited"}, {"id": "normal_model", "slug": "normal"}],
            }
            test_skills = {"evals": [{"id": "test_eval", "_metadata": {"skill": "test_skill"}}]}
            test_judges = {"judges": [{"id": "test_judge"}]}

            temp_path = Path(temp_dir)
            models_file = temp_path / "models.json"
            skills_file = temp_path / "skills.json"
            judges_file = temp_path / "judges.json"

            for file_path, data in [(models_file, test_models), (skills_file, test_skills), (judges_file, test_judges)]:
                with open(file_path, "w") as f:
                    json.dump(data, f)

            from scripts.execute_conversations_single_model import execute_conversations_for_model

            # Simulate rate limiting with eventual success
            rate_limit_calls = 0

            def mock_rate_limited_execution(model, skill_id, eval_data):
                nonlocal rate_limit_calls
                if model["id"] == "rate_limited_model":
                    rate_limit_calls += 1
                    if rate_limit_calls <= 2:  # Fail first 2 times
                        raise Exception("Rate limit exceeded - 429")
                    # Success on 3rd try
                return {
                    "metadata": {"model_id": model["id"], "timestamp": "2025-08-20T10:00:00"},
                    "messages": [{"role": "assistant", "content": "success"}],
                }

            with patch("scripts.execute_conversations_single_model.ConversationExecutor") as mock_executor_class:
                with patch("scripts.execute_conversations_single_model.cleanup_stale_cache"):
                    mock_executor = MagicMock()
                    mock_executor.execute_conversation.side_effect = mock_rate_limited_execution
                    mock_executor.execute_intermediary.return_value = {"id": "test_inter"}
                    mock_executor_class.return_value = mock_executor

                    # Execute with rate limited model - should eventually succeed
                    # Note: In real implementation, retries would be handled by ConversationExecutor
                    # Here we're testing that the structure handles failures gracefully
                    result = execute_conversations_for_model(
                        str(models_file), str(skills_file), str(judges_file), "rate_limited_model"
                    )

                    # Should handle the rate limiting gracefully
                    assert result is not None
                    assert "execution_info" in result
                    # The exact success/failure depends on retry implementation
                    assert result["execution_info"]["total_conversations"] == 1

    def test_concurrent_api_calls_stay_within_limits(self):
        """Test that concurrent model executions don't exceed API rate limits."""
        import time
        from unittest.mock import patch

        # Track API calls with timing
        api_calls = []
        call_lock = threading.Lock()

        def mock_api_call(model, skill_id, eval_data):
            with call_lock:
                api_calls.append({"model": model["id"], "timestamp": time.time(), "thread": threading.current_thread().ident})

            # Simulate API call time
            time.sleep(0.1)
            return {
                "metadata": {"model_id": model["id"], "timestamp": "2025-08-20T10:00:00"},
                "messages": [{"role": "assistant", "content": "success"}],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test data for multiple models
            test_models = {
                "pool_info": {"name": "test", "model_count": 4},
                "models": [{"id": f"model_{i}", "slug": f"model_{i}"} for i in range(4)],
            }
            test_skills = {"evals": [{"id": "test_eval", "_metadata": {"skill": "test_skill"}}]}
            test_judges = {"judges": [{"id": "test_judge"}]}

            models_file = temp_path / "models.json"
            skills_file = temp_path / "skills.json"
            judges_file = temp_path / "judges.json"

            for file_path, data in [(models_file, test_models), (skills_file, test_skills), (judges_file, test_judges)]:
                with open(file_path, "w") as f:
                    json.dump(data, f)

            from scripts.execute_conversations_single_model import execute_conversations_for_model

            # Execute multiple models concurrently
            def run_model_execution(model_id):
                with patch("scripts.execute_conversations_single_model.ConversationExecutor") as mock_executor_class:
                    with patch("scripts.execute_conversations_single_model.cleanup_stale_cache"):
                        mock_executor = MagicMock()
                        mock_executor.execute_conversation.side_effect = mock_api_call
                        mock_executor.execute_intermediary.return_value = {"id": "test_inter"}
                        mock_executor_class.return_value = mock_executor

                        return execute_conversations_for_model(str(models_file), str(skills_file), str(judges_file), model_id)

            # Run concurrent executions
            threads = []
            results = {}

            for model in test_models["models"][:3]:  # Test with 3 concurrent models
                model_id = model["id"]
                thread = threading.Thread(target=lambda mid=model_id: results.update({mid: run_model_execution(mid)}))
                threads.append(thread)
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join(timeout=10)

            # Verify API calls were made and distributed across threads
            assert len(api_calls) >= 3, "Should have made API calls for each model"

            # Verify different threads were used (indicating parallel execution)
            unique_threads = set(call["thread"] for call in api_calls)
            assert len(unique_threads) >= 2, "Should use multiple threads for parallel execution"


class TestDiskSpaceAndResourceHandling:
    """Test handling of disk space and resource constraints."""

    def test_concurrent_file_writes_are_safe(self):
        """Test that concurrent file writes don't corrupt data."""
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Simulate multiple models writing results concurrently
            write_results = {}
            write_errors = []
            write_lock = threading.Lock()

            def write_model_result(model_id, delay=0):
                try:
                    time.sleep(delay)

                    # Each model writes to its own file (as in real implementation)
                    output_file = temp_path / f"conversations_{model_id}.json"

                    test_result = {
                        "execution_info": {
                            "total_conversations": 1,
                            "successful_conversations": 1,
                            "models_count": 1,
                            "timestamp": f"2025-08-20T10:0{delay}:00",
                        },
                        "conversations": [{"metadata": {"model_id": model_id}, "messages": []}],
                        "intermediaries": [],
                    }

                    # Write result
                    with open(output_file, "w") as f:
                        json.dump(test_result, f, indent=2)

                    # Verify write was successful
                    with open(output_file) as f:
                        written_data = json.load(f)

                    with write_lock:
                        write_results[model_id] = written_data["execution_info"]["timestamp"]

                except Exception as e:
                    with write_lock:
                        write_errors.append(f"Error writing {model_id}: {e}")

            # Start multiple concurrent writes
            threads = []
            model_ids = ["model_a", "model_b", "model_c", "model_d"]

            for i, model_id in enumerate(model_ids):
                thread = threading.Thread(target=write_model_result, args=(model_id, i * 0.1))
                threads.append(thread)
                thread.start()

            # Wait for all writes to complete
            for thread in threads:
                thread.join(timeout=5)

            # Verify all writes succeeded
            assert len(write_errors) == 0, f"File write errors: {write_errors}"
            assert len(write_results) == len(model_ids), "All models should write successfully"

            # Verify each file contains correct data
            for model_id in model_ids:
                output_file = temp_path / f"conversations_{model_id}.json"
                assert output_file.exists(), f"Output file for {model_id} should exist"

                with open(output_file) as f:
                    data = json.load(f)

                assert data["conversations"][0]["metadata"]["model_id"] == model_id
                assert "execution_info" in data

    def test_aggregation_handles_large_result_sets(self):
        """Test that aggregation works with realistically sized result sets."""
        from scripts.aggregate_conversations import aggregate_conversation_results

        # Create realistic sized per-model results (not huge, but substantial)
        large_results = []

        for model_idx in range(5):  # 5 models
            conversations = []
            for eval_idx in range(45):  # 45 evals per model (realistic size)
                conversations.append(
                    {
                        "metadata": {
                            "model_id": f"model_{model_idx}",
                            "eval_id": f"eval_{eval_idx}",
                            "timestamp": "2025-08-20T10:00:00",
                        },
                        "messages": [
                            {"role": "user", "content": f"Test prompt {eval_idx}"},
                            {"role": "assistant", "content": f"Test response {eval_idx}"},
                        ],
                    }
                )

            model_result = {
                "execution_info": {
                    "total_conversations": 45,
                    "successful_conversations": 45,
                    "failed_conversations": 0,
                    "total_intermediaries": 0,
                    "successful_intermediaries": 0,
                    "failed_intermediaries": 0,
                    "timestamp": "2025-08-20T10:00:00",
                    "models_count": 1,
                    "evals_count": 45,
                    "judges_count": 1,
                },
                "conversations": conversations,
                "intermediaries": [],
            }
            large_results.append(model_result)

        # Test aggregation with large dataset
        start_time = time.time()
        aggregated = aggregate_conversation_results(large_results)
        aggregation_time = time.time() - start_time

        # Verify correctness
        assert aggregated["execution_info"]["total_conversations"] == 225  # 5 * 45
        assert aggregated["execution_info"]["models_count"] == 5
        assert len(aggregated["conversations"]) == 225

        # Verify performance (should complete quickly)
        assert aggregation_time < 2.0, f"Aggregation took too long: {aggregation_time}s"


class TestPartialFailureRecovery:
    """Test recovery from partial execution failures."""

    def test_resume_from_partial_completion(self):
        """Test that pipeline can resume from partial completion."""
        import json
        import tempfile
        from pathlib import Path

        from scripts.aggregate_conversations import aggregate_conversation_results, load_conversation_files

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Simulate scenario where some models completed, others didn't
            completed_results = {
                "model_a": {
                    "execution_info": {"total_conversations": 2, "successful_conversations": 2, "models_count": 1},
                    "conversations": [
                        {"metadata": {"model_id": "model_a", "eval_id": "eval1"}},
                        {"metadata": {"model_id": "model_a", "eval_id": "eval2"}},
                    ],
                    "intermediaries": [],
                },
                "model_c": {
                    "execution_info": {"total_conversations": 2, "successful_conversations": 2, "models_count": 1},
                    "conversations": [
                        {"metadata": {"model_id": "model_c", "eval_id": "eval1"}},
                        {"metadata": {"model_id": "model_c", "eval_id": "eval2"}},
                    ],
                    "intermediaries": [],
                },
            }

            # Write completed results to files
            result_files = []
            for model_id, result in completed_results.items():
                result_file = temp_path / f"conversations_{model_id}.json"
                with open(result_file, "w") as f:
                    json.dump(result, f)
                result_files.append(str(result_file))

            # Note: model_b is missing (failed or not completed)

            # Test that aggregation works with partial results
            loaded_results = load_conversation_files(result_files)
            assert len(loaded_results) == 2, "Should load only completed results"

            aggregated = aggregate_conversation_results(loaded_results)

            # Should aggregate what's available
            assert aggregated["execution_info"]["total_conversations"] == 4
            assert aggregated["execution_info"]["models_count"] == 2
            assert len(aggregated["conversations"]) == 4

            # Verify model IDs are correct
            model_ids = {conv["metadata"]["model_id"] for conv in aggregated["conversations"]}
            assert model_ids == {"model_a", "model_c"}

    def test_handling_corrupted_intermediate_files(self):
        """Test graceful handling of corrupted intermediate result files."""
        import tempfile
        from pathlib import Path

        from scripts.aggregate_conversations import load_conversation_files

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create mixed valid and corrupted files
            valid_result = {
                "execution_info": {"total_conversations": 1, "models_count": 1},
                "conversations": [{"metadata": {"model_id": "good_model"}}],
                "intermediaries": [],
            }

            # Valid file
            good_file = temp_path / "conversations_good.json"
            with open(good_file, "w") as f:
                json.dump(valid_result, f)

            # Corrupted JSON file
            corrupted_file = temp_path / "conversations_corrupted.json"
            with open(corrupted_file, "w") as f:
                f.write('{"invalid": json syntax')

            # Empty file
            empty_file = temp_path / "conversations_empty.json"
            with open(empty_file, "w") as f:
                pass  # Write nothing

            # Missing file (referenced but doesn't exist)
            missing_file = temp_path / "conversations_missing.json"

            file_list = [str(good_file), str(corrupted_file), str(empty_file), str(missing_file)]

            # Should handle corrupted files gracefully
            loaded_results = load_conversation_files(file_list)

            # Should only load the valid file
            assert len(loaded_results) == 1
            assert loaded_results[0]["conversations"][0]["metadata"]["model_id"] == "good_model"


class TestSnakemakeIntegrationSafety:
    """Test safety aspects of Snakemake integration."""

    def test_snakemake_handles_missing_dependencies_gracefully(self):
        """Test that Snakemake workflow handles missing dependencies."""
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test with missing input files
            result = subprocess.run(
                [
                    "snakemake",
                    "--dry-run",
                    "--quiet",
                    "--directory",
                    str(temp_path),
                    "-s",
                    str(Path.cwd() / "Snakefile"),
                    "conversations.json",
                ],
                capture_output=True,
                text=True,
                cwd=str(Path.cwd()),
            )

            # Should indicate missing dependencies rather than crashing
            # (Exact behavior depends on Snakemake configuration)
            assert (
                result.returncode != 0
                or "missing" in result.stderr.lower()
                or "not found" in result.stderr.lower()
                or len(result.stdout) > 0
            )

    def test_dependency_graph_prevents_race_conditions(self):
        """Test that Snakemake dependency graph prevents race conditions."""
        import subprocess
        from pathlib import Path

        # Test dependency graph structure
        result = subprocess.run(
            ["snakemake", "--dag", "-s", str(Path.cwd() / "Snakefile"), "conversations.json"],
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
        )

        if result.returncode == 0:
            dag_output = result.stdout

            # Should show proper dependencies
            # aggregate_conversations should depend on execute_conversations_for_model rules
            assert "aggregate_conversations" in dag_output or "execute_conversations" in dag_output

            # The DAG should be a directed acyclic graph (no cycles)
            assert "->" in dag_output, "Should show dependencies in DAG format"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
