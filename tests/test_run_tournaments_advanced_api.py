"""Advanced tests for API integration and view building logic in run_tournaments.py."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from scripts.run_tournaments import JudgeExecutor, SwissTournament, TournamentMatch


class TestAdvancedAPIIntegration:
    """Tests targeting API integration and advanced judge execution paths."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("requests.post")
    def test_api_request_successful(self, mock_post):
        """Test successful API request flow."""
        executor = JudgeExecutor()

        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "I think Model A is better because it provides more detailed analysis. MY VOTE IS FOR: A"
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Test API request
        messages = [
            {"role": "system", "content": "You are an expert judge"},
            {"role": "user", "content": "Please evaluate these models"},
        ]

        result = executor._make_api_request("gpt-4", messages)

        # Verify API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "gpt-4"
        assert call_args[1]["json"]["messages"] == messages
        assert "Authorization" in call_args[1]["headers"]
        assert "Bearer " in call_args[1]["headers"]["Authorization"]

        # Verify result
        assert "choices" in result
        assert "Model A is better" in result["choices"][0]["message"]["content"]

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("requests.post")
    def test_api_request_http_error(self, mock_post):
        """Test API request with HTTP error."""
        executor = JudgeExecutor()

        # Mock HTTP error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("API Error")
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "test"}]

        # Should raise the HTTP error
        with pytest.raises(requests.HTTPError):
            executor._make_api_request("gpt-4", messages)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("requests.post")
    def test_api_request_invalid_response(self, mock_post):
        """Test API request with invalid response format."""
        executor = JudgeExecutor()

        # Mock response without choices
        mock_response = Mock()
        mock_response.json.return_value = {"error": "Invalid request"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "test"}]
        result = executor._make_api_request("gpt-4", messages)

        # Should return the invalid response (error handling is in calling code)
        assert result == {"error": "Invalid request"}

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_step_kind_final_part(self):
        """Test view building with step kind and final part."""
        executor = JudgeExecutor()

        conversations_data = {
            "conversations": [
                {
                    "metadata": {"model_id": "model_a", "skill_id": "skill_1", "eval_id": "eval_1"},
                    "messages": [
                        {"role": "user", "content": "Please solve this problem"},
                        {"role": "assistant", "content": "Here is my detailed solution"},
                    ],
                }
            ]
        }

        view_spec = [{"kind": "step", "id": "step_1", "part": "final"}]

        content = executor._build_view_content(view_spec, conversations_data, {}, "model_a", "skill_1", "eval_1")

        assert "Here is my detailed solution" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_step_kind_history_part(self):
        """Test view building with step kind and history part."""
        executor = JudgeExecutor()

        conversations_data = {
            "conversations": [
                {
                    "metadata": {"model_id": "model_b", "skill_id": "skill_2", "eval_id": "eval_2"},
                    "messages": [
                        {"role": "user", "content": "What is 2+2?"},
                        {"role": "assistant", "content": "2+2 equals 4"},
                        {"role": "user", "content": "Explain why"},
                        {"role": "assistant", "content": "Addition combines quantities"},
                    ],
                }
            ]
        }

        view_spec = [{"kind": "step", "id": "step_1", "part": "history"}]

        content = executor._build_view_content(view_spec, conversations_data, {}, "model_b", "skill_2", "eval_2")

        assert "user: What is 2+2?" in content
        assert "assistant: 2+2 equals 4" in content
        assert "user: Explain why" in content
        assert "assistant: Addition combines quantities" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_step_not_found(self):
        """Test view building when conversation is not found."""
        executor = JudgeExecutor()

        conversations_data = {
            "conversations": [
                {"metadata": {"model_id": "different_model", "skill_id": "skill_1", "eval_id": "eval_1"}, "messages": []}
            ]
        }

        view_spec = [{"kind": "step", "id": "step_missing", "part": "final"}]

        content = executor._build_view_content(
            view_spec, conversations_data, {}, "model_a", "skill_1", "eval_1"  # Different model - won't match
        )

        assert "[STEP_NOT_FOUND: step_missing]" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_no_final_response(self):
        """Test view building when conversation has insufficient messages."""
        executor = JudgeExecutor()

        conversations_data = {
            "conversations": [
                {
                    "metadata": {"model_id": "model_a", "skill_id": "skill_1", "eval_id": "eval_1"},
                    "messages": [
                        {"role": "user", "content": "Hello"}
                        # Missing assistant response
                    ],
                }
            ]
        }

        view_spec = [{"kind": "step", "id": "step_1", "part": "final"}]

        content = executor._build_view_content(view_spec, conversations_data, {}, "model_a", "skill_1", "eval_1")

        assert "[NO_FINAL_RESPONSE]" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_intermediary_kind(self):
        """Test view building with intermediary kind."""
        executor = JudgeExecutor()

        intermediaries_data = {
            "intermediaries": [
                {
                    "metadata": {
                        "judge_model_id": "judge_model",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "intermediary_id": "inter_1",
                    },
                    "messages": [
                        {"role": "user", "content": "Analyze this"},
                        {"role": "assistant", "content": "My analysis is complete"},
                    ],
                }
            ]
        }

        view_spec = [{"kind": "intermediary", "id": "inter_1", "part": "final"}]

        content = executor._build_view_content(view_spec, {}, intermediaries_data, "model_a", "skill_1", "eval_1")

        assert "My analysis is complete" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_intermediary_history(self):
        """Test view building with intermediary history."""
        executor = JudgeExecutor()

        intermediaries_data = {
            "intermediaries": [
                {
                    "metadata": {
                        "judge_model_id": "judge_model",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "intermediary_id": "inter_2",
                    },
                    "messages": [
                        {"role": "user", "content": "Evaluate this"},
                        {"role": "assistant", "content": "Step 1: Analysis"},
                        {"role": "user", "content": "Continue"},
                        {"role": "assistant", "content": "Step 2: Conclusion"},
                    ],
                }
            ]
        }

        view_spec = [{"kind": "intermediary", "id": "inter_2", "part": "history"}]

        content = executor._build_view_content(view_spec, {}, intermediaries_data, "model_a", "skill_1", "eval_1")

        assert "user: Evaluate this" in content
        assert "assistant: Step 1: Analysis" in content
        assert "user: Continue" in content
        assert "assistant: Step 2: Conclusion" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_intermediary_not_found(self):
        """Test view building when intermediary is not found."""
        executor = JudgeExecutor()

        intermediaries_data = {
            "intermediaries": [
                {
                    "metadata": {
                        "judge_model_id": "judge_model",
                        "skill_id": "different_skill",
                        "eval_id": "eval_1",
                        "intermediary_id": "inter_1",
                    }
                }
            ]
        }

        view_spec = [{"kind": "intermediary", "id": "missing_inter", "part": "final"}]

        content = executor._build_view_content(view_spec, {}, intermediaries_data, "model_a", "skill_1", "eval_1")

        assert "[INTERMEDIARY_NOT_FOUND: missing_inter]" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_intermediary_no_response(self):
        """Test view building when intermediary has no messages."""
        executor = JudgeExecutor()

        intermediaries_data = {
            "intermediaries": [
                {
                    "metadata": {
                        "judge_model_id": "judge_model",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "intermediary_id": "inter_1",
                    },
                    "messages": [],  # No messages
                }
            ]
        }

        view_spec = [{"kind": "intermediary", "id": "inter_1", "part": "final"}]

        content = executor._build_view_content(view_spec, {}, intermediaries_data, "model_a", "skill_1", "eval_1")

        assert "[NO_INTERMEDIARY_RESPONSE]" in content

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_view_building_multiple_parts(self):
        """Test view building with multiple view specifications."""
        executor = JudgeExecutor()

        conversations_data = {
            "conversations": [
                {
                    "metadata": {"model_id": "model_a", "skill_id": "skill_1", "eval_id": "eval_1"},
                    "messages": [{"role": "user", "content": "Question"}, {"role": "assistant", "content": "Answer"}],
                }
            ]
        }

        intermediaries_data = {
            "intermediaries": [
                {
                    "metadata": {
                        "judge_model_id": "judge_model",
                        "skill_id": "skill_1",
                        "eval_id": "eval_1",
                        "intermediary_id": "inter_1",
                    },
                    "messages": [{"role": "user", "content": "Analyze"}, {"role": "assistant", "content": "Analysis result"}],
                }
            ]
        }

        view_spec = [
            {"kind": "step", "id": "step_1", "part": "final"},
            {"kind": "intermediary", "id": "inter_1", "part": "final"},
        ]

        content = executor._build_view_content(
            view_spec, conversations_data, intermediaries_data, "model_a", "skill_1", "eval_1"
        )

        assert "Answer" in content
        assert "Analysis result" in content


class TestAdvancedJudgeExecution:
    """Tests for advanced judge execution flows."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("requests.post")
    def test_judge_execution_with_caching(self, mock_post):
        """Test complete judge execution flow with caching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = JudgeExecutor(cache_dir=Path(temp_dir))

            # Mock API response
            mock_response = Mock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Model A provides better reasoning. MY VOTE IS FOR: A"}}]
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            # Create test data
            match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")

            judge = {"id": "gpt-4", "name": "GPT-4 Judge"}

            eval_config = {
                "judge": {
                    "view": {
                        "A": [{"kind": "step", "id": "step_1", "part": "final"}],
                        "B": [{"kind": "step", "id": "step_1", "part": "final"}],
                    },
                    "prompt": "Compare Model A: {{A}} vs Model B: {{B}}",
                    "system": "You are an expert judge",
                }
            }

            conversations_data = {
                "conversations": [
                    {
                        "metadata": {"model_id": "model_a", "skill_id": "skill_1", "eval_id": "eval_1"},
                        "messages": [
                            {"role": "user", "content": "Solve this"},
                            {"role": "assistant", "content": "Solution A"},
                        ],
                    },
                    {
                        "metadata": {"model_id": "model_b", "skill_id": "skill_1", "eval_id": "eval_1"},
                        "messages": [
                            {"role": "user", "content": "Solve this"},
                            {"role": "assistant", "content": "Solution B"},
                        ],
                    },
                ]
            }

            intermediaries_data = {}

            # First execution should call API
            vote1, messages1, explanation1 = executor.execute_judge_decision(
                match, judge, eval_config, conversations_data, intermediaries_data
            )

            assert vote1 == "A"
            assert "Model A provides better reasoning" in explanation1
            assert mock_post.call_count == 1

            # Second execution should use cache
            vote2, messages2, explanation2 = executor.execute_judge_decision(
                match, judge, eval_config, conversations_data, intermediaries_data
            )

            assert vote2 == "A"
            assert vote1 == vote2
            assert explanation1 == explanation2
            # API should not be called again
            assert mock_post.call_count == 1

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("requests.post")
    def test_judge_execution_api_error_handling(self, mock_post):
        """Test judge execution with API errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = JudgeExecutor(cache_dir=Path(temp_dir))

            # Mock API error
            mock_post.side_effect = requests.HTTPError("API Rate Limited")

            match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
            judge = {"id": "gpt-4", "name": "GPT-4 Judge"}
            eval_config = {
                "judge": {"view": {"A": [], "B": []}, "prompt": "Compare {{A}} vs {{B}}", "system": "You are a judge"}
            }

            with patch("builtins.print"):  # Suppress error prints
                vote, messages, explanation = executor.execute_judge_decision(match, judge, eval_config, {}, {})

            # Should default to TIE on error
            assert vote == "TIE"
            assert "[JUDGE_ERROR:" in explanation
            assert "API Rate Limited" in explanation

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("requests.post")
    def test_judge_execution_invalid_api_response(self, mock_post):
        """Test judge execution with invalid API response."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = JudgeExecutor(cache_dir=Path(temp_dir))

            # Mock invalid response (no choices)
            mock_response = Mock()
            mock_response.json.return_value = {"error": "No choices"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
            judge = {"id": "gpt-4", "name": "GPT-4 Judge"}
            eval_config = {"judge": {"view": {"A": [], "B": []}, "prompt": "Compare {{A}} vs {{B}}"}}

            with patch("builtins.print"):  # Suppress error prints
                vote, messages, explanation = executor.execute_judge_decision(match, judge, eval_config, {}, {})

            # Should handle invalid response gracefully
            assert vote == "TIE"
            assert "[JUDGE_ERROR:" in explanation
