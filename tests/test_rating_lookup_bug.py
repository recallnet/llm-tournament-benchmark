"""
Test to reproduce the exact rating lookup bug where real ratings exist
but the app returns 1500.0 default instead of the actual rating.
"""

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


class TestRatingLookupBug:
    """Test the exact rating lookup failure causing 1500.0 defaults."""

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_rating_lookup_returns_default_instead_of_real_ratings(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """
        Test the exact scenario where ratings exist but lookup returns 1500.0 default.
        This reproduces the bug seen in the webapp where all ratings show 1500.0.
        """

        # Exact data structure mimicking what load_validated_tournament_data() returns
        webapp_data_structure = {
            "models": {
                "models": [
                    {
                        "id": "thedrummer/unslopnemo-12b",
                        "author": "TheDrummer",
                        "context_window": 32768,
                        "endpoint": "openrouter",
                    }
                ]
            },
            "tournaments": {
                "harm_avoidance": {
                    "model_rankings": [
                        {"model_id": "thedrummer/unslopnemo-12b", "wins": 14, "losses": 1, "ties": 0, "rank": 1}
                    ]
                },
                "code_generation": {
                    "model_rankings": [
                        {"model_id": "thedrummer/unslopnemo-12b", "wins": 1, "losses": 20, "ties": 0, "rank": 4}
                    ]
                },
                "persuasiveness": {
                    "model_rankings": [
                        {"model_id": "thedrummer/unslopnemo-12b", "wins": 4, "losses": 10, "ties": 1, "rank": 4}
                    ]
                },
            },
            # This is the key - what structure does ratings actually have?
            # From load_validated_tournament_data: 'ratings': ratings_data['skill_ratings']
            "ratings": {
                "harm_avoidance": {"model_ratings": {"thedrummer/unslopnemo-12b": {"mu": 1652.8276258868207, "sigma": 64.0}}},
                "code_generation": {"model_ratings": {"thedrummer/unslopnemo-12b": {"mu": 1314.4072209169015, "sigma": 57.6}}},
                "persuasiveness": {"model_ratings": {"thedrummer/unslopnemo-12b": {"mu": 1520.123, "sigma": 55.0}}},
            },
        }

        mock_selectbox.return_value = "thedrummer/unslopnemo-12b"

        print("\nDEBUG: Testing rating lookup with exact webapp data structure...")

        # Test the exact lookup that's failing in the code
        model_id = "thedrummer/unslopnemo-12b"
        ratings = webapp_data_structure["ratings"]

        print("\nDEBUG: Manual rating lookup test:")
        for skill in ["harm_avoidance", "code_generation", "persuasiveness"]:
            # This is the exact code from line 161-162 in site/app.py
            skill_ratings = ratings.get(skill, {})
            model_rating = skill_ratings.get("model_ratings", {}).get(model_id, {}).get("mu", 1500)
            print(f"  {skill}: {model_rating}")

            # These should NOT be 1500.0!
            if skill == "harm_avoidance":
                assert model_rating == 1652.8276258868207, f"Expected 1652.83, got {model_rating}"
            elif skill == "code_generation":
                assert model_rating == 1314.4072209169015, f"Expected 1314.41, got {model_rating}"

        # Now test the full app function
        show_models_page(webapp_data_structure)

        # Check the detailed model performance table (second dataframe call)
        detailed_table = mock_dataframe.call_args_list[1][0][0]

        print("\nDEBUG: Detailed model performance table ratings:")
        for _, row in detailed_table.iterrows():
            skill = row["Skill"]
            rating = float(row["Rating"])
            print(f"  {skill}: {rating}")

            # BUG: These should NOT all be 1500.0
            if skill == "harm_avoidance":
                if rating == 1500.0:
                    print("🐛 BUG: harm_avoidance shows 1500.0 instead of 1652.83")
                    pytest.fail("Rating lookup failed - got default 1500.0 instead of real rating 1652.83")
                else:
                    assert abs(rating - 1652.83) < 0.1, f"Expected ~1652.83, got {rating}"

            elif skill == "code_generation":
                if rating == 1500.0:
                    print("🐛 BUG: code_generation shows 1500.0 instead of 1314.41")
                    pytest.fail("Rating lookup failed - got default 1500.0 instead of real rating 1314.41")
                else:
                    assert abs(rating - 1314.41) < 0.1, f"Expected ~1314.41, got {rating}"

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_debug_exact_data_structure_from_load_function(self, mock_subheader, mock_selectbox, mock_header, mock_dataframe):
        """
        Debug what data structure load_validated_tournament_data() actually returns
        vs what the rating lookup expects.
        """

        # Let's see if there's a mismatch between what load function returns
        # and what the models page expects

        mock_selectbox.return_value = "thedrummer/unslopnemo-12b"

        # Potential bug scenarios:

        # Scenario 1: What if ratings structure is different?
        wrong_ratings_structure = {
            "models": {"models": [{"id": "thedrummer/unslopnemo-12b", "author": "Test"}]},
            "tournaments": {
                "harm_avoidance": {
                    "model_rankings": [{"model_id": "thedrummer/unslopnemo-12b", "wins": 14, "losses": 1, "rank": 1}]
                }
            },
            "ratings": {
                "harm_avoidance": {
                    # What if it's missing 'model_ratings' wrapper?
                    "thedrummer/unslopnemo-12b": {"mu": 1652.83, "sigma": 64.0}
                    # Instead of: 'model_ratings': { 'thedrummer/unslopnemo-12b': {...} }
                }
            },
        }

        print("\nDEBUG: Testing wrong ratings structure (missing model_ratings wrapper)...")

        skill_ratings = wrong_ratings_structure["ratings"].get("harm_avoidance", {})
        model_rating = skill_ratings.get("model_ratings", {}).get("thedrummer/unslopnemo-12b", {}).get("mu", 1500)
        print(f"  Rating lookup result: {model_rating}")

        if model_rating == 1500:
            print("🐛 FOUND BUG: Missing 'model_ratings' wrapper causes default 1500!")

        show_models_page(wrong_ratings_structure)
        detailed_table = mock_dataframe.call_args_list[1][0][0]

        harm_avoidance_row = detailed_table[detailed_table["Skill"] == "harm_avoidance"].iloc[0]
        rating = float(harm_avoidance_row["Rating"])

        print(f"  App result: {rating}")

        # Scenario 2: What if model_id has different format?
        model_id_format_issue = {
            "models": {"models": [{"id": "thedrummer/unslopnemo-12b", "author": "Test"}]},
            "tournaments": {
                "harm_avoidance": {
                    "model_rankings": [{"model_id": "thedrummer/unslopnemo-12b", "wins": 14, "losses": 1, "rank": 1}]
                }
            },
            "ratings": {
                "harm_avoidance": {
                    "model_ratings": {
                        # What if the key has extra spaces or different format?
                        " thedrummer/unslopnemo-12b ": {"mu": 1652.83, "sigma": 64.0}
                        # Or different encoding issue?
                    }
                }
            },
        }

        print("\nDEBUG: Testing model ID format mismatch...")
        skill_ratings = model_id_format_issue["ratings"].get("harm_avoidance", {})
        model_rating = skill_ratings.get("model_ratings", {}).get("thedrummer/unslopnemo-12b", {}).get("mu", 1500)
        print(f"  Rating lookup result: {model_rating}")

        if model_rating == 1500:
            print("🐛 FOUND BUG: Model ID format mismatch causes default 1500!")
            # Show what keys actually exist
            actual_keys = list(skill_ratings.get("model_ratings", {}).keys())
            print(f"  Available model keys: {actual_keys}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
