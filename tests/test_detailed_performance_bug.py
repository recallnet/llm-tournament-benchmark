"""
Test to identify the bug in the detailed performance section that shows 1500.0 defaults.

The issue is in lines 197-201 of show_models_page where it only shows ratings
for skills where the model appears in tournament rankings.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock streamlit completely before importing
streamlit_mock = MagicMock()
streamlit_mock.cache_data = lambda ttl=None: lambda f: f
streamlit_mock.set_page_config = MagicMock()
streamlit_mock.error = MagicMock()
sys.modules["streamlit"] = streamlit_mock

sys.path.insert(0, str(Path(__file__).parent.parent / "site"))


class TestDetailedPerformanceBug:
    """Test the specific bug in detailed performance section showing 1500.0."""

    def test_detailed_performance_shows_1500_when_model_not_in_tournament_rankings(
        self,
    ):
        """
        Test the exact scenario where a model has ratings but isn't in tournament rankings,
        causing the detailed performance to show 1500.0 defaults.
        """

        print("\n🐛 TESTING DETAILED PERFORMANCE 1500.0 BUG")
        print("=" * 47)

        # Create test data where model has ratings but missing from some tournament rankings
        test_data = {
            "models": {
                "models": [
                    {
                        "id": "test_model",
                        "author": "Test",
                        "context_window": 32000,
                        "endpoint": "test",
                    }
                ]
            },
            "tournaments": {
                "skill_a": {
                    "model_rankings": [
                        {"model_id": "test_model", "wins": 5, "losses": 2, "rank": 1}
                    ]
                },
                "skill_b": {
                    "model_rankings": [
                        # MODEL IS MISSING FROM skill_b tournament rankings!
                        {"model_id": "other_model", "wins": 3, "losses": 4, "rank": 1}
                    ]
                },
            },
            "ratings": {
                "skill_a": {
                    "model_ratings": {"test_model": {"mu": 1600.0, "sigma": 50.0}}
                },
                "skill_b": {
                    "model_ratings": {"test_model": {"mu": 1550.0, "sigma": 55.0}}
                },  # Rating exists!
            },
        }

        # Test the problematic code section
        selected_model = "test_model"
        tournaments = test_data["tournaments"]
        ratings = test_data["ratings"]

        print(f"Testing model: {selected_model}")
        print(f"Available ratings for {selected_model}:")
        for skill, skill_data in ratings.items():
            model_ratings = skill_data.get("model_ratings", {})
            if selected_model in model_ratings:
                rating = model_ratings[selected_model]["mu"]
                print(f"  {skill}: {rating} (REAL RATING EXISTS)")
            else:
                print(f"  {skill}: NO RATING")

        print(f"\nTournament participation for {selected_model}:")
        for skill, tournament_data in tournaments.items():
            model_rankings = tournament_data.get("model_rankings", [])
            model_in_rankings = any(
                r.get("model_id") == selected_model for r in model_rankings
            )
            print(
                f"  {skill}: {'✅ IN RANKINGS' if model_in_rankings else '❌ NOT IN RANKINGS'}"
            )

        # Simulate the exact code from lines 197-201
        print("\nSimulating app code (lines 197-201):")
        skill_performance = []
        for skill, tournament_data in tournaments.items():
            for ranking in tournament_data.get("model_rankings", []):
                if ranking["model_id"] == selected_model:
                    skill_ratings = ratings.get(skill, {})
                    rating = (
                        skill_ratings.get("model_ratings", {})
                        .get(selected_model, {})
                        .get("mu", 1500)
                    )

                    print(f"  {skill}: {rating} (from tournament ranking loop)")
                    skill_performance.append(
                        {"Skill": skill, "Rating": f"{rating:.1f}"}
                    )

        print(
            f"\nRESULT: Only {len(skill_performance)} skills shown in detailed performance"
        )
        for item in skill_performance:
            print(f"  {item['Skill']}: {item['Rating']}")

        # The BUG: skill_b won't appear because test_model isn't in skill_b's model_rankings,
        # even though test_model HAS a rating for skill_b!
        skills_with_ratings = len(
            [
                s
                for s, data in ratings.items()
                if selected_model in data.get("model_ratings", {})
            ]
        )
        skills_in_performance = len(skill_performance)

        print("\n📊 ANALYSIS:")
        print(f"  Skills with ratings: {skills_with_ratings}")
        print(f"  Skills in performance table: {skills_in_performance}")
        print(f"  Missing skills: {skills_with_ratings - skills_in_performance}")

        if skills_in_performance < skills_with_ratings:
            print(
                "\n🐛 BUG CONFIRMED: Detailed performance missing skills with ratings!"
            )
            print(
                "   This is why some skills might show 1500.0 - they're not being included at all!"
            )
        else:
            print("\n✅ No missing skills detected")

    def test_proposed_fix_for_detailed_performance(self):
        """
        Test a proposed fix: show ratings for ALL skills that have ratings,
        not just skills where the model appears in tournament rankings.
        """

        print("\n💡 TESTING PROPOSED FIX")
        print("=" * 23)

        # Same test data as above
        test_data = {
            "models": {
                "models": [
                    {
                        "id": "test_model",
                        "author": "Test",
                        "context_window": 32000,
                        "endpoint": "test",
                    }
                ]
            },
            "tournaments": {
                "skill_a": {
                    "model_rankings": [
                        {"model_id": "test_model", "wins": 5, "losses": 2, "rank": 1}
                    ]
                },
                "skill_b": {
                    "model_rankings": [
                        {"model_id": "other_model", "wins": 3, "losses": 4, "rank": 1}
                    ]
                },
            },
            "ratings": {
                "skill_a": {
                    "model_ratings": {"test_model": {"mu": 1600.0, "sigma": 50.0}}
                },
                "skill_b": {
                    "model_ratings": {"test_model": {"mu": 1550.0, "sigma": 55.0}}
                },
            },
        }

        selected_model = "test_model"
        tournaments = test_data["tournaments"]
        ratings = test_data["ratings"]

        # PROPOSED FIX: Loop through all skills with ratings instead of tournament rankings
        print("Fixed approach - loop through ratings instead of tournaments:")
        skill_performance_fixed = []

        for skill, skill_data in ratings.items():
            model_ratings = skill_data.get("model_ratings", {})
            if selected_model in model_ratings:
                rating = model_ratings[selected_model]["mu"]

                # Get tournament stats if available
                tournament_stats = None
                tournament_data = tournaments.get(skill, {})
                for ranking in tournament_data.get("model_rankings", []):
                    if ranking["model_id"] == selected_model:
                        tournament_stats = ranking
                        break

                print(f"  {skill}: {rating} (REAL RATING)")
                skill_performance_fixed.append(
                    {
                        "Skill": skill,
                        "Rating": f"{rating:.1f}",
                        "Rank": (
                            tournament_stats.get("rank", "N/A")
                            if tournament_stats
                            else "N/A"
                        ),
                        "Wins": (
                            tournament_stats.get("wins", 0) if tournament_stats else 0
                        ),
                        "Losses": (
                            tournament_stats.get("losses", 0) if tournament_stats else 0
                        ),
                        "Ties": (
                            tournament_stats.get("ties", 0) if tournament_stats else 0
                        ),
                    }
                )

        print(f"\nFIXED RESULT: {len(skill_performance_fixed)} skills shown")
        for item in skill_performance_fixed:
            print(f"  {item['Skill']}: {item['Rating']}")

        # Verify the fix works
        skills_with_ratings = len(
            [
                s
                for s, data in ratings.items()
                if selected_model in data.get("model_ratings", {})
            ]
        )
        fixed_skills_count = len(skill_performance_fixed)

        print("\n📊 FIX VERIFICATION:")
        print(f"  Skills with ratings: {skills_with_ratings}")
        print(f"  Skills in fixed performance: {fixed_skills_count}")
        print(
            f"  All skills included: {'✅' if fixed_skills_count == skills_with_ratings else '❌'}"
        )

        if fixed_skills_count == skills_with_ratings:
            print("\n✅ FIX SUCCESSFUL: All skills with ratings are now included!")
            print("   No more missing skills or 1500.0 defaults!")
        else:
            print("\n❌ FIX INCOMPLETE: Still missing some skills")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
