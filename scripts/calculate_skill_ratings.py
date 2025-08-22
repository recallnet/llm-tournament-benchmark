#!/usr/bin/env python3
"""
Skill Rating Calculator - Uses OpenSkill Bradley-Terry ratings for model evaluation.
Processes all matches in chronological order across tournaments to maintain proper rating progression.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from openskill.models import BradleyTerryFull, BradleyTerryFullRating

# Constants to avoid magic numbers
DEFAULT_MU = 1500.0
DEFAULT_SIGMA = 100.0
DEFAULT_TAU = 0.1
CONSERVATIVE_MULTIPLIER = 3  # μ - 3σ for conservative estimate
CACHE_KEY_LENGTH = 16


class SkillRatingCalculator:
    """Calculates and manages model ratings using OpenSkill Bradley-Terry system."""

    def __init__(self, cache_dir: Path) -> None:
        # SAFETY: Cache directory must always be provided by caller to prevent path confusion
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # OpenSkill configuration (Bradley-Terry)
        self.model = BradleyTerryFull()
        self.default_mu = DEFAULT_MU
        self.default_sigma = DEFAULT_SIGMA
        self.default_tau = DEFAULT_TAU

    def _create_rating(
        self, mu: float | None = None, sigma: float | None = None
    ) -> BradleyTerryFullRating:
        """Create an OpenSkill rating object."""
        return BradleyTerryFullRating(
            mu=mu if mu is not None else self.default_mu,
            sigma=sigma if sigma is not None else self.default_sigma,
        )

    def _generate_cache_key(
        self,
        current_models: list[dict[str, Any]],
        current_judges: list[dict[str, Any]],
        current_evals: list[dict[str, Any]],
        tournament_summaries: dict[str, Any],
    ) -> str:
        """Generate cache key based on current state of models, judges, evals, and tournaments."""
        # Create a stable representation of the current state
        model_ids = sorted([model["id"] for model in current_models])
        judge_ids = sorted([judge["id"] for judge in current_judges])
        eval_ids = sorted([eval_data["id"] for eval_data in current_evals])

        # Include tournament match data to detect changes
        tournament_data = {}
        for skill_id, skill_data in tournament_summaries.items():
            matches = skill_data.get("match_history", [])
            # Create hash of all match data (IDs, timestamps, outcomes)
            match_signatures = []
            for match in matches:
                # Validate required fields - throw halting error if missing
                required_fields = ["match_id", "winner", "timestamp"]
                missing_fields = [
                    field for field in required_fields if field not in match
                ]
                if missing_fields:
                    raise ValueError(
                        f"Tournament data integrity error in skill '{skill_id}': Missing required fields {missing_fields} in match: {match}"
                    )

                # Include model participants to prevent cache collisions when models are swapped
                model_a = match.get("model_a", "unknown_a")
                model_b = match.get("model_b", "unknown_b")
                match_sig = f"{match['match_id']}:{model_a}:{model_b}:{match['winner']}:{match['timestamp']}"
                match_signatures.append(match_sig)
            tournament_data[skill_id] = sorted(match_signatures)

        cache_content = {
            "models": model_ids,
            "judges": judge_ids,
            "evals": eval_ids,
            "tournaments": tournament_data,
        }

        return hashlib.sha256(
            json.dumps(cache_content, sort_keys=True).encode()
        ).hexdigest()[:CACHE_KEY_LENGTH]

    def _sanitize_path_component(self, component: str) -> str:
        """Sanitize a path component to prevent directory traversal and other attacks."""
        import re

        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", component)
        # Remove directory traversal sequences
        sanitized = sanitized.replace("..", "_")
        # Limit length to prevent filesystem issues
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        # Ensure it's not empty or just dots/spaces
        if not sanitized or sanitized.strip("._ ") == "":
            sanitized = "invalid_id"
        return sanitized

    def _get_cache_path(self, skill_id: str, cache_key: str) -> Path:
        """Get cache file path for skill ratings."""
        # Sanitize skill_id to prevent directory traversal attacks
        safe_skill_id = self._sanitize_path_component(skill_id)
        return self.cache_dir / f"{safe_skill_id}_{cache_key}.json"

    def _load_cached_ratings(
        self, cache_path: Path
    ) -> tuple[dict[str, Any] | None, bool]:
        """Load cached skill ratings.

        Returns:
            tuple: (cached_data, was_corrupted)
        """
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    return json.load(f), False
            except (OSError, json.JSONDecodeError):
                cache_path.unlink(missing_ok=True)
                return None, True
        return None, False

    def _save_cached_ratings(
        self, cache_path: Path, ratings_data: dict[str, Any]
    ) -> None:
        """Save skill ratings to cache."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(ratings_data, f, indent=2)

    def cleanup_invalid_rating_cache(
        self,
        current_models: list[dict[str, Any]],
        current_judges: list[dict[str, Any]],
        current_evals: list[dict[str, Any]],
    ) -> None:
        """Remove all cached ratings that are no longer valid."""
        # CRITICAL SAFETY: Prevent production data destruction during testing
        try:
            from scripts.safety_guards import (
                check_production_data_access,
                ensure_test_mode_for_cache_operations,
            )
        except ModuleNotFoundError:
            # When running through wrapper, try without the scripts prefix
            from safety_guards import (
                check_production_data_access,
                ensure_test_mode_for_cache_operations,
            )

        ensure_test_mode_for_cache_operations()
        check_production_data_access(self.cache_dir, "rating cache cleanup")
        current_model_ids = {model["id"] for model in current_models}
        {judge["id"] for judge in current_judges}
        {eval_data["id"] for eval_data in current_evals}
        current_skill_ids = {
            eval_data["_metadata"]["skill"] for eval_data in current_evals
        }

        cleaned_count = 0

        print("🧹 Cleaning invalid skill rating cache entries...")

        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                should_remove = False
                remove_reason = ""

                try:
                    # Parse skill from filename (format: skill_id_cache_key.json)
                    filename = cache_file.stem
                    if "_" in filename:
                        parts = filename.split("_")
                        # Assume last part is cache key, everything before is skill_id
                        skill_id = "_".join(parts[:-1])
                    else:
                        skill_id = filename

                    # Check if skill still exists
                    if skill_id not in current_skill_ids:
                        should_remove = True
                        remove_reason = f"skill '{skill_id}' no longer exists"
                    else:
                        # Load cache file to check model references
                        with open(cache_file) as f:
                            cached_data = json.load(f)

                        model_ratings = cached_data.get("model_ratings", {})

                        # Check if any cached models no longer exist
                        for model_id in model_ratings.keys():
                            if model_id not in current_model_ids:
                                should_remove = True
                                remove_reason = (
                                    f"cached model '{model_id}' no longer exists"
                                )
                                break

                except (OSError, json.JSONDecodeError, IndexError):
                    should_remove = True
                    remove_reason = "corrupted cache file"

                if should_remove:
                    print(
                        f"   🗑️  Removing invalid rating cache: {cache_file.name} ({remove_reason})"
                    )
                    cache_file.unlink()
                    cleaned_count += 1

        if cleaned_count > 0:
            print(f"   ✅ Cleaned {cleaned_count} invalid rating cache files")
        else:
            print("   ✅ No invalid rating cache files found")

    def calculate_skill_ratings(
        self, skill_id: str, tournament_data: dict[str, Any], cache_key: str
    ) -> dict[str, Any]:
        """Calculate ratings for a skill using all matches in chronological order."""
        cache_path = self._get_cache_path(skill_id, cache_key)

        # Try to load from cache first
        cached_ratings, was_corrupted = self._load_cached_ratings(cache_path)
        if cached_ratings:
            print(f"    📋 Using cached skill ratings: {skill_id}")
            return cached_ratings

        print(f"    🎯 Calculating skill ratings: {skill_id}")
        if was_corrupted:
            print(
                f"    ⚠️  Corrupted cache detected for {skill_id}, recalculating without saving to cache"
            )

        # Get all matches in chronological order
        match_history = tournament_data.get("match_history", [])

        if not match_history:
            print(f"    ⚠️  No matches found for skill {skill_id}")
            return {
                "skill_id": skill_id,
                "model_ratings": {},
                "model_rankings": [],
                "total_matches": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Initialize all models with default ratings
        model_ratings = {}
        model_ids = set()

        # Collect all unique model IDs from matches
        for match in match_history:
            model_ids.add(match["model_a"])
            model_ids.add(match["model_b"])

        # Initialize ratings
        for model_id in model_ids:
            model_ratings[model_id] = self._create_rating()

        print(
            f"    📊 Processing {len(match_history)} matches for {len(model_ids)} models"
        )

        # Process matches in chronological order
        match_results = []
        for i, match in enumerate(match_history):
            model_a = match["model_a"]
            model_b = match["model_b"]
            winner = match["winner"]
            timestamp = match.get("timestamp", "")

            # Get current ratings
            rating_a = model_ratings[model_a]
            rating_b = model_ratings[model_b]

            # Determine match outcome for OpenSkill
            if winner == "A":
                # Model A wins
                new_ratings = self.model.rate([[rating_a], [rating_b]], ranks=[0, 1])
            elif winner == "B":
                # Model B wins
                new_ratings = self.model.rate([[rating_a], [rating_b]], ranks=[1, 0])
            else:  # TIE
                # Tied match
                new_ratings = self.model.rate([[rating_a], [rating_b]], ranks=[0, 0])

            # Update ratings
            model_ratings[model_a] = new_ratings[0][0]
            model_ratings[model_b] = new_ratings[1][0]

            # Record match result with rating changes
            match_results.append(
                {
                    "match_number": i + 1,
                    "match_id": match["match_id"],
                    "model_a": model_a,
                    "model_b": model_b,
                    "winner": winner,
                    "timestamp": timestamp,
                    "rating_changes": {
                        model_a: {
                            "before": {"mu": rating_a.mu, "sigma": rating_a.sigma},
                            "after": {
                                "mu": new_ratings[0][0].mu,
                                "sigma": new_ratings[0][0].sigma,
                            },
                        },
                        model_b: {
                            "before": {"mu": rating_b.mu, "sigma": rating_b.sigma},
                            "after": {
                                "mu": new_ratings[1][0].mu,
                                "sigma": new_ratings[1][0].sigma,
                            },
                        },
                    },
                }
            )

        # Create final model rankings
        model_rankings = []
        for model_id, rating in model_ratings.items():
            model_rankings.append(
                {
                    "model_id": model_id,
                    "rating": round(rating.mu, 2),
                    "sigma": round(rating.sigma, 2),
                    "conservative_rating": round(
                        rating.mu - CONSERVATIVE_MULTIPLIER * rating.sigma, 2
                    ),
                    "rank": 0,  # Will be set after sorting
                }
            )

        # Sort by rating (descending)
        model_rankings.sort(key=lambda x: x["rating"], reverse=True)

        # Add rank numbers
        for i, model in enumerate(model_rankings):
            model["rank"] = i + 1

        # Prepare final result
        ratings_data = {
            "skill_id": skill_id,
            "model_ratings": {
                model_id: {
                    "mu": rating.mu,
                    "sigma": rating.sigma,
                    "conservative": rating.mu - CONSERVATIVE_MULTIPLIER * rating.sigma,
                }
                for model_id, rating in model_ratings.items()
            },
            "model_rankings": model_rankings,
            "match_progression": match_results,
            "total_matches": len(match_history),
            "total_models": len(model_ids),
            "timestamp": datetime.utcnow().isoformat(),
            "cache_key": cache_key,
        }

        # Save to cache only if corruption wasn't detected
        if not was_corrupted:
            self._save_cached_ratings(cache_path, ratings_data)
            print(
                f"    ✅ Calculated ratings for {skill_id}: {len(model_ids)} models, {len(match_history)} matches"
            )
        else:
            print(
                f"    ✅ Calculated ratings for {skill_id}: {len(model_ids)} models, {len(match_history)} matches (not cached due to corruption)"
            )

        return ratings_data


def main_with_data_dir(
    data_dir: Path,
    summaries_file: Path,
    models_file: Path,
    judges_file: Path,
    skills_file: Path,
    output_file: Path,
) -> None:
    """Main function for skill rating calculation with custom data directory."""
    skill_ratings_cache_dir = data_dir / "skill_ratings"

    print("🎯 Skill Rating Calculator Starting!")

    if not summaries_file.exists():
        print(f"⚠️  Tournament summaries file not found at {summaries_file}")
        result = {
            "skill_ratings": {},
            "execution_info": {
                "status": "no_tournament_data",
                "message": "No tournament summaries found",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
    else:
        # Load input data
        with open(summaries_file) as f:
            summaries_data = json.load(f)

        with open(models_file) as f:
            models_data = json.load(f)

        with open(judges_file) as f:
            judges_data = json.load(f)

        with open(skills_file) as f:
            skills_data = json.load(f)

        tournaments = summaries_data.get("tournaments", {})
        models = models_data["models"]
        judges = judges_data["judges"]
        evals = skills_data["evals"]

        if not tournaments:
            print("⚠️  No tournament data found")
            result = {
                "skill_ratings": {},
                "execution_info": {
                    "status": "no_tournaments",
                    "message": "No tournaments found in summaries",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
        else:
            calculator = SkillRatingCalculator(cache_dir=skill_ratings_cache_dir)

            # Clean up invalid cache first
            calculator.cleanup_invalid_rating_cache(models, judges, evals)

            # Generate cache key based on current state
            cache_key = calculator._generate_cache_key(
                models, judges, evals, tournaments
            )

            print(f"🔑 Cache key: {cache_key}")
            print(f"🏟️  Processing ratings for {len(tournaments)} skills...")

            skill_ratings = {}

            for skill_id, tournament_data in tournaments.items():
                skill_rating = calculator.calculate_skill_ratings(
                    skill_id, tournament_data, cache_key
                )
                skill_ratings[skill_id] = skill_rating

                # Print top 3 models for this skill
                print(f"   🏆 Top 3 models in {skill_id}:")
                for model in skill_rating["model_rankings"][:3]:
                    print(
                        f"      {model['rank']}. {model['model_id']} - {model['rating']} (±{model['sigma']:.1f})"
                    )

            result = {
                "skill_ratings": skill_ratings,
                "execution_info": {
                    "status": "completed",
                    "total_skills": len(skill_ratings),
                    "cache_key": cache_key,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }

    # Save results
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n💾 Skill ratings saved to: {output_file}")


def main() -> None:
    """Main function for skill rating calculation (legacy)."""
    # SAFETY: Require explicit data directory
    data_dir_env = os.getenv("AFBENCH_DATA_DIR")
    if not data_dir_env:
        raise ValueError(
            "🚨 SAFETY: calculate_skill_ratings.py requires explicit data directory.\n"
            "Set AFBENCH_DATA_DIR environment variable or run via Snakemake."
        )
    data_dir = Path(data_dir_env)
    summaries_file = data_dir / "tournament_summaries.json"
    models_file = data_dir / "loaded_models.json"
    judges_file = data_dir / "loaded_judges.json"
    skills_file = data_dir / "loaded_skills.json"
    output_file = data_dir / "skill_ratings.json"

    main_with_data_dir(
        data_dir, summaries_file, models_file, judges_file, skills_file, output_file
    )


if __name__ == "__main__":
    main()
