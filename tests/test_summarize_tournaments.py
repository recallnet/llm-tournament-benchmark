"""Tests for tournament summarizer."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.summarize_tournaments import calculate_match_result, create_tournament_summary, load_judge_cache_files, main


class TestTournamentSummarizer:
    """Test cases for tournament summarization functions."""

    @pytest.fixture
    def temp_tournaments_dir(self) -> Path:
        """Create a temporary tournaments directory with sample data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tournaments_dir = Path(tmp_dir)

            # Create skill directories
            skill1_dir = tournaments_dir / "skill_1"
            skill1_dir.mkdir()

            # Create sample judge cache files
            judge_data_1 = {
                "vote": "A",
                "conversation": [{"role": "user", "content": "test"}],
                "explanation": "Model A is better",
                "metadata": {
                    "match_id": "match_1",
                    "judge_id": "judge_1",
                    "model_a_id": "model_a",
                    "model_b_id": "model_b",
                    "eval_id": "eval_1",
                    "skill_id": "skill_1",
                    "timestamp": "2024-01-01T00:00:00",
                },
            }

            judge_data_2 = {
                "vote": "A",
                "conversation": [{"role": "user", "content": "test"}],
                "explanation": "Model A is clearly superior",
                "metadata": {
                    "match_id": "match_1",
                    "judge_id": "judge_2",
                    "model_a_id": "model_a",
                    "model_b_id": "model_b",
                    "eval_id": "eval_1",
                    "skill_id": "skill_1",
                    "timestamp": "2024-01-01T00:00:00",
                },
            }

            # Save cache files
            with open(skill1_dir / "match_1_judge_1_cache.json", "w") as f:
                json.dump(judge_data_1, f)
            with open(skill1_dir / "match_1_judge_2_cache.json", "w") as f:
                json.dump(judge_data_2, f)

            yield tournaments_dir

    @pytest.fixture
    def sample_judge_votes(self) -> list[dict[str, str]]:
        """Sample judge votes for testing."""
        return [
            {"vote": "A", "metadata": {"judge_id": "judge_1"}},
            {"vote": "A", "metadata": {"judge_id": "judge_2"}},
            {"vote": "B", "metadata": {"judge_id": "judge_3"}},
        ]

    @pytest.fixture
    def sample_tie_votes(self) -> list[dict[str, str]]:
        """Sample tied judge votes."""
        return [
            {"vote": "A", "metadata": {"judge_id": "judge_1"}},
            {"vote": "B", "metadata": {"judge_id": "judge_2"}},
            {"vote": "TIE", "metadata": {"judge_id": "judge_3"}},
        ]

    def test_load_judge_cache_files_empty_dir(self) -> None:
        """Test loading from empty directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            empty_dir = Path(tmp_dir)
            result = load_judge_cache_files(empty_dir)
            assert result == {}

    def test_load_judge_cache_files_nonexistent_dir(self) -> None:
        """Test loading from non-existent directory."""
        result = load_judge_cache_files(Path("/non/existent/path"))
        assert result == {}

    def test_load_judge_cache_files_valid_data(self, temp_tournaments_dir: Path) -> None:
        """Test loading valid cache files."""
        result = load_judge_cache_files(temp_tournaments_dir)

        assert "match_1" in result
        assert len(result["match_1"]) == 2

        # Check that both judge votes are loaded
        judge_ids = [vote["metadata"]["judge_id"] for vote in result["match_1"]]
        assert "judge_1" in judge_ids
        assert "judge_2" in judge_ids

    def test_calculate_match_result_clear_winner(self, sample_judge_votes: list[dict[str, str]]) -> None:
        """Test match result calculation with clear winner."""
        result, vote_counts, judge_details = calculate_match_result(sample_judge_votes)

        assert result == "A"  # 2-1 in favor of A
        assert vote_counts == {"A": 2, "B": 1, "TIE": 0}
        assert len(judge_details) == 3

        # Check judge details structure
        for judge_detail in judge_details:
            assert "judge_id" in judge_detail
            assert "vote" in judge_detail

    def test_calculate_match_result_tie(self, sample_tie_votes: list[dict[str, str]]) -> None:
        """Test match result calculation with no clear winner."""
        result, vote_counts, judge_details = calculate_match_result(sample_tie_votes)

        assert result == "TIE"  # No clear majority
        assert vote_counts == {"A": 1, "B": 1, "TIE": 1}

    def test_calculate_match_result_empty_votes(self) -> None:
        """Test match result calculation with no votes."""
        result, vote_counts, judge_details = calculate_match_result([])

        assert result == "TIE"  # Default when no votes
        assert vote_counts == {"A": 0, "B": 0, "TIE": 0}
        assert judge_details == []

    def test_calculate_match_result_invalid_vote(self) -> None:
        """Test handling of invalid vote values."""
        invalid_votes = [
            {"vote": "INVALID", "metadata": {"judge_id": "judge_1"}},
            {"vote": "A", "metadata": {"judge_id": "judge_2"}},
        ]

        result, vote_counts, judge_details = calculate_match_result(invalid_votes)

        # Invalid vote should be converted to TIE
        assert vote_counts["TIE"] == 1
        assert vote_counts["A"] == 1
        assert judge_details[0]["vote"] == "TIE"  # Invalid vote converted

    def test_create_tournament_summary_empty_matches(self) -> None:
        """Test tournament summary creation with no matches."""
        result = create_tournament_summary({})
        assert result == {}

    def test_create_tournament_summary_single_match(self) -> None:
        """Test tournament summary with single match."""
        matches = {
            "match_1": [
                {
                    "vote": "A",
                    "metadata": {
                        "judge_id": "judge_1",
                        "match_id": "match_1",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "model_a_id": "model_a",
                        "model_b_id": "model_b",
                        "timestamp": "2024-01-01T00:00:00",
                    },
                }
            ]
        }

        result = create_tournament_summary(matches)

        assert "skill_1" in result
        skill_data = result["skill_1"]

        assert skill_data["skill_id"] == "skill_1"
        assert skill_data["total_matches"] == 1
        assert len(skill_data["model_rankings"]) == 2  # Both models get ranked
        assert "eval_1" in skill_data["evals"]

        # Check match history is included
        assert len(skill_data["match_history"]) == 1
        assert skill_data["match_history"][0]["match_id"] == "match_1"

    def test_create_tournament_summary_model_scoring(self) -> None:
        """Test that model scoring is calculated correctly."""
        matches = {
            "match_1": [
                {
                    "vote": "A",
                    "metadata": {
                        "judge_id": "judge_1",
                        "match_id": "match_1",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "model_a_id": "model_a",
                        "model_b_id": "model_b",
                        "timestamp": "2024-01-01T00:00:00",
                    },
                }
            ],
            "match_2": [
                {
                    "vote": "TIE",
                    "metadata": {
                        "judge_id": "judge_1",
                        "match_id": "match_2",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "model_a_id": "model_a",
                        "model_b_id": "model_c",
                        "timestamp": "2024-01-01T01:00:00",
                    },
                }
            ],
        }

        result = create_tournament_summary(matches)
        skill_data = result["skill_1"]

        # Find model_a in rankings
        model_a_ranking = next(r for r in skill_data["model_rankings"] if r["model_id"] == "model_a")

        assert model_a_ranking["wins"] == 1
        assert model_a_ranking["ties"] == 1
        assert model_a_ranking["losses"] == 0
        assert model_a_ranking["total_matches"] == 2
        assert model_a_ranking["points"] == 1.5  # 1 win + 0.5 tie

    def test_create_tournament_summary_ranking_order(self) -> None:
        """Test that model rankings are in correct order."""
        matches = {
            "match_1": [  # model_a beats model_b
                {
                    "vote": "A",
                    "metadata": {
                        "judge_id": "judge_1",
                        "match_id": "match_1",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "model_a_id": "model_a",
                        "model_b_id": "model_b",
                        "timestamp": "2024-01-01T00:00:00",
                    },
                }
            ],
            "match_2": [  # model_b beats model_c
                {
                    "vote": "A",
                    "metadata": {
                        "judge_id": "judge_1",
                        "match_id": "match_2",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "model_a_id": "model_b",
                        "model_b_id": "model_c",
                        "timestamp": "2024-01-01T01:00:00",
                    },
                }
            ],
        }

        result = create_tournament_summary(matches)
        rankings = result["skill_1"]["model_rankings"]

        # Rankings should be ordered by points (descending)
        for i in range(len(rankings) - 1):
            assert rankings[i]["points"] >= rankings[i + 1]["points"]

        # Check rank assignment
        for i, ranking in enumerate(rankings):
            assert ranking["rank"] == i + 1

    def test_create_tournament_summary_chronological_order(self) -> None:
        """Test that match history is in chronological order."""
        matches = {
            "match_1": [
                {
                    "vote": "A",
                    "metadata": {
                        "judge_id": "judge_1",
                        "match_id": "match_1",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "model_a_id": "model_a",
                        "model_b_id": "model_b",
                        "timestamp": "2024-01-01T02:00:00",  # Later timestamp
                    },
                }
            ],
            "match_2": [
                {
                    "vote": "B",
                    "metadata": {
                        "judge_id": "judge_1",
                        "match_id": "match_2",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "model_a_id": "model_a",
                        "model_b_id": "model_c",
                        "timestamp": "2024-01-01T01:00:00",  # Earlier timestamp
                    },
                }
            ],
        }

        result = create_tournament_summary(matches)
        match_history = result["skill_1"]["match_history"]

        # Should be ordered chronologically (earliest first)
        assert match_history[0]["match_id"] == "match_2"
        assert match_history[1]["match_id"] == "match_1"

    @patch("scripts.summarize_tournaments.Path")
    @patch("builtins.open")
    @patch("json.dump")
    def test_main_no_tournament_data(self, mock_dump, mock_open, mock_path) -> None:
        """Test main function when no tournament data exists."""
        mock_path.return_value.exists.return_value = False

        main()

        # Check that appropriate result is saved
        mock_dump.assert_called_once()
        result = mock_dump.call_args[0][0]
        assert result["execution_info"]["status"] == "no_tournament_data"

    @patch("scripts.summarize_tournaments.load_judge_cache_files")
    @patch("scripts.summarize_tournaments.Path")
    @patch("builtins.open")
    @patch("json.dump")
    def test_main_no_valid_matches(self, mock_dump, mock_open, mock_path, mock_load) -> None:
        """Test main function when no valid matches found."""
        mock_path.return_value.exists.return_value = True
        mock_load.return_value = {}  # No matches

        main()

        mock_dump.assert_called_once()
        result = mock_dump.call_args[0][0]
        assert result["execution_info"]["status"] == "no_valid_matches"
