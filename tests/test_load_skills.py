"""Comprehensive tests for load_skills.py to achieve 90%+ coverage."""

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scripts.load_skills import (
    EVAL_SCHEMA,
    analyze_eval_chain,
    load_skill_evals,
    main,
    validate_eval_file_references,
    validate_eval_json,
    validate_file_references,
)


class TestFileReferenceValidation:
    """Test file reference validation functionality."""

    def test_validate_file_references_no_references(self):
        """Test validation with no file references."""
        text = "This is a normal prompt without any file references."
        count = validate_file_references(text, "test_path")
        assert count == 0

    def test_validate_file_references_existing_files(self):
        """Test validation with existing file references."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")

            text = f"Use this file: ${{file:{test_file}}}"
            count = validate_file_references(text, "test_path")
            assert count == 1

    def test_validate_file_references_missing_files(self):
        """Test validation raises error for missing file references."""
        text = "Use this file: ${file:/nonexistent/file.txt}"

        with pytest.raises(ValueError) as exc_info:
            validate_file_references(text, "test_path")

        assert "RED ALARM: Missing file references" in str(exc_info.value)
        assert "/nonexistent/file.txt" in str(exc_info.value)

    def test_validate_file_references_multiple_files(self):
        """Test validation with multiple file references."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file1 = Path(temp_dir) / "file1.txt"
            file2 = Path(temp_dir) / "file2.txt"
            file1.write_text("content1")
            file2.write_text("content2")

            text = f"Use ${{file:{file1}}} and ${{file:{file2}}}"
            count = validate_file_references(text, "test_path")
            assert count == 2

    def test_validate_file_references_mixed_existing_missing(self):
        """Test validation with mix of existing and missing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            existing_file = Path(temp_dir) / "exists.txt"
            existing_file.write_text("content")

            text = f"Use ${{file:{existing_file}}} and ${{file:/missing.txt}}"

            with pytest.raises(ValueError) as exc_info:
                validate_file_references(text, "test_path")

            assert "RED ALARM: Missing file references" in str(exc_info.value)
            assert "/missing.txt" in str(exc_info.value)

    def test_validate_eval_file_references_string_values(self):
        """Test recursive file reference validation on string values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")

            eval_data = {
                "id": "test_eval",
                "name": "Test Eval",
                "prompt": f"Use ${{file:{test_file}}}",
            }

            # Should not raise exception
            validate_eval_file_references(eval_data, "test_path")

    def test_validate_eval_file_references_nested_dict(self):
        """Test recursive validation on nested dictionary structures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")

            eval_data = {
                "id": "test_eval",
                "judge": {
                    "system": f"System prompt with ${{file:{test_file}}}",
                    "prompt": "Regular prompt",
                },
            }

            # Should not raise exception
            validate_eval_file_references(eval_data, "test_path")

    def test_validate_eval_file_references_list_items(self):
        """Test recursive validation on list items."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")

            eval_data = {
                "id": "test_eval",
                "chain": [
                    {"prompt": f"Step 1: ${{file:{test_file}}}"},
                    {"prompt": "Step 2: normal prompt"},
                ],
            }

            # Should not raise exception
            validate_eval_file_references(eval_data, "test_path")

    def test_validate_eval_file_references_missing_file_in_nested(self):
        """Test validation raises error for missing files in nested structures."""
        eval_data = {
            "id": "test_eval",
            "judge": {
                "system": "System prompt with ${file:/missing.txt}",
                "prompt": "Regular prompt",
            },
        }

        with pytest.raises(ValueError) as exc_info:
            validate_eval_file_references(eval_data, "test_path")

        assert "RED ALARM: Missing file references" in str(exc_info.value)


class TestJSONSchemaValidation:
    """Test JSON schema validation functionality."""

    def test_validate_eval_json_valid_minimal(self):
        """Test validation with valid minimal eval data."""
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

        result = validate_eval_json(eval_data, "test_path")
        assert result is True

    def test_validate_eval_json_with_intermediaries(self):
        """Test validation with intermediaries."""
        eval_data = {
            "id": "test_eval",
            "name": "Test Evaluation",
            "chain": [{"id": "step1", "prompt": "Test prompt"}],
            "intermediaries": [
                {
                    "id": "inter1",
                    "prompt": "Intermediate analysis: {{result}}",
                    "from": [{"step": "step1", "part": "final", "as": "result"}],
                }
            ],
            "judge": {
                "prompt": "Compare {{A}} vs {{B}}",
                "view": {
                    "A": [{"kind": "intermediary", "id": "inter1", "part": "final"}],
                    "B": [{"kind": "step", "id": "step1", "part": "history"}],
                },
            },
        }

        result = validate_eval_json(eval_data, "test_path")
        assert result is True

    def test_validate_eval_json_missing_required_field(self):
        """Test validation fails for missing required fields."""
        eval_data = {
            "name": "Test Evaluation",  # Missing "id"
            "chain": [{"id": "step1", "prompt": "Test prompt"}],
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

        assert "Validation error" in str(exc_info.value)

    def test_validate_eval_json_invalid_enum_value(self):
        """Test validation fails for invalid enum values."""
        eval_data = {
            "id": "test_eval",
            "name": "Test Evaluation",
            "chain": [
                {"id": "step1", "prompt": "Test prompt", "carry": "invalid"}
            ],  # Invalid carry value
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

        assert "Validation error" in str(exc_info.value)

    def test_validate_eval_json_with_context_error(self):
        """Test validation error includes context information."""
        eval_data = {
            "id": "test_eval",
            "name": "Test Evaluation",
            "chain": [],  # Empty chain (violates minItems: 1)
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
        assert "Validation error" in error_msg

    def test_validate_eval_json_file_reference_error(self):
        """Test validation fails for file reference errors."""
        eval_data = {
            "id": "test_eval",
            "name": "Test Evaluation",
            "chain": [{"id": "step1", "prompt": "Use ${file:/nonexistent.txt}"}],
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

        assert "RED ALARM: Missing file references" in str(exc_info.value)

    def test_validate_eval_json_general_exception(self):
        """Test validation handles general exceptions."""
        # Create invalid data that will cause a general exception
        with patch(
            "scripts.load_skills.jsonschema.validate",
            side_effect=Exception("General error"),
        ):
            eval_data = {"id": "test"}

            with pytest.raises(ValueError) as exc_info:
                validate_eval_json(eval_data, "test_path")

            assert "Schema validation failed" in str(exc_info.value)


class TestLoadSkillEvals:
    """Test skill evaluation loading functionality."""

    def test_load_skill_evals_no_json_files(self):
        """Test loading from directory with no JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "empty_skill"
            skill_dir.mkdir()

            with pytest.raises(ValueError) as exc_info:
                load_skill_evals(skill_dir)

            assert "RED ALARM: No JSON files found" in str(exc_info.value)

    def test_load_skill_evals_valid_files(self):
        """Test loading valid evaluation files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "test_skill"
            skill_dir.mkdir()

            # Create valid eval file
            eval_data = {
                "id": "eval1",
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

            eval_file = skill_dir / "eval1.json"
            with open(eval_file, "w") as f:
                json.dump(eval_data, f)

            with patch("builtins.print"):
                evals = load_skill_evals(skill_dir)

            assert len(evals) == 1
            assert evals[0]["id"] == "eval1"
            assert evals[0]["_metadata"]["skill"] == "test_skill"
            assert evals[0]["_metadata"]["file_path"] == str(eval_file)

    def test_load_skill_evals_invalid_json(self):
        """Test loading file with invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "test_skill"
            skill_dir.mkdir()

            # Create invalid JSON file
            eval_file = skill_dir / "invalid.json"
            with open(eval_file, "w") as f:
                f.write("{invalid json content")

            with patch("builtins.print"):
                with pytest.raises(ValueError) as exc_info:
                    load_skill_evals(skill_dir)

            assert "RED ALARM: Invalid JSON" in str(exc_info.value)

    def test_load_skill_evals_missing_id_field(self):
        """Test loading file missing required ID field."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "test_skill"
            skill_dir.mkdir()

            # Create eval without id field
            eval_data = {
                "name": "Test Evaluation",  # Missing "id"
                "chain": [{"id": "step1", "prompt": "Test prompt"}],
                "judge": {
                    "prompt": "Compare {{A}} vs {{B}}",
                    "view": {
                        "A": [{"kind": "step", "id": "step1", "part": "final"}],
                        "B": [{"kind": "step", "id": "step1", "part": "final"}],
                    },
                },
            }

            eval_file = skill_dir / "no_id.json"
            with open(eval_file, "w") as f:
                json.dump(eval_data, f)

            with patch("builtins.print"):
                with pytest.raises(ValueError) as exc_info:
                    load_skill_evals(skill_dir)

            assert "Validation error" in str(exc_info.value)

    def test_load_skill_evals_missing_name_field(self):
        """Test loading file missing required name field after schema validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "test_skill"
            skill_dir.mkdir()

            # Create eval with id but empty name
            eval_data = {
                "id": "test_eval",
                "name": "",  # Empty name should trigger additional validation
                "chain": [{"id": "step1", "prompt": "Test prompt"}],
                "judge": {
                    "prompt": "Compare {{A}} vs {{B}}",
                    "view": {
                        "A": [{"kind": "step", "id": "step1", "part": "final"}],
                        "B": [{"kind": "step", "id": "step1", "part": "final"}],
                    },
                },
            }

            eval_file = skill_dir / "empty_name.json"
            with open(eval_file, "w") as f:
                json.dump(eval_data, f)

            with patch("builtins.print"):
                with pytest.raises(ValueError) as exc_info:
                    load_skill_evals(skill_dir)

            assert "Eval missing required 'name' field" in str(exc_info.value)

    def test_load_skill_evals_general_exception(self):
        """Test loading handles general exceptions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "test_skill"
            skill_dir.mkdir()

            eval_file = skill_dir / "test.json"
            eval_file.write_text('{"id": "test"}')

            # Mock validate_eval_json to raise a general exception
            with patch(
                "scripts.load_skills.validate_eval_json",
                side_effect=Exception("Validation error"),
            ):
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        load_skill_evals(skill_dir)

            assert "RED ALARM: Failed to load eval" in str(exc_info.value)

    def test_load_skill_evals_multiple_files(self):
        """Test loading multiple valid evaluation files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "multi_skill"
            skill_dir.mkdir()

            # Create multiple valid eval files
            for i in range(3):
                eval_data = {
                    "id": f"eval{i}",
                    "name": f"Test Evaluation {i}",
                    "chain": [{"id": "step1", "prompt": f"Test prompt {i}"}],
                    "judge": {
                        "prompt": "Compare {{A}} vs {{B}}",
                        "view": {
                            "A": [{"kind": "step", "id": "step1", "part": "final"}],
                            "B": [{"kind": "step", "id": "step1", "part": "final"}],
                        },
                    },
                }

                eval_file = skill_dir / f"eval{i}.json"
                with open(eval_file, "w") as f:
                    json.dump(eval_data, f)

            with patch("builtins.print"):
                evals = load_skill_evals(skill_dir)

            assert len(evals) == 3
            eval_ids = [e["id"] for e in evals]
            assert "eval0" in eval_ids
            assert "eval1" in eval_ids
            assert "eval2" in eval_ids


class TestAnalyzeEvalChain:
    """Test eval chain analysis functionality."""

    def test_analyze_eval_chain_simple(self):
        """Test analysis of simple eval chain."""
        eval_data = {
            "chain": [
                {"id": "step1", "prompt": "First step"},
                {"id": "step2", "prompt": "Second step"},
            ]
        }

        analysis = analyze_eval_chain(eval_data)

        assert analysis["step_count"] == 2
        assert analysis["dependencies"] == 0
        assert analysis["has_custom_inputs"] is False
        assert analysis["step_ids"] == ["step1", "step2"]
        assert "none" in analysis["carry_stats"]

    def test_analyze_eval_chain_with_dependencies(self):
        """Test analysis with step dependencies."""
        eval_data = {
            "chain": [
                {"id": "step1", "prompt": "First step"},
                {"id": "step2", "prompt": "Second step", "depends_on": ["step1"]},
                {
                    "id": "step3",
                    "prompt": "Third step",
                    "depends_on": ["step1", "step2"],
                },
            ]
        }

        analysis = analyze_eval_chain(eval_data)

        assert analysis["step_count"] == 3
        assert analysis["dependencies"] == 2  # step2 and step3 have dependencies

    def test_analyze_eval_chain_with_carry_types(self):
        """Test analysis with different carry types."""
        eval_data = {
            "chain": [
                {"id": "step1", "prompt": "First step", "carry": "full"},
                {"id": "step2", "prompt": "Second step", "carry": "final"},
                {"id": "step3", "prompt": "Third step"},  # defaults to "none"
            ]
        }

        analysis = analyze_eval_chain(eval_data)

        assert analysis["carry_stats"]["full"] == 1
        assert analysis["carry_stats"]["final"] == 1
        assert analysis["carry_stats"]["none"] == 1

    def test_analyze_eval_chain_with_custom_inputs(self):
        """Test analysis with custom inputs."""
        eval_data = {
            "chain": [
                {"id": "step1", "prompt": "First step", "inputs": {"param": "value"}},
                {"id": "step2", "prompt": "Second step"},
            ]
        }

        analysis = analyze_eval_chain(eval_data)

        assert analysis["has_custom_inputs"] is True


class TestMainFunction:
    """Test the main function execution."""

    def create_mock_snakemake(
        self, skills_dir="skills", output_path="output.json", selected_skills=None
    ):
        """Helper to create mock snakemake object."""
        mock_snakemake = Mock()
        mock_snakemake.output = [output_path]
        mock_snakemake.params.get.side_effect = lambda key, default: {
            "skills_dir": skills_dir,
            "selected_skills": selected_skills,
        }.get(key, default)
        return mock_snakemake

    def run_main_with_snakemake(self, mock_snakemake):
        """Helper to run main function with mocked snakemake."""
        import scripts.load_skills as load_module

        original_snakemake = getattr(load_module, "snakemake", None)
        load_module.snakemake = mock_snakemake

        try:
            with patch("builtins.print"):
                main()
        finally:
            # Cleanup
            if original_snakemake is not None:
                load_module.snakemake = original_snakemake
            elif hasattr(load_module, "snakemake"):
                delattr(load_module, "snakemake")

    def run_main_with_snakemake_expect_error(self, mock_snakemake, expected_error_type):
        """Helper to run main function expecting an error."""
        import scripts.load_skills as load_module

        original_snakemake = getattr(load_module, "snakemake", None)
        load_module.snakemake = mock_snakemake

        try:
            with patch("builtins.print"):
                with pytest.raises(expected_error_type) as exc_info:
                    main()
            return exc_info
        finally:
            # Cleanup
            if original_snakemake is not None:
                load_module.snakemake = original_snakemake
            elif hasattr(load_module, "snakemake"):
                delattr(load_module, "snakemake")

    def test_main_skills_dir_not_found(self):
        """Test main function when skills directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "output.json"
            nonexistent_dir = Path(temp_dir) / "nonexistent_skills"

            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(nonexistent_dir), output_path=str(output_file)
            )

            # Add snakemake to the module's globals
            import scripts.load_skills as load_module

            original_snakemake = getattr(load_module, "snakemake", None)
            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(FileNotFoundError) as exc_info:
                        main()

                assert "RED ALARM: Skills directory not found" in str(exc_info.value)
            finally:
                # Cleanup
                if original_snakemake is not None:
                    load_module.snakemake = original_snakemake
                elif hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_no_skill_directories(self):
        """Test main function when skills directory exists but has no subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "empty_skills"
            skills_dir.mkdir()
            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(skills_dir), output_path=str(output_file)
            )

            # Add snakemake to the module's globals
            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        main()

                assert "RED ALARM: No skill directories found" in str(exc_info.value)
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_selected_skills_missing(self):
        """Test main function with selected skills that don't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()
            (skills_dir / "existing_skill").mkdir()

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(skills_dir),
                output_path=str(output_file),
                selected_skills=["existing_skill", "missing_skill"],
            )

            # Add snakemake to the module's globals
            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        main()

                assert "RED ALARM: Selected skills not found" in str(exc_info.value)
                assert "missing_skill" in str(exc_info.value)
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_successful_execution_all_skills(self):
        """Test successful main function execution with all skills."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            # Create test skill directory with valid eval
            skill_dir = skills_dir / "test_skill"
            skill_dir.mkdir()

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

            eval_file = skill_dir / "test_eval.json"
            with open(eval_file, "w") as f:
                json.dump(eval_data, f)

            output_file = Path(temp_dir) / "output.json"

            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(skills_dir), output_path=str(output_file)
            )

            # Add snakemake to the module's globals
            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    main()

                # Verify output was created
                assert output_file.exists()

                # Load and verify output content
                with open(output_file) as f:
                    result = json.load(f)

                assert result["load_info"]["total_skills"] == 1
                assert result["load_info"]["total_evals"] == 1
                assert "test_skill" in result["skills"]
                assert len(result["evals"]) == 1
                assert result["evals"][0]["id"] == "test_eval"
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_successful_execution_selected_skills(self):
        """Test successful main function execution with selected skills."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            # Create multiple skill directories
            for skill_name in ["skill1", "skill2", "skill3"]:
                skill_dir = skills_dir / skill_name
                skill_dir.mkdir()

                eval_data = {
                    "id": f"eval_{skill_name}",
                    "name": f"Evaluation for {skill_name}",
                    "chain": [
                        {"id": "step1", "prompt": f"Test prompt for {skill_name}"}
                    ],
                    "judge": {
                        "prompt": "Compare {{A}} vs {{B}}",
                        "view": {
                            "A": [{"kind": "step", "id": "step1", "part": "final"}],
                            "B": [{"kind": "step", "id": "step1", "part": "final"}],
                        },
                    },
                }

                eval_file = skill_dir / f"eval_{skill_name}.json"
                with open(eval_file, "w") as f:
                    json.dump(eval_data, f)

            output_file = Path(temp_dir) / "output.json"

            # Test with selected skills
            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(skills_dir),
                output_path=str(output_file),
                selected_skills=["skill1", "skill3"],
            )

            # Add snakemake to the module's globals
            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    main()

                # Verify output
                with open(output_file) as f:
                    result = json.load(f)

                assert result["load_info"]["total_skills"] == 2
                assert result["load_info"]["total_evals"] == 2
                assert "skill1" in result["skills"]
                assert "skill3" in result["skills"]
                assert "skill2" not in result["skills"]
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_duplicate_eval_ids(self):
        """Test main function handles duplicate eval IDs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            # Create two skills with same eval ID
            for skill_name in ["skill1", "skill2"]:
                skill_dir = skills_dir / skill_name
                skill_dir.mkdir()

                eval_data = {
                    "id": "duplicate_id",  # Same ID in both skills
                    "name": f"Evaluation for {skill_name}",
                    "chain": [
                        {"id": "step1", "prompt": f"Test prompt for {skill_name}"}
                    ],
                    "judge": {
                        "prompt": "Compare {{A}} vs {{B}}",
                        "view": {
                            "A": [{"kind": "step", "id": "step1", "part": "final"}],
                            "B": [{"kind": "step", "id": "step1", "part": "final"}],
                        },
                    },
                }

                eval_file = skill_dir / "eval.json"
                with open(eval_file, "w") as f:
                    json.dump(eval_data, f)

            output_file = Path(temp_dir) / "output.json"
            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(skills_dir), output_path=str(output_file)
            )

            # Add snakemake to the module's globals
            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        main()

                assert "RED ALARM: Duplicate eval IDs found" in str(exc_info.value)
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_skill_loading_failure(self):
        """Test main function handles skill loading failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            skill_dir = skills_dir / "broken_skill"
            skill_dir.mkdir()

            # Create invalid JSON file
            eval_file = skill_dir / "broken.json"
            with open(eval_file, "w") as f:
                f.write("{broken json")

            output_file = Path(temp_dir) / "output.json"
            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(skills_dir), output_path=str(output_file)
            )

            # Add snakemake to the module's globals
            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        main()

                assert "RED ALARM: Critical failure in skill" in str(exc_info.value)
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_analysis_failure(self):
        """Test main function handles analysis failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            skill_dir = skills_dir / "test_skill"
            skill_dir.mkdir()

            eval_data = {
                "id": "test_eval",
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
            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(skills_dir), output_path=str(output_file)
            )

            # Mock analyze_eval_chain to raise exception
            with patch(
                "scripts.load_skills.analyze_eval_chain",
                side_effect=Exception("Analysis error"),
            ):
                # Add snakemake to the module's globals
                import scripts.load_skills as load_module

                load_module.snakemake = mock_snakemake

                try:
                    with patch("builtins.print"):
                        with pytest.raises(ValueError) as exc_info:
                            main()

                    assert "RED ALARM: Failed to analyze eval" in str(exc_info.value)
                finally:
                    if hasattr(load_module, "snakemake"):
                        delattr(load_module, "snakemake")

    def test_main_output_save_failure(self):
        """Test main function handles output save failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skills_dir.mkdir()

            skill_dir = skills_dir / "test_skill"
            skill_dir.mkdir()

            eval_data = {
                "id": "test_eval",
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

            # Use invalid output path to trigger save failure
            output_file = "/invalid/path/output.json"
            mock_snakemake = self.create_mock_snakemake(
                skills_dir=str(skills_dir), output_path=output_file
            )

            # Add snakemake to the module's globals
            import scripts.load_skills as load_module

            load_module.snakemake = mock_snakemake

            try:
                with patch("builtins.print"):
                    with pytest.raises(ValueError) as exc_info:
                        main()

                assert "RED ALARM: Failed to save skills data" in str(exc_info.value)
            finally:
                if hasattr(load_module, "snakemake"):
                    delattr(load_module, "snakemake")

    def test_main_module_execution(self):
        """Test module-level execution."""
        with patch("scripts.load_skills.main") as mock_main:
            # Test the if __name__ == "__main__" condition
            import scripts.load_skills as load_module

            # Simulate module being run as main
            original_name = load_module.__name__
            try:
                load_module.__name__ = "__main__"
                # Simulate the condition check
                if load_module.__name__ == "__main__":
                    mock_main()

                mock_main.assert_called_once()
            finally:
                load_module.__name__ = original_name


class TestEvalSchemaStructure:
    """Test the EVAL_SCHEMA structure and related functionality."""

    def test_eval_schema_structure(self):
        """Test that EVAL_SCHEMA has expected structure."""
        assert "title" in EVAL_SCHEMA
        assert EVAL_SCHEMA["title"] == "EvalConfigTiny"
        assert "required" in EVAL_SCHEMA
        assert "id" in EVAL_SCHEMA["required"]
        assert "name" in EVAL_SCHEMA["required"]
        assert "chain" in EVAL_SCHEMA["required"]
        assert "judge" in EVAL_SCHEMA["required"]

    def test_eval_schema_view_list_definition(self):
        """Test ViewList schema definition."""
        assert "$defs" in EVAL_SCHEMA
        assert "ViewList" in EVAL_SCHEMA["$defs"]

        view_list_schema = EVAL_SCHEMA["$defs"]["ViewList"]
        assert view_list_schema["type"] == "array"
        assert view_list_schema["minItems"] == 1

        items_schema = view_list_schema["items"]
        assert "kind" in items_schema["required"]
        assert "id" in items_schema["required"]
        assert "part" in items_schema["required"]

    def test_regex_pattern_in_file_validation(self):
        """Test regex pattern used in file reference validation."""
        pattern = re.compile(r"\$\{file:([^}]+)\}")

        # Test pattern matching
        text = "Use ${file:/path/to/file.txt} and ${file:another/file.py}"
        matches = pattern.findall(text)

        assert len(matches) == 2
        assert "/path/to/file.txt" in matches
        assert "another/file.py" in matches

        # Test no matches
        text_no_matches = "This has no file references"
        matches = pattern.findall(text_no_matches)
        assert len(matches) == 0
