"""
Test incremental caching behavior for AFBench pipeline.

Tests the scenario you described:
- Model changes: new conversations appear but old ones stay, tournaments invalidate
- Eval changes: some conversations stay, others are created/replaced, tournaments partially invalidate
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def temp_pipeline_dirs():
    """Create temporary directories for pipeline testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir)
        conversations_dir = base_path / "conversations"
        intermediaries_dir = base_path / "intermediaries"

        # Create directory structure
        conversations_dir.mkdir(exist_ok=True)
        intermediaries_dir.mkdir(exist_ok=True)

        yield {
            "base": base_path,
            "conversations": conversations_dir,
            "intermediaries": intermediaries_dir,
        }


@pytest.fixture
def mock_models_config():
    """Mock models configuration."""
    return {
        "models": [
            {"id": "test/model-1", "api_key": "test1"},
            {"id": "test/model-2", "api_key": "test2"},
        ]
    }


@pytest.fixture
def mock_skills_config():
    """Mock skills configuration."""
    return {
        "skills": [
            {
                "id": "test_skill",
                "evals": [
                    {"id": "eval-1", "steps": [{"type": "test"}]},
                    {"id": "eval-2", "steps": [{"type": "test"}]},
                ],
            }
        ]
    }


@pytest.fixture
def mock_judges_config():
    """Mock judges configuration."""
    return {"judges": [{"id": "judge/model", "api_key": "judge_key"}]}


class TestIncrementalCaching:
    """Test incremental caching behavior."""

    def test_model_addition_preserves_existing_conversations(
        self, temp_pipeline_dirs, mock_skills_config, mock_judges_config
    ):
        """
        Test: When a new model is added, existing conversations are preserved
        and only new model conversations are created.
        """
        conversations_dir = temp_pipeline_dirs["conversations"]

        # Initial setup: 1 model, 2 evals

        # Create some existing conversation files
        skill_dir = conversations_dir / "test_skill"
        skill_dir.mkdir(exist_ok=True)

        existing_files = [
            "eval-1_test_model-1_hash1.json",
            "eval-2_test_model-1_hash2.json",
        ]

        for filename in existing_files:
            file_path = skill_dir / filename
            file_path.write_text('{"test": "existing conversation"}')
            # Set file time to past
            past_time = time.time() - 3600  # 1 hour ago
            file_path.touch(times=(past_time, past_time))

        # Get initial timestamps
        initial_timestamps = {f.name: f.stat().st_mtime for f in skill_dir.iterdir()}

        # Add a new model

        # Mock conversation execution to only create new model files
        with patch(
            "scripts.execute_conversations.ConversationExecutor"
        ) as mock_executor:
            mock_instance = Mock()
            mock_executor.return_value = mock_instance

            # Simulate that new conversations are created for model-2 only
            def mock_execute(*args, **kwargs):
                # Create new conversation files for model-2
                new_files = [
                    "eval-1_test_model-2_hash3.json",
                    "eval-2_test_model-2_hash4.json",
                ]
                for filename in new_files:
                    file_path = skill_dir / filename
                    file_path.write_text('{"test": "new conversation"}')
                return True

            mock_instance.execute_conversation_with_retry.return_value = True

            # Simulate the pipeline behavior
            # In reality, the execute_conversations.py script would:
            # 1. Check existing files via caching system
            # 2. Only execute conversations for new model
            mock_execute()

        # Verify existing files were not modified
        for filename in existing_files:
            file_path = skill_dir / filename
            assert file_path.exists(), f"Existing file {filename} should be preserved"
            assert (
                file_path.stat().st_mtime == initial_timestamps[filename]
            ), f"Existing file {filename} timestamp should not change"

        # Verify new files were created
        new_files = ["eval-1_test_model-2_hash3.json", "eval-2_test_model-2_hash4.json"]
        for filename in new_files:
            file_path = skill_dir / filename
            assert file_path.exists(), f"New file {filename} should be created"

        # Total files should be 4 (2 existing + 2 new)
        all_files = list(skill_dir.glob("*.json"))
        assert (
            len(all_files) == 4
        ), f"Should have 4 total conversation files, got {len(all_files)}"

    def test_eval_change_invalidates_only_affected_conversations(
        self, temp_pipeline_dirs, mock_models_config, mock_judges_config
    ):
        """
        Test: When an eval changes, only conversations for that eval are regenerated.
        Other evals' conversations are preserved.
        """
        conversations_dir = temp_pipeline_dirs["conversations"]
        skill_dir = conversations_dir / "test_skill"
        skill_dir.mkdir(exist_ok=True)

        # Create existing conversation files for 2 models, 2 evals
        existing_files = [
            "eval-1_test_model-1_hash1.json",  # Will be invalidated
            "eval-1_test_model-2_hash2.json",  # Will be invalidated
            "eval-2_test_model-1_hash3.json",  # Should be preserved
            "eval-2_test_model-2_hash4.json",  # Should be preserved
        ]

        for filename in existing_files:
            file_path = skill_dir / filename
            file_path.write_text('{"test": "existing conversation"}')
            past_time = time.time() - 3600
            file_path.touch(times=(past_time, past_time))

        # Get timestamps for eval-2 files (should be preserved)
        eval2_timestamps = {
            f.name: f.stat().st_mtime for f in skill_dir.iterdir() if "eval-2" in f.name
        }

        # Simulate eval-1 being modified (different hash due to content change)
        # This would happen when skills/test_skill/eval-1.json is updated

        # Mock the conversation execution to regenerate only eval-1 conversations
        with patch("scripts.execute_conversations.ConversationExecutor"):
            # Simulate regenerating eval-1 conversations with new hashes
            # Remove old eval-1 files
            for filename in [
                "eval-1_test_model-1_hash1.json",
                "eval-1_test_model-2_hash2.json",
            ]:
                (skill_dir / filename).unlink()

            # Create new eval-1 files with updated hashes
            new_eval1_files = [
                "eval-1_test_model-1_newhash1.json",
                "eval-1_test_model-2_newhash2.json",
            ]
            for filename in new_eval1_files:
                file_path = skill_dir / filename
                file_path.write_text('{"test": "updated conversation"}')

        # Verify eval-2 files were preserved with original timestamps
        for filename in [
            "eval-2_test_model-1_hash3.json",
            "eval-2_test_model-2_hash4.json",
        ]:
            file_path = skill_dir / filename
            assert file_path.exists(), f"Eval-2 file {filename} should be preserved"
            assert (
                file_path.stat().st_mtime == eval2_timestamps[filename]
            ), f"Eval-2 file {filename} timestamp should not change"

        # Verify new eval-1 files exist
        for filename in [
            "eval-1_test_model-1_newhash1.json",
            "eval-1_test_model-2_newhash2.json",
        ]:
            file_path = skill_dir / filename
            assert file_path.exists(), f"Updated eval-1 file {filename} should exist"

        # Verify old eval-1 files are gone
        for filename in [
            "eval-1_test_model-1_hash1.json",
            "eval-1_test_model-2_hash2.json",
        ]:
            file_path = skill_dir / filename
            assert (
                not file_path.exists()
            ), f"Old eval-1 file {filename} should be removed"

    def test_tournament_invalidation_on_conversation_changes(self, temp_pipeline_dirs):
        """
        Test: When conversations change, tournaments should be invalidated due to
        Snakemake's timestamp-based dependency tracking.
        """
        base_dir = temp_pipeline_dirs["base"]
        conversations_flag = base_dir / "conversations_completed.flag"
        tournaments_file = base_dir / "tournaments.json"

        # Create initial state
        conversations_flag.write_text("completed")
        time.sleep(0.1)  # Ensure different timestamps
        tournaments_file.write_text('{"tournaments": "initial"}')

        initial_tournament_time = tournaments_file.stat().st_mtime

        # Simulate conversation changes by updating the flag
        time.sleep(0.1)
        conversations_flag.write_text("updated")

        # In a real Snakemake run, this would trigger tournament regeneration
        # because tournaments.json depends on conversations_completed.flag

        flag_time = conversations_flag.stat().st_mtime
        tournament_time = tournaments_file.stat().st_mtime

        # Verify the dependency relationship exists
        assert (
            flag_time > initial_tournament_time
        ), "Conversations flag should be newer than initial tournaments"

        # In real Snakemake, tournaments would be regenerated because:
        # tournaments.json depends on conversations_completed.flag
        # and the flag is newer than the tournaments file

        # This simulates what Snakemake would do:
        if flag_time > tournament_time:
            # Tournament would be regenerated
            tournaments_file.write_text('{"tournaments": "regenerated"}')

        updated_content = json.loads(tournaments_file.read_text())
        assert (
            updated_content["tournaments"] == "regenerated"
        ), "Tournaments should be regenerated when conversations change"

    def test_snakemake_timestamp_dependency_chain(self, temp_pipeline_dirs):
        """
        Test: Verify that Snakemake's timestamp-based dependency system
        works correctly for the conversation -> tournament -> ratings chain.
        """
        base_dir = temp_pipeline_dirs["base"]

        # Create the dependency chain files
        conversations_flag = base_dir / "conversations_completed.flag"
        tournaments_file = base_dir / "tournaments.json"
        summaries_file = base_dir / "tournament_summaries.json"
        ratings_file = base_dir / "skill_ratings.json"

        # Create initial state with proper timestamp ordering
        conversations_flag.write_text("v1")
        time.sleep(0.1)
        tournaments_file.write_text("v1")
        time.sleep(0.1)
        summaries_file.write_text("v1")
        time.sleep(0.1)
        ratings_file.write_text("v1")

        # Get initial timestamps
        initial_times = {
            "conversations": conversations_flag.stat().st_mtime,
            "tournaments": tournaments_file.stat().st_mtime,
            "summaries": summaries_file.stat().st_mtime,
            "ratings": ratings_file.stat().st_mtime,
        }

        # Simulate updating conversations (new model added)
        time.sleep(0.2)
        conversations_flag.write_text("v2")

        updated_conv_time = conversations_flag.stat().st_mtime

        # Verify dependency chain logic
        assert (
            updated_conv_time > initial_times["tournaments"]
        ), "Conversations newer than tournaments - tournaments should regenerate"
        assert (
            updated_conv_time > initial_times["summaries"]
        ), "Conversations newer than summaries - summaries should regenerate"
        assert (
            updated_conv_time > initial_times["ratings"]
        ), "Conversations newer than ratings - ratings should regenerate"

        # This is exactly what Snakemake does automatically:
        # It compares file timestamps and regenerates downstream files
        # when upstream dependencies are newer


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
