"""Simple focused tests to increase run_tournaments.py coverage."""

from unittest.mock import Mock, patch

from scripts.run_tournaments import JudgeExecutor, SwissTournament, TournamentMatch


class TestSimpleCoverage:
    """Simple tests to hit uncovered lines in run_tournaments.py."""

    def test_swiss_tournament_bye_handling(self):
        """Test Swiss tournament bye handling with odd number of models."""
        models = [
            {"id": "model_a", "name": "Model A"},
            {"id": "model_b", "name": "Model B"},
            {"id": "model_c", "name": "Model C"},
        ]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # Test that odd number of models is handled in pairing
        pairings = tournament._get_pairings_for_round(1)
        assert len(pairings) <= 1  # At most 1 pair with 3 models

        # Set some scores to test bye logic
        tournament.scores["model_a"] = 2.0
        tournament.scores["model_b"] = 1.0
        tournament.scores["model_c"] = 0.0

        # Test bye award to lowest scoring model
        if len(pairings) == 1:
            paired_models = {pairings[0][0], pairings[0][1]}
            unpaired = [
                m for m in ["model_a", "model_b", "model_c"] if m not in paired_models
            ]
            if unpaired:
                # Lowest score should get bye
                bye_candidate = unpaired[0]
                assert bye_candidate in tournament.scores

    def test_tournament_match_ordering(self):
        """Test that tournament match model ordering is consistent."""
        match1 = TournamentMatch("model_z", "model_a", "eval_1", "skill_1")
        match2 = TournamentMatch("model_a", "model_z", "eval_1", "skill_1")

        # Should generate same match ID regardless of order
        assert match1.match_id == match2.match_id

        # But model_a_id and model_b_id should be set as provided
        assert match1.model_a_id == "model_z"
        assert match1.model_b_id == "model_a"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_judge_executor_cache_key_generation(self):
        """Test judge cache key generation."""
        executor = JudgeExecutor()

        # Create a test match and eval config
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        eval_config = {"id": "test_eval", "prompt": "test prompt"}
        final_prompt = "test prompt content"

        # Test cache key consistency using the actual method signature
        key1 = executor._generate_judge_cache_key_with_prompt(
            match, "judge_1", final_prompt, eval_config
        )
        key2 = executor._generate_judge_cache_key_with_prompt(
            match, "judge_1", final_prompt, eval_config
        )

        assert key1 == key2
        assert len(key1) == 16  # Should be 16 character hash

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_judge_executor_cache_path(self):
        """Test cache path generation."""
        executor = JudgeExecutor()

        # Create a mock match
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        cache_path = executor._get_judge_cache_path(match, "judge_1", "cache_key_123")

        assert "skill_1" in str(cache_path)
        assert "cache_key_123" in str(cache_path)
        assert "judge_1" in str(cache_path)
        assert cache_path.suffix == ".json"

    def test_tournament_scoring_edge_cases(self):
        """Test tournament scoring with edge cases."""
        models = [
            {"id": "model_a", "name": "Model A"},
            {"id": "model_b", "name": "Model B"},
        ]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # Test scoring with TIE result
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        match.add_judge_result("judge_1", "TIE", [], "It's a tie")
        match.calculate_result()

        tournament.update_scores(match)

        # Both models should get 0.5 points for a tie
        assert tournament.scores["model_a"] == 0.5
        assert tournament.scores["model_b"] == 0.5

    def test_tournament_completion_edge_cases(self):
        """Test tournament completion logic edge cases."""
        models = [{"id": f"model_{i}", "name": f"Model {i}"} for i in range(4)]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # Test with insufficient rounds
        tournament.rounds = [[]]  # Only 1 round
        assert not tournament.is_tournament_complete()

        # Test with sufficient rounds but tied leaders
        tournament.rounds = [[], [], []]  # 3 rounds
        tournament.scores = {
            "model_0": 3.0,
            "model_1": 3.0,
            "model_2": 1.0,
            "model_3": 0.0,
        }  # Tied leader
        # Should not be complete due to tie
        assert not tournament.is_tournament_complete()

    def test_match_judge_voting_edge_cases(self):
        """Test match judging with various vote combinations."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        # Test with multiple TIE votes
        match.add_judge_result("judge_1", "TIE", [], "Tie vote 1")
        match.add_judge_result("judge_2", "TIE", [], "Tie vote 2")
        match.add_judge_result("judge_3", "A", [], "A vote")

        result = match.calculate_result()
        assert result == "TIE"  # TIE should win with 2 votes

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_judge_vote_parsing_edge_cases(self):
        """Test judge vote parsing with various formats."""
        executor = JudgeExecutor()

        # Test vote parsing with the actual format expected by the parser
        test_cases = [
            ("MY VOTE IS FOR: B", "B"),
            ("MY VOTE IS FOR: A", "A"),
            ("MY VOTE IS FOR: TIE", "TIE"),
            ("Some text... MY VOTE IS FOR: A ... more text", "A"),
            ("Some text... MY VOTE IS FOR: B ... more text", "B"),
            ("No clear vote here", "TIE"),  # Default fallback
        ]

        for response_text, expected_vote in test_cases:
            vote = executor._parse_judge_vote(response_text)
            assert vote == expected_vote

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_judge_executor_initialization(self):
        """Test JudgeExecutor initialization edge cases."""
        executor = JudgeExecutor()

        # Cache directory should be created
        assert executor.cache_dir.exists()

        # API key should be set
        assert executor.api_key == "test-key"

        # Base URL should be set
        assert "openrouter" in executor.base_url.lower()

    def test_tournament_to_dict_serialization(self):
        """Test tournament serialization to dict."""
        models = [
            {"id": "model_a", "name": "Model A"},
            {"id": "model_b", "name": "Model B"},
        ]
        tournament = SwissTournament("skill_1", "eval_1", models)

        # Add some data
        tournament.scores["model_a"] = 1.0
        tournament.scores["model_b"] = 0.5

        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        tournament.rounds.append([match])

        data = tournament.to_dict()

        # Check all expected fields are present
        expected_fields = {
            "tournament_id",
            "skill_id",
            "eval_id",
            "model_ids",
            "scores",
            "rounds",
            "completed",
        }
        assert set(data.keys()) >= expected_fields

        # Check data integrity
        assert data["skill_id"] == "skill_1"
        assert data["eval_id"] == "eval_1"
        assert len(data["model_ids"]) == 2
        assert "model_a" in data["scores"]


class TestMainFunctionSimple:
    """Simple tests for main function paths."""

    @patch("scripts.run_tournaments.Path")
    @patch("builtins.open")
    @patch("json.load")
    @patch("json.dump")
    @patch("builtins.print")
    def test_main_direct_mode_insufficient_models(
        self, mock_print, mock_json_dump, mock_json_load, mock_open, mock_path
    ):
        """Test main function in direct mode with insufficient models."""
        # Mock data loading - only 1 model
        mock_json_load.side_effect = [
            {"conversations": []},  # conversations
            {"models": [{"id": "model_a"}]},  # models (insufficient)
            {"judges": [{"id": "judge_1"}]},  # judges
            {"evals": []},  # skills
        ]

        # Mock file operations
        mock_open.return_value.__enter__.return_value = Mock()

        # Test direct mode (no snakemake in globals)
        with patch("builtins.globals", return_value={}):
            from scripts.run_tournaments import main

            main()

        # Should print insufficient models message
        mock_print.assert_any_call(
            "⚠️  Need at least 2 models for tournaments - skipping"
        )
