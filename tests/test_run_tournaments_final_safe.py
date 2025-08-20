"""Safe final tests to push coverage closer to 90% without breaking functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scripts.run_tournaments import JudgeExecutor, SwissTournament, TournamentMatch


class TestSafeFinalCoverage:
    """Safe tests targeting remaining uncovered lines."""

    def test_tournament_rounds_calculation_edge_cases(self):
        """Test rounds calculation with various model counts."""
        # Test actual behavior of current implementation
        test_cases = [
            (2, 1),  # 2 models need 1 round
            (3, 2),  # 3 models: min(3-1, max(3, ceil(log2(3)))) = min(2, max(3, 2)) = min(2, 3) = 2
            (4, 3),  # 4 models: min(4-1, max(3, ceil(log2(4)))) = min(3, max(3, 2)) = min(3, 3) = 3
            (5, 3),  # 5 models: min(5-1, max(3, ceil(log2(5)))) = min(4, max(3, 3)) = min(4, 3) = 3
            (8, 3),  # 8 models: min(8-1, max(3, ceil(log2(8)))) = min(7, max(3, 3)) = min(7, 3) = 3
            (16, 4),  # 16 models: min(16-1, max(3, ceil(log2(16)))) = min(15, max(3, 4)) = min(15, 4) = 4
        ]

        for num_models, expected_rounds in test_cases:
            models = [{"id": f"model_{i}", "name": f"Model {i}"} for i in range(num_models)]
            tournament = SwissTournament("skill_1", "eval_1", models)

            calculated_rounds = tournament._calculate_rounds_needed()
            assert (
                calculated_rounds == expected_rounds
            ), f"For {num_models} models, expected {expected_rounds} rounds but got {calculated_rounds}"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_judge_executor_error_handling(self):
        """Test judge executor handles missing cache gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = JudgeExecutor(cache_dir=Path(temp_dir))

            # Test loading non-existent cache
            missing_path = Path(temp_dir) / "missing_cache.json"
            result = executor._load_judge_cache(missing_path)
            assert result is None

    def test_swiss_tournament_edge_case_pairings(self):
        """Test Swiss tournament handles edge cases in pairing generation."""
        # Test with 2 models (minimum)
        models = [{"id": "model_a", "name": "Model A"}, {"id": "model_b", "name": "Model B"}]
        tournament = SwissTournament("skill_1", "eval_1", models)

        pairings = tournament._get_pairings_for_round(1)
        assert len(pairings) == 1
        assert set(pairings[0]) == {"model_a", "model_b"}

    def test_tournament_match_comprehensive_voting(self):
        """Test tournament match with comprehensive voting scenarios."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        # Test scenario: Multiple judges with clear majority
        match.add_judge_result("judge_1", "A", [{"role": "user", "content": "msg1"}], "A is better")
        match.add_judge_result("judge_2", "A", [{"role": "user", "content": "msg2"}], "A wins")
        match.add_judge_result("judge_3", "B", [{"role": "user", "content": "msg3"}], "B is good")

        result = match.calculate_result()
        assert result == "A"  # A should win with 2/3 votes

        # Verify all judge data is preserved
        assert len(match.judge_votes) == 3
        assert len(match.judge_conversations) == 3
        assert len(match.judge_explanations) == 3

    def test_cache_cleanup_no_directories(self):
        """Test cache cleanup when cache directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use non-existent cache directory
            cache_dir = Path(temp_dir) / "nonexistent_cache"
            executor = JudgeExecutor(cache_dir=cache_dir)

            valid_models = [{"id": "model_a"}]
            valid_judges = [{"id": "judge_1"}]
            valid_evals = [{"id": "eval_1", "_metadata": {"skill": "skill_1"}}]

            # Should handle non-existent directory gracefully
            with patch("builtins.print"):
                executor.cleanup_invalid_match_cache(valid_models, valid_judges, valid_evals)

            # Should complete without error

    def test_tournament_serialization_with_matches(self):
        """Test tournament serialization includes match data."""
        models = [{"id": "model_a", "name": "Model A"}, {"id": "model_b", "name": "Model B"}]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # Add completed match
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        match.add_judge_result("judge_1", "A", [], "A wins")
        match.calculate_result()

        tournament.rounds = [[match]]
        tournament.update_scores(match)

        # Serialize to dict
        data = tournament.to_dict()

        # Should include rounds data
        assert "rounds" in data
        assert len(data["rounds"]) == 1
        assert len(data["rounds"][0]) == 1

        # Should include correct model scores
        assert data["scores"]["model_a"] == 1.0
        assert data["scores"]["model_b"] == 0.0

    def test_match_conversation_keys(self):
        """Test match conversation key assignment."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        # Set conversation keys (as would happen in real execution)
        match.conversation_a_key = "conv_key_a_123"
        match.conversation_b_key = "conv_key_b_456"
        match.timestamp = "2024-01-01T12:00:00Z"

        # Add judge result
        match.add_judge_result("judge_1", "TIE", [], "Both are good")
        match.calculate_result()

        # Verify serialization includes all data
        data = match.to_dict()
        assert data["conversation_a_key"] == "conv_key_a_123"
        assert data["conversation_b_key"] == "conv_key_b_456"
        assert data["timestamp"] == "2024-01-01T12:00:00Z"
        assert data["result"] == "TIE"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_judge_cache_directory_creation(self):
        """Test judge cache directory creation for different skills."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = JudgeExecutor(cache_dir=Path(temp_dir))

            match1 = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
            match2 = TournamentMatch("model_c", "model_d", "eval_2", "skill_2")

            # Get cache paths for different skills
            path1 = executor._get_judge_cache_path(match1, "judge_1", "key1")
            path2 = executor._get_judge_cache_path(match2, "judge_1", "key2")

            # Should create different skill directories
            assert "skill_1" in str(path1)
            assert "skill_2" in str(path2)
            assert path1.parent.name == "skill_1"
            assert path2.parent.name == "skill_2"

    def test_swiss_tournament_completion_with_many_models(self):
        """Test tournament completion logic with larger numbers of models."""
        # Test with 8 models
        models = [{"id": f"model_{i}", "name": f"Model {i}"} for i in range(8)]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # Simulate 3 complete rounds
        tournament.rounds = [[], [], []]

        # Set up scores with clear winner
        tournament.scores = {f"model_{i}": max(0, 3 - i * 0.5) for i in range(8)}

        # Should be complete with clear leader
        assert tournament.is_tournament_complete()

        # Test tied scenario
        tournament.scores["model_0"] = 2.5
        tournament.scores["model_1"] = 2.5  # Now tied for first

        # Should not be complete due to tie
        assert not tournament.is_tournament_complete()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_judge_cache_save_and_load_integration(self):
        """Test judge cache save and load integration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = JudgeExecutor(cache_dir=Path(temp_dir))

            match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
            cache_path = executor._get_judge_cache_path(match, "judge_1", "test_key")

            # Test save then load
            test_data = {"vote": "A", "explanation": "A is better", "metadata": {"test": True}}
            executor._save_judge_cache(cache_path, test_data)

            loaded_data = executor._load_judge_cache(cache_path)
            assert loaded_data == test_data
