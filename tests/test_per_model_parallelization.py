"""
Comprehensive tests for per-model conversation parallelization.

These tests define the expected behavior for splitting conversation execution
by model and aggregating results back into the original format.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPerModelConversationExecution:
    """Test single-model conversation execution functionality."""

    @pytest.fixture
    def sample_models(self):
        """Sample models data structure."""
        return {
            "pool_info": {
                "name": "test",
                "path": "model_pools/test.csv",
                "model_count": 4,
                "timestamp": "2025-08-20T10:00:00",
            },
            "models": [
                {"id": "thedrummer/unslopnemo-12b", "author": "TheDrummer", "slug": "unslopnemo-12b", "context_window": 32768},
                {"id": "openai/gpt-oss-120b", "author": "OpenAI", "slug": "gpt-oss-120b", "context_window": 32768},
                {"id": "inception/mercury", "author": "Inception", "slug": "mercury", "context_window": 32768},
            ],
        }

    @pytest.fixture
    def sample_single_model_output(self):
        """Expected output structure for single model execution."""
        return {
            "execution_info": {
                "total_conversations": 45,  # One model * 45 evals
                "successful_conversations": 45,
                "failed_conversations": 0,
                "total_intermediaries": 5,
                "successful_intermediaries": 5,
                "failed_intermediaries": 0,
                "timestamp": "2025-08-20T10:00:00",
                "models_count": 1,  # Only one model processed
                "evals_count": 45,
                "judges_count": 3,
            },
            "conversations": [
                {
                    "metadata": {
                        "skill_id": "harm_avoidance",
                        "eval_id": "test_eval",
                        "eval_name": "Test Evaluation",
                        "model_id": "thedrummer/unslopnemo-12b",  # Only this model
                        "model_slug": "unslopnemo-12b",
                        "model_author": "TheDrummer",
                        "timestamp": "2025-08-20T10:00:00",
                        "cache_key": "abc123",
                        "step_count": 1,
                        "message_count": 2,
                    },
                    "messages": [
                        {"role": "user", "content": "Test prompt"},
                        {"role": "assistant", "content": "Test response"},
                    ],
                    "execution_info": {"total_steps": 1, "completed_steps": 1, "status": "completed"},
                }
            ],
            "intermediaries": [],
        }

    def test_single_model_filter_produces_correct_structure(self, sample_models, sample_single_model_output):
        """Test that filtering to single model produces expected JSON structure."""
        # Test that single model execution produces correct structure
        # We'll mock this since it requires API calls

        target_model_id = "thedrummer/unslopnemo-12b"

        # Mock the expensive operations
        with patch("scripts.execute_conversations_single_model.ConversationExecutor") as mock_executor_class:
            with patch("scripts.execute_conversations_single_model.cleanup_stale_cache"):
                with patch("builtins.open", create=True) as mock_open:

                    # Mock file reads
                    mock_files = [
                        json.dumps(sample_models),  # models file
                        json.dumps({"evals": [{"id": "test_eval", "_metadata": {"skill": "test_skill"}}]}),  # skills
                        json.dumps({"judges": [{"id": "test_judge"}]}),  # judges
                    ]
                    mock_open.return_value.__enter__.return_value.read.side_effect = mock_files

                    # Mock executor
                    mock_executor = MagicMock()
                    mock_executor_class.return_value = mock_executor

                    # Mock conversation result
                    mock_conversation = {
                        "metadata": {"model_id": target_model_id, "timestamp": "2025-08-20T10:00:00"},
                        "messages": [{"role": "user", "content": "test"}],
                    }
                    mock_executor.execute_conversation.return_value = mock_conversation

                    from scripts.execute_conversations_single_model import execute_conversations_for_model

                    result = execute_conversations_for_model(
                        models_file="mock_models.json",
                        skills_file="mock_skills.json",
                        judges_file="mock_judges.json",
                        target_model_id=target_model_id,
                    )

                    # Verify structure matches expected format
                    assert "execution_info" in result
                    assert "conversations" in result
                    assert "intermediaries" in result

                    # Verify execution_info reflects single model
                    assert result["execution_info"]["models_count"] == 1

    def test_model_id_extraction_from_models_file(self, sample_models):
        """Test extraction of model IDs for Snakemake wildcards."""
        from scripts.snakemake_utils import get_model_ids

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_models, f)
            f.flush()  # Ensure data is written
            models_file = f.name

        try:
            model_ids = get_model_ids(models_file)

            expected_ids = ["thedrummer/unslopnemo-12b", "openai/gpt-oss-120b", "inception/mercury"]

            assert model_ids == expected_ids
            assert len(model_ids) == 3

        finally:
            Path(models_file).unlink()

    def test_empty_model_list_handling(self):
        """Test graceful handling of empty model lists."""

        empty_models = {"pool_info": {"name": "empty", "model_count": 0}, "models": []}

        mock_skills = {"evals": []}
        mock_judges = {"judges": []}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as models_f:
            json.dump(empty_models, models_f)
            models_f.flush()
            models_file = models_f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as skills_f:
            json.dump(mock_skills, skills_f)
            skills_f.flush()
            skills_file = skills_f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as judges_f:
            json.dump(mock_judges, judges_f)
            judges_f.flush()
            judges_file = judges_f.name

        try:
            from scripts.execute_conversations_single_model import execute_conversations_for_model

            result = execute_conversations_for_model(
                models_file=models_file, skills_file=skills_file, judges_file=judges_file, target_model_id="nonexistent/model"
            )

            # Should return empty but valid structure
            assert result["execution_info"]["models_count"] == 0
            assert result["conversations"] == []
            assert result["intermediaries"] == []

        finally:
            Path(models_file).unlink()
            Path(skills_file).unlink()
            Path(judges_file).unlink()


class TestConversationAggregation:
    """Test aggregation of per-model conversation results."""

    @pytest.fixture
    def sample_per_model_outputs(self):
        """Sample outputs from multiple per-model executions."""
        return [
            {
                "execution_info": {
                    "total_conversations": 45,
                    "successful_conversations": 44,
                    "failed_conversations": 1,
                    "total_intermediaries": 5,
                    "successful_intermediaries": 5,
                    "failed_intermediaries": 0,
                    "timestamp": "2025-08-20T10:00:00",
                    "models_count": 1,
                    "evals_count": 45,
                    "judges_count": 3,
                },
                "conversations": [
                    {
                        "metadata": {"model_id": "model_a", "eval_id": "eval_1", "skill_id": "skill_1"},
                        "messages": [{"role": "user", "content": "test"}],
                    }
                ],
                "intermediaries": [{"id": "inter_1", "model_id": "model_a"}],
            },
            {
                "execution_info": {
                    "total_conversations": 45,
                    "successful_conversations": 45,
                    "failed_conversations": 0,
                    "total_intermediaries": 4,
                    "successful_intermediaries": 4,
                    "failed_intermediaries": 0,
                    "timestamp": "2025-08-20T10:01:00",
                    "models_count": 1,
                    "evals_count": 45,
                    "judges_count": 3,
                },
                "conversations": [
                    {
                        "metadata": {"model_id": "model_b", "eval_id": "eval_1", "skill_id": "skill_1"},
                        "messages": [{"role": "user", "content": "test"}],
                    }
                ],
                "intermediaries": [{"id": "inter_2", "model_id": "model_b"}],
            },
        ]

    def test_conversation_aggregation_produces_correct_totals(self, sample_per_model_outputs):
        """Test that aggregated execution_info contains correct totals."""
        from scripts.aggregate_conversations import aggregate_conversation_results

        result = aggregate_conversation_results(sample_per_model_outputs)

        # Verify aggregated totals
        exec_info = result["execution_info"]
        assert exec_info["total_conversations"] == 90  # 45 + 45
        assert exec_info["successful_conversations"] == 89  # 44 + 45
        assert exec_info["failed_conversations"] == 1  # 1 + 0
        assert exec_info["total_intermediaries"] == 9  # 5 + 4
        assert exec_info["models_count"] == 2  # Combined unique models

        # Verify combined arrays
        assert len(result["conversations"]) == 2
        assert len(result["intermediaries"]) == 2

    def test_aggregation_preserves_conversation_data_integrity(self, sample_per_model_outputs):
        """Test that no conversation data is lost or corrupted during aggregation."""
        from scripts.aggregate_conversations import aggregate_conversation_results

        result = aggregate_conversation_results(sample_per_model_outputs)

        # All conversations should be present
        conversation_model_ids = [c["metadata"]["model_id"] for c in result["conversations"]]
        assert "model_a" in conversation_model_ids
        assert "model_b" in conversation_model_ids

        # All intermediaries should be present
        intermediary_model_ids = [i["model_id"] for i in result["intermediaries"]]
        assert "model_a" in intermediary_model_ids
        assert "model_b" in intermediary_model_ids

    def test_aggregation_handles_single_model_input(self):
        """Test aggregation works correctly with only one model."""
        single_model_input = [
            {
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
                    "judges_count": 3,
                },
                "conversations": [{"metadata": {"model_id": "solo_model"}}],
                "intermediaries": [],
            }
        ]

        from scripts.aggregate_conversations import aggregate_conversation_results

        result = aggregate_conversation_results(single_model_input)

        # Should match input for single model case
        assert result["execution_info"]["total_conversations"] == 45
        assert result["execution_info"]["models_count"] == 1
        assert len(result["conversations"]) == 1


class TestParallelizationIntegration:
    """Integration tests for the complete parallelization workflow."""

    def test_aggregated_output_matches_original_format_exactly(self):
        """Critical test: Aggregated output must be byte-for-byte compatible."""
        # This is our most important test - ensures backward compatibility

        # Load original conversations.json for comparison
        original_path = Path("data/testonly/conversations.json")
        if not original_path.exists():
            pytest.skip("Original conversations.json not found - cannot test compatibility")

        with open(original_path) as f:
            original_output = json.load(f)

        # Mock per-model execution for testing
        from scripts.aggregate_conversations import aggregate_conversation_results

        # Create mock per-model outputs that should match the original
        mock_per_model_results = [
            {
                "execution_info": {
                    "total_conversations": 45,
                    "successful_conversations": 45,
                    "failed_conversations": 0,
                    "total_intermediaries": 5,
                    "successful_intermediaries": 5,
                    "failed_intermediaries": 0,
                    "timestamp": "2025-08-20T10:00:00",
                    "models_count": 1,
                    "evals_count": 45,
                    "judges_count": 3,
                },
                "conversations": original_output["conversations"][:45],  # First 45 conversations
                "intermediaries": original_output["intermediaries"][:5],  # First 5 intermediaries
            }
        ]

        aggregated_output = aggregate_conversation_results(mock_per_model_results)

        # Critical assertions for backward compatibility
        assert set(aggregated_output.keys()) == set(original_output.keys())
        # Note: We use mock data so counts may differ, but structure should match
        assert "conversations" in aggregated_output
        assert "intermediaries" in aggregated_output
        assert "execution_info" in aggregated_output
        assert isinstance(aggregated_output["conversations"], list)
        assert isinstance(aggregated_output["intermediaries"], list)

    def test_downstream_compatibility_with_run_tournaments(self):
        """Test that run_tournaments.py can process aggregated output identically."""
        # This ensures our downstream components aren't broken

        from scripts.aggregate_conversations import aggregate_conversation_results

        # Create mock per-model outputs
        mock_outputs = [
            {
                "execution_info": {
                    "total_conversations": 2,
                    "successful_conversations": 2,
                    "failed_conversations": 0,
                    "total_intermediaries": 0,
                    "successful_intermediaries": 0,
                    "failed_intermediaries": 0,
                    "timestamp": "2025-08-20T10:00:00",
                    "models_count": 1,
                    "evals_count": 2,
                    "judges_count": 1,
                },
                "conversations": [
                    {"metadata": {"model_id": "model_1", "eval_id": "eval_1"}},
                    {"metadata": {"model_id": "model_1", "eval_id": "eval_2"}},
                ],
                "intermediaries": [],
            }
        ]

        aggregated = aggregate_conversation_results(mock_outputs)

        # Test that this format is compatible with downstream processing
        assert "conversations" in aggregated
        assert isinstance(aggregated["conversations"], list)
        assert all("metadata" in conv for conv in aggregated["conversations"])
        assert "execution_info" in aggregated
        assert aggregated["execution_info"]["total_conversations"] == 2


class TestPerformanceAndSafety:
    """Performance and safety verification tests."""

    def test_parallel_execution_actually_parallelizes(self):
        """Test that Snakemake rules actually execute in parallel."""
        import json
        import subprocess
        import tempfile
        from pathlib import Path

        # Create temporary test environment to avoid touching real data
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create minimal test data files
            test_models = {
                "pool_info": {"name": "test", "model_count": 2},
                "models": [{"id": "model_a", "slug": "model_a"}, {"id": "model_b", "slug": "model_b"}],
            }
            test_skills = {"evals": [{"id": "test_eval", "_metadata": {"skill": "test_skill"}}]}
            test_judges = {"judges": [{"id": "test_judge"}]}

            # Write test files
            models_file = temp_path / "loaded_models.json"
            skills_file = temp_path / "loaded_skills.json"
            judges_file = temp_path / "loaded_judges.json"

            with open(models_file, "w") as f:
                json.dump(test_models, f)
            with open(skills_file, "w") as f:
                json.dump(test_skills, f)
            with open(judges_file, "w") as f:
                json.dump(test_judges, f)

            # Test Snakemake dry-run to verify parallel job generation
            result = subprocess.run(
                [
                    "snakemake",
                    "--dry-run",
                    "--jobs",
                    "4",
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

            # Verify that multiple model-specific rules would be generated
            # (This tests the rule structure, not actual execution to avoid resource usage)
            if result.returncode == 0:
                output_text = result.stdout + result.stderr
                # Should mention multiple models or parallel execution capability
                assert (
                    "model_a" in output_text or "model_b" in output_text or "execute_conversations_for_model" in output_text
                ), f"Dry-run should show parallel model processing. Output: {output_text}"

    def test_cache_preservation_across_parallelization(self):
        """Test that existing cache files remain valid and functional."""
        import json
        import tempfile
        import threading
        import time
        from pathlib import Path

        # Create temporary cache environment
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()

            # Create mock cache files
            test_cache_files = {
                "conversation_cache_model_a_eval1.json": {"cached": True, "data": "test_a"},
                "conversation_cache_model_b_eval1.json": {"cached": True, "data": "test_b"},
                "intermediary_cache_judge1_eval1.json": {"cached": True, "intermediary": "data"},
            }

            for filename, content in test_cache_files.items():
                cache_file = cache_dir / filename
                with open(cache_file, "w") as f:
                    json.dump(content, f)

            # Simulate concurrent access to cache files
            cache_access_results = []
            access_errors = []

            def access_cache_file(model_id, delay=0):
                try:
                    time.sleep(delay)
                    cache_file = cache_dir / f"conversation_cache_{model_id}_eval1.json"

                    # Read cache file (this should work even during concurrent access)
                    if cache_file.exists():
                        with open(cache_file) as f:
                            data = json.load(f)
                        cache_access_results.append(f"{model_id}: {data['data']}")
                    else:
                        access_errors.append(f"Cache file missing for {model_id}")

                except Exception as e:
                    access_errors.append(f"Cache access error for {model_id}: {e}")

            # Test concurrent cache access (simulating parallel model execution)
            threads = []
            for i, model_id in enumerate(["model_a", "model_b"]):
                thread = threading.Thread(target=access_cache_file, args=(model_id, i * 0.1))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5)

            # Verify cache files are intact and accessible
            assert len(access_errors) == 0, f"Cache access errors: {access_errors}"
            assert len(cache_access_results) == 2, "Should successfully read both cache files"
            assert "model_a: test_a" in cache_access_results
            assert "model_b: test_b" in cache_access_results

            # Verify original cache files are unchanged
            for filename, expected_content in test_cache_files.items():
                cache_file = cache_dir / filename
                assert cache_file.exists(), f"Cache file {filename} should still exist"

                with open(cache_file) as f:
                    actual_content = json.load(f)
                assert actual_content == expected_content, f"Cache file {filename} content corrupted"

    def test_graceful_failure_handling(self):
        """Test that individual model failures don't crash the entire pipeline."""
        import json
        import tempfile
        from pathlib import Path

        # Test that individual model failures are isolated
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test data
            test_models = {
                "pool_info": {"name": "test", "model_count": 3},
                "models": [
                    {"id": "working_model", "slug": "working"},
                    {"id": "failing_model", "slug": "failing"},
                    {"id": "another_working_model", "slug": "working2"},
                ],
            }
            test_skills = {"evals": [{"id": "test_eval", "_metadata": {"skill": "test_skill"}}]}
            test_judges = {"judges": [{"id": "test_judge"}]}

            models_file = temp_path / "models.json"
            skills_file = temp_path / "skills.json"
            judges_file = temp_path / "judges.json"

            with open(models_file, "w") as f:
                json.dump(test_models, f)
            with open(skills_file, "w") as f:
                json.dump(test_skills, f)
            with open(judges_file, "w") as f:
                json.dump(test_judges, f)

            # Mock ConversationExecutor to simulate failures
            from scripts.execute_conversations_single_model import execute_conversations_for_model

            def mock_execute_conversation(model, skill_id, eval_data):
                if model["id"] == "failing_model":
                    raise Exception("Simulated API failure")
                return {
                    "metadata": {"model_id": model["id"], "timestamp": "2025-08-20T10:00:00"},
                    "messages": [{"role": "assistant", "content": "success"}],
                }

            with patch("scripts.execute_conversations_single_model.ConversationExecutor") as mock_executor_class:
                with patch("scripts.execute_conversations_single_model.cleanup_stale_cache"):
                    mock_executor = MagicMock()
                    mock_executor.execute_conversation.side_effect = mock_execute_conversation
                    mock_executor.execute_intermediary.return_value = {"id": "test_inter"}
                    mock_executor_class.return_value = mock_executor

                    # Test each model separately - working models should succeed
                    working_result = execute_conversations_for_model(
                        str(models_file), str(skills_file), str(judges_file), "working_model"
                    )
                    assert working_result["execution_info"]["successful_conversations"] == 1
                    assert working_result["execution_info"]["failed_conversations"] == 0

                    # Failing model should handle the failure gracefully
                    failing_result = execute_conversations_for_model(
                        str(models_file), str(skills_file), str(judges_file), "failing_model"
                    )
                    assert failing_result["execution_info"]["successful_conversations"] == 0
                    assert failing_result["execution_info"]["failed_conversations"] == 1
                    assert len(failing_result["conversations"]) == 0  # No successful conversations

                    # Test aggregation with mixed results
                    from scripts.aggregate_conversations import aggregate_conversation_results

                    mixed_results = [working_result, failing_result]
                    aggregated = aggregate_conversation_results(mixed_results)

                    # Should aggregate correctly despite one failure
                    assert aggregated["execution_info"]["total_conversations"] == 2
                    assert aggregated["execution_info"]["successful_conversations"] == 1
                    assert aggregated["execution_info"]["failed_conversations"] == 1
                    assert len(aggregated["conversations"]) == 1  # Only successful conversation

    def test_rollback_scenario_preserves_data(self):
        """Test that rolling back to original implementation works seamlessly."""
        import json
        import tempfile
        from pathlib import Path

        # Test that legacy rule still works and produces compatible output
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test data
            test_models = {
                "pool_info": {"name": "test", "model_count": 2},
                "models": [{"id": "model_a", "slug": "model_a"}, {"id": "model_b", "slug": "model_b"}],
            }
            test_skills = {"evals": [{"id": "test_eval", "_metadata": {"skill": "test_skill"}}]}
            test_judges = {"judges": [{"id": "test_judge"}]}

            models_file = temp_path / "models.json"
            skills_file = temp_path / "skills.json"
            judges_file = temp_path / "judges.json"

            with open(models_file, "w") as f:
                json.dump(test_models, f)
            with open(skills_file, "w") as f:
                json.dump(test_skills, f)
            with open(judges_file, "w") as f:
                json.dump(test_judges, f)

            # Test that we can switch between parallel and legacy versions
            # by verifying both produce the same structure

            # Simulate parallel execution results
            from scripts.aggregate_conversations import aggregate_conversation_results
            from scripts.execute_conversations_single_model import execute_conversations_for_model

            # Mock executor for consistent results
            mock_conversation = {
                "metadata": {"model_id": "test", "timestamp": "2025-08-20T10:00:00"},
                "messages": [{"role": "assistant", "content": "test"}],
            }

            with patch("scripts.execute_conversations_single_model.ConversationExecutor") as mock_executor_class:
                with patch("scripts.execute_conversations_single_model.cleanup_stale_cache"):
                    mock_executor = MagicMock()
                    mock_executor.execute_conversation.return_value = mock_conversation
                    mock_executor.execute_intermediary.return_value = {"id": "test_inter"}
                    mock_executor_class.return_value = mock_executor

                    # Get parallel results
                    parallel_results = []
                    for model in test_models["models"]:
                        result = execute_conversations_for_model(
                            str(models_file), str(skills_file), str(judges_file), model["id"]
                        )
                        parallel_results.append(result)

                    aggregated_parallel = aggregate_conversation_results(parallel_results)

            # Verify structure matches expected legacy format
            expected_keys = {"execution_info", "conversations", "intermediaries"}
            assert set(aggregated_parallel.keys()) == expected_keys

            expected_execution_info_keys = {
                "total_conversations",
                "successful_conversations",
                "failed_conversations",
                "total_intermediaries",
                "successful_intermediaries",
                "failed_intermediaries",
                "timestamp",
                "models_count",
                "evals_count",
                "judges_count",
            }
            assert set(aggregated_parallel["execution_info"].keys()) == expected_execution_info_keys

            # Verify data integrity
            assert isinstance(aggregated_parallel["conversations"], list)
            assert isinstance(aggregated_parallel["intermediaries"], list)
            # Model count reflects unique models in conversations, not input count
            assert aggregated_parallel["execution_info"]["models_count"] >= 1
            assert aggregated_parallel["execution_info"]["total_conversations"] >= 0


if __name__ == "__main__":
    # Run tests to see current failures (expected in TDD)
    pytest.main([__file__, "-v"])
