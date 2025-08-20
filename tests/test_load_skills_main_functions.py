"""Additional tests specifically for load_skills main function to improve coverage."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scripts.load_skills import main


class TestMainFunctionSimplified:
    """Simplified tests for main function to achieve coverage."""

    def test_main_with_mock_snakemake_success(self):
        """Test main function with successful execution path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create skills directory structure
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            skill_dir = skills_dir / "test_skill"
            skill_dir.mkdir()

            # Create valid eval file
            eval_data = {
                "id": "test_eval",
                "name": "Test Evaluation",
                "chain": [{"id": "step1", "prompt": "Test prompt"}],
                "judge": {
                    "prompt": "Compare {{A}} vs {{B}}",
                    "view": {
                        "A": [{"kind": "step", "id": "step1", "part": "final"}],
                        "B": [{"kind": "step", "id": "step1", "part": "final"}],
                    },
                },
            }

            eval_file = skill_dir / "test.json"
            with open(eval_file, "w") as f:
                json.dump(eval_data, f)

            output_file = Path(temp_dir) / "output.json"

            # Mock snakemake object
            mock_snakemake = Mock()
            mock_snakemake.output = [str(output_file)]
            mock_snakemake.params.get.side_effect = lambda key, default: {
                "skills_dir": str(skills_dir),
                "selected_skills": None,
            }.get(key, default)

            # Test by directly setting the module attribute
            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    main()

                # Verify output was created
                assert output_file.exists()

                with open(output_file) as f:
                    result = json.load(f)

                assert result["load_info"]["total_skills"] == 1
                assert result["load_info"]["total_evals"] == 1

            finally:
                # Cleanup
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_error_conditions(self):
        """Test main function error conditions."""
        # Test with nonexistent skills directory
        mock_snakemake = Mock()
        mock_snakemake.output = ["/tmp/output.json"]
        mock_snakemake.params.get.side_effect = lambda key, default: {
            "skills_dir": "/nonexistent/skills",
            "selected_skills": None,
        }.get(key, default)

        import scripts.load_skills as load_module

        load_module.snakemake = mock_snakemake

        try:
            with patch("builtins.print"):
                with pytest.raises(FileNotFoundError):
                    main()
        finally:
            if hasattr(load_module, "snakemake"):
                delattr(load_module, "snakemake")

    def test_main_selected_skills(self):
        """Test main function with selected skills."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            # Create multiple skills
            for skill_name in ["skill1", "skill2"]:
                skill_dir = skills_dir / skill_name
                skill_dir.mkdir()

                eval_data = {
                    "id": f"eval_{skill_name}",
                    "name": f"Test {skill_name}",
                    "chain": [{"id": "step1", "prompt": "Test"}],
                    "judge": {
                        "prompt": "Compare {{A}} vs {{B}}",
                        "view": {
                            "A": [{"kind": "step", "id": "step1", "part": "final"}],
                            "B": [{"kind": "step", "id": "step1", "part": "final"}],
                        },
                    },
                }

                eval_file = skill_dir / f"{skill_name}.json"
                with open(eval_file, "w") as f:
                    json.dump(eval_data, f)

            output_file = Path(temp_dir) / "output.json"

            # Test with selected skills
            mock_snakemake = Mock()
            mock_snakemake.output = [str(output_file)]
            mock_snakemake.params.get.side_effect = lambda key, default: {
                "skills_dir": str(skills_dir),
                "selected_skills": ["skill1"],  # Only select skill1
            }.get(key, default)

            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    main()

                with open(output_file) as f:
                    result = json.load(f)

                assert result["load_info"]["total_skills"] == 1
                assert "skill1" in result["skills"]
                assert "skill2" not in result["skills"]

            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_missing_eval_id_field(self):
        """Test additional validation checks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            skill_dir = skills_dir / "test_skill"
            skill_dir.mkdir()

            # Create eval without ID (but valid JSON schema)
            eval_data = {
                "id": "",  # Empty ID
                "name": "Test Evaluation",
                "chain": [{"id": "step1", "prompt": "Test"}],
                "judge": {
                    "prompt": "Compare {{A}} vs {{B}}",
                    "view": {
                        "A": [{"kind": "step", "id": "step1", "part": "final"}],
                        "B": [{"kind": "step", "id": "step1", "part": "final"}],
                    },
                },
            }

            eval_file = skill_dir / "test.json"
            with open(eval_file, "w") as f:
                json.dump(eval_data, f)

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = Mock()
            mock_snakemake.output = [str(output_file)]
            mock_snakemake.params.get.side_effect = lambda key, default: {
                "skills_dir": str(skills_dir),
                "selected_skills": None,
            }.get(key, default)

            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        main()

                assert "Eval missing required 'id' field" in str(exc_info.value)

            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_json_decode_error_path(self):
        """Test JSON decode error handling path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            skill_dir = skills_dir / "test_skill"
            skill_dir.mkdir()

            # Create invalid JSON file
            eval_file = skill_dir / "invalid.json"
            with open(eval_file, "w") as f:
                f.write("{invalid json")

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = Mock()
            mock_snakemake.output = [str(output_file)]
            mock_snakemake.params.get.side_effect = lambda key, default: {
                "skills_dir": str(skills_dir),
                "selected_skills": None,
            }.get(key, default)

            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        main()

                # Should hit the JSON decode error path (lines 192-195)
                assert "RED ALARM: Invalid JSON" in str(exc_info.value)

            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_validation_error_with_path_and_context(self):
        """Test validation error handling with context information."""
        # Test schema validation error paths (lines 146-149)
        from scripts.load_skills import validate_eval_json

        # Create eval data that will fail schema validation
        eval_data = {
            "id": "test",
            "name": "Test",
            "chain": [],  # Empty chain violates minItems constraint
            "judge": {
                "prompt": "Compare {{A}} vs {{B}}",
                "view": {
                    "A": [{"kind": "step", "id": "step1", "part": "final"}],
                    "B": [{"kind": "step", "id": "step1", "part": "final"}],
                },
            },
        }

        with pytest.raises(ValueError) as exc_info:
            validate_eval_json(eval_data, "test_path")

        error_msg = str(exc_info.value)
        assert "Validation error in test_path" in error_msg
        # The validation error should include path information


class TestAdditionalCoverage:
    """Tests to cover remaining uncovered lines."""

    def test_coverage_edge_cases(self):
        """Test remaining edge cases for coverage."""
        from scripts.load_skills import analyze_eval_chain

        # Test analyze_eval_chain with edge cases
        eval_data = {
            "chain": [
                {"id": "step1", "prompt": "Test", "depends_on": ["other"]},
                {"id": "step2", "prompt": "Test", "inputs": {"key": "value"}},
                {"id": "step3", "prompt": "Test", "carry": "final"},
            ]
        }

        analysis = analyze_eval_chain(eval_data)
        assert analysis["dependencies"] == 1  # Only step1 has depends_on
        assert analysis["has_custom_inputs"] is True  # step2 has inputs
        assert "final" in analysis["carry_stats"]
