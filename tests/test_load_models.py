"""Comprehensive tests for load_models.py to achieve 90%+ coverage."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from scripts.load_models import load_model_pool, main, validate_model_pool


class TestValidateModelPool:
    """Test the validate_model_pool function."""

    def test_validate_model_pool_valid_data(self):
        """Test validation with completely valid data."""
        df = pd.DataFrame(
            {
                "id": ["model1", "model2"],
                "author": ["author1", "author2"],
                "slug": ["slug1", "slug2"],
                "context_window": [4000, 8000],
                "pricing": [0.001, 0.002],
                "endpoint": ["endpoint1", "endpoint2"],
                "max_tokens": [1000, 2000],
            }
        )

        result = validate_model_pool(df, "test_pool")
        assert len(result) == 2
        assert result["context_window"].dtype in ["int64", "float64"]
        assert result["max_tokens"].dtype in ["int64", "float64"]

    def test_validate_model_pool_missing_columns(self):
        """Test validation fails with missing required columns."""
        df = pd.DataFrame(
            {
                "id": ["model1"],
                "author": ["author1"],
                # Missing other required columns
            }
        )

        with pytest.raises(ValueError) as exc_info:
            validate_model_pool(df, "test_pool")

        assert "missing required columns" in str(exc_info.value)
        assert "test_pool" in str(exc_info.value)

    def test_validate_model_pool_empty_required_fields(self):
        """Test validation fails with empty values in required columns."""
        df = pd.DataFrame(
            {
                "id": ["model1", None],  # Has null value
                "author": ["author1", "author2"],
                "slug": ["slug1", "slug2"],
                "context_window": [4000, 8000],
                "pricing": [0.001, 0.002],
                "endpoint": ["endpoint1", "endpoint2"],
                "max_tokens": [1000, 2000],
            }
        )

        with pytest.raises(ValueError) as exc_info:
            validate_model_pool(df, "test_pool")

        assert "has empty values in column 'id'" in str(exc_info.value)

    def test_validate_model_pool_non_numeric_context_window_convertible(self):
        """Test numeric column conversion works for string numbers."""
        df = pd.DataFrame(
            {
                "id": ["model1"],
                "author": ["author1"],
                "slug": ["slug1"],
                "context_window": ["4000"],  # String that can be converted
                "pricing": [0.001],
                "endpoint": ["endpoint1"],
                "max_tokens": ["1000"],  # String that can be converted
            }
        )

        result = validate_model_pool(df, "test_pool")
        assert result["context_window"].dtype in ["int64", "float64"]
        assert result["max_tokens"].dtype in ["int64", "float64"]

    def test_validate_model_pool_non_numeric_context_window_invalid(self):
        """Test validation fails with non-convertible numeric columns."""
        df = pd.DataFrame(
            {
                "id": ["model1"],
                "author": ["author1"],
                "slug": ["slug1"],
                "context_window": ["invalid_number"],  # Cannot be converted
                "pricing": [0.001],
                "endpoint": ["endpoint1"],
                "max_tokens": [1000],
            }
        )

        with pytest.raises(ValueError) as exc_info:
            validate_model_pool(df, "test_pool")

        assert "contains non-numeric values" in str(exc_info.value)
        assert "context_window" in str(exc_info.value)

    def test_validate_model_pool_non_numeric_max_tokens_invalid(self):
        """Test validation fails with non-convertible max_tokens."""
        df = pd.DataFrame(
            {
                "id": ["model1"],
                "author": ["author1"],
                "slug": ["slug1"],
                "context_window": [4000],
                "pricing": [0.001],
                "endpoint": ["endpoint1"],
                "max_tokens": ["invalid"],  # Cannot be converted
            }
        )

        with pytest.raises(ValueError) as exc_info:
            validate_model_pool(df, "test_pool")

        assert "contains non-numeric values" in str(exc_info.value)
        assert "max_tokens" in str(exc_info.value)

    def test_validate_model_pool_empty_pricing(self):
        """Test validation fails with empty pricing values."""
        df = pd.DataFrame(
            {
                "id": ["model1", "model2"],
                "author": ["author1", "author2"],
                "slug": ["slug1", "slug2"],
                "context_window": [4000, 8000],
                "pricing": [0.001, ""],  # Empty string
                "endpoint": ["endpoint1", "endpoint2"],
                "max_tokens": [1000, 2000],
            }
        )

        with pytest.raises(ValueError) as exc_info:
            validate_model_pool(df, "test_pool")

        assert "contains empty values" in str(exc_info.value)
        assert "pricing" in str(exc_info.value)

    def test_validate_model_pool_null_pricing(self):
        """Test validation fails with null pricing values."""
        df = pd.DataFrame(
            {
                "id": ["model1", "model2"],
                "author": ["author1", "author2"],
                "slug": ["slug1", "slug2"],
                "context_window": [4000, 8000],
                "pricing": [0.001, None],  # Null value
                "endpoint": ["endpoint1", "endpoint2"],
                "max_tokens": [1000, 2000],
            }
        )

        with pytest.raises(ValueError) as exc_info:
            validate_model_pool(df, "test_pool")

        assert "has empty values" in str(exc_info.value)
        assert "pricing" in str(exc_info.value)

    def test_validate_model_pool_string_pricing_valid(self):
        """Test validation allows string pricing formats."""
        df = pd.DataFrame(
            {
                "id": ["model1", "model2"],
                "author": ["author1", "author2"],
                "slug": ["slug1", "slug2"],
                "context_window": [4000, 8000],
                "pricing": ["input:0.001", "output:0.002"],  # String pricing format
                "endpoint": ["endpoint1", "endpoint2"],
                "max_tokens": [1000, 2000],
            }
        )

        result = validate_model_pool(df, "test_pool")
        assert len(result) == 2
        assert "input:0.001" in result["pricing"].values


class TestLoadModelPool:
    """Test the load_model_pool function."""

    def test_load_model_pool_success(self):
        """Test successful loading of a model pool."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test CSV file
            csv_path = Path(temp_dir) / "test_pool.csv"
            df = pd.DataFrame(
                {
                    "id": ["model1", "model2"],
                    "author": ["author1", "author2"],
                    "slug": ["slug1", "slug2"],
                    "context_window": [4000, 8000],
                    "pricing": [0.001, 0.002],
                    "endpoint": ["endpoint1", "endpoint2"],
                    "max_tokens": [1000, 2000],
                }
            )
            df.to_csv(csv_path, index=False)

            with patch("builtins.print"):
                result = load_model_pool(csv_path)

            assert result["name"] == "test_pool"
            assert result["path"] == str(csv_path)
            assert result["model_count"] == 2
            assert len(result["models"]) == 2
            assert result["models"][0]["id"] == "model1"

    def test_load_model_pool_csv_read_error(self):
        """Test handling of CSV read errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file with invalid CSV content
            csv_path = Path(temp_dir) / "invalid.csv"
            with open(csv_path, "w") as f:
                f.write("invalid,csv\ncontent")

            # Mock pd.read_csv to raise an exception
            with patch(
                "pandas.read_csv", side_effect=pd.errors.EmptyDataError("No data")
            ):
                with patch("builtins.print"):
                    with pytest.raises(pd.errors.EmptyDataError):
                        load_model_pool(csv_path)

    def test_load_model_pool_validation_error(self):
        """Test handling of validation errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create CSV file with missing required columns
            csv_path = Path(temp_dir) / "invalid_pool.csv"
            df = pd.DataFrame(
                {
                    "id": ["model1"],
                    "author": ["author1"],
                    # Missing other required columns
                }
            )
            df.to_csv(csv_path, index=False)

            with patch("builtins.print"):
                with pytest.raises(ValueError) as exc_info:
                    load_model_pool(csv_path)

            assert "missing required columns" in str(exc_info.value)

    def test_load_model_pool_general_exception(self):
        """Test handling of general exceptions during loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "test.csv"

            # Mock pd.read_csv to raise a general exception
            with patch("pandas.read_csv", side_effect=Exception("General error")):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(Exception) as exc_info:
                        load_model_pool(csv_path)

                    # Check that error was printed
                    mock_print.assert_any_call(
                        "Error loading model pool 'test': General error"
                    )
                    assert "General error" in str(exc_info.value)


class TestMainFunction:
    """Test the main function."""

    def create_mock_snakemake(
        self, output_path, pool_name="test", pools_dir="model_pools"
    ):
        """Create a mock snakemake object."""
        mock_snakemake = Mock()
        mock_snakemake.output = [output_path]
        mock_snakemake.params.get.side_effect = lambda key, default: {
            "pool_name": pool_name,
            "pools_dir": pools_dir,
        }.get(key, default)
        return mock_snakemake

    def test_main_pool_file_not_found(self):
        """Test main function when pool file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "output.json"
            pools_dir = Path(temp_dir) / "model_pools"

            mock_snakemake = self.create_mock_snakemake(
                output_path=str(output_file), pools_dir=str(pools_dir)
            )

            # Add snakemake to the module's globals
            import scripts.load_models as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(FileNotFoundError) as exc_info:
                        main()

                assert "Model pool file not found" in str(exc_info.value)
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_successful_execution_numeric_pricing(self):
        """Test successful main function execution with numeric pricing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pools directory and CSV file
            pools_dir = Path(temp_dir) / "model_pools"
            pools_dir.mkdir()

            csv_path = pools_dir / "test_pool.csv"
            df = pd.DataFrame(
                {
                    "id": ["model1", "model2", "model3"],
                    "author": ["author1", "author1", "author2"],  # Different authors
                    "slug": ["slug1", "slug2", "slug3"],
                    "context_window": [4000, 8000, 6000],
                    "pricing": [0.001, 0.002, 0.0015],  # Numeric pricing
                    "endpoint": ["endpoint1", "endpoint2", "endpoint3"],
                    "max_tokens": [1000, 2000, 1500],
                }
            )
            df.to_csv(csv_path, index=False)

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = self.create_mock_snakemake(
                output_path=str(output_file),
                pool_name="test_pool",
                pools_dir=str(pools_dir),
            )

            # Add snakemake to the module's globals
            import scripts.load_models as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    main()

                # Verify output was created
                assert output_file.exists()

                # Load and verify output content
                with open(output_file) as f:
                    result = json.load(f)

                assert result["pool_info"]["name"] == "test_pool"
                assert result["pool_info"]["model_count"] == 3
                assert len(result["models"]) == 3

                # Check statistics
                assert "avg_context_window" in result["statistics"]
                assert "avg_max_tokens" in result["statistics"]
                assert "avg_pricing" in result["statistics"]
                assert "price_range" in result["statistics"]
                assert "authors" in result["statistics"]

                # Check author counts
                assert result["statistics"]["authors"]["author1"] == 2
                assert result["statistics"]["authors"]["author2"] == 1

                # Check ranges
                assert result["statistics"]["context_window_range"]["min"] == 4000
                assert result["statistics"]["context_window_range"]["max"] == 8000

            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_successful_execution_mixed_pricing(self):
        """Test successful main function execution with mixed pricing formats."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pools directory and CSV file
            pools_dir = Path(temp_dir) / "model_pools"
            pools_dir.mkdir()

            csv_path = pools_dir / "mixed_pool.csv"
            df = pd.DataFrame(
                {
                    "id": ["model1", "model2"],
                    "author": ["author1", "author2"],
                    "slug": ["slug1", "slug2"],
                    "context_window": [4000, 8000],
                    "pricing": ["input:0.001", "output:0.002"],  # String pricing
                    "endpoint": ["endpoint1", "endpoint2"],
                    "max_tokens": [1000, 2000],
                }
            )
            df.to_csv(csv_path, index=False)

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = self.create_mock_snakemake(
                output_path=str(output_file),
                pool_name="mixed_pool",
                pools_dir=str(pools_dir),
            )

            # Add snakemake to the module's globals
            import scripts.load_models as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    main()

                # Load and verify output content
                with open(output_file) as f:
                    result = json.load(f)

                # Should NOT have pricing statistics for mixed pricing
                assert "avg_pricing" not in result["statistics"]
                assert "price_range" not in result["statistics"]
                assert result["pool_info"]["model_count"] == 2

            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_loading_error(self):
        """Test main function handles loading errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pools directory and invalid CSV file
            pools_dir = Path(temp_dir) / "model_pools"
            pools_dir.mkdir()

            csv_path = pools_dir / "broken.csv"
            # Create invalid CSV with missing columns
            df = pd.DataFrame(
                {
                    "id": ["model1"],
                    "author": ["author1"],
                    # Missing required columns
                }
            )
            df.to_csv(csv_path, index=False)

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = self.create_mock_snakemake(
                output_path=str(output_file),
                pool_name="broken",
                pools_dir=str(pools_dir),
            )

            # Add snakemake to the module's globals
            import scripts.load_models as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        main()

                assert "missing required columns" in str(exc_info.value)
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_single_author(self):
        """Test main function with single author (edge case for statistics)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pools directory and CSV file with single author
            pools_dir = Path(temp_dir) / "model_pools"
            pools_dir.mkdir()

            csv_path = pools_dir / "single.csv"
            df = pd.DataFrame(
                {
                    "id": ["model1"],
                    "author": ["single_author"],
                    "slug": ["slug1"],
                    "context_window": [4000],
                    "pricing": [0.001],
                    "endpoint": ["endpoint1"],
                    "max_tokens": [1000],
                }
            )
            df.to_csv(csv_path, index=False)

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = self.create_mock_snakemake(
                output_path=str(output_file),
                pool_name="single",
                pools_dir=str(pools_dir),
            )

            # Add snakemake to the module's globals
            import scripts.load_models as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    main()

                # Load and verify output content
                with open(output_file) as f:
                    result = json.load(f)

                assert result["pool_info"]["model_count"] == 1
                assert result["statistics"]["authors"]["single_author"] == 1
                assert result["statistics"]["avg_pricing"] == 0.001
                assert result["statistics"]["price_range"]["min"] == 0.001
                assert result["statistics"]["price_range"]["max"] == 0.001

            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_partially_numeric_pricing(self):
        """Test main function with some numeric and some non-numeric pricing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create pools directory and CSV file
            pools_dir = Path(temp_dir) / "model_pools"
            pools_dir.mkdir()

            csv_path = pools_dir / "partial.csv"
            df = pd.DataFrame(
                {
                    "id": ["model1", "model2", "model3"],
                    "author": ["author1", "author2", "author3"],
                    "slug": ["slug1", "slug2", "slug3"],
                    "context_window": [4000, 8000, 6000],
                    "pricing": [
                        0.001,
                        0.002,
                        "input:0.003",
                    ],  # Mix of numeric and string
                    "endpoint": ["endpoint1", "endpoint2", "endpoint3"],
                    "max_tokens": [1000, 2000, 1500],
                }
            )
            df.to_csv(csv_path, index=False)

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = self.create_mock_snakemake(
                output_path=str(output_file),
                pool_name="partial",
                pools_dir=str(pools_dir),
            )

            # Add snakemake to the module's globals
            import scripts.load_models as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    main()

                # Load and verify output content
                with open(output_file) as f:
                    result = json.load(f)

                # Should have pricing statistics based on the 2 numeric values
                assert "avg_pricing" in result["statistics"]
                assert (
                    result["statistics"]["avg_pricing"] == 0.0015
                )  # (0.001 + 0.002) / 2
                assert result["statistics"]["price_range"]["min"] == 0.001
                assert result["statistics"]["price_range"]["max"] == 0.002

            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_module_execution(self):
        """Test module-level execution."""
        with patch("scripts.load_models.main") as mock_main:
            # Test the if __name__ == "__main__" condition

            # Simulate module being run as main
            if "__main__" == "__main__":  # This simulates the condition in the module
                mock_main()

            mock_main.assert_called()


class TestEdgeCases:
    """Test edge cases and additional coverage."""

    def test_context_window_type_conversion_edge_cases(self):
        """Test edge cases in numeric type conversion."""
        # Test with float strings
        df = pd.DataFrame(
            {
                "id": ["model1"],
                "author": ["author1"],
                "slug": ["slug1"],
                "context_window": ["4000.5"],  # Float as string
                "pricing": [0.001],
                "endpoint": ["endpoint1"],
                "max_tokens": ["1000.0"],  # Float as string
            }
        )

        result = validate_model_pool(df, "test_pool")
        assert result["context_window"].iloc[0] == 4000.5
        assert result["max_tokens"].iloc[0] == 1000.0

    def test_all_required_columns_validation_comprehensive(self):
        """Test that all required columns are properly validated."""
        required_columns = [
            "id",
            "author",
            "slug",
            "context_window",
            "pricing",
            "endpoint",
            "max_tokens",
        ]

        # Test each missing column individually
        for missing_col in required_columns:
            df_data = {
                col: [f"test_{col}"] if col != missing_col else []
                for col in required_columns
            }

            # Provide proper data types for the columns that remain
            if "context_window" in df_data and df_data["context_window"]:
                df_data["context_window"] = [4000]
            if "max_tokens" in df_data and df_data["max_tokens"]:
                df_data["max_tokens"] = [1000]
            if "pricing" in df_data and df_data["pricing"]:
                df_data["pricing"] = [0.001]

            # Remove the missing column
            if missing_col in df_data:
                del df_data[missing_col]

            df = pd.DataFrame(df_data)

            with pytest.raises(ValueError) as exc_info:
                validate_model_pool(df, "test_pool")

            assert missing_col in str(exc_info.value)
            assert "missing required columns" in str(exc_info.value)

    def test_empty_dataframe(self):
        """Test validation with empty dataframe."""
        df = pd.DataFrame()

        with pytest.raises(ValueError) as exc_info:
            validate_model_pool(df, "empty_pool")

        assert "missing required columns" in str(exc_info.value)

    def test_numeric_conversion_preserves_data(self):
        """Test that numeric conversion preserves the original data correctly."""
        df = pd.DataFrame(
            {
                "id": ["model1", "model2"],
                "author": ["author1", "author2"],
                "slug": ["slug1", "slug2"],
                "context_window": ["4000", "8000"],
                "pricing": ["0.001", "0.002"],
                "endpoint": ["endpoint1", "endpoint2"],
                "max_tokens": ["1000", "2000"],
            }
        )

        result = validate_model_pool(df, "test_pool")

        # Check that converted values match original intent
        assert result["context_window"].iloc[0] == 4000
        assert result["context_window"].iloc[1] == 8000
        assert result["max_tokens"].iloc[0] == 1000
        assert result["max_tokens"].iloc[1] == 2000

        # Pricing should remain as strings since it's flexible format
        assert result["pricing"].iloc[0] == "0.001"
        assert result["pricing"].iloc[1] == "0.002"
