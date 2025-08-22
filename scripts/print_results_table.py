#!/usr/bin/env python3
"""
Print a nicely formatted table of model performance by skill.
"""

import json
import sys
from pathlib import Path
from typing import Any


def load_skill_ratings(data_dir: str) -> dict[str, Any]:
    """Load skill ratings data."""
    ratings_file = Path(data_dir) / "skill_ratings.json"
    if not ratings_file.exists():
        print("❌ No skill ratings found. Run the pipeline first.")
        sys.exit(1)

    with open(ratings_file) as f:
        return json.load(f)


def format_results_table(ratings_data: dict[str, Any]) -> None:
    """Print a nicely formatted table of model performance."""
    skill_ratings = ratings_data.get("skill_ratings", {})

    if not skill_ratings:
        print("❌ No skill ratings data found.")
        return

    # Get all models across all skills
    all_models = set()
    for skill_data in skill_ratings.values():
        model_ratings = skill_data.get("model_ratings", {})
        all_models.update(model_ratings.keys())

    all_models = sorted(all_models)
    skills = sorted(skill_ratings.keys())

    if not all_models or not skills:
        print("❌ No model ratings found.")
        return

    # Print header
    print("\n" + "=" * 80)
    print("🏆 AFBENCH FINAL RESULTS")
    print("=" * 80)

    # Calculate column widths
    model_width = max(len("Model"), max(len(model) for model in all_models)) + 2
    skill_width = 12  # Fixed width for ratings

    # Print table header
    header = "Model".ljust(model_width)
    for skill in skills:
        # Truncate long skill names
        display_skill = skill.replace("_", " ").title()
        if len(display_skill) > skill_width - 2:
            display_skill = display_skill[: skill_width - 3] + "..."
        header += display_skill.rjust(skill_width)
    header += "Avg Rating".rjust(skill_width)

    print(header)
    print("-" * len(header))

    # Print each model's ratings
    for model in all_models:
        row = model.ljust(model_width)
        model_ratings = []

        for skill in skills:
            skill_data = skill_ratings.get(skill, {})
            model_rating_data = skill_data.get("model_ratings", {}).get(model)

            if model_rating_data is not None:
                # Extract mu value from OpenSkill rating
                model_rating = model_rating_data.get("mu", 0)
                rating_str = f"{model_rating:.1f}"
                model_ratings.append(model_rating)
            else:
                rating_str = "N/A"

            row += rating_str.rjust(skill_width)

        # Calculate average rating
        if model_ratings:
            avg_rating = sum(model_ratings) / len(model_ratings)
            avg_str = f"{avg_rating:.1f}"
        else:
            avg_str = "N/A"

        row += avg_str.rjust(skill_width)
        print(row)

    # Print summary statistics
    print("-" * len(header))

    # Find best model per skill
    print("\n🥇 SKILL CHAMPIONS:")
    for skill in skills:
        skill_data = skill_ratings.get(skill, {})
        model_ratings = skill_data.get("model_ratings", {})

        if model_ratings:
            best_model = max(model_ratings.items(), key=lambda x: x[1].get("mu", 0))
            display_skill = skill.replace("_", " ").title()
            rating = best_model[1].get("mu", 0)
            print(f"  {display_skill}: {best_model[0]} ({rating:.1f})")

    # Find overall best model (highest average)
    model_averages = {}
    for model in all_models:
        ratings = []
        for skill in skills:
            skill_data = skill_ratings.get(skill, {})
            rating_data = skill_data.get("model_ratings", {}).get(model)
            if rating_data is not None:
                rating = rating_data.get("mu", 0)
                ratings.append(rating)

        if ratings:
            model_averages[model] = sum(ratings) / len(ratings)

    if model_averages:
        best_overall = max(model_averages.items(), key=lambda x: x[1])
        print(f"\n🏆 OVERALL CHAMPION: {best_overall[0]} ({best_overall[1]:.1f} avg)")

    # Print metadata
    exec_info = ratings_data.get("execution_info", {})
    cache_key = exec_info.get("cache_key", "Unknown")
    timestamp = exec_info.get("timestamp", "Unknown")

    print(f"\n📊 Generated: {timestamp}")
    print(f"🔑 Cache Key: {cache_key}")
    print("=" * 80)


def main():
    """Main entry point."""
    try:
        # Require data directory as command line argument
        if len(sys.argv) < 2:
            raise ValueError(
                "🚨 SAFETY: print_results_table.py requires explicit data directory.\n"
                "Usage: python print_results_table.py <data_dir>"
            )
        data_dir = sys.argv[1]
        ratings_data = load_skill_ratings(data_dir)
        format_results_table(ratings_data)
    except Exception as e:
        print(f"❌ Error printing results table: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
