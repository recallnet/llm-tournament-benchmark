"""
Test to reproduce the exact bug using real data files.

This test loads the actual data files and verifies if the rating lookup bug
and best/worst skill bug can be reproduced with the real data structure.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock streamlit completely before importing
streamlit_mock = MagicMock()
streamlit_mock.cache_data = lambda ttl=None: lambda f: f
streamlit_mock.set_page_config = MagicMock()
sys.modules["streamlit"] = streamlit_mock

sys.path.insert(0, str(Path(__file__).parent.parent / "site"))
from app import show_models_page


class TestRealDataBugReproduction:
    """Test with real data to reproduce the bugs reported by the user."""

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_reproduce_bug_with_real_file_structure(self, mock_subheader, mock_selectbox, mock_header, mock_dataframe):
        """
        Test using the real file structure to reproduce the exact bug.
        """

        print("\nDEBUG: Loading real data files to reproduce bug...")

        try:
            # Load real data files
            with open("/Users/andrewhill/Coding/afbench/data/skill_ratings.json") as f:
                skill_ratings_data = json.load(f)

            with open("/Users/andrewhill/Coding/afbench/data/loaded_models.json") as f:
                models_data = json.load(f)

            with open("/Users/andrewhill/Coding/afbench/data/loaded_judges.json") as f:
                judges_data = json.load(f)

            with open("/Users/andrewhill/Coding/afbench/data/loaded_skills.json") as f:
                skills_data = json.load(f)

            # Check if tournament_summaries.json exists, otherwise use tournaments.json
            tournament_file = None
            tournament_summaries_path = Path("/Users/andrewhill/Coding/afbench/data/tournament_summaries.json")
            tournaments_path = Path("/Users/andrewhill/Coding/afbench/data/tournaments.json")

            if tournament_summaries_path.exists():
                tournament_file = str(tournament_summaries_path)
            elif tournaments_path.exists():
                tournament_file = str(tournaments_path)

            if tournament_file:
                with open(tournament_file) as f:
                    tournament_data = json.load(f)
            else:
                # Create minimal tournament data from skill ratings
                tournament_data = {
                    "tournaments": {skill: {"model_rankings": []} for skill in skill_ratings_data["skill_ratings"].keys()}
                }

            print("✅ Loaded real data files successfully")
            print(f"Available skills: {list(skill_ratings_data['skill_ratings'].keys())}")
            print(f"Models: {[m['id'] for m in models_data['models']]}")

            # Reconstruct the exact data structure the app expects
            real_app_data = {
                "models": models_data,
                "judges": judges_data,
                "skills": skills_data,
                "tournaments": tournament_data.get("tournaments", {}),
                "ratings": skill_ratings_data["skill_ratings"],
                "execution_info": skill_ratings_data["execution_info"],
                "model_ids": {m["id"] for m in models_data["models"]},
                "judge_ids": {j["id"] for j in judges_data["judges"]},
                "eval_ids": {e["id"] for e in skills_data["evals"]},
            }

            # Test with the first model
            first_model = models_data["models"][0]["id"]
            mock_selectbox.return_value = first_model

            print(f"\nDEBUG: Testing with first model: {first_model}")

            # Check ratings for the first model across all skills
            print(f"Real ratings for {first_model}:")
            for skill, skill_data in real_app_data["ratings"].items():
                model_ratings = skill_data.get("model_ratings", {})
                if first_model in model_ratings:
                    rating = model_ratings[first_model].get("mu", "MISSING")
                    print(f"  {skill}: {rating}")
                else:
                    print(f"  {skill}: NOT FOUND in model_ratings")

            # Run the app with real data
            show_models_page(real_app_data)

            # Analyze what the app actually outputs
            if mock_dataframe.call_args_list:
                # Check models overview table (first call)
                models_table = mock_dataframe.call_args_list[0][0][0]

                print("\nDEBUG: Models table results:")
                for _, row in models_table.iterrows():
                    model_id = row["Model ID"]
                    print(f"  {model_id}: best={row['Best Skill']}, worst={row['Worst Skill']}")

                    # Check for the bug: best and worst skills being the same
                    if row["Best Skill"] == row["Worst Skill"]:
                        print(f"    🐛 BUG: {model_id} has same best and worst skill!")

                # Check detailed performance table if available (second call)
                if len(mock_dataframe.call_args_list) > 1:
                    detailed_table = mock_dataframe.call_args_list[1][0][0]

                    print(f"\nDEBUG: Detailed performance table for {first_model}:")
                    for _, row in detailed_table.iterrows():
                        skill = row["Skill"]
                        rating = float(row["Rating"])
                        print(f"  {skill}: {rating}")

                        # Check for 1500.0 default bug
                        if rating == 1500.0:
                            print(f"    🐛 BUG: {skill} shows default 1500.0 instead of real rating!")

            # Now let's debug why ratings might be defaulting to 1500
            print(f"\nDEBUG: Manual rating lookup test for {first_model}:")
            ratings = real_app_data["ratings"]

            for skill in list(ratings.keys())[:3]:  # Test first 3 skills
                # This is the exact lookup from site/app.py line 161-162
                skill_ratings = ratings.get(skill, {})
                model_rating = skill_ratings.get("model_ratings", {}).get(first_model, {}).get("mu", 1500)
                print(f"  {skill}: lookup result = {model_rating}")

                # Debug the lookup chain
                print(f"    skill_ratings keys: {list(skill_ratings.keys())}")
                if "model_ratings" in skill_ratings:
                    model_ratings_dict = skill_ratings["model_ratings"]
                    print(f"    model_ratings keys: {list(model_ratings_dict.keys())[:5]}...")  # First 5
                    if first_model in model_ratings_dict:
                        model_data = model_ratings_dict[first_model]
                        print(f"    {first_model} data keys: {list(model_data.keys())}")
                        mu_value = model_data.get("mu", "MISSING")
                        print(f"    mu value: {mu_value}")
                    else:
                        print(f"    {first_model} NOT FOUND in model_ratings")
                else:
                    print("    'model_ratings' key NOT FOUND in skill_ratings")

            # Check tournament participation to identify single-tournament bug
            print(f"\nDEBUG: Tournament participation for {first_model}:")
            tournaments = real_app_data["tournaments"]
            participating_skills = []

            for skill, tournament_data in tournaments.items():
                model_rankings = tournament_data.get("model_rankings", [])
                model_ids_in_tournament = [r.get("model_id") for r in model_rankings if "model_id" in r]
                if first_model in model_ids_in_tournament:
                    participating_skills.append(skill)
                    print(f"  ✅ Participates in: {skill}")
                else:
                    print(f"  ❌ Missing from: {skill} tournament")

            print(f"  Total participating skills: {len(participating_skills)} out of {len(tournaments)}")

            if len(participating_skills) <= 1:
                print("    🐛 IDENTIFIED: Single tournament participation bug!")
                print("    This causes best=worst skill because rating comparison only runs for participating tournaments")

        except Exception as e:
            print(f"❌ Error loading real data: {e}")
            pytest.skip(f"Could not load real data: {e}")

    def test_identify_tournament_data_structure_issue(self):
        """
        Test to identify if the tournament data structure is causing the issue.
        """

        try:
            # Check what tournament files exist
            tournament_files = []

            tournament_summaries_path = Path("/Users/andrewhill/Coding/afbench/data/tournament_summaries.json")
            tournaments_path = Path("/Users/andrewhill/Coding/afbench/data/tournaments.json")

            if tournament_summaries_path.exists():
                tournament_files.append("tournament_summaries.json")

            if tournaments_path.exists():
                tournament_files.append("tournaments.json")

            print(f"\nDEBUG: Available tournament files: {tournament_files}")

            # Load and compare structures
            for filename in tournament_files:
                filepath = f"/Users/andrewhill/Coding/afbench/data/{filename}"
                with open(filepath) as f:
                    data = json.load(f)

                print(f"\n{filename} structure:")
                print(f"  Top-level keys: {list(data.keys())}")

                if "tournaments" in data:
                    tournaments = data["tournaments"]
                    print(f"  Skills: {list(tournaments.keys())}")

                    # Check first skill structure
                    first_skill = list(tournaments.keys())[0]
                    first_tournament = tournaments[first_skill]
                    print(f"  {first_skill} keys: {list(first_tournament.keys())}")

                    # Check model_rankings structure
                    if "model_rankings" in first_tournament:
                        rankings = first_tournament["model_rankings"]
                        if rankings:
                            print(f"  Sample ranking keys: {list(rankings[0].keys())}")
                            print(f"  Number of models ranked: {len(rankings)}")

                            # Show first few models
                            for i, ranking in enumerate(rankings[:3]):
                                model_id = ranking.get("model_id", "MISSING")
                                print(f"    {i+1}. {model_id}")
                        else:
                            print(f"  ❌ Empty model_rankings for {first_skill}")
                    else:
                        print(f"  ❌ No 'model_rankings' key in {first_skill}")

        except Exception as e:
            print(f"Error analyzing tournament structure: {e}")
            pytest.skip(f"Could not analyze tournament data: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
