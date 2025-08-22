"""Tests for fetch_openrouter_models.py script."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from scripts.fetch_openrouter_models import OpenRouterModelsFetcher, main


class TestOpenRouterModelsFetcher:
    """Test OpenRouter models fetching and filtering functionality."""

    @pytest.fixture
    def mock_openrouter_response(self):
        """Mock OpenRouter API response with test models."""
        return {
            "data": [
                {
                    "id": "openai/gpt-4-turbo",
                    "name": "GPT-4 Turbo",
                    "description": "GPT-4 Turbo model",
                    "pricing": {"prompt": 0.01, "completion": 0.03},
                    "context_length": 128000,
                    "architecture": {"modality": "text", "tokenizer": "cl100k_base"},
                    "top_provider": {"max_completion_tokens": 4096},
                    "per_request_limits": None,
                },
                {
                    "id": "anthropic/claude-3-5-sonnet-20241022",
                    "name": "Claude 3.5 Sonnet",
                    "description": "Claude 3.5 Sonnet model",
                    "pricing": {"prompt": 0.003, "completion": 0.015},
                    "context_length": 200000,
                    "architecture": {"modality": "text", "tokenizer": "claude"},
                    "top_provider": {"max_completion_tokens": 8192},
                    "per_request_limits": None,
                },
                {
                    "id": "thedrummer/unslopnemo-12b",
                    "name": "UnslopNemo 12B",
                    "description": "UnslopNemo 12B model",
                    "pricing": {"prompt": 0.0001, "completion": 0.0001},
                    "context_length": 32768,
                    "architecture": {"modality": "text", "tokenizer": "llama"},
                    "top_provider": {"max_completion_tokens": 4000000},
                    "per_request_limits": None,
                },
                {
                    "id": "some/other-model",
                    "name": "Other Model",
                    "description": "A model not in our pools",
                    "pricing": {"prompt": 0.005, "completion": 0.01},
                    "context_length": 8192,
                    "architecture": {"modality": "text", "tokenizer": "gpt2"},
                    "top_provider": {"max_completion_tokens": 2048},
                    "per_request_limits": None,
                },
            ]
        }

    @pytest.fixture
    def mock_models_data(self):
        """Mock loaded models data."""
        return {
            "models": [
                {"id": "openai/gpt-4-turbo", "author": "OpenAI", "slug": "gpt-4-turbo"},
                {
                    "id": "thedrummer/unslopnemo-12b",
                    "author": "TheDrummer",
                    "slug": "unslopnemo-12b",
                },
            ]
        }

    @pytest.fixture
    def mock_judges_data(self):
        """Mock loaded judges data."""
        return {
            "models": [
                {
                    "id": "anthropic/claude-3-5-sonnet-20241022",
                    "author": "Anthropic",
                    "slug": "claude-3-5-sonnet",
                },
            ]
        }

    def test_fetch_openrouter_models_success(self, mock_openrouter_response):
        """Test successful fetching of OpenRouter models."""
        fetcher = OpenRouterModelsFetcher()

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_openrouter_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = fetcher.fetch_openrouter_models()

            assert result == mock_openrouter_response
            mock_get.assert_called_once_with(
                "https://openrouter.ai/api/v1/models",
                headers={"HTTP-Referer": "https://github.com/anthropics/afbench"},
                timeout=30,
            )

    def test_fetch_openrouter_models_request_failure(self):
        """Test handling of request failures."""
        fetcher = OpenRouterModelsFetcher()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")

            with pytest.raises(requests.RequestException, match="Network error"):
                fetcher.fetch_openrouter_models()

    def test_fetch_openrouter_models_http_error(self):
        """Test handling of HTTP errors."""
        fetcher = OpenRouterModelsFetcher()

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "404 Not Found"
            )
            mock_get.return_value = mock_response

            with pytest.raises(requests.HTTPError, match="404 Not Found"):
                fetcher.fetch_openrouter_models()

    def test_get_model_ids_from_pools(self, mock_models_data, mock_judges_data):
        """Test extraction of model IDs from loaded pools."""
        fetcher = OpenRouterModelsFetcher()

        model_ids = fetcher.get_model_ids_from_pools(mock_models_data, mock_judges_data)

        expected_ids = {
            "openai/gpt-4-turbo",
            "thedrummer/unslopnemo-12b",
            "anthropic/claude-3-5-sonnet-20241022",
        }
        assert model_ids == expected_ids

    def test_get_model_ids_empty_pools(self):
        """Test extraction with empty model pools."""
        fetcher = OpenRouterModelsFetcher()

        empty_models = {"models": []}
        empty_judges = {"models": []}

        model_ids = fetcher.get_model_ids_from_pools(empty_models, empty_judges)

        assert model_ids == set()

    def test_filter_openrouter_models(self, mock_openrouter_response):
        """Test filtering OpenRouter models to only include those in our pools."""
        fetcher = OpenRouterModelsFetcher()

        pool_model_ids = {"openai/gpt-4-turbo", "anthropic/claude-3-5-sonnet-20241022"}

        filtered = fetcher.filter_openrouter_models(
            mock_openrouter_response, pool_model_ids
        )

        # Should maintain same structure but only include matching models
        assert "data" in filtered
        assert len(filtered["data"]) == 2

        filtered_ids = {model["id"] for model in filtered["data"]}
        assert filtered_ids == pool_model_ids

    def test_filter_openrouter_models_no_matches(self, mock_openrouter_response):
        """Test filtering when no models match our pools."""
        fetcher = OpenRouterModelsFetcher()

        pool_model_ids = {"non/existent-model"}

        filtered = fetcher.filter_openrouter_models(
            mock_openrouter_response, pool_model_ids
        )

        assert "data" in filtered
        assert len(filtered["data"]) == 0

    def test_process_models_integration(
        self, mock_openrouter_response, mock_models_data, mock_judges_data
    ):
        """Test the full processing pipeline."""
        fetcher = OpenRouterModelsFetcher()

        with patch.object(
            fetcher, "fetch_openrouter_models", return_value=mock_openrouter_response
        ):
            full_data, filtered_data = fetcher.process_models(
                mock_models_data, mock_judges_data
            )

            # Full data should be unchanged
            assert full_data == mock_openrouter_response

            # Filtered data should only contain models in our pools
            expected_model_ids = {
                "openai/gpt-4-turbo",
                "thedrummer/unslopnemo-12b",
                "anthropic/claude-3-5-sonnet-20241022",
            }
            filtered_ids = {model["id"] for model in filtered_data["data"]}
            assert filtered_ids == expected_model_ids


class TestMain:
    """Test the main function that integrates with Snakemake."""

    def test_main_success(self):
        """Test successful execution of main function."""
        mock_models_data = {"models": [{"id": "openai/gpt-4-turbo"}]}
        mock_judges_data = {"models": [{"id": "anthropic/claude-3-5-sonnet-20241022"}]}
        mock_openrouter_data = {
            "data": [
                {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo"},
                {"id": "anthropic/claude-3-5-sonnet-20241022", "name": "Claude 3.5"},
            ]
        }
        mock_filtered_data = {
            "data": [
                {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo"},
                {"id": "anthropic/claude-3-5-sonnet-20241022", "name": "Claude 3.5"},
            ]
        }

        # Mock snakemake object
        mock_snakemake = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_models = Path(temp_dir) / "models.json"
            temp_judges = Path(temp_dir) / "judges.json"
            temp_full = Path(temp_dir) / "full.json"
            temp_filtered = Path(temp_dir) / "filtered.json"

            # Write mock input files
            with open(temp_models, "w") as f:
                json.dump(mock_models_data, f)
            with open(temp_judges, "w") as f:
                json.dump(mock_judges_data, f)

            # Configure mock snakemake paths
            mock_snakemake.input.models = str(temp_models)
            mock_snakemake.input.judges = str(temp_judges)
            mock_snakemake.output = [str(temp_full), str(temp_filtered)]

            with patch(
                "scripts.fetch_openrouter_models.OpenRouterModelsFetcher"
            ) as mock_fetcher_class:
                mock_fetcher = Mock()
                mock_fetcher.process_models.return_value = (
                    mock_openrouter_data,
                    mock_filtered_data,
                )
                mock_fetcher_class.return_value = mock_fetcher

                # Inject snakemake object into the module's globals
                import scripts.fetch_openrouter_models as fetch_module

                fetch_module.snakemake = mock_snakemake

                try:
                    with patch("builtins.print") as mock_print:
                        main()
                finally:
                    # Clean up
                    if hasattr(fetch_module, "snakemake"):
                        delattr(fetch_module, "snakemake")

                # Verify fetcher was called correctly
                mock_fetcher.process_models.assert_called_once_with(
                    mock_models_data, mock_judges_data
                )

                # Verify output files were created
                assert temp_full.exists()
                assert temp_filtered.exists()

                # Verify output contents
                with open(temp_full) as f:
                    full_result = json.load(f)
                with open(temp_filtered) as f:
                    filtered_result = json.load(f)

                assert full_result == mock_openrouter_data
                assert filtered_result == mock_filtered_data

                # Verify console output
                mock_print.assert_any_call("Fetching OpenRouter models...")
                mock_print.assert_any_call(f"Saved full OpenRouter data to {temp_full}")
                mock_print.assert_any_call(
                    f"Saved filtered OpenRouter data to {temp_filtered}"
                )

    def test_main_file_not_found_error(self):
        """Test main function handling of missing input files."""
        mock_snakemake = Mock()
        mock_snakemake.input.models = "/nonexistent/models.json"
        mock_snakemake.input.judges = "/nonexistent/judges.json"
        mock_snakemake.output = [
            "/path/to/openrouter_models_full.json",
            "/path/to/openrouter_models_filtered.json",
        ]

        # Inject snakemake object into the module's globals
        import scripts.fetch_openrouter_models as fetch_module

        fetch_module.snakemake = mock_snakemake

        try:
            with pytest.raises(FileNotFoundError):
                main()
        finally:
            # Clean up
            if hasattr(fetch_module, "snakemake"):
                delattr(fetch_module, "snakemake")

    def test_main_json_decode_error(self):
        """Test main function handling of malformed JSON files."""
        mock_snakemake = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_models = Path(temp_dir) / "models.json"
            temp_judges = Path(temp_dir) / "judges.json"

            # Write malformed JSON
            with open(temp_models, "w") as f:
                f.write("invalid json {")
            with open(temp_judges, "w") as f:
                json.dump({"models": []}, f)

            mock_snakemake.input.models = str(temp_models)
            mock_snakemake.input.judges = str(temp_judges)
            mock_snakemake.output = ["/path/to/full.json", "/path/to/filtered.json"]

            # Inject snakemake object into the module's globals
            import scripts.fetch_openrouter_models as fetch_module

            fetch_module.snakemake = mock_snakemake

            try:
                with pytest.raises(json.JSONDecodeError):
                    main()
            finally:
                # Clean up
                if hasattr(fetch_module, "snakemake"):
                    delattr(fetch_module, "snakemake")
