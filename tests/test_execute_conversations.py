"""Comprehensive tests for execute_conversations.py to achieve 90%+ coverage."""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
import requests

from scripts.execute_conversations import ConversationExecutor, cleanup_stale_cache, execute_all_conversations, main


class TestConversationExecutorInit:
    """Test ConversationExecutor initialization and basic functionality."""

    def test_init_with_api_key(self):
        """Test initialization with valid API key."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-api-key"}):
            with tempfile.TemporaryDirectory() as temp_dir:
                cache_dir = Path(temp_dir) / "conversations"
                intermediary_dir = Path(temp_dir) / "intermediaries"

                executor = ConversationExecutor(cache_dir=cache_dir, intermediary_cache_dir=intermediary_dir)

                assert executor.api_key == "test-api-key"
                assert executor.base_url == "https://openrouter.ai/api/v1/chat/completions"
                assert executor.cache_dir == cache_dir
                assert executor.intermediary_cache_dir == intermediary_dir
                assert cache_dir.exists()
                assert intermediary_dir.exists()
                assert executor.min_interval == 0.1
                assert executor.last_request_time == 0

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY not found"):
                ConversationExecutor()

    def test_init_default_paths(self):
        """Test initialization with default paths."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            with patch("pathlib.Path.mkdir") as mock_mkdir:
                executor = ConversationExecutor()

                assert executor.cache_dir == Path("data/conversations")
                assert executor.intermediary_cache_dir == Path("data/intermediaries")
                assert mock_mkdir.call_count >= 2


class TestRateLimiting:
    """Test rate limiting functionality."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_rate_limit_enforcement(self):
        """Test rate limiting enforces minimum interval."""
        executor = ConversationExecutor()

        # Mock time to control timing
        with patch("time.time") as mock_time, patch("time.sleep") as mock_sleep:
            # First request - set initial time
            mock_time.return_value = 1.0
            executor._rate_limit()
            mock_sleep.assert_not_called()
            assert executor.last_request_time == 1.0

            # Second request too soon - should sleep
            # current_time - last_request_time = 1.05 - 1.0 = 0.05 < 0.1, so sleep(0.05)
            mock_time.side_effect = [1.05, 1.15]  # first call gets current, second call sets new last_time
            executor._rate_limit()
            # Check that sleep was called with approximately the right value (floating point precision)
            mock_sleep.assert_called_once()
            sleep_arg = mock_sleep.call_args[0][0]
            assert abs(sleep_arg - 0.05) < 1e-10

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_rate_limit_no_sleep_when_enough_time_passed(self):
        """Test no sleep when enough time has passed."""
        executor = ConversationExecutor()
        executor.last_request_time = 1.0

        with patch("time.time") as mock_time, patch("time.sleep") as mock_sleep:
            # Simulate enough time has passed
            mock_time.side_effect = [1.2, 1.2]  # elapsed=0.2, more than min_interval
            executor._rate_limit()
            mock_sleep.assert_not_called()


class TestCacheKeyGeneration:
    """Test cache key generation logic."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_generate_cache_key_with_file_hash(self):
        """Test cache key generation using file hash."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor()

            # Create test file
            test_file = Path(temp_dir) / "test_eval.json"
            test_content = b"test content for hashing"
            with open(test_file, "wb") as f:
                f.write(test_content)

            eval_data = {
                "id": "test_eval",
                "_metadata": {"file_path": str(test_file)},
                "chain": [{"id": "step1", "prompt": "test"}],
            }

            key = executor._generate_cache_key("test_model", eval_data)

            # Should be 16-character hash
            assert len(key) == 16
            assert isinstance(key, str)

            # Should be consistent
            key2 = executor._generate_cache_key("test_model", eval_data)
            assert key == key2

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_generate_cache_key_fallback_to_content_hash(self):
        """Test cache key generation falls back to content hash when no file."""
        executor = ConversationExecutor()

        eval_data = {
            "id": "test_eval",
            "_metadata": {"file_path": "/nonexistent/file.json"},
            "chain": [{"id": "step1", "prompt": "test"}],
        }

        key = executor._generate_cache_key("test_model", eval_data)

        assert len(key) == 16
        assert isinstance(key, str)

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_generate_cache_key_without_metadata(self):
        """Test cache key generation without metadata."""
        executor = ConversationExecutor()

        eval_data = {"id": "test_eval", "chain": [{"id": "step1", "prompt": "test"}]}

        key = executor._generate_cache_key("test_model", eval_data)

        assert len(key) == 16
        assert isinstance(key, str)


class TestCacheOperations:
    """Test cache loading and saving operations."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_cache_path_generation(self):
        """Test cache path generation handles special characters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            # Test model ID with slashes and colons
            path = executor._get_cache_path("skill_1", "eval_1", "company/model:version", "cache123")

            expected_filename = "eval_1_company_model_version_cache123.json"
            assert path.name == expected_filename
            assert path.parent.name == "skill_1"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_save_and_load_cache_success(self):
        """Test successful cache save and load."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            cache_path = Path(temp_dir) / "skill_1" / "test_cache.json"
            test_data = {"messages": [], "metadata": {"test": True}}

            # Save to cache
            executor._save_to_cache(cache_path, test_data)
            assert cache_path.exists()

            # Load from cache
            loaded_data = executor._load_from_cache(cache_path)
            assert loaded_data == test_data

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_load_cache_missing_file(self):
        """Test loading from non-existent cache file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            missing_path = Path(temp_dir) / "missing.json"
            result = executor._load_from_cache(missing_path)
            assert result is None

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_load_cache_corrupted_file(self):
        """Test loading corrupted cache file removes it."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            corrupted_path = Path(temp_dir) / "corrupted.json"
            with open(corrupted_path, "w") as f:
                f.write("{invalid json content")

            result = executor._load_from_cache(corrupted_path)
            assert result is None
            assert not corrupted_path.exists()  # Should be removed

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_load_cache_os_error(self):
        """Test loading cache handles OS errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            cache_path = Path(temp_dir) / "test.json"
            with open(cache_path, "w") as f:
                json.dump({"test": "data"}, f)

            # Mock open to raise OSError
            with patch("builtins.open", side_effect=OSError("Permission denied")):
                result = executor._load_from_cache(cache_path)
                assert result is None


class TestAPIRequests:
    """Test API request functionality."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_make_api_request_success(self, mock_post):
        """Test successful API request."""
        executor = ConversationExecutor()

        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch.object(executor, "_rate_limit") as mock_rate_limit:
            messages = [{"role": "user", "content": "test"}]
            result = executor._make_api_request("test-model", messages)

            mock_rate_limit.assert_called_once()
            mock_post.assert_called_once()

            # Check request parameters
            call_args = mock_post.call_args
            assert call_args[0][0] == executor.base_url
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"
            assert call_args[1]["json"]["model"] == "test-model"
            assert call_args[1]["json"]["messages"] == messages

            assert result["choices"][0]["message"]["content"] == "Test response"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_make_api_request_http_error(self, mock_post):
        """Test API request with HTTP error."""
        executor = ConversationExecutor()

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("API Error")
        mock_post.return_value = mock_response

        with patch.object(executor, "_rate_limit"):
            with pytest.raises(requests.HTTPError):
                executor._make_api_request("test-model", [])


class TestFileReferences:
    """Test file reference resolution."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_resolve_file_references_success(self):
        """Test successful file reference resolution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor()

            test_file = Path(temp_dir) / "test.txt"
            with open(test_file, "w") as f:
                f.write("File content here")

            text = f"Before ${{file:{test_file}}} After"
            result = executor._resolve_file_references(text)

            assert result == "Before File content here After"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_resolve_file_references_missing_file(self):
        """Test file reference resolution with missing file."""
        executor = ConversationExecutor()

        text = "Before ${file:/nonexistent/file.txt} After"
        result = executor._resolve_file_references(text)

        assert "[FILE_ERROR:" in result
        assert "nonexistent" in result

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_resolve_file_references_multiple(self):
        """Test resolving multiple file references."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor()

            file1 = Path(temp_dir) / "file1.txt"
            file2 = Path(temp_dir) / "file2.txt"

            with open(file1, "w") as f:
                f.write("Content 1")
            with open(file2, "w") as f:
                f.write("Content 2")

            text = f"${{file:{file1}}} and ${{file:{file2}}}"
            result = executor._resolve_file_references(text)

            assert result == "Content 1 and Content 2"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_resolve_file_references_no_references(self):
        """Test text without file references remains unchanged."""
        executor = ConversationExecutor()

        text = "No file references here"
        result = executor._resolve_file_references(text)

        assert result == text


class TestStepInputPreparation:
    """Test step input preparation and variable substitution."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_prepare_step_inputs_basic(self):
        """Test basic step input preparation."""
        executor = ConversationExecutor()

        step = {"prompt": "Basic prompt without variables"}
        result = executor._prepare_step_inputs(step, [])

        assert result == "Basic prompt without variables"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_prepare_step_inputs_with_file_references(self):
        """Test step input preparation with file references."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor()

            test_file = Path(temp_dir) / "prompt.txt"
            with open(test_file, "w") as f:
                f.write("File-based prompt")

            step = {"prompt": f"${{file:{test_file}}}"}
            result = executor._prepare_step_inputs(step, [])

            assert result == "File-based prompt"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_prepare_step_inputs_with_custom_inputs(self):
        """Test step input preparation with custom input variables."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor()

            input_file = Path(temp_dir) / "input.txt"
            with open(input_file, "w") as f:
                f.write("Dynamic input")

            step = {"prompt": "Use this {{variable}} in the prompt", "inputs": {"variable": f"${{file:{input_file}}}"}}

            result = executor._prepare_step_inputs(step, [])

            assert result == "Use this Dynamic input in the prompt"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_prepare_step_inputs_multiple_variables(self):
        """Test step input preparation with multiple variables."""
        executor = ConversationExecutor()

        step = {"prompt": "{{var1}} and {{var2}} together", "inputs": {"var1": "Value1", "var2": "Value2"}}

        result = executor._prepare_step_inputs(step, [])

        assert result == "Value1 and Value2 together"


class TestIntermediaryExecution:
    """Test intermediary execution functionality."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_get_intermediary_cache_path(self):
        """Test intermediary cache path generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(intermediary_cache_dir=Path(temp_dir))

            path = executor._get_intermediary_cache_path("skill_1", "eval_1", "inter_1", "judge/model:v1", "cache123")

            expected_filename = "eval_1_inter_1_judge_model_v1_cache123.json"
            assert path.name == expected_filename
            assert path.parent.name == "skill_1"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_substitute_intermediary_variables_final(self):
        """Test intermediary variable substitution with 'final' part."""
        executor = ConversationExecutor()

        intermediary = {"prompt": "Analyze this: {{result}}", "from": [{"step": "step1", "part": "final", "as": "result"}]}

        conversation_result = {
            "messages": [{"role": "user", "content": "Question"}, {"role": "assistant", "content": "Final answer"}]
        }

        result = executor._substitute_intermediary_variables(intermediary, conversation_result)

        assert result == "Analyze this: Final answer"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_substitute_intermediary_variables_history(self):
        """Test intermediary variable substitution with 'history' part."""
        executor = ConversationExecutor()

        intermediary = {
            "prompt": "Review this conversation: {{history}}",
            "from": [{"step": "step1", "part": "history", "as": "history"}],
        }

        conversation_result = {
            "messages": [{"role": "user", "content": "Question"}, {"role": "assistant", "content": "Answer"}]
        }

        result = executor._substitute_intermediary_variables(intermediary, conversation_result)

        assert result == "Review this conversation: user: Question\nassistant: Answer"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_substitute_intermediary_variables_no_content(self):
        """Test intermediary variable substitution with insufficient messages."""
        executor = ConversationExecutor()

        intermediary = {"prompt": "Analyze: {{result}}", "from": [{"step": "step1", "part": "final", "as": "result"}]}

        conversation_result = {"messages": [{"role": "user", "content": "Only question"}]}

        result = executor._substitute_intermediary_variables(intermediary, conversation_result)

        assert "[NO_CONTENT_FOUND]" in result

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_substitute_intermediary_variables_unknown_part(self):
        """Test intermediary variable substitution with unknown part type."""
        executor = ConversationExecutor()

        intermediary = {"prompt": "Process: {{data}}", "from": [{"step": "step1", "part": "unknown", "as": "data"}]}

        conversation_result = {"messages": []}

        result = executor._substitute_intermediary_variables(intermediary, conversation_result)

        assert "[UNKNOWN_PART: unknown]" in result

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_execute_intermediary_success(self, mock_post):
        """Test successful intermediary execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(intermediary_cache_dir=Path(temp_dir))

            # Mock API response
            mock_response = Mock()
            mock_response.json.return_value = {"choices": [{"message": {"content": "Intermediary analysis complete"}}]}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            intermediary = {
                "id": "inter_1",
                "prompt": "Analyze this result: {{output}}",
                "from": [{"step": "step1", "part": "final", "as": "output"}],
            }

            conversation_result = {
                "metadata": {"cache_key": "conv123"},
                "messages": [{"role": "user", "content": "Question"}, {"role": "assistant", "content": "Model response"}],
            }

            judge_model = {"id": "judge-model"}

            with patch("builtins.print"):
                result = executor.execute_intermediary(intermediary, conversation_result, judge_model, "skill_1", "eval_1")

            assert result["metadata"]["intermediary_id"] == "inter_1"
            assert result["metadata"]["judge_model_id"] == "judge-model"
            assert result["execution_info"]["status"] == "completed"
            assert len(result["messages"]) == 2  # user + assistant
            assert result["messages"][1]["content"] == "Intermediary analysis complete"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_execute_intermediary_cached(self, mock_post):
        """Test intermediary execution uses cache when available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(intermediary_cache_dir=Path(temp_dir))

            # Create cached result
            cache_data = {
                "metadata": {"intermediary_id": "inter_1"},
                "messages": [{"role": "assistant", "content": "Cached result"}],
                "execution_info": {"status": "completed"},
            }

            intermediary = {"id": "inter_1", "prompt": "Test"}
            conversation_result = {"metadata": {"cache_key": "conv123"}, "messages": []}
            judge_model = {"id": "judge-model"}

            # Mock cache loading
            with patch.object(executor, "_load_from_cache", return_value=cache_data):
                with patch("builtins.print"):
                    result = executor.execute_intermediary(intermediary, conversation_result, judge_model, "skill_1", "eval_1")

            assert result == cache_data
            mock_post.assert_not_called()  # Should not make API call

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_execute_intermediary_api_error(self, mock_post):
        """Test intermediary execution handles API errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(intermediary_cache_dir=Path(temp_dir))

            mock_post.side_effect = requests.HTTPError("API Error")

            intermediary = {"id": "inter_1", "prompt": "Test"}
            conversation_result = {"metadata": {"cache_key": "conv123"}, "messages": []}
            judge_model = {"id": "judge-model"}

            with patch("builtins.print"):
                result = executor.execute_intermediary(intermediary, conversation_result, judge_model, "skill_1", "eval_1")

            assert result["metadata"]["error"] == "API Error"
            assert result["execution_info"]["status"] == "failed"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_execute_intermediary_invalid_response(self, mock_post):
        """Test intermediary execution handles invalid API response."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(intermediary_cache_dir=Path(temp_dir))

            # Mock invalid response
            mock_response = Mock()
            mock_response.json.return_value = {"error": "No choices"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            intermediary = {"id": "inter_1", "prompt": "Test"}
            conversation_result = {"metadata": {"cache_key": "conv123"}, "messages": []}
            judge_model = {"id": "judge-model"}

            with patch("builtins.print"):
                result = executor.execute_intermediary(intermediary, conversation_result, judge_model, "skill_1", "eval_1")

            assert result["execution_info"]["status"] == "failed"
            assert "Invalid API response" in result["metadata"]["error"]


class TestConversationExecution:
    """Test main conversation execution functionality."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_execute_conversation_success(self, mock_post):
        """Test successful conversation execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            # Mock API responses for each step
            responses = [
                Mock(json=lambda: {"choices": [{"message": {"content": "Step 1 response"}}]}),
                Mock(json=lambda: {"choices": [{"message": {"content": "Step 2 response"}}]}),
            ]
            for response in responses:
                response.raise_for_status.return_value = None
            mock_post.side_effect = responses

            model = {"id": "test-model", "slug": "test", "author": "test-author"}
            eval_data = {
                "id": "eval_1",
                "name": "Test Eval",
                "chain": [{"id": "step1", "prompt": "First prompt"}, {"id": "step2", "prompt": "Second prompt"}],
            }

            with patch("builtins.print"):
                result = executor.execute_conversation(model, "skill_1", eval_data)

            assert result["metadata"]["model_id"] == "test-model"
            assert result["metadata"]["eval_id"] == "eval_1"
            assert result["metadata"]["step_count"] == 2
            assert result["metadata"]["message_count"] == 4  # 2 user + 2 assistant
            assert result["execution_info"]["status"] == "completed"
            assert len(result["messages"]) == 4

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_execute_conversation_cached(self):
        """Test conversation execution uses cache when available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            cached_data = {
                "metadata": {"model_id": "test-model", "eval_id": "eval_1"},
                "messages": [],
                "execution_info": {"status": "completed"},
            }

            model = {"id": "test-model"}
            eval_data = {"id": "eval_1", "name": "Test Eval", "chain": []}

            with patch.object(executor, "_load_from_cache", return_value=cached_data):
                with patch("builtins.print"):
                    result = executor.execute_conversation(model, "skill_1", eval_data)

            assert result == cached_data

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_execute_conversation_api_error(self, mock_post):
        """Test conversation execution handles API errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            mock_post.side_effect = requests.HTTPError("API Error")

            model = {"id": "test-model"}
            eval_data = {"id": "eval_1", "name": "Test Eval", "chain": [{"id": "step1", "prompt": "Test prompt"}]}

            with patch("builtins.print"):
                result = executor.execute_conversation(model, "skill_1", eval_data)

            assert result["metadata"]["error"] == "API Error"
            assert result["execution_info"]["status"] == "failed"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("requests.post")
    def test_execute_conversation_invalid_api_response(self, mock_post):
        """Test conversation execution handles invalid API response."""
        with tempfile.TemporaryDirectory() as temp_dir:
            executor = ConversationExecutor(cache_dir=Path(temp_dir))

            # Mock invalid response
            mock_response = Mock()
            mock_response.json.return_value = {"error": "No choices"}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            model = {"id": "test-model"}
            eval_data = {"id": "eval_1", "name": "Test Eval", "chain": [{"id": "step1", "prompt": "Test prompt"}]}

            with patch("builtins.print"):
                result = executor.execute_conversation(model, "skill_1", eval_data)

            assert result["execution_info"]["status"] == "failed"
            assert "Invalid API response" in result["metadata"]["error"]


class TestStaleCache:
    """Test stale cache cleanup functionality."""

    def test_cleanup_stale_cache_conversations(self):
        """Test cleanup of stale conversation cache entries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "conversations"
            intermediary_dir = Path(temp_dir) / "intermediaries"
            cache_dir.mkdir(parents=True)

            skill_dir = cache_dir / "skill_1"
            skill_dir.mkdir()

            # Create cache files that should be removed (no matching models)
            stale_cache1 = skill_dir / "eval_1_old_model_hash1.json"
            stale_cache2 = skill_dir / "eval_2_another_old_hash2.json"

            stale_cache1.touch()
            stale_cache2.touch()

            models = [{"id": "current_model"}]  # Only this model exists
            judges = [{"id": "judge1"}]

            with patch("builtins.print"):
                cleanup_stale_cache(models, judges, cache_dir, intermediary_dir)

            # All stale caches should be removed since no models match
            assert not stale_cache1.exists()
            assert not stale_cache2.exists()

    def test_cleanup_stale_cache_intermediaries(self):
        """Test cleanup of stale intermediary cache entries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "conversations"
            intermediary_dir = Path(temp_dir) / "intermediaries"
            intermediary_dir.mkdir(parents=True)

            skill_dir = intermediary_dir / "skill_1"
            skill_dir.mkdir()

            # Create intermediary cache files that should be removed (no matching judges)
            stale_cache1 = skill_dir / "eval_1_inter_1_old_judge_hash1.json"
            stale_cache2 = skill_dir / "eval_2_inter_2_another_judge_hash2.json"

            stale_cache1.touch()
            stale_cache2.touch()

            models = [{"id": "model1"}]
            judges = [{"id": "current_judge"}]  # Only this judge exists

            with patch("builtins.print"):
                cleanup_stale_cache(models, judges, cache_dir, intermediary_dir)

            # All stale caches should be removed since no judges match
            assert not stale_cache1.exists()
            assert not stale_cache2.exists()

    def test_cleanup_stale_cache_no_directories(self):
        """Test cleanup when cache directories don't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "nonexistent_cache"
            intermediary_dir = Path(temp_dir) / "nonexistent_intermediary"

            models = [{"id": "model1"}]
            judges = [{"id": "judge1"}]

            # Should complete without error
            with patch("builtins.print"):
                cleanup_stale_cache(models, judges, cache_dir, intermediary_dir)

    def test_cleanup_stale_cache_underscore_fallback(self):
        """Test cleanup properly removes files when no match is found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "conversations"
            cache_dir.mkdir(parents=True)

            skill_dir = cache_dir / "skill_1"
            skill_dir.mkdir()

            # Create cache files that should be removed
            stale_cache = skill_dir / "eval_1_nonexistent_model_hash1.json"
            stale_cache.touch()

            models = [{"id": "different_model"}]  # No match for nonexistent/model
            judges = []

            with patch("builtins.print"):
                cleanup_stale_cache(models, judges, cache_dir, Path(temp_dir) / "intermediaries")

            # Should remove stale cache since no model matches
            assert not stale_cache.exists()
