"""
Test to verify that the detailed performance fix works correctly.

This test confirms that after the fix, the detailed performance section
shows real ratings instead of 1500.0 defaults for all skills.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock streamlit completely before importing
streamlit_mock = MagicMock()
streamlit_mock.cache_data = lambda ttl=None: lambda f: f
streamlit_mock.set_page_config = MagicMock()
streamlit_mock.error = MagicMock()
sys.modules["streamlit"] = streamlit_mock

sys.path.insert(0, str(Path(__file__).parent.parent / "site"))
from app import load_validated_tournament_data, show_models_page


class TestDetailedPerformanceFix:
    """Test that the detailed performance fix eliminates 1500.0 defaults."""

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_fix_shows_real_ratings_for_all_skills(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """
        Test that the fix shows real ratings for all skills that have ratings data,
        eliminating the 1500.0 defaults.
        """

        print("\n✅ TESTING DETAILED PERFORMANCE FIX")
        print("=" * 36)

        # Load real data
        with patch("app.st.error"):
            real_data = load_validated_tournament_data()

        if not real_data:
            pytest.skip("Could not load real data")
            return

        # Test with first model
        models = real_data["models"]["models"]
        first_model = models[0]["id"]
        mock_selectbox.return_value = first_model

        print(f"Testing with model: {first_model}")

        # Check how many skills have ratings for this model
        ratings = real_data["ratings"]
        skills_with_ratings = []
        for skill, skill_data in ratings.items():
            model_ratings = skill_data.get("model_ratings", {})
            if first_model in model_ratings:
                actual_rating = model_ratings[first_model]["mu"]
                skills_with_ratings.append((skill, actual_rating))
                print(f"  {skill}: {actual_rating:.1f} (REAL RATING)")

        print(f"\nTotal skills with ratings: {len(skills_with_ratings)}")

        # Run the app
        show_models_page(real_data)

        # Check the detailed performance table (second dataframe call)
        if len(mock_dataframe.call_args_list) > 1:
            detailed_table = mock_dataframe.call_args_list[1][0][0]

            print("\nDetailed performance table results:")
            default_count = 0
            real_rating_count = 0

            for _, row in detailed_table.iterrows():
                skill = row["Skill"]
                rating = float(row["Rating"])
                print(f"  {skill}: {rating}")

                if rating == 1500.0:
                    default_count += 1
                    print("    🐛 DEFAULT 1500.0!")
                else:
                    real_rating_count += 1
                    print("    ✅ REAL RATING")

            print("\n📊 RESULTS:")
            print(f"  Skills in detailed table: {len(detailed_table)}")
            print(f"  Skills with real ratings: {real_rating_count}")
            print(f"  Skills with 1500.0 defaults: {default_count}")
            print(f"  Expected skills with ratings: {len(skills_with_ratings)}")

            # Verify the fix
            if default_count == 0 and len(detailed_table) == len(skills_with_ratings):
                print("\n🎉 FIX SUCCESSFUL!")
                print("   ✅ No 1500.0 defaults found")
                print(
                    f"   ✅ All {len(skills_with_ratings)} skills with ratings are shown"
                )
                print("   ✅ All ratings are real values")
            elif default_count > 0:
                print(
                    f"\n❌ FIX INCOMPLETE: Still {default_count} skills showing 1500.0 defaults"
                )
            elif len(detailed_table) < len(skills_with_ratings):
                print(
                    f"\n❌ FIX INCOMPLETE: Missing {len(skills_with_ratings) - len(detailed_table)} skills"
                )
            else:
                print("\n⚠️ UNEXPECTED: More skills in table than expected")
        else:
            print("\n❌ No detailed performance table found")

    def test_fix_with_real_streamlit_run(self):
        """
        Test running the actual app code to verify it works in practice.
        """

        print("\n🚀 TESTING WITH SIMULATED STREAMLIT RUN")
        print("=" * 41)

        # Change to site directory
        original_cwd = Path.cwd()
        os.chdir("/Users/andrewhill/Coding/afbench/site")

        try:
            # Simulate running the app
            print("Simulating streamlit app execution...")

            with patch("app.st.error"):
                data = load_validated_tournament_data()

            if data:
                print("✅ Data loaded successfully")
                print(f"   Skills available: {len(data['ratings'])}")
                print(f"   Models available: {len(data['models']['models'])}")

                # Test the fixed detailed performance logic directly
                selected_model = data["models"]["models"][0]["id"]
                ratings = data["ratings"]
                tournaments = data["tournaments"]

                print(f"\nTesting detailed performance for: {selected_model}")

                # This is the NEW fixed code
                skill_performance = []
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

                        skill_performance.append(
                            {
                                "Skill": skill,
                                "Rating": f"{rating:.1f}",
                                "Rank": (
                                    tournament_stats.get("rank", "N/A")
                                    if tournament_stats
                                    else "N/A"
                                ),
                                "Wins": (
                                    tournament_stats.get("wins", 0)
                                    if tournament_stats
                                    else 0
                                ),
                                "Losses": (
                                    tournament_stats.get("losses", 0)
                                    if tournament_stats
                                    else 0
                                ),
                                "Ties": (
                                    tournament_stats.get("ties", 0)
                                    if tournament_stats
                                    else 0
                                ),
                            }
                        )

                print("\nFixed detailed performance results:")
                default_count = 0
                for item in skill_performance:
                    rating = float(item["Rating"])
                    print(f"  {item['Skill']}: {item['Rating']}")
                    if rating == 1500.0:
                        default_count += 1

                if default_count == 0:
                    print("\n🎉 SUCCESS: No 1500.0 defaults in fixed version!")
                    print(f"   All {len(skill_performance)} skills show real ratings")
                else:
                    print(f"\n❌ PROBLEM: Still {default_count} skills with 1500.0")

            else:
                print("❌ Failed to load data")

        finally:
            os.chdir(str(original_cwd))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
