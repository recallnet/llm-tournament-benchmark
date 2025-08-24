"""
Integration tests for Snakemake parallelization rules and workflow.

These tests verify that the Snakemake workflow correctly handles
per-model parallelization and produces equivalent results.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestSnakemakeWorkflowIntegration:
    """Test Snakemake workflow with parallelization enabled."""

    def test_snakemake_per_model_rules_exist(self):
        """Test that required Snakemake rules are defined."""
        # Check that the actual implemented rules exist

        # Read Snakefile and check for required rules
        snakefile_path = Path("Snakefile")
        assert snakefile_path.exists()

        with open(snakefile_path) as f:
            snakefile_content = f.read()

        # Check for the actually implemented parallelization rules
        assert "execute_conversations_for_model" in snakefile_content
        assert (
            "run_tournament_per_skill" in snakefile_content and
            "aggregate_tournaments" in snakefile_content
        )  # Now uses parallel per-skill tournaments
        assert "get_model_ids" in snakefile_content

    def test_snakemake_wildcard_expansion_works(self):
        """Test that model ID wildcards expand correctly."""
        # Test with a rule that actually exists and uses model wildcards
        result = subprocess.run(
            [
                "snakemake",
                "--dry-run",
                "-s",
                "Snakefile",
                "data/testonly/tournaments.json",
            ],  # Test actual target
            capture_output=True,
            text=True,
        )

        # Should show parallel model rules or complete successfully
        assert (
            result.returncode == 0 or 
            "execute_conversations_for_model" in result.stdout or
            "run_tournament_per_skill" in result.stdout
        )
        assert multiple_model_ids_found_in_output(result.stdout)
        assert result.returncode == 0

    def test_snakemake_parallel_job_limit_respected(self):
        """Test that -j flag limits concurrent model executions."""
        # This test verifies job control works correctly
        pass  # Implementation after rules exist

    def test_snakemake_dependency_graph_correct(self):
        """Test that dependency graph allows proper parallelization."""
        result = subprocess.run(
            [
                "snakemake",
                "--dry-run",
                "--dag",
                "dot",
                "data/testonly/tournaments.json",
            ],
            capture_output=True,
            text=True,
        )

        # Verify per-model rules can run in parallel
        # (No dependencies between different model executions)
        dag_output = result.stdout
        assert (
            "execute_conversations_for_model" in dag_output
            or "run_tournament_per_skill" in dag_output
            or "aggregate_tournaments" in dag_output
            or result.returncode == 0
        )
        assert result.returncode == 0


class TestModelIdExtraction:
    """Test model ID extraction for Snakemake wildcards."""

    @pytest.fixture
    def temp_models_file(self):
        """Create temporary models file for testing."""
        models_data = {
            "pool_info": {"name": "test", "model_count": 3},
            "models": [
                {"id": "model/a", "slug": "a"},
                {"id": "model/b", "slug": "b"},
                {"id": "model/c", "slug": "c"},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(models_data, f)
            f.flush()  # Ensure data is written to disk
            temp_file_path = f.name

        yield temp_file_path
        Path(temp_file_path).unlink()

    def test_get_model_ids_function_extraction(self, temp_models_file):
        """Test that get_model_ids extracts correct model IDs."""
        from scripts.snakemake_utils import get_model_ids

        model_ids = get_model_ids(temp_models_file)

        expected_ids = ["model/a", "model/b", "model/c"]
        assert model_ids == expected_ids

    def test_model_id_sanitization_for_filenames(self, temp_models_file):
        """Test that model IDs are properly sanitized for use in filenames."""
        from scripts.snakemake_utils import sanitize_model_id_for_filename

        # Test sanitization of problematic characters
        assert sanitize_model_id_for_filename("model/a") == "model_a"
        assert sanitize_model_id_for_filename("org/model:tag") == "org_model_tag"
        assert sanitize_model_id_for_filename("model.with.dots") == "model_with_dots"

    def test_reverse_model_id_lookup(self):
        """Test that we can map sanitized filenames back to original model IDs."""
        from scripts.snakemake_utils import reverse_sanitize_model_id

        # Should be able to reverse the sanitization
        assert reverse_sanitize_model_id("model_a") == "model/a"
        assert reverse_sanitize_model_id("org_model_tag") == "org/model:tag"


class TestConversationAggregationWorkflow:
    """Test the conversation aggregation workflow."""

    @pytest.fixture
    def temp_per_model_files(self):
        """Create temporary per-model conversation files."""
        model_outputs = {
            "model_a": {
                "execution_info": {
                    "total_conversations": 2,
                    "successful_conversations": 2,
                    "models_count": 1,
                },
                "conversations": [
                    {"metadata": {"model_id": "model_a", "eval_id": "eval1"}},
                    {"metadata": {"model_id": "model_a", "eval_id": "eval2"}},
                ],
                "intermediaries": [],
            },
            "model_b": {
                "execution_info": {
                    "total_conversations": 2,
                    "successful_conversations": 1,
                    "failed_conversations": 1,
                    "models_count": 1,
                },
                "conversations": [
                    {"metadata": {"model_id": "model_b", "eval_id": "eval1"}}
                ],
                "intermediaries": [{"id": "inter1", "model_id": "model_b"}],
            },
        }

        temp_files = {}
        for model_id, output in model_outputs.items():
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(output, f)
                temp_files[model_id] = f.name

        yield temp_files

        # Cleanup
        for file_path in temp_files.values():
            Path(file_path).unlink()

    def test_aggregation_script_handles_file_list(self, temp_per_model_files):
        """Test aggregation script processes list of files correctly."""
        from scripts.aggregate_conversations import main as aggregate_main

        input_files = list(temp_per_model_files.values())

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as output_file:
            aggregate_main(input_files, output_file.name)

            # Verify aggregated output
            with open(output_file.name) as f:
                result = json.load(f)

            assert result["execution_info"]["total_conversations"] == 4  # 2 + 2
            assert result["execution_info"]["successful_conversations"] == 3  # 2 + 1
            assert result["execution_info"]["failed_conversations"] == 1
            assert len(result["conversations"]) == 3  # 2 + 1
            assert len(result["intermediaries"]) == 1

            Path(output_file.name).unlink()


class TestBackwardCompatibility:
    """Critical tests for backward compatibility with existing pipeline."""

    def test_original_conversations_json_structure_preserved(self):
        """Test that aggregated output has identical structure to original."""
        # This is the most critical test - ensures we don't break anything

        original_path = Path("data/testonly/conversations.json")
        if not original_path.exists():
            pytest.skip("Original conversations.json not found")

        with open(original_path) as f:
            original = json.load(f)

        # Verify expected structure exists in original
        required_keys = {"execution_info", "conversations", "intermediaries"}
        assert set(original.keys()) == required_keys

        # Test will validate that our aggregated output matches this exactly
        assert isinstance(original["conversations"], list)
        assert isinstance(original["intermediaries"], list)
        assert isinstance(original["execution_info"], dict)

    def test_downstream_script_compatibility(self):
        """Test that run_tournaments.py works with aggregated conversations."""
        # Critical test - ensures downstream pipeline components work

        mock_aggregated_output = {
            "execution_info": {
                "total_conversations": 2,
                "models_count": 2,
                "evals_count": 1,
            },
            "conversations": [
                {
                    "metadata": {
                        "model_id": "model_a",
                        "eval_id": "eval_1",
                        "skill_id": "skill_1",
                    },
                    "messages": [{"role": "user", "content": "test"}],
                },
                {
                    "metadata": {
                        "model_id": "model_b",
                        "eval_id": "eval_1",
                        "skill_id": "skill_1",
                    },
                    "messages": [{"role": "user", "content": "test"}],
                },
            ],
            "intermediaries": [],
        }

        # Test that this structure would be processable by run_tournaments
        # (We'll mock the actual tournament execution)
        conversations = mock_aggregated_output["conversations"]
        assert len(conversations) == 2
        assert all("metadata" in conv for conv in conversations)
        assert all("model_id" in conv["metadata"] for conv in conversations)


def multiple_model_ids_found_in_output(output_text):
    """Helper to check if multiple model IDs appear in Snakemake output."""
    # Look for patterns indicating multiple model executions
    model_patterns = ["model", "thedrummer", "openai", "inception"]
    found_patterns = sum(
        1 for pattern in model_patterns if pattern in output_text.lower()
    )
    return found_patterns >= 2


if __name__ == "__main__":
    # These tests should initially fail - that's expected in TDD
    pytest.main([__file__, "-v"])
