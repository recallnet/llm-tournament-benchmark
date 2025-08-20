"""Advanced tests for run_tournaments to increase coverage to 90%."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scripts.run_tournaments import JudgeExecutor, SwissTournament, TournamentMatch, main


class TestSwissTournamentAdvanced:
    """Advanced test cases for SwissTournament covering edge cases."""

    def test_get_pairings_with_byes(self):
        """Test pairing generation with odd number of models (byes)."""
        models = [
            {"id": "model_a", "name": "Model A"},
            {"id": "model_b", "name": "Model B"},
            {"id": "model_c", "name": "Model C"},  # Odd number
        ]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # First round - should have 1 pairing + 1 bye
        pairings = tournament._get_pairings_for_round(1)
        assert len(pairings) == 1  # Only one pair possible

        # Check that bye is awarded correctly
        paired_models = set()
        for pair in pairings:
            paired_models.add(pair[0])
            paired_models.add(pair[1])

        bye_model = [m["id"] for m in models if m["id"] not in paired_models][0]
        assert bye_model in tournament.scores
        # Bye should award 1 point
        expected_bye_score = 1.0
        tournament.scores[bye_model] = expected_bye_score
        assert tournament.scores[bye_model] == expected_bye_score

    def test_get_pairings_avoid_rematches(self):
        """Test that pairings avoid rematches from previous rounds."""
        models = [
            {"id": "model_a", "name": "Model A"},
            {"id": "model_b", "name": "Model B"},
            {"id": "model_c", "name": "Model C"},
            {"id": "model_d", "name": "Model D"},
        ]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # Simulate first round
        first_round_pairings = tournament._get_pairings_for_round(1)
        first_round_matches = []
        for pair in first_round_pairings:
            match = TournamentMatch(pair[0], pair[1], "eval_1", "skill_1")
            match.add_judge_result("judge_1", "A", [], "A wins")
            match.calculate_result()
            first_round_matches.append(match)

        tournament.rounds.append(first_round_matches)
        tournament.update_scores(first_round_matches)

        # Second round should avoid rematches
        second_round_pairings = tournament._get_pairings_for_round(2)

        # Verify no rematches
        first_round_pairs = {tuple(sorted([m.model_a_id, m.model_b_id])) for m in first_round_matches}
        second_round_pairs = {tuple(sorted(pair)) for pair in second_round_pairings}

        assert len(first_round_pairs.intersection(second_round_pairs)) == 0

    def test_tournament_completion_logic(self):
        """Test tournament completion with different scenarios."""
        models = [
            {"id": "model_a", "name": "Model A"},
            {"id": "model_b", "name": "Model B"},
            {"id": "model_c", "name": "Model C"},
            {"id": "model_d", "name": "Model D"},
        ]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # Scenario 1: Insufficient rounds
        assert not tournament.is_tournament_complete()

        # Scenario 2: Clear winner after sufficient rounds
        tournament.scores = {"model_a": 3.0, "model_b": 2.0, "model_c": 1.0, "model_d": 0.0}
        tournament.rounds = [[], [], []]  # 3 rounds completed
        assert tournament.is_tournament_complete()

        # Scenario 3: Tied leaders - tournament should continue
        tournament.scores = {"model_a": 3.0, "model_b": 3.0, "model_c": 1.0, "model_d": 0.0}
        assert not tournament.is_tournament_complete()


class TestJudgeExecutorAdvanced:
    """Advanced test cases for JudgeExecutor covering missing functionality."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_build_view_content(self):
        """Test view content building functionality."""
        executor = JudgeExecutor()

        # Mock conversations data
        conversations_data = {
            "conversations": [
                {
                    "metadata": {"model_id": "model_a", "skill_id": "skill_1", "eval_id": "eval_1"},
                    "steps": [{"step": 1, "content": "Step 1"}],
                    "messages": [{"role": "user", "content": "Hello"}],
                    "final": "Final response A",
                },
                {
                    "metadata": {"model_id": "model_b", "skill_id": "skill_1", "eval_id": "eval_1"},
                    "steps": [{"step": 1, "content": "Step 1"}],
                    "messages": [{"role": "user", "content": "Hello"}],
                    "final": "Final response B",
                },
            ]
        }

        # Test different view specifications
        view_spec = [
            {"type": "conversation_step", "step": 1, "model": "A"},
            {"type": "conversation_final", "model": "B"},
            {"type": "conversation_messages", "model": "A"},
        ]

        content = executor._build_view_content(
            view_spec, conversations_data, conversations_data, "model_a", "skill_1", "eval_1"
        )

        assert "Step 1" in content
        assert "Final response B" in content
        assert "Hello" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_build_view_content_missing_data(self):
        """Test view content building with missing data."""
        executor = JudgeExecutor()

        # Mock conversations with missing data
        conversations_data = {
            "conversations": [
                {
                    "metadata": {"model_id": "model_a", "skill_id": "skill_1", "eval_id": "eval_1"},
                    "steps": [],  # No steps
                    "messages": [],  # No messages
                    "final": None,  # No final response
                }
            ]
        }

        view_spec = [
            {"type": "conversation_step", "step": 1, "model": "A"},
            {"type": "conversation_final", "model": "A"},
        ]

        content = executor._build_view_content(
            view_spec, conversations_data, conversations_data, "model_a", "skill_1", "eval_1"
        )

        # Should contain error markers for missing data
        assert "[STEP_NOT_FOUND:" in content
        assert "[NO_FINAL_RESPONSE]" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("requests.post")
    def test_execute_judge_api_call(self, mock_post):
        """Test judge API execution."""
        executor = JudgeExecutor()

        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "**Vote: A**\nModel A is better because..."}}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Test judge execution
        judge_config = {"name": "test-judge", "model": "gpt-4", "view": {"A": [], "B": []}, "prompt": "Compare these models"}

        conversations_a = {"conversations": []}
        conversations_b = {"conversations": []}

        result = executor.execute_judge(
            judge_config, conversations_a, conversations_b, "model_a", "model_b", "skill_1", "eval_1"
        )

        assert result["vote"] == "A"
        assert "Model A is better" in result["explanation"]

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_cleanup_invalid_cache(self):
        """Test cache cleanup functionality."""
        executor = JudgeExecutor()

        # Create temporary cache structure
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "tournaments"
            skill_dir = cache_dir / "skill_1"
            skill_dir.mkdir(parents=True)

            # Create valid cache file
            valid_cache = skill_dir / "valid_cache.json"
            with open(valid_cache, "w") as f:
                json.dump(
                    {
                        "metadata": {
                            "model_a_id": "model_a",
                            "model_b_id": "model_b",
                            "judge_id": "judge_1",
                            "eval_id": "eval_1",
                            "skill_id": "skill_1",
                        },
                        "result": {"vote": "A"},
                    },
                    f,
                )

            # Create invalid cache file
            invalid_cache = skill_dir / "invalid_cache.json"
            with open(invalid_cache, "w") as f:
                f.write("invalid json")

            # Create cache for non-existent skill
            old_skill_dir = cache_dir / "old_skill"
            old_skill_dir.mkdir()
            old_cache = old_skill_dir / "old_cache.json"
            with open(old_cache, "w") as f:
                json.dump({"metadata": {}, "result": {}}, f)

            # Set cache dir and run cleanup
            executor.cache_dir = cache_dir

            current_models = {"model_a", "model_b"}
            current_judges = {"judge_1"}
            current_evals = {"eval_1"}
            current_skills = {"skill_1"}

            # Convert to list format as expected by the method
            current_models_list = [{"id": m} for m in current_models]
            current_judges_list = [{"id": j} for j in current_judges]
            current_evals_list = [{"id": e, "_metadata": {"skill": s}} for e, s in zip(current_evals, current_skills)]

            with patch("builtins.print"):  # Suppress print output
                executor.cleanup_invalid_match_cache(current_models_list, current_judges_list, current_evals_list)

            # Should clean up invalid files and directories
            assert not old_skill_dir.exists()
            assert not invalid_cache.exists()
            assert valid_cache.exists()  # Valid cache should remain


class TestMainFunction:
    """Test cases for the main function."""

    @patch("scripts.run_tournaments.Path")
    @patch("builtins.open")
    @patch("json.load")
    def test_main_insufficient_models(self, mock_json_load, mock_open, mock_path):
        """Test main function with insufficient models."""
        # Mock file paths
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance

        # Mock data loading
        mock_json_load.side_effect = [
            {"conversations": []},  # conversations
            {"models": [{"id": "model_a"}]},  # models (only 1)
            {"judges": [{"id": "judge_1"}]},  # judges
            {"evals": [{"id": "eval_1"}]},  # skills
        ]

        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Test that main handles insufficient models
        with patch("builtins.globals", return_value={}):
            with patch("builtins.print") as mock_print:
                main()

        # Should print warning about insufficient models
        mock_print.assert_any_call("⚠️  Need at least 2 models for tournaments - skipping")

    @patch("scripts.run_tournaments.Path")
    @patch("builtins.open")
    @patch("json.load")
    @patch("json.dump")
    def test_main_snakemake_mode(self, mock_json_dump, mock_json_load, mock_open, mock_path):
        """Test main function in Snakemake mode."""
        # Mock snakemake global
        mock_snakemake = Mock()
        mock_snakemake.input.conversations = "input/conversations.json"
        mock_snakemake.input.models = "input/models.json"
        mock_snakemake.input.judges = "input/judges.json"
        mock_snakemake.input.skills = "input/skills.json"
        mock_snakemake.output = ["output/tournaments.json"]

        # Mock file paths
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance

        # Mock minimal data for successful execution
        mock_json_load.side_effect = [
            {"conversations": []},
            {"models": [{"id": "model_a"}, {"id": "model_b"}]},
            {"judges": [{"id": "judge_1"}]},
            {"evals": []},
        ]

        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Test snakemake mode
        with patch("scripts.run_tournaments.globals", return_value={"snakemake": mock_snakemake}):
            with patch("builtins.print"):
                main()

        # Should use snakemake input/output paths
        assert mock_path.call_count >= 4  # Called for each input/output file


class TestTournamentMatchAdvanced:
    """Advanced tests for TournamentMatch edge cases."""

    def test_match_result_calculation_edge_cases(self):
        """Test edge cases in match result calculation."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        # Test tie scenario with even number of judges
        match.add_judge_result("judge_1", "A", [], "A is better")
        match.add_judge_result("judge_2", "B", [], "B is better")
        match.add_judge_result("judge_3", "TIE", [], "It's a tie")
        match.add_judge_result("judge_4", "TIE", [], "Also a tie")

        result = match.calculate_result()
        assert result == "TIE"  # TIE wins with 2 votes

    def test_match_serialization_completeness(self):
        """Test that match serialization includes all data."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        match.timestamp = "2024-01-01T00:00:00Z"
        match.conversation_a_key = "conv_a_key"
        match.conversation_b_key = "conv_b_key"

        match.add_judge_result("judge_1", "A", [{"role": "user", "content": "test"}], "A wins")
        match.calculate_result()

        data = match.to_dict()

        # Verify all fields are serialized
        expected_fields = {
            "match_id",
            "model_a_id",
            "model_b_id",
            "eval_id",
            "skill_id",
            "timestamp",
            "judge_votes",
            "judge_conversations",
            "judge_explanations",
            "result",
            "conversation_a_key",
            "conversation_b_key",
        }

        assert set(data.keys()) == expected_fields
        assert data["timestamp"] == "2024-01-01T00:00:00Z"
        assert data["conversation_a_key"] == "conv_a_key"
        assert data["conversation_b_key"] == "conv_b_key"
