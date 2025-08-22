"""
Focused test to expose the best/worst skill calculation bug in the Models page.

This test specifically targets the scenario where all models show the same
best and worst skill, which indicates a bug in the skill comparison logic.
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


class TestModelsBestWorstSkillBug:
    """Test the specific bug where all models show the same best/worst skill."""

    @pytest.fixture
    def realistic_multi_skill_data(self):
        """
        Realistic test data with multiple skills where different models
        should have different best/worst performing skills.
        """
        return {
            "models": {
                "models": [
                    {
                        "id": "openai/gpt-4",
                        "author": "OpenAI",
                        "context_window": 128000,
                        "endpoint": "openrouter",
                    },
                    {
                        "id": "anthropic/claude",
                        "author": "Anthropic",
                        "context_window": 200000,
                        "endpoint": "openrouter",
                    },
                    {
                        "id": "meta/llama",
                        "author": "Meta",
                        "context_window": 32000,
                        "endpoint": "openrouter",
                    },
                ]
            },
            "tournaments": {
                "harm_avoidance": {
                    "total_matches": 15,
                    "model_rankings": [
                        {
                            "model_id": "openai/gpt-4",
                            "wins": 12,
                            "losses": 3,
                            "ties": 0,
                            "rank": 1,
                        },
                        {
                            "model_id": "anthropic/claude",
                            "wins": 7,
                            "losses": 8,
                            "ties": 0,
                            "rank": 2,
                        },
                        {
                            "model_id": "meta/llama",
                            "wins": 2,
                            "losses": 13,
                            "ties": 0,
                            "rank": 3,
                        },
                    ],
                },
                "code_generation": {
                    "total_matches": 15,
                    "model_rankings": [
                        {
                            "model_id": "anthropic/claude",
                            "wins": 13,
                            "losses": 2,
                            "ties": 0,
                            "rank": 1,
                        },
                        {
                            "model_id": "meta/llama",
                            "wins": 8,
                            "losses": 7,
                            "ties": 0,
                            "rank": 2,
                        },
                        {
                            "model_id": "openai/gpt-4",
                            "wins": 4,
                            "losses": 11,
                            "ties": 0,
                            "rank": 3,
                        },
                    ],
                },
                "persuasiveness": {
                    "total_matches": 15,
                    "model_rankings": [
                        {
                            "model_id": "meta/llama",
                            "wins": 11,
                            "losses": 4,
                            "ties": 0,
                            "rank": 1,
                        },
                        {
                            "model_id": "openai/gpt-4",
                            "wins": 9,
                            "losses": 6,
                            "ties": 0,
                            "rank": 2,
                        },
                        {
                            "model_id": "anthropic/claude",
                            "wins": 5,
                            "losses": 10,
                            "ties": 0,
                            "rank": 3,
                        },
                    ],
                },
            },
            "ratings": {
                "harm_avoidance": {
                    "model_ratings": {
                        "openai/gpt-4": {
                            "mu": 1700.0,
                            "sigma": 50.0,
                        },  # Best at harm_avoidance
                        "anthropic/claude": {"mu": 1550.0, "sigma": 55.0},
                        "meta/llama": {"mu": 1350.0, "sigma": 60.0},
                    }
                },
                "code_generation": {
                    "model_ratings": {
                        "anthropic/claude": {
                            "mu": 1680.0,
                            "sigma": 45.0,
                        },  # Best at code_generation
                        "meta/llama": {"mu": 1520.0, "sigma": 50.0},
                        "openai/gpt-4": {
                            "mu": 1400.0,
                            "sigma": 55.0,
                        },  # Worst at code_generation
                    }
                },
                "persuasiveness": {
                    "model_ratings": {
                        "meta/llama": {
                            "mu": 1650.0,
                            "sigma": 48.0,
                        },  # Best at persuasiveness
                        "openai/gpt-4": {"mu": 1580.0, "sigma": 52.0},
                        "anthropic/claude": {
                            "mu": 1420.0,
                            "sigma": 58.0,
                        },  # Worst at persuasiveness
                    }
                },
            },
        }

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_different_models_have_different_best_worst_skills(
        self,
        mock_subheader,
        mock_selectbox,
        mock_header,
        mock_dataframe,
        realistic_multi_skill_data,
    ):
        """
        Test that different models show different best and worst skills based on their ratings.

        Expected behavior:
        - openai/gpt-4: best=harm_avoidance (1700.0), worst=code_generation (1400.0)
        - anthropic/claude: best=code_generation (1680.0), worst=persuasiveness (1420.0)
        - meta/llama: best=persuasiveness (1650.0), worst=harm_avoidance (1350.0)
        """
        mock_selectbox.return_value = "openai/gpt-4"

        show_models_page(realistic_multi_skill_data)

        # Get the models overview table (first call to dataframe)
        models_table = mock_dataframe.call_args_list[0][0][0]

        # Extract the best and worst skills for each model
        model_skills = {}
        for _, row in models_table.iterrows():
            model_id = row["Model ID"]
            model_skills[model_id] = {
                "best_skill": row["Best Skill"],
                "worst_skill": row["Worst Skill"],
            }

        print("DEBUG: Actual model skills found:")
        for model_id, skills in model_skills.items():
            print(
                f"  {model_id}: best={skills['best_skill']}, worst={skills['worst_skill']}"
            )

        # Verify each model has different best/worst skills based on their ratings
        assert (
            model_skills["openai/gpt-4"]["best_skill"] == "harm_avoidance"
        ), f"openai/gpt-4 should be best at harm_avoidance (1700.0), got: {model_skills['openai/gpt-4']['best_skill']}"

        assert (
            model_skills["openai/gpt-4"]["worst_skill"] == "code_generation"
        ), f"openai/gpt-4 should be worst at code_generation (1400.0), got: {model_skills['openai/gpt-4']['worst_skill']}"

        assert (
            model_skills["anthropic/claude"]["best_skill"] == "code_generation"
        ), f"anthropic/claude should be best at code_generation (1680.0), got: {model_skills['anthropic/claude']['best_skill']}"

        assert (
            model_skills["anthropic/claude"]["worst_skill"] == "persuasiveness"
        ), f"anthropic/claude should be worst at persuasiveness (1420.0), got: {model_skills['anthropic/claude']['worst_skill']}"

        assert (
            model_skills["meta/llama"]["best_skill"] == "persuasiveness"
        ), f"meta/llama should be best at persuasiveness (1650.0), got: {model_skills['meta/llama']['best_skill']}"

        assert (
            model_skills["meta/llama"]["worst_skill"] == "harm_avoidance"
        ), f"meta/llama should be worst at harm_avoidance (1350.0), got: {model_skills['meta/llama']['worst_skill']}"

        # Most importantly: verify they're NOT all the same
        best_skills = [skills["best_skill"] for skills in model_skills.values()]
        worst_skills = [skills["worst_skill"] for skills in model_skills.values()]

        assert (
            len(set(best_skills)) > 1
        ), f"BUG: All models show same best skill: {best_skills}"
        assert (
            len(set(worst_skills)) > 1
        ), f"BUG: All models show same worst skill: {worst_skills}"

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_single_skill_scenario_handles_gracefully(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """Test edge case where there's only one skill - all models should show same best/worst."""
        single_skill_data = {
            "models": {
                "models": [
                    {
                        "id": "model_a",
                        "author": "Test",
                        "context_window": 32000,
                        "endpoint": "test",
                    },
                    {
                        "id": "model_b",
                        "author": "Test",
                        "context_window": 32000,
                        "endpoint": "test",
                    },
                ]
            },
            "tournaments": {
                "only_skill": {
                    "total_matches": 5,
                    "model_rankings": [
                        {
                            "model_id": "model_a",
                            "wins": 3,
                            "losses": 2,
                            "ties": 0,
                            "rank": 1,
                        },
                        {
                            "model_id": "model_b",
                            "wins": 2,
                            "losses": 3,
                            "ties": 0,
                            "rank": 2,
                        },
                    ],
                }
            },
            "ratings": {
                "only_skill": {
                    "model_ratings": {
                        "model_a": {"mu": 1600.0, "sigma": 50.0},
                        "model_b": {"mu": 1500.0, "sigma": 55.0},
                    }
                }
            },
        }

        mock_selectbox.return_value = "model_a"

        show_models_page(single_skill_data)

        models_table = mock_dataframe.call_args_list[0][0][0]

        # In single skill scenario, both best and worst should be the same skill for all models
        for _, row in models_table.iterrows():
            assert row["Best Skill"] == "only_skill"
            assert row["Worst Skill"] == "only_skill"

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_debug_actual_data_structure(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """Debug test using the actual data structure from the real app."""

        # Let's try to load the actual data and see what's happening
        mock_selectbox.return_value = "thedrummer/unslopnemo-12b"

        try:
            # Import the actual data loading function
            with patch("app.st.error"):
                with patch("builtins.open"):
                    # Try to call with actual data
                    from app import load_validated_tournament_data

                    actual_data = load_validated_tournament_data()

                    if actual_data:
                        print("\nDEBUG: Actual data structure found!")

                        # Show available skills
                        print(
                            f"Available skills: {list(actual_data.get('ratings', {}).keys())}"
                        )

                        # Show sample ratings for first model
                        if actual_data.get("models", {}).get("models"):
                            first_model = actual_data["models"]["models"][0]["id"]
                            print(f"\nRatings for {first_model}:")
                            for skill, skill_data in actual_data.get(
                                "ratings", {}
                            ).items():
                                model_ratings = skill_data.get("model_ratings", {})
                                if first_model in model_ratings:
                                    rating = model_ratings[first_model].get("mu", "N/A")
                                    print(f"  {skill}: {rating}")

                        show_models_page(actual_data)

                        # Check what the actual output shows
                        models_table = mock_dataframe.call_args_list[0][0][0]

                        print("\nDEBUG: Actual models table output:")
                        for _, row in models_table.head(
                            3
                        ).iterrows():  # Show first 3 rows
                            print(
                                f"  {row['Model ID']}: best={row['Best Skill']}, worst={row['Worst Skill']}"
                            )

        except Exception as e:
            # If we can't load real data, create a scenario that reproduces the bug
            print(
                f"\nDEBUG: Couldn't load real data ({e}), testing potential bug scenarios..."
            )

            # Scenario 1: What if ratings data is missing/empty?
            missing_ratings_data = {
                "models": {
                    "models": [
                        {
                            "id": "thedrummer/unslopnemo-12b",
                            "author": "TheDrummer",
                            "context_window": 32768,
                            "endpoint": "openrouter",
                        },
                        {
                            "id": "openai/gpt-oss-120b",
                            "author": "OpenAI",
                            "context_window": 32768,
                            "endpoint": "openrouter",
                        },
                        {
                            "id": "inception/mercury",
                            "author": "Inception",
                            "context_window": 32768,
                            "endpoint": "openrouter",
                        },
                    ]
                },
                "tournaments": {
                    "harm_avoidance": {
                        "model_rankings": [
                            {
                                "model_id": "thedrummer/unslopnemo-12b",
                                "wins": 10,
                                "rank": 1,
                            },
                            {"model_id": "openai/gpt-oss-120b", "wins": 8, "rank": 2},
                            {"model_id": "inception/mercury", "wins": 6, "rank": 3},
                        ]
                    }
                },
                "ratings": {},  # Empty ratings!
            }

            show_models_page(missing_ratings_data)
            models_table = mock_dataframe.call_args_list[0][0][0]

            print("\nDEBUG: With empty ratings data:")
            for _, row in models_table.iterrows():
                print(
                    f"  {row['Model ID']}: best={row['Best Skill']}, worst={row['Worst Skill']}"
                )

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_bug_scenario_all_models_same_default_rating(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """Test scenario where all models get default rating of 1500, causing same best/worst."""

        # This could happen if the model isn't found in ratings data
        same_rating_data = {
            "models": {
                "models": [
                    {
                        "id": "model_a",
                        "author": "Test",
                        "context_window": 32000,
                        "endpoint": "test",
                    },
                    {
                        "id": "model_b",
                        "author": "Test",
                        "context_window": 32000,
                        "endpoint": "test",
                    },
                    {
                        "id": "model_c",
                        "author": "Test",
                        "context_window": 32000,
                        "endpoint": "test",
                    },
                ]
            },
            "tournaments": {
                "skill_1": {
                    "model_rankings": [
                        {"model_id": "model_a", "wins": 5, "rank": 1},
                        {"model_id": "model_b", "wins": 3, "rank": 2},
                        {"model_id": "model_c", "wins": 1, "rank": 3},
                    ]
                },
                "skill_2": {
                    "model_rankings": [
                        {"model_id": "model_b", "wins": 4, "rank": 1},
                        {"model_id": "model_c", "wins": 2, "rank": 2},
                        {"model_id": "model_a", "wins": 0, "rank": 3},
                    ]
                },
            },
            "ratings": {
                "skill_1": {
                    "model_ratings": {
                        # Only model_a has ratings, others will get default 1500
                        "model_a": {"mu": 1600.0, "sigma": 50.0}
                        # model_b and model_c missing -> will get default 1500
                    }
                },
                "skill_2": {
                    "model_ratings": {
                        # Only model_a has ratings, others will get default 1500
                        "model_a": {"mu": 1550.0, "sigma": 55.0}
                        # model_b and model_c missing -> will get default 1500
                    }
                },
            },
        }

        mock_selectbox.return_value = "model_a"

        show_models_page(same_rating_data)
        models_table = mock_dataframe.call_args_list[0][0][0]

        print("\nDEBUG: Same default rating scenario:")
        for _, row in models_table.iterrows():
            print(
                f"  {row['Model ID']}: best={row['Best Skill']}, worst={row['Worst Skill']}"
            )

        # Models with no rating data should both have same best/worst (both get 1500 default)
        model_b_row = models_table[models_table["Model ID"] == "model_b"].iloc[0]
        model_c_row = models_table[models_table["Model ID"] == "model_c"].iloc[0]

        # If they both get 1500 for all skills, they should have same best/worst
        # This might be the bug scenario!
        print(
            f"\nDEBUG: model_b best={model_b_row['Best Skill']}, worst={model_b_row['Worst Skill']}"
        )
        print(
            f"DEBUG: model_c best={model_c_row['Best Skill']}, worst={model_c_row['Worst Skill']}"
        )

        # BUG: Models with default ratings show same skill as both best AND worst
        assert (
            model_b_row["Best Skill"] == model_b_row["Worst Skill"]
        ), "BUG CONFIRMED: When model gets default rating for all skills, best and worst are the same!"
        assert (
            model_c_row["Best Skill"] == model_c_row["Worst Skill"]
        ), "BUG CONFIRMED: When model gets default rating for all skills, best and worst are the same!"

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_debug_rating_lookup_failure(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """Debug why the app isn't finding the real ratings and using 1500 default."""

        # This should reproduce the exact scenario from the user's data
        realistic_production_data = {
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
                            "ties": 0,
                            "rank": 1,
                        }
                    ]
                },
                "code_generation": {
                    "model_rankings": [
                        {
                            "model_id": "thedrummer/unslopnemo-12b",
                            "wins": 5,
                            "losses": 10,
                            "ties": 0,
                            "rank": 3,
                        }
                    ]
                },
                "hidden_messages": {
                    "model_rankings": [
                        {
                            "model_id": "thedrummer/unslopnemo-12b",
                            "wins": 8,
                            "losses": 7,
                            "ties": 0,
                            "rank": 2,
                        }
                    ]
                },
            },
            # HERE'S THE KEY: What data structure is the app actually getting?
            "ratings": {
                "harm_avoidance": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1652.83, "sigma": 64.0}
                    }
                },
                "code_generation": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1314.41, "sigma": 57.6}
                    }
                },
                "hidden_messages": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1520.0, "sigma": 55.0}
                    }
                },
            },
        }

        mock_selectbox.return_value = "thedrummer/unslopnemo-12b"

        # Let's trace what the app is actually doing
        print("\nDEBUG: Testing with realistic production-like data...")

        # Add some debugging to see what's being accessed
        def debug_get_call(obj, key, default=None):
            print(
                f"    DEBUG: .get('{key}') called, returning: {obj.get(key, default) if hasattr(obj, 'get') else default}"
            )
            return obj.get(key, default) if hasattr(obj, "get") else default

        # Monkey patch the data to trace access
        realistic_production_data["ratings"]

        show_models_page(realistic_production_data)
        models_table = mock_dataframe.call_args_list[0][0][0]

        print("\nDEBUG: Model ratings in table:")
        for _, row in models_table.iterrows():
            print(
                f"  {row['Model ID']}: best={row['Best Skill']}, worst={row['Worst Skill']}"
            )

        # Check if it's working correctly with our test data
        model_row = models_table.iloc[0]
        expected_best = "harm_avoidance"  # 1652.83 is highest
        expected_worst = "code_generation"  # 1314.41 is lowest

        if (
            model_row["Best Skill"] != expected_best
            or model_row["Worst Skill"] != expected_worst
        ):
            print("\nBUG DETECTED:")
            print(f"  Expected: best={expected_best}, worst={expected_worst}")
            print(
                f"  Actual: best={model_row['Best Skill']}, worst={model_row['Worst Skill']}"
            )

            # Let's debug what ratings the app is actually seeing
            print("\nDEBUG: Checking rating access...")
            model_id = "thedrummer/unslopnemo-12b"
            ratings = realistic_production_data["ratings"]

            for skill in ["harm_avoidance", "code_generation", "hidden_messages"]:
                skill_ratings = ratings.get(skill, {})
                model_rating = (
                    skill_ratings.get("model_ratings", {})
                    .get(model_id, {})
                    .get("mu", 1500)
                )
                print(
                    f"    {skill}: {model_rating} (from {skill_ratings.get('model_ratings', {}).get(model_id, 'MISSING')})"
                )
        else:
            print("✅ Test data works correctly - bug must be in real data structure")

    @patch("app.st.dataframe")
    @patch("app.st.header")
    @patch("app.st.selectbox")
    @patch("app.st.subheader")
    def test_model_only_in_one_tournament_bug(
        self, mock_subheader, mock_selectbox, mock_header, mock_dataframe
    ):
        """
        REAL BUG: Test when model only appears in tournament rankings for one skill.
        This causes both best and worst skill to be the same skill!
        """

        # This reproduces the actual bug scenario
        single_tournament_data = {
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
                            "ties": 0,
                            "rank": 1,
                        }
                    ]
                },
                "code_generation": {
                    "model_rankings": [
                        # MODEL IS MISSING FROM THIS TOURNAMENT! This is the bug!
                        {
                            "model_id": "some_other_model",
                            "wins": 5,
                            "losses": 10,
                            "ties": 0,
                            "rank": 1,
                        }
                    ]
                },
                "persuasiveness": {
                    "model_rankings": [
                        # MODEL IS MISSING FROM THIS TOURNAMENT TOO!
                        {
                            "model_id": "another_model",
                            "wins": 8,
                            "losses": 7,
                            "ties": 0,
                            "rank": 1,
                        }
                    ]
                },
            },
            "ratings": {
                "harm_avoidance": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1652.83, "sigma": 64.0}
                    }
                },
                "code_generation": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1314.41, "sigma": 57.6}
                    }  # Ratings exist!
                },
                "persuasiveness": {
                    "model_ratings": {
                        "thedrummer/unslopnemo-12b": {"mu": 1520.0, "sigma": 55.0}
                    }  # Ratings exist!
                },
            },
        }

        mock_selectbox.return_value = "thedrummer/unslopnemo-12b"

        show_models_page(single_tournament_data)
        models_table = mock_dataframe.call_args_list[0][0][0]

        model_row = models_table.iloc[0]

        print("\nDEBUG: Single tournament participation bug:")
        print("  Model participates in: harm_avoidance only")
        print(
            "  Ratings available for: harm_avoidance, code_generation, persuasiveness"
        )
        print(
            f"  Result - best={model_row['Best Skill']}, worst={model_row['Worst Skill']}"
        )

        # THE BUG: Both best and worst will be 'harm_avoidance' because the model
        # only appears in harm_avoidance tournament rankings, so the rating comparison
        # loop (lines 160-170) only runs for that one skill!
        assert (
            model_row["Best Skill"] == "harm_avoidance"
        ), "Best skill should be harm_avoidance (only tournament participated)"
        assert (
            model_row["Worst Skill"] == "harm_avoidance"
        ), "BUG: Worst skill also becomes harm_avoidance!"

        print("🐛 BUG CONFIRMED: Model only in one tournament makes best=worst skill!")
        print(
            "   Fix: Rating comparison should check ALL skills with ratings, not just tournament participation"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
