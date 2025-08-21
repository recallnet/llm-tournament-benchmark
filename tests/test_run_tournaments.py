"""Tests for tournament runner."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.run_tournaments import JudgeExecutor, SwissTournament, TournamentMatch


class TestTournamentMatch:
    """Test cases for TournamentMatch class."""

    def test_match_id_generation_deterministic(self) -> None:
        """Test that match IDs are generated deterministically."""
        match1 = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        match2 = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        assert match1.match_id == match2.match_id

    def test_match_id_generation_order_independent(self) -> None:
        """Test that match ID is the same regardless of model order."""
        match1 = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        match2 = TournamentMatch("model_b", "model_a", "eval_1", "skill_1")

        assert match1.match_id == match2.match_id

    def test_match_id_generation_unique_for_different_inputs(self) -> None:
        """Test that different inputs produce different match IDs."""
        match1 = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        match2 = TournamentMatch("model_a", "model_c", "eval_1", "skill_1")
        match3 = TournamentMatch("model_a", "model_b", "eval_2", "skill_1")
        match4 = TournamentMatch("model_a", "model_b", "eval_1", "skill_2")

        ids = {match1.match_id, match2.match_id, match3.match_id, match4.match_id}
        assert len(ids) == 4  # All unique

    def test_add_judge_result_valid_vote(self) -> None:
        """Test adding a valid judge result."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        match.add_judge_result("judge_1", "A", [{"role": "user", "content": "test"}], "Model A is better")

        assert match.judge_votes["judge_1"] == "A"
        assert match.judge_explanations["judge_1"] == "Model A is better"
        assert len(match.judge_conversations["judge_1"]) == 1

    def test_add_judge_result_invalid_vote(self) -> None:
        """Test that invalid votes raise ValueError."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        with pytest.raises(ValueError, match="Invalid vote"):
            match.add_judge_result("judge_1", "INVALID", [], "")

    def test_calculate_result_clear_winner(self) -> None:
        """Test result calculation with clear winner."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        match.add_judge_result("judge_1", "A", [], "")
        match.add_judge_result("judge_2", "A", [], "")
        match.add_judge_result("judge_3", "B", [], "")

        result = match.calculate_result()
        assert result == "A"
        assert match.result == "A"

    def test_calculate_result_tie_in_voting(self) -> None:
        """Test result calculation when judges tie."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        match.add_judge_result("judge_1", "A", [], "")
        match.add_judge_result("judge_2", "B", [], "")

        result = match.calculate_result()
        assert result == "TIE"
        assert match.result == "TIE"

    def test_calculate_result_no_votes(self) -> None:
        """Test that calculating result with no votes raises error."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

        with pytest.raises(ValueError, match="No judge votes available"):
            match.calculate_result()

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        match.timestamp = "2024-01-01T00:00:00"
        match.add_judge_result("judge_1", "A", [{"role": "user", "content": "test"}], "Model A wins")
        match.calculate_result()

        result_dict = match.to_dict()

        assert result_dict["match_id"] == match.match_id
        assert result_dict["model_a_id"] == "model_a"
        assert result_dict["model_b_id"] == "model_b"
        assert result_dict["eval_id"] == "eval_1"
        assert result_dict["skill_id"] == "skill_1"
        assert result_dict["timestamp"] == "2024-01-01T00:00:00"
        assert result_dict["result"] == "A"


class TestSwissTournament:
    """Test cases for SwissTournament class."""

    @pytest.fixture
    def sample_models(self) -> list[dict[str, str]]:
        """Sample models for testing."""
        return [
            {"id": "model_1", "author": "OpenAI"},
            {"id": "model_2", "author": "Anthropic"},
            {"id": "model_3", "author": "Google"},
            {"id": "model_4", "author": "Meta"},
        ]

    @pytest.fixture
    def tournament(self, sample_models: list[dict[str, str]]) -> SwissTournament:
        """Create a SwissTournament instance."""
        return SwissTournament("skill_1", "eval_1", sample_models)

    def test_tournament_id_generation(self, sample_models: list[dict[str, str]]) -> None:
        """Test tournament ID generation."""
        tournament1 = SwissTournament("skill_1", "eval_1", sample_models)
        tournament2 = SwissTournament("skill_1", "eval_1", sample_models)

        assert tournament1.tournament_id == tournament2.tournament_id

    def test_tournament_id_uniqueness(self, sample_models: list[dict[str, str]]) -> None:
        """Test that different tournaments have unique IDs."""
        tournament1 = SwissTournament("skill_1", "eval_1", sample_models)
        tournament2 = SwissTournament("skill_2", "eval_1", sample_models)
        tournament3 = SwissTournament("skill_1", "eval_2", sample_models)

        ids = {tournament1.tournament_id, tournament2.tournament_id, tournament3.tournament_id}
        assert len(ids) == 3

    def test_calculate_rounds_needed(self, sample_models: list[dict[str, str]]) -> None:
        """Test calculation of required rounds."""
        tournament = SwissTournament("skill_1", "eval_1", sample_models)
        rounds_needed = tournament._calculate_rounds_needed()

        # For 4 models, should be 3 rounds (min(4-1, max(3, ceil(log2(4)))))
        assert rounds_needed == 3

    def test_calculate_rounds_needed_two_models(self) -> None:
        """Test rounds calculation with minimum models."""
        models = [{"id": "model_1"}, {"id": "model_2"}]
        tournament = SwissTournament("skill_1", "eval_1", models)

        rounds_needed = tournament._calculate_rounds_needed()
        assert rounds_needed == 1

    def test_get_pairings_first_round_random(self, tournament: SwissTournament) -> None:
        """Test that first round pairings are random."""
        pairings = tournament._get_pairings_for_round(0)

        assert len(pairings) == 2  # 4 models = 2 pairings

        # Check all models are paired
        paired_models = set()
        for model_a, model_b in pairings:
            paired_models.add(model_a)
            paired_models.add(model_b)

        assert len(paired_models) == 4

    def test_get_pairings_subsequent_rounds_by_score(self, tournament: SwissTournament) -> None:
        """Test that subsequent rounds pair by score."""
        # Set up scores (model_1 and model_2 should be paired as top scorers)
        tournament.scores = {"model_1": 2.0, "model_2": 2.0, "model_3": 1.0, "model_4": 0.0}

        pairings = tournament._get_pairings_for_round(1)

        # Should pair high scorers together and low scorers together
        assert len(pairings) == 2

        # Check that we avoid any previous matchups (none in this case)
        paired_models = set()
        for model_a, model_b in pairings:
            paired_models.add(model_a)
            paired_models.add(model_b)

        assert len(paired_models) == 4

    def test_update_scores_model_a_wins(self, tournament: SwissTournament) -> None:
        """Test score updates when model A wins."""
        match = TournamentMatch("model_1", "model_2", "eval_1", "skill_1")
        match.result = "A"

        initial_score_1 = tournament.scores["model_1"]
        initial_score_2 = tournament.scores["model_2"]

        tournament.update_scores(match)

        assert tournament.scores["model_1"] == initial_score_1 + 1.0
        assert tournament.scores["model_2"] == initial_score_2

    def test_update_scores_model_b_wins(self, tournament: SwissTournament) -> None:
        """Test score updates when model B wins."""
        match = TournamentMatch("model_1", "model_2", "eval_1", "skill_1")
        match.result = "B"

        initial_score_1 = tournament.scores["model_1"]
        initial_score_2 = tournament.scores["model_2"]

        tournament.update_scores(match)

        assert tournament.scores["model_1"] == initial_score_1
        assert tournament.scores["model_2"] == initial_score_2 + 1.0

    def test_update_scores_tie(self, tournament: SwissTournament) -> None:
        """Test score updates when match is tied."""
        match = TournamentMatch("model_1", "model_2", "eval_1", "skill_1")
        match.result = "TIE"

        initial_score_1 = tournament.scores["model_1"]
        initial_score_2 = tournament.scores["model_2"]

        tournament.update_scores(match)

        assert tournament.scores["model_1"] == initial_score_1 + 0.5
        assert tournament.scores["model_2"] == initial_score_2 + 0.5

    def test_is_tournament_complete_insufficient_rounds(self, tournament: SwissTournament) -> None:
        """Test tournament completion check with insufficient rounds."""
        # No rounds played yet
        assert not tournament.is_tournament_complete()

    def test_is_tournament_complete_clear_winner(self, tournament: SwissTournament) -> None:
        """Test tournament completion with clear winner."""
        # Simulate enough rounds
        tournament.rounds = [[], [], []]  # 3 rounds (enough for 4 models)

        # Set clear winner
        tournament.scores = {"model_1": 3.0, "model_2": 1.5, "model_3": 1.0, "model_4": 0.5}  # Clear leader

        assert tournament.is_tournament_complete()
        assert tournament.winner == "model_1"

    def test_is_tournament_complete_tied_leaders(self, tournament: SwissTournament) -> None:
        """Test tournament completion with tied leaders."""
        tournament.rounds = [[], [], []]  # Enough rounds

        # Set tied leaders
        tournament.scores = {"model_1": 2.0, "model_2": 2.0, "model_3": 1.0, "model_4": 0.5}  # Tied for lead  # Tied for lead

        # Should not be complete due to tie
        assert not tournament.is_tournament_complete()

    def test_to_dict(self, tournament: SwissTournament) -> None:
        """Test tournament serialization."""
        # Add some sample data
        match = TournamentMatch("model_1", "model_2", "eval_1", "skill_1")
        match.result = "A"
        tournament.rounds = [[match]]
        tournament.update_scores(match)
        tournament.winner = "model_1"
        tournament.completed = True

        result_dict = tournament.to_dict()

        assert result_dict["tournament_id"] == tournament.tournament_id
        assert result_dict["skill_id"] == "skill_1"
        assert result_dict["eval_id"] == "eval_1"
        assert result_dict["model_ids"] == tournament.model_ids
        assert result_dict["completed"] == True
        assert result_dict["winner"] == "model_1"
        assert len(result_dict["rounds"]) == 1
        assert len(result_dict["rounds"][0]) == 1


class TestJudgeExecutor:
    """Test cases for JudgeExecutor class."""

    @pytest.fixture
    def temp_cache_dir(self) -> Path:
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    @pytest.fixture
    def judge_executor(self, temp_cache_dir: Path) -> JudgeExecutor:
        """Create JudgeExecutor instance."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            return JudgeExecutor(cache_dir=temp_cache_dir)

    @pytest.fixture
    def sample_match(self) -> TournamentMatch:
        """Create sample match."""
        return TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

    @pytest.fixture
    def sample_judge(self) -> dict[str, str]:
        """Sample judge data."""
        return {"id": "test_judge", "author": "Test"}

    @pytest.fixture
    def sample_eval_config(self) -> dict[str, str]:
        """Sample evaluation configuration."""
        return {
            "judge": {
                "system": "You are a helpful judge",
                "prompt": "Compare {{A}} and {{B}}",
                "view": {
                    "A": [{"kind": "step", "id": "main", "part": "final"}],
                    "B": [{"kind": "step", "id": "main", "part": "final"}],
                },
            }
        }

    def test_init_requires_api_key(self, temp_cache_dir: Path) -> None:
        """Test that initialization requires API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY not found"):
                JudgeExecutor(cache_dir=temp_cache_dir)

    def test_init_creates_cache_dir(self, temp_cache_dir: Path) -> None:
        """Test that initialization creates cache directory."""
        new_cache_dir = temp_cache_dir / "new_cache"
        assert not new_cache_dir.exists()

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"}):
            JudgeExecutor(cache_dir=new_cache_dir)

        assert new_cache_dir.exists()

    def test_generate_judge_cache_key_consistent(
        self, judge_executor: JudgeExecutor, sample_match: TournamentMatch, sample_eval_config: dict[str, str]
    ) -> None:
        """Test that cache key generation is consistent."""
        final_prompt = "Test prompt"
        judge_id = "test_judge"

        key1 = judge_executor._generate_judge_cache_key_with_prompt(sample_match, judge_id, final_prompt, sample_eval_config)
        key2 = judge_executor._generate_judge_cache_key_with_prompt(sample_match, judge_id, final_prompt, sample_eval_config)

        assert key1 == key2
        assert len(key1) == 16

    def test_get_judge_cache_path(self, judge_executor: JudgeExecutor, sample_match: TournamentMatch) -> None:
        """Test judge cache path generation."""
        judge_id = "test/judge:1"  # With special characters
        cache_key = "abc123"

        path = judge_executor._get_judge_cache_path(sample_match, judge_id, cache_key)

        # Should sanitize judge ID
        expected_filename = f"{sample_match.match_id}_test_judge_1_{cache_key}.json"
        assert path.name == expected_filename
        assert path.parent == judge_executor.cache_dir / sample_match.skill_id

    def test_parse_judge_vote_explicit_format(self, judge_executor: JudgeExecutor) -> None:
        """Test parsing explicit vote format."""
        assert judge_executor._parse_judge_vote("MY VOTE IS FOR: A") == "A"
        assert judge_executor._parse_judge_vote("MY VOTE IS FOR: B") == "B"
        assert judge_executor._parse_judge_vote("MY VOTE IS FOR: TIE") == "TIE"

    def test_parse_judge_vote_case_insensitive(self, judge_executor: JudgeExecutor) -> None:
        """Test that vote parsing is case insensitive."""
        assert judge_executor._parse_judge_vote("my vote is for: a") == "A"
        assert judge_executor._parse_judge_vote("My Vote Is For: b") == "B"

    def test_parse_judge_vote_fallback_patterns(self, judge_executor: JudgeExecutor) -> None:
        """Test fallback vote parsing patterns."""
        assert judge_executor._parse_judge_vote("I choose A") == "A"
        assert judge_executor._parse_judge_vote("Option B is better") == "B"
        assert judge_executor._parse_judge_vote("It's a tie between them") == "TIE"

    def test_parse_judge_vote_default_tie(self, judge_executor: JudgeExecutor) -> None:
        """Test that unclear responses default to TIE."""
        assert judge_executor._parse_judge_vote("This is unclear") == "TIE"
        assert judge_executor._parse_judge_vote("") == "TIE"

    def test_cleanup_invalid_match_cache(self, judge_executor: JudgeExecutor, temp_cache_dir: Path) -> None:
        """Test cleanup of invalid match cache files."""
        # Create skill directory
        skill_dir = temp_cache_dir / "skill_1"
        skill_dir.mkdir()

        # Create valid cache file
        valid_cache = {
            "vote": "A",
            "metadata": {
                "model_a_id": "model_a",
                "model_b_id": "model_b",
                "judge_id": "judge_1",
                "eval_id": "eval_1",
                "skill_id": "skill_1",
            },
        }
        valid_file = skill_dir / "valid_cache.json"
        with open(valid_file, "w") as f:
            json.dump(valid_cache, f)

        # Create invalid cache file (references non-existent model)
        invalid_cache = {
            "vote": "A",
            "metadata": {
                "model_a_id": "nonexistent_model",
                "model_b_id": "model_b",
                "judge_id": "judge_1",
                "eval_id": "eval_1",
                "skill_id": "skill_1",
            },
        }
        invalid_file = skill_dir / "invalid_cache.json"
        with open(invalid_file, "w") as f:
            json.dump(invalid_cache, f)

        # Define current entities
        models = [{"id": "model_a"}, {"id": "model_b"}]
        judges = [{"id": "judge_1"}]
        evals = [{"id": "eval_1", "_metadata": {"skill": "skill_1"}}]

        assert valid_file.exists()
        assert invalid_file.exists()

        judge_executor.cleanup_invalid_match_cache(models, judges, evals)

        assert valid_file.exists()  # Should remain
        assert not invalid_file.exists()  # Should be removed
