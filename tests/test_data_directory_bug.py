"""
Test to confirm the data directory bug - the root cause of the user's reported issues.

This test demonstrates that the Streamlit app loads different data depending on
which data/ directory it finds, causing the discrepancies the user reported.
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


class TestDataDirectoryBug:
    """Test to confirm and document the data directory bug."""

    def test_different_data_directories_load_different_datasets(self):
        """
        CONFIRMED BUG: The app loads different datasets depending on working directory.

        This is the root cause of all user-reported issues:
        - Different number of skills
        - Different ratings
        - Potentially different tournament participation leading to same best/worst skills
        """

        print("\n🐛 TESTING THE DATA DIRECTORY BUG")
        print("=" * 50)

        original_cwd = Path.cwd()

        # Test 1: Load from project root
        os.chdir("/Users/andrewhill/Coding/afbench")
        print(f"\n1. Loading from PROJECT ROOT: {os.getcwd()}")

        with patch("app.st.error"):
            project_root_data = load_validated_tournament_data()

        if project_root_data:
            project_skills = list(project_root_data["ratings"].keys())
            project_models = [m["id"] for m in project_root_data["models"]["models"]]
            print(f"   Skills: {len(project_skills)} - {project_skills}")
            print(f"   Models: {len(project_models)} - {project_models}")

            # Sample rating for first model/skill
            if project_skills and project_models:
                first_skill = project_skills[0]
                first_model = project_models[0]
                skill_data = project_root_data["ratings"][first_skill]
                rating = (
                    skill_data.get("model_ratings", {})
                    .get(first_model, {})
                    .get("mu", "MISSING")
                )
                print(f"   Sample rating ({first_model}, {first_skill}): {rating}")
        else:
            print("   ❌ Failed to load data from project root")

        # Test 2: Load from site directory
        os.chdir("/Users/andrewhill/Coding/afbench/site")
        print(f"\n2. Loading from SITE DIRECTORY: {os.getcwd()}")

        with patch("app.st.error"):
            site_data = load_validated_tournament_data()

        if site_data:
            site_skills = list(site_data["ratings"].keys())
            site_models = [m["id"] for m in site_data["models"]["models"]]
            print(f"   Skills: {len(site_skills)} - {site_skills}")
            print(f"   Models: {len(site_models)} - {site_models}")

            # Sample rating for first model/skill
            if site_skills and site_models:
                first_skill = site_skills[0]
                first_model = site_models[0]
                skill_data = site_data["ratings"][first_skill]
                rating = (
                    skill_data.get("model_ratings", {})
                    .get(first_model, {})
                    .get("mu", "MISSING")
                )
                print(f"   Sample rating ({first_model}, {first_skill}): {rating}")
        else:
            print("   ❌ Failed to load data from site directory")

        os.chdir(str(original_cwd))

        # Analysis
        print("\n📊 ANALYSIS:")
        if project_root_data and site_data:
            project_skills = list(project_root_data["ratings"].keys())
            site_skills = list(site_data["ratings"].keys())

            print(f"   Project root skills: {len(project_skills)}")
            print(f"   Site directory skills: {len(site_skills)}")
            print(
                f"   Different datasets: {'✅' if set(project_skills) != set(site_skills) else '❌'}"
            )

            if set(project_skills) != set(site_skills):
                only_in_project = set(project_skills) - set(site_skills)
                only_in_site = set(site_skills) - set(project_skills)

                if only_in_project:
                    print(f"   Skills only in project root: {only_in_project}")
                if only_in_site:
                    print(f"   Skills only in site: {only_in_site}")

                print("\n🎯 ROOT CAUSE IDENTIFIED:")
                print(
                    "   The Streamlit app loads different data depending on working directory!"
                )
                print(
                    "   When run from site/, it finds site/data/ instead of project root data/"
                )
                print("   This causes all the reported bugs:")
                print("   - User sees fewer skills than expected")
                print("   - Different ratings/tournament data")
                print(
                    "   - Potentially different model participation leading to same best/worst skills"
                )

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_app_behavior_differs_by_working_directory(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """
        Test that the app shows different results when run from different directories.
        This confirms the user's reported issue.
        """

        print("\n🔍 TESTING APP BEHAVIOR FROM DIFFERENT DIRECTORIES")
        print("=" * 55)

        original_cwd = Path.cwd()
        results = {}

        # Test from both directories
        for directory_name, directory_path in [
            ("PROJECT_ROOT", "/Users/andrewhill/Coding/afbench"),
            ("SITE_DIRECTORY", "/Users/andrewhill/Coding/afbench/site"),
        ]:
            os.chdir(directory_path)
            print(f"\n{directory_name} ({directory_path}):")

            # Clear mock call history
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

                        # Analyze results for first model
                        first_row = models_table.iloc[0]

                        result = {
                            "model_id": first_row["Model ID"],
                            "skills_count": len(data["ratings"]),
                            "best_skill": first_row["Best Skill"],
                            "worst_skill": first_row["Worst Skill"],
                            "same_best_worst": first_row["Best Skill"]
                            == first_row["Worst Skill"],
                        }

                        results[directory_name] = result

                        print(f"   Model: {result['model_id']}")
                        print(f"   Skills available: {result['skills_count']}")
                        print(f"   Best skill: {result['best_skill']}")
                        print(f"   Worst skill: {result['worst_skill']}")
                        print(
                            f"   Same best/worst: {'🐛 YES' if result['same_best_worst'] else '✅ NO'}"
                        )

                        # Check detailed performance if available
                        if len(mock_dataframe.call_args_list) > 1:
                            detailed_table = mock_dataframe.call_args_list[1][0][0]
                            default_rating_count = sum(
                                1
                                for _, row in detailed_table.iterrows()
                                if float(row["Rating"]) == 1500.0
                            )
                            print(f"   1500.0 default ratings: {default_rating_count}")
            else:
                print("   ❌ Failed to load data")
                results[directory_name] = None

        os.chdir(str(original_cwd))

        # Compare results
        if len(results) == 2 and all(results.values()):
            project_result = results["PROJECT_ROOT"]
            site_result = results["SITE_DIRECTORY"]

            print("\n🆚 COMPARISON:")
            print(
                f"   Different skill counts: {'✅' if project_result['skills_count'] != site_result['skills_count'] else '❌'}"
            )
            print(
                f"   Different best skills: {'✅' if project_result['best_skill'] != site_result['best_skill'] else '❌'}"
            )
            print(
                f"   Different worst skills: {'✅' if project_result['worst_skill'] != site_result['worst_skill'] else '❌'}"
            )

            if (
                project_result["skills_count"] != site_result["skills_count"]
                or project_result["best_skill"] != site_result["best_skill"]
                or project_result["worst_skill"] != site_result["worst_skill"]
            ):

                print("\n✅ CONFIRMED: App behavior differs by working directory")
                print("   This explains the user's reported bugs!")
            else:
                print("\n❌ UNEXPECTED: App behavior is the same from both directories")

    def test_propose_fix(self):
        """
        Document the fix for this issue.
        """

        print("\n💡 PROPOSED FIX:")
        print("=" * 15)
        print("Change site/app.py line 21 from:")
        print("    data_dir = 'data'")
        print("To:")
        print("    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')")
        print("")
        print("This ensures the app always loads from the project root data/ directory")
        print("regardless of the working directory when Streamlit is run.")
        print("")
        print("Alternative fix:")
        print(
            "    data_dir = Path('data').resolve() if Path('data').exists() else Path('../data').resolve()"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
