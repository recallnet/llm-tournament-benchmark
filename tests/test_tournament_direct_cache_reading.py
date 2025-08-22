"""
TDD tests for tournament system reading directly from conversation cache.

This tests the refactored tournament system that bypasses the mega
conversations.json file and reads directly from individual cache files.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestTournamentDirectCacheReading:
    """Test tournament system reading directly from conversation cache."""

    def setup_method(self):
        """Set up test environment with mock conversation cache."""
        # Create temporary directory structure
        self.temp_dir = tempfile.mkdtemp()
        self.conversations_dir = Path(self.temp_dir) / "conversations"
        self.conversations_dir.mkdir(parents=True)

        # Create skill subdirectories
        for skill in ["harm_avoidance", "code_generation"]:
            (self.conversations_dir / skill).mkdir()

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def create_mock_conversation_file(
        self, skill: str, eval_id: str, model_id: str, messages: list
    ):
        """Create a mock conversation cache file."""
        safe_model_id = model_id.replace("/", "_").replace(":", "_")
        filename = f"{eval_id}_{safe_model_id}_abc123.json"
        file_path = self.conversations_dir / skill / filename

        conversation_data = {
            "metadata": {
                "skill_id": skill,
                "eval_id": eval_id,
                "model_id": model_id,
                "cache_key": "abc123",
            },
            "messages": messages,
            "execution_info": {"status": "completed"},
        }

        with open(file_path, "w") as f:
            json.dump(conversation_data, f, indent=2)

        return file_path

    def test_find_conversation_in_cache_basic(self):
        """Test finding a conversation directly from cache files."""
        print("\\n🔍 TESTING: Find conversation in cache")

        # Create test conversation
        messages = [
            {"role": "user", "content": "Test prompt"},
            {"role": "assistant", "content": "Test response"},
        ]

        self.create_mock_conversation_file(
            "harm_avoidance", "test_eval", "thedrummer/unslopnemo-12b", messages
        )

        # Test the function we need to implement
        from scripts.run_tournaments import find_conversation_in_cache

        conversation = find_conversation_in_cache(
            str(self.conversations_dir),
            "harm_avoidance",
            "test_eval",
            "thedrummer/unslopnemo-12b",
        )

        assert conversation is not None, "Should find conversation in cache"
        assert conversation["metadata"]["model_id"] == "thedrummer/unslopnemo-12b"
        assert conversation["metadata"]["eval_id"] == "test_eval"
        assert len(conversation["messages"]) == 2
        assert conversation["messages"][-1]["content"] == "Test response"

        print("✅ Successfully found conversation in cache")

    def test_find_conversation_in_cache_missing(self):
        """Test handling of missing conversation in cache."""
        print("\\n❓ TESTING: Handle missing conversation")

        from scripts.run_tournaments import find_conversation_in_cache

        conversation = find_conversation_in_cache(
            str(self.conversations_dir),
            "harm_avoidance",
            "nonexistent_eval",
            "thedrummer/unslopnemo-12b",
        )

        assert conversation is None, "Should return None for missing conversation"
        print("✅ Correctly handled missing conversation")

    def test_find_conversation_multiple_models(self):
        """Test finding conversations for different models in same eval."""
        print("\\n👥 TESTING: Multiple models same eval")

        # Create conversations for different models
        models = [
            "thedrummer/unslopnemo-12b",
            "openai/gpt-oss-20b",
            "inception/mercury",
        ]

        for i, model_id in enumerate(models):
            messages = [
                {"role": "user", "content": f"Test prompt for {model_id}"},
                {"role": "assistant", "content": f"Response from {model_id} #{i}"},
            ]
            self.create_mock_conversation_file(
                "code_generation", "python_task", model_id, messages
            )

        from scripts.run_tournaments import find_conversation_in_cache

        # Test finding each conversation
        for i, model_id in enumerate(models):
            conversation = find_conversation_in_cache(
                str(self.conversations_dir), "code_generation", "python_task", model_id
            )

            assert conversation is not None, f"Should find conversation for {model_id}"
            assert conversation["metadata"]["model_id"] == model_id
            assert (
                f"Response from {model_id} #{i}"
                in conversation["messages"][-1]["content"]
            )

        print(f"✅ Found conversations for all {len(models)} models")

    def test_tournament_system_without_mega_file(self):
        """Test that tournament system works without conversations.json."""
        print("\\n🏆 TESTING: Tournament system without mega file")

        # Create test conversations
        test_conversations = [
            ("harm_avoidance", "eval1", "thedrummer/unslopnemo-12b", "Response A1"),
            ("harm_avoidance", "eval1", "openai/gpt-oss-20b", "Response B1"),
            ("harm_avoidance", "eval2", "thedrummer/unslopnemo-12b", "Response A2"),
            ("harm_avoidance", "eval2", "openai/gpt-oss-20b", "Response B2"),
        ]

        for skill, eval_id, model_id, response in test_conversations:
            messages = [
                {"role": "user", "content": f"Prompt for {eval_id}"},
                {"role": "assistant", "content": response},
            ]
            self.create_mock_conversation_file(skill, eval_id, model_id, messages)

        # Mock the tournament system to use cache directly
        with patch("scripts.run_tournaments.find_conversation_in_cache") as mock_find:
            # Mock successful cache lookups
            def mock_find_impl(cache_dir, skill, eval_id, model_id):
                for test_skill, test_eval, test_model, response in test_conversations:
                    if (
                        test_skill == skill
                        and test_eval == eval_id
                        and test_model == model_id
                    ):
                        return {
                            "metadata": {
                                "skill_id": skill,
                                "eval_id": eval_id,
                                "model_id": model_id,
                            },
                            "messages": [
                                {"role": "user", "content": f"Prompt for {eval_id}"},
                                {"role": "assistant", "content": response},
                            ],
                        }
                return None

            mock_find.side_effect = mock_find_impl

            # This should work without needing conversations.json
            from scripts.run_tournaments import build_judge_prompt_from_cache

            prompt = build_judge_prompt_from_cache(
                str(self.conversations_dir),
                "harm_avoidance",
                "eval1",
                "thedrummer/unslopnemo-12b",
                "openai/gpt-oss-20b",
            )

            assert "Response A1" in prompt, "Should include model A response"
            assert "Response B1" in prompt, "Should include model B response"

        print("✅ Tournament system works without mega file")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
