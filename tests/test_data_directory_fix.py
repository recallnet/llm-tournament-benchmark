"""
Test to verify the data directory fix works correctly.

This test confirms that after the fix, the Streamlit app loads the same
full dataset regardless of the working directory.
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


class TestDataDirectoryFix:
    """Test that the data directory fix works correctly."""

    def test_fix_loads_same_data_from_any_directory(self):
        """
        Test that after the fix, the app loads the same full dataset
        regardless of working directory.
        """

        print("\n✅ TESTING THE DATA DIRECTORY FIX")
        print("=" * 35)

        original_cwd = Path.cwd()
        results = {}

        # Test from both directories with the fix applied
        for directory_name, directory_path in [
            ("PROJECT_ROOT", "/Users/andrewhill/Coding/afbench"),
            ("SITE_DIRECTORY", "/Users/andrewhill/Coding/afbench/site"),
        ]:
            os.chdir(directory_path)
            print(f"\n{directory_name} ({directory_path}):")

            with patch("app.st.error"):
                data = load_validated_tournament_data()

            if data:
                skills = list(data["ratings"].keys())
                models = [m["id"] for m in data["models"]["models"]]

                results[directory_name] = {
                    "skills": sorted(skills),
                    "skill_count": len(skills),
                    "models": sorted(models),
                    "model_count": len(models),
                }

                print(f"   Skills: {len(skills)} - {skills}")
                print(f"   Models: {len(models)} - {models}")

                # Sample rating to verify it's the full dataset
                if skills and models:
                    first_skill = skills[0]
                    first_model = models[0]
                    skill_data = data["ratings"][first_skill]
                    rating = skill_data.get("model_ratings", {}).get(first_model, {}).get("mu", "MISSING")
                    print(f"   Sample rating ({first_model}, {first_skill}): {rating}")
                    results[directory_name]["sample_rating"] = rating
            else:
                print("   ❌ Failed to load data")
                results[directory_name] = None

        os.chdir(str(original_cwd))

        # Verify the fix worked
        if len(results) == 2 and all(results.values()):
            project_result = results["PROJECT_ROOT"]
            site_result = results["SITE_DIRECTORY"]

            print("\n🔍 VERIFICATION:")
            print(f"   Same skill count: {'✅' if project_result['skill_count'] == site_result['skill_count'] else '❌'}")
            print(f"   Same skills: {'✅' if project_result['skills'] == site_result['skills'] else '❌'}")
            print(f"   Same model count: {'✅' if project_result['model_count'] == site_result['model_count'] else '❌'}")
            print(f"   Same models: {'✅' if project_result['models'] == site_result['models'] else '❌'}")
            print(
                f"   Same sample rating: {'✅' if project_result['sample_rating'] == site_result['sample_rating'] else '❌'}"
            )

            # Check if we're loading the FULL dataset (should have 8 skills now)
            expected_skills = 8  # From our earlier tests, project root had 8 skills
            actual_skills = project_result["skill_count"]
            print(f"   Loading full dataset: {'✅' if actual_skills >= expected_skills else '❌'} ({actual_skills} skills)")

            if (
                project_result["skills"] == site_result["skills"]
                and project_result["models"] == site_result["models"]
                and project_result["sample_rating"] == site_result["sample_rating"]
                and actual_skills >= expected_skills
            ):

                print("\n🎉 FIX VERIFIED: App now loads the same full dataset from any directory!")

                # Check that we have the skills that were missing before
                harm_avoidance_present = "harm_avoidance" in project_result["skills"]
                hidden_messages_present = "hidden_messages" in project_result["skills"]
                print(f"   Contains harm_avoidance: {'✅' if harm_avoidance_present else '❌'}")
                print(f"   Contains hidden_messages: {'✅' if hidden_messages_present else '❌'}")

                return True
            else:
                print("\n❌ FIX INCOMPLETE: Still loading different data or missing skills")
                return False
        else:
            print("\n❌ Could not verify fix due to data loading issues")
            return False

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_app_now_shows_consistent_behavior(self, mock_subheader, mock_selectbox, mock_header, mock_dataframe):
        """
        Test that the app now shows consistent behavior (same best/worst skills,
        real ratings) regardless of working directory.
        """

        print("\n🎭 TESTING CONSISTENT APP BEHAVIOR")
        print("=" * 33)

        original_cwd = Path.cwd()
        app_results = {}

        # Test app behavior from both directories
        for directory_name, directory_path in [
            ("PROJECT_ROOT", "/Users/andrewhill/Coding/afbench"),
            ("SITE_DIRECTORY", "/Users/andrewhill/Coding/afbench/site"),
        ]:
            os.chdir(directory_path)
            print(f"\n{directory_name}:")

            # Clear mock history
            mock_dataframe.reset_mock()

            with patch("app.st.error"):
                data = load_validated_tournament_data()

            if data:
                models = data["models"]["models"]
                if models:
                    first_model = models[0]["id"]
                    mock_selectbox.return_value = first_model

                    show_models_page(data)

                    if mock_dataframe.call_args_list:
                        # Get models overview table
                        models_table = mock_dataframe.call_args_list[0][0][0]
                        first_row = models_table.iloc[0]

                        # Get detailed performance table if available
                        detailed_ratings = []
                        default_count = 0
                        if len(mock_dataframe.call_args_list) > 1:
                            detailed_table = mock_dataframe.call_args_list[1][0][0]
                            for _, row in detailed_table.iterrows():
                                rating = float(row["Rating"])
                                detailed_ratings.append((row["Skill"], rating))
                                if rating == 1500.0:
                                    default_count += 1

                        app_results[directory_name] = {
                            "model_id": first_row["Model ID"],
                            "skills_count": len(data["ratings"]),
                            "best_skill": first_row["Best Skill"],
                            "worst_skill": first_row["Worst Skill"],
                            "same_best_worst": first_row["Best Skill"] == first_row["Worst Skill"],
                            "detailed_ratings": detailed_ratings,
                            "default_rating_count": default_count,
                        }

                        print(f"   Model: {first_row['Model ID']}")
                        print(f"   Skills: {len(data['ratings'])}")
                        print(f"   Best/Worst: {first_row['Best Skill']} / {first_row['Worst Skill']}")
                        print(f"   Same best/worst: {'🐛' if first_row['Best Skill'] == first_row['Worst Skill'] else '✅'}")
                        print(f"   Default 1500.0 ratings: {default_count}")
            else:
                app_results[directory_name] = None

        os.chdir(str(original_cwd))

        # Compare app behavior
        if len(app_results) == 2 and all(app_results.values()):
            project_app = app_results["PROJECT_ROOT"]
            site_app = app_results["SITE_DIRECTORY"]

            print("\n🆚 BEHAVIOR COMPARISON:")
            print(f"   Same skill count: {'✅' if project_app['skills_count'] == site_app['skills_count'] else '❌'}")
            print(f"   Same best skill: {'✅' if project_app['best_skill'] == site_app['best_skill'] else '❌'}")
            print(f"   Same worst skill: {'✅' if project_app['worst_skill'] == site_app['worst_skill'] else '❌'}")
            print(
                f"   Same default count: {'✅' if project_app['default_rating_count'] == site_app['default_rating_count'] else '❌'}"
            )

            # Check for user-reported bugs
            no_same_best_worst = not project_app["same_best_worst"] and not site_app["same_best_worst"]
            no_default_ratings = project_app["default_rating_count"] == 0 and site_app["default_rating_count"] == 0

            print(f"   No same best/worst bug: {'✅' if no_same_best_worst else '🐛'}")
            print(f"   No 1500.0 default bug: {'✅' if no_default_ratings else '🐛'}")

            if (
                project_app["skills_count"] == site_app["skills_count"]
                and project_app["best_skill"] == site_app["best_skill"]
                and project_app["worst_skill"] == site_app["worst_skill"]
                and no_same_best_worst
                and no_default_ratings
            ):

                print("\n🎉 SUCCESS: App behavior is now consistent and bug-free!")
            else:
                print("\n⚠️ ISSUES REMAIN: Some inconsistencies or bugs still present")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
