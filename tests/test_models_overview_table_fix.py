"""
Test to verify that the models overview table fix works correctly.

This test focuses specifically on the first table (models overview) that shows
best/worst skills for each model, which was still buggy after we fixed the
detailed performance table.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Mock streamlit completely before importing
class MockSessionState(dict):
    """Mock session state that supports both dict and attribute access."""

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        if key in self:
            del self[key]


streamlit_mock = MagicMock()
streamlit_mock.cache_data = lambda ttl=None: lambda f: f
streamlit_mock.set_page_config = MagicMock()
streamlit_mock.error = MagicMock()
streamlit_mock.session_state = MockSessionState()
sys.modules["streamlit"] = streamlit_mock

sys.path.insert(0, str(Path(__file__).parent.parent))
from admin_ui import show_models_page


class TestModelsOverviewTableFix:
    """Test the models overview table best/worst skill calculation."""

    @patch("admin_ui.st.dataframe")
    @patch("admin_ui.st.header")
    @patch("admin_ui.st.selectbox")
    @patch("admin_ui.st.subheader")
    def test_models_overview_shows_correct_best_worst_skills(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """
        Test that the models overview table (first table) shows correct
        best and worst skills for each model based on their actual ratings.
        """

        print("\n🎯 TESTING MODELS OVERVIEW TABLE FIX")
        print("=" * 36)

        # Create test data matching the user's actual data
        test_data = {
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
                        {
                            "model_id": "thedrummer/unslopnemo-12b",
                            "wins": 14,
                            "losses": 1,
                            "total_matches": 15,
                            "rank": 1,
                        }
                    ]
                },
                "code_generation": {
                    "model_rankings": [
                        {
                            "model_id": "thedrummer/unslopnemo-12b",
                            "wins": 1,
                            "losses": 20,
                            "total_matches": 21,
                            "rank": 4,
                        }
                    ]
                },
            },
            "ratings": {
                "harm_avoidance": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1652.8, "sigma": 64.0}
                    }
                },
                "hidden_messages": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1539.5, "sigma": 34.6}
                    }
                },
                "document_summarization": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1476.8, "sigma": 55.9}
                    }
                },
                "empathy": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1525.8, "sigma": 44.2}
                    }
                },
                "respect_no_em_dash_requests": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1497.7, "sigma": 38.8}
                    }
                },
                "code_generation": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1314.4, "sigma": 57.6}
                    }  # LOWEST RATING
                },
                "persuasiveness": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1410.2, "sigma": 55.0}
                    }
                },
                "ethical_loopholes": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1375.7, "sigma": 48.3}
                    }
                },
            },
        }

        mock_selectbox.return_value = "thedrummer/unslopnemo-12b"

        print("Testing with thedrummer/unslopnemo-12b:")
        print("Expected best skill: harm_avoidance (1652.8)")
        print("Expected worst skill: code_generation (1314.4)")

        # Run the models page
        show_models_page(test_data)

        # Check the models overview table (first dataframe call)
        if mock_dataframe.call_args_list:
            models_overview = mock_dataframe.call_args_list[0][0][0]

            print("\nModels overview table results:")
            for _, row in models_overview.iterrows():
                model_id = row["Model ID"]
                best_skill = row["Best Skill"]
                worst_skill = row["Worst Skill"]

                print(f"  {model_id}:")
                print(f"    Best skill: {best_skill}")
                print(f"    Worst skill: {worst_skill}")
                print(
                    f"    Same best/worst: {'🐛 YES' if best_skill == worst_skill else '✅ NO'}"
                )

                # Verify correctness
                if model_id == "thedrummer/unslopnemo-12b":
                    if (
                        best_skill == "harm_avoidance"
                        and worst_skill == "code_generation"
                    ):
                        print(f"    🎉 CORRECT: Best={best_skill}, Worst={worst_skill}")
                    else:
                        print(
                            "    ❌ WRONG: Expected best=harm_avoidance, worst=code_generation"
                        )
                        print(f"    Got: best={best_skill}, worst={worst_skill}")

                        # Debug the rating calculation
                        print(f"\n    DEBUG: Checking all ratings for {model_id}:")
                        ratings = test_data["ratings"]
                        for skill, skill_data in ratings.items():
                            model_ratings = skill_data.get("model_ratings", {})
                            if model_id in model_ratings:
                                rating = model_ratings[model_id]["mu"]
                                print(f"      {skill}: {rating}")

                        pytest.fail("Models overview showing wrong best/worst skills")
        else:
            print("❌ No dataframe calls found")
            pytest.fail("No models overview table generated")

    def test_why_previous_tests_didnt_catch_this(self):
        """
        Debug why our previous tests didn't catch the models overview bug.
        """

        print("\n🔍 WHY DIDN'T PREVIOUS TESTS CATCH THIS BUG?")
        print("=" * 44)

        print("Analysis of our previous testing approach:")
        print("1. ✅ We tested the detailed performance table (2nd table) - WORKED")
        print("2. ❌ We didn't specifically test models overview table (1st table)")
        print(
            "3. ❌ Most tests used mock data that didn't reveal the rating lookup bug"
        )
        print("4. ❌ Real data tests focused on data loading, not UI table generation")
        print("5. ❌ We fixed site/app.py but not admin_ui.py (wrong file issue)")

        print("\nLessons learned:")
        print("1. 🎯 Test BOTH tables separately when there are multiple data displays")
        print("2. 🎯 Use realistic data that matches production scenarios")
        print(
            "3. 🎯 Verify we're testing the actual running code, not a different file"
        )
        print("4. 🎯 Test the specific UI components users interact with")

        print("\nThis is why comprehensive testing is iterative - each bug teaches us")
        print("about blind spots in our testing approach! 🧠")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
