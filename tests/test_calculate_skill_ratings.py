"""Tests for skill rating calculator."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.calculate_skill_ratings import DEFAULT_MU, DEFAULT_SIGMA, SkillRatingCalculator


class TestSkillRatingCalculator:
    """Test cases for SkillRatingCalculator class."""

    @pytest.fixture
    def temp_cache_dir(self) -> Path:
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    @pytest.fixture
    def calculator(self, temp_cache_dir: Path) -> SkillRatingCalculator:
        """Create a SkillRatingCalculator instance."""
        return SkillRatingCalculator(cache_dir=temp_cache_dir)

    @pytest.fixture
    def sample_models(self) -> list[dict[str, str]]:
        """Sample model data."""
        return [
            {"id": "model_a", "author": "OpenAI"},
            {"id": "model_b", "author": "Anthropic"},
            {"id": "model_c", "author": "Google"},
        ]

    @pytest.fixture
    def sample_judges(self) -> list[dict[str, str]]:
        """Sample judge data."""
        return [
            {"id": "judge_1", "author": "OpenAI"},
            {"id": "judge_2", "author": "Anthropic"},
        ]

    @pytest.fixture
    def sample_evals(self) -> list[dict[str, str]]:
        """Sample evaluation data."""
        return [
            {"id": "eval_1", "_metadata": {"skill": "skill_1"}},
            {"id": "eval_2", "_metadata": {"skill": "skill_1"}},
        ]

    @pytest.fixture
    def sample_tournament_data(self) -> dict[str, list[dict[str, str]]]:
        """Sample tournament match history."""
        return {
            "match_history": [
                {
                    "match_id": "match_1",
                    "model_a": "model_a",
                    "model_b": "model_b",
                    "winner": "A",
                    "timestamp": "2024-01-01T00:00:00",
                },
                {
                    "match_id": "match_2",
                    "model_a": "model_b",
                    "model_b": "model_c",
                    "winner": "B",
                    "timestamp": "2024-01-01T01:00:00",
                },
                {
                    "match_id": "match_3",
                    "model_a": "model_a",
                    "model_b": "model_c",
                    "winner": "TIE",
                    "timestamp": "2024-01-01T02:00:00",
                },
            ]
        }

    def test_init_creates_cache_dir(self) -> None:
        """Test that initialization creates cache directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "new_cache"
            assert not cache_dir.exists()
            SkillRatingCalculator(cache_dir=cache_dir)
            assert cache_dir.exists()

    def test_create_rating_defaults(self, calculator: SkillRatingCalculator) -> None:
        """Test creating rating with default values."""
        rating = calculator._create_rating()
        assert rating.mu == DEFAULT_MU
        assert rating.sigma == DEFAULT_SIGMA

    def test_create_rating_custom(self, calculator: SkillRatingCalculator) -> None:
        """Test creating rating with custom values."""
        custom_mu = 1600.0
        custom_sigma = 120.0
        rating = calculator._create_rating(mu=custom_mu, sigma=custom_sigma)
        assert rating.mu == custom_mu
        assert rating.sigma == custom_sigma

    def test_generate_cache_key_consistent(
        self,
        calculator: SkillRatingCalculator,
        sample_models: list[dict[str, str]],
        sample_judges: list[dict[str, str]],
        sample_evals: list[dict[str, str]],
    ) -> None:
        """Test that cache key generation is consistent."""
        tournament_data = {"skill_1": {"match_history": []}}

        key1 = calculator._generate_cache_key(sample_models, sample_judges, sample_evals, tournament_data)
        key2 = calculator._generate_cache_key(sample_models, sample_judges, sample_evals, tournament_data)

        assert key1 == key2
        assert len(key1) == 16  # CACHE_KEY_LENGTH

    def test_generate_cache_key_changes_with_data(
        self,
        calculator: SkillRatingCalculator,
        sample_models: list[dict[str, str]],
        sample_judges: list[dict[str, str]],
        sample_evals: list[dict[str, str]],
    ) -> None:
        """Test that cache key changes when data changes."""
        tournament_data1 = {"skill_1": {"match_history": []}}
        tournament_data2 = {
            "skill_1": {"match_history": [{"match_id": "test", "winner": "A", "timestamp": "2024-01-01T00:00:00"}]}
        }

        key1 = calculator._generate_cache_key(sample_models, sample_judges, sample_evals, tournament_data1)
        key2 = calculator._generate_cache_key(sample_models, sample_judges, sample_evals, tournament_data2)

        assert key1 != key2

    def test_get_cache_path(self, calculator: SkillRatingCalculator) -> None:
        """Test cache path generation."""
        skill_id = "test_skill"
        cache_key = "abc123"

        path = calculator._get_cache_path(skill_id, cache_key)

        assert path.name == f"{skill_id}_{cache_key}.json"
        assert path.parent == calculator.cache_dir

    def test_calculate_skill_ratings_no_matches(self, calculator: SkillRatingCalculator) -> None:
        """Test rating calculation with no matches."""
        tournament_data = {"match_history": []}

        result = calculator.calculate_skill_ratings("test_skill", tournament_data, "test_key")

        assert result["skill_id"] == "test_skill"
        assert result["total_matches"] == 0
        assert result["model_ratings"] == {}
        assert result["model_rankings"] == []

    def test_calculate_skill_ratings_basic(
        self, calculator: SkillRatingCalculator, sample_tournament_data: dict[str, list[dict[str, str]]]
    ) -> None:
        """Test basic rating calculation."""
        result = calculator.calculate_skill_ratings("test_skill", sample_tournament_data, "test_key")

        assert result["skill_id"] == "test_skill"
        assert result["total_matches"] == 3
        assert len(result["model_ratings"]) == 3
        assert len(result["model_rankings"]) == 3

        # Check that rankings are ordered by rating (descending)
        rankings = result["model_rankings"]
        for i in range(len(rankings) - 1):
            assert rankings[i]["rating"] >= rankings[i + 1]["rating"]

        # Check that ranks are assigned correctly
        for i, model in enumerate(rankings):
            assert model["rank"] == i + 1

    def test_calculate_skill_ratings_caching(
        self, calculator: SkillRatingCalculator, sample_tournament_data: dict[str, list[dict[str, str]]]
    ) -> None:
        """Test that results are cached correctly."""
        skill_id = "test_skill"
        cache_key = "test_key"

        # First call should calculate
        result1 = calculator.calculate_skill_ratings(skill_id, sample_tournament_data, cache_key)

        # Second call should use cache
        result2 = calculator.calculate_skill_ratings(skill_id, sample_tournament_data, cache_key)

        assert result1 == result2

        # Verify cache file exists
        cache_path = calculator._get_cache_path(skill_id, cache_key)
        assert cache_path.exists()

    def test_cleanup_invalid_rating_cache(
        self,
        calculator: SkillRatingCalculator,
        sample_models: list[dict[str, str]],
        sample_judges: list[dict[str, str]],
        sample_evals: list[dict[str, str]],
    ) -> None:
        """Test cleanup of invalid rating cache."""
        # Create a valid cache file
        cache_data = {
            "skill_id": "skill_1",
            "model_ratings": {"model_a": {"mu": 1500.0, "sigma": 100.0}},
            "model_rankings": [],
            "total_matches": 1,
        }
        cache_file = calculator.cache_dir / "skill_1_test.json"
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Create an invalid cache file (model no longer exists)
        invalid_cache_data = {
            "skill_id": "skill_1",
            "model_ratings": {"invalid_model": {"mu": 1500.0, "sigma": 100.0}},
            "model_rankings": [],
            "total_matches": 1,
        }
        invalid_cache_file = calculator.cache_dir / "skill_1_invalid.json"
        with open(invalid_cache_file, "w") as f:
            json.dump(invalid_cache_data, f)

        assert cache_file.exists()
        assert invalid_cache_file.exists()

        calculator.cleanup_invalid_rating_cache(sample_models, sample_judges, sample_evals)

        assert cache_file.exists()  # Valid cache should remain
        assert not invalid_cache_file.exists()  # Invalid cache should be removed

    def test_match_progression_tracking(
        self, calculator: SkillRatingCalculator, sample_tournament_data: dict[str, list[dict[str, str]]]
    ) -> None:
        """Test that match progression is tracked correctly."""
        result = calculator.calculate_skill_ratings("test_skill", sample_tournament_data, "test_key")

        progression = result["match_progression"]
        assert len(progression) == 3

        # Check that matches are processed in order
        for i, match in enumerate(progression):
            assert match["match_number"] == i + 1
            assert "rating_changes" in match
            assert match["model_a"] in match["rating_changes"]
            assert match["model_b"] in match["rating_changes"]

            # Check rating change structure
            for model_id in [match["model_a"], match["model_b"]]:
                changes = match["rating_changes"][model_id]
                assert "before" in changes
                assert "after" in changes
                assert "mu" in changes["before"]
                assert "sigma" in changes["before"]
                assert "mu" in changes["after"]
                assert "sigma" in changes["after"]

    def test_load_cached_ratings_corrupted_file(self, calculator: SkillRatingCalculator) -> None:
        """Test handling of corrupted cache files."""
        cache_path = calculator.cache_dir / "corrupted.json"

        # Create corrupted JSON file
        with open(cache_path, "w") as f:
            f.write("invalid json content")

        result = calculator._load_cached_ratings(cache_path)
        assert result is None
        assert not cache_path.exists()  # Should be cleaned up

    def test_cleanup_filename_without_underscore(
        self,
        calculator: SkillRatingCalculator,
        sample_models: list[dict[str, str]],
        sample_judges: list[dict[str, str]],
        sample_evals: list[dict[str, str]],
    ) -> None:
        """Test cleanup with filename without underscore."""
        cache_data = {
            "skill_id": "skill1",
            "model_ratings": {"model_a": {"mu": 1500.0, "sigma": 100.0}},
            "model_rankings": [],
            "total_matches": 1,
        }
        cache_file = calculator.cache_dir / "skill1.json"
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Add skill1 to evals so it won't be removed for missing skill
        sample_evals.append({"id": "eval_3", "_metadata": {"skill": "skill1"}})

        calculator.cleanup_invalid_rating_cache(sample_models, sample_judges, sample_evals)

        assert cache_file.exists()  # Should remain since skill1 exists and model_a is valid
