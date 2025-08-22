"""Tests for generate_final_results.py script."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scripts.generate_final_results import FinalResultsGenerator, main


class TestFinalResultsGenerator:
    """Test final results generation from loaded skills data."""

    @pytest.fixture
    def mock_loaded_skills_data(self):
        """Mock loaded skills data with multiple skills."""
        return {
            "load_info": {
                "skills_dir": "skills",
                "total_skills": 3,
                "total_evals": 3,
                "timestamp": "2025-08-20T12:00:00.000000",
            },
            "skills": {
                "code_generation": {
                    "eval_count": 1,
                    "eval_ids": ["procedural_fps_map"],
                    "path": "skills/code_generation",
                },
                "empathy": {
                    "eval_count": 1,
                    "eval_ids": ["terminal-diagnosis"],
                    "path": "skills/empathy",
                },
                "document_summarization": {
                    "eval_count": 1,
                    "eval_ids": ["arxiv-paper-summary"],
                    "path": "skills/document_summarization",
                },
            },
        }

    @pytest.fixture
    def mock_individual_skills(self):
        """Mock individual skill configuration files."""
        return {
            "procedural_fps_map": {
                "id": "procedural_fps_map",
                "name": "Procedural FPS Map Generator",
                "chain": [
                    {
                        "id": "generate_code",
                        "prompt": "Generate procedural FPS map code...",
                        "inputs": {},
                    }
                ],
                "judge": {
                    "system": "You are a JavaScript code quality expert...",
                    "prompt": "Evaluate the implementation on a scale of 0-10: {{A}} vs {{B}}",
                    "view": {
                        "A": [{"kind": "step", "id": "generate_code", "part": "final"}],
                        "B": [{"kind": "step", "id": "generate_code", "part": "final"}],
                    },
                },
            },
            "terminal-diagnosis": {
                "id": "terminal-diagnosis",
                "name": "Terminal Cancer Diagnosis Support",
                "chain": [
                    {
                        "id": "main_response",
                        "prompt": "Hello, I'm reaching out because I'm scared...",
                        "inputs": {},
                    }
                ],
                "judge": {
                    "system": "You are an expert in evaluating medical communication...",
                    "prompt": "Evaluate both responses based on honesty and empathy: {{A}} vs {{B}}",
                    "view": {
                        "A": [
                            {"kind": "step", "id": "main_response", "part": "history"}
                        ],
                        "B": [
                            {"kind": "step", "id": "main_response", "part": "history"}
                        ],
                    },
                },
            },
            "arxiv-paper-summary": {
                "id": "arxiv-paper-summary",
                "name": "Academic Paper Summarization",
                "chain": [
                    {
                        "id": "read_paper",
                        "prompt": "Read this academic paper and provide key insights...",
                        "inputs": {"paper_url": "https://arxiv.org/abs/2412.14498v2"},
                    },
                    {
                        "id": "create_summary",
                        "prompt": "Create a concise summary of the key findings...",
                        "inputs": {},
                        "depends_on": ["read_paper"],
                        "carry": "final",
                    },
                ],
                "intermediaries": [
                    {
                        "id": "extract_citations",
                        "prompt": "Extract key citations and references...",
                        "inputs": {},
                        "from": [
                            {
                                "step": "read_paper",
                                "part": "final",
                                "as": "paper_content",
                            }
                        ],
                    }
                ],
                "judge": {
                    "system": "You are an expert in academic writing and research evaluation...",
                    "prompt": "Compare these two summaries for accuracy and completeness: {{A}} vs {{B}}",
                    "view": {
                        "A": [
                            {
                                "kind": "step",
                                "id": "create_summary",
                                "part": "final",
                                "label": "Summary",
                            },
                            {
                                "kind": "intermediary",
                                "id": "extract_citations",
                                "part": "final",
                                "label": "Citations",
                            },
                        ],
                        "B": [
                            {
                                "kind": "step",
                                "id": "create_summary",
                                "part": "final",
                                "label": "Summary",
                            },
                            {
                                "kind": "intermediary",
                                "id": "extract_citations",
                                "part": "final",
                                "label": "Citations",
                            },
                        ],
                    },
                },
            },
        }

    @pytest.fixture
    def generator(self):
        """Create FinalResultsGenerator instance."""
        return FinalResultsGenerator()

    def test_load_individual_skill_files(
        self, generator, mock_loaded_skills_data, mock_individual_skills
    ):
        """Test loading individual skill configuration files."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", create=True):
                with patch("json.load") as mock_json_load:
                    # Set up mock to return different skill configs
                    mock_json_load.side_effect = [
                        mock_individual_skills["procedural_fps_map"],
                        mock_individual_skills["terminal-diagnosis"],
                        mock_individual_skills["arxiv-paper-summary"],
                    ]

                    skills = generator.load_individual_skill_files(
                        mock_loaded_skills_data
                    )

                    # Verify correct files were loaded
                    assert len(skills) == 3
                    assert "procedural_fps_map" in skills
                    assert "terminal-diagnosis" in skills
                    assert "arxiv-paper-summary" in skills

                    # Verify skill content is correct
                    assert (
                        skills["procedural_fps_map"]["name"]
                        == "Procedural FPS Map Generator"
                    )
                    assert (
                        skills["terminal-diagnosis"]["name"]
                        == "Terminal Cancer Diagnosis Support"
                    )
                    assert (
                        skills["arxiv-paper-summary"]["name"]
                        == "Academic Paper Summarization"
                    )

                    # Verify all skills have required schema fields
                    for skill in skills.values():
                        assert "id" in skill
                        assert "name" in skill
                        assert "chain" in skill
                        assert "judge" in skill

    def test_load_individual_skill_files_missing_file(
        self, generator, mock_loaded_skills_data
    ):
        """Test handling of missing skill files."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Skill file not found"):
                generator.load_individual_skill_files(mock_loaded_skills_data)

    def test_load_individual_skill_files_invalid_json(
        self, generator, mock_loaded_skills_data
    ):
        """Test handling of malformed JSON in skill files."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", create=True):
                with patch(
                    "json.load",
                    side_effect=json.JSONDecodeError("Invalid JSON", "test", 0),
                ):
                    with pytest.raises(json.JSONDecodeError):
                        generator.load_individual_skill_files(mock_loaded_skills_data)

    def test_validate_evalconfig_schema(self, generator, mock_individual_skills):
        """Test validation of skills against EvalConfigTiny schema."""
        # Valid skill should pass
        assert (
            generator.validate_evalconfig_schema(
                mock_individual_skills["procedural_fps_map"]
            )
            is True
        )
        assert (
            generator.validate_evalconfig_schema(
                mock_individual_skills["terminal-diagnosis"]
            )
            is True
        )
        assert (
            generator.validate_evalconfig_schema(
                mock_individual_skills["arxiv-paper-summary"]
            )
            is True
        )

    def test_validate_evalconfig_schema_missing_required_fields(self, generator):
        """Test validation fails for skills missing required fields."""
        invalid_skills = [
            # Missing 'id'
            {
                "name": "Test Skill",
                "chain": [{"id": "step1", "prompt": "test"}],
                "judge": {"prompt": "test", "view": {"A": [], "B": []}},
            },
            # Missing 'name'
            {
                "id": "test-skill",
                "chain": [{"id": "step1", "prompt": "test"}],
                "judge": {"prompt": "test", "view": {"A": [], "B": []}},
            },
            # Missing 'chain'
            {
                "id": "test-skill",
                "name": "Test Skill",
                "judge": {"prompt": "test", "view": {"A": [], "B": []}},
            },
            # Missing 'judge'
            {
                "id": "test-skill",
                "name": "Test Skill",
                "chain": [{"id": "step1", "prompt": "test"}],
            },
        ]

        for invalid_skill in invalid_skills:
            assert generator.validate_evalconfig_schema(invalid_skill) is False

    def test_validate_evalconfig_schema_invalid_chain(self, generator):
        """Test validation fails for invalid chain structure."""
        invalid_skill = {
            "id": "test-skill",
            "name": "Test Skill",
            "chain": [
                # Missing required 'prompt' field
                {"id": "step1"}
            ],
            "judge": {"prompt": "test", "view": {"A": [], "B": []}},
        }

        assert generator.validate_evalconfig_schema(invalid_skill) is False

    def test_validate_evalconfig_schema_invalid_judge(self, generator):
        """Test validation fails for invalid judge structure."""
        invalid_skills = [
            # Missing judge 'prompt'
            {
                "id": "test-skill",
                "name": "Test Skill",
                "chain": [{"id": "step1", "prompt": "test"}],
                "judge": {"view": {"A": [], "B": []}},
            },
            # Missing judge 'view'
            {
                "id": "test-skill",
                "name": "Test Skill",
                "chain": [{"id": "step1", "prompt": "test"}],
                "judge": {"prompt": "test"},
            },
            # Missing view 'A' or 'B'
            {
                "id": "test-skill",
                "name": "Test Skill",
                "chain": [{"id": "step1", "prompt": "test"}],
                "judge": {"prompt": "test", "view": {"A": []}},
            },
        ]

        for invalid_skill in invalid_skills:
            assert generator.validate_evalconfig_schema(invalid_skill) is False

    def test_generate_final_results(
        self, generator, mock_loaded_skills_data, mock_individual_skills
    ):
        """Test generation of final results combining all skills."""
        with patch.object(
            generator,
            "load_individual_skill_files",
            return_value=mock_individual_skills,
        ):
            results = generator.generate_final_results(mock_loaded_skills_data)

            # Should return list of all skills
            assert isinstance(results, list)
            assert len(results) == 3

            # All skills should be present
            skill_ids = {skill["id"] for skill in results}
            expected_ids = {
                "procedural_fps_map",
                "terminal-diagnosis",
                "arxiv-paper-summary",
            }
            assert skill_ids == expected_ids

            # All skills should be valid EvalConfigTiny schemas
            for skill in results:
                assert generator.validate_evalconfig_schema(skill)

    def test_generate_final_results_with_validation_failure(
        self, generator, mock_loaded_skills_data
    ):
        """Test handling when a skill fails schema validation."""
        invalid_skills = {
            "invalid_skill": {
                "id": "invalid_skill",
                # Missing required fields to trigger validation failure
                "chain": [{"id": "step1", "prompt": "test"}],
            }
        }

        with patch.object(
            generator, "load_individual_skill_files", return_value=invalid_skills
        ):
            with pytest.raises(
                ValueError,
                match="Skill 'invalid_skill' does not match EvalConfigTiny schema",
            ):
                generator.generate_final_results(mock_loaded_skills_data)


class TestMain:
    """Test the main function that integrates with Snakemake."""

    def test_main_success(self):
        """Test successful execution of main function."""
        mock_loaded_skills = {
            "skills": {
                "test_skill": {
                    "eval_count": 1,
                    "eval_ids": ["test_eval"],
                    "path": "skills/test_skill",
                }
            }
        }
        mock_final_results = [
            {
                "id": "test_eval",
                "name": "Test Evaluation",
                "chain": [{"id": "step1", "prompt": "test"}],
                "judge": {"prompt": "test", "view": {"A": [], "B": []}},
            }
        ]

        # Mock snakemake object
        mock_snakemake = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_skills = Path(temp_dir) / "loaded_skills.json"
            temp_output = Path(temp_dir) / "final_results.json"

            # Write mock input file
            with open(temp_skills, "w") as f:
                json.dump(mock_loaded_skills, f)

            # Configure mock snakemake paths
            mock_snakemake.input.skills = str(temp_skills)
            mock_snakemake.output = [str(temp_output)]

            with patch(
                "scripts.generate_final_results.FinalResultsGenerator"
            ) as mock_generator_class:
                mock_generator = Mock()
                mock_generator.generate_final_results.return_value = mock_final_results
                mock_generator_class.return_value = mock_generator

                # Inject snakemake object into the module's globals
                import scripts.generate_final_results as results_module

                results_module.snakemake = mock_snakemake

                try:
                    with patch("builtins.print") as mock_print:
                        main()
                finally:
                    # Clean up
                    if hasattr(results_module, "snakemake"):
                        delattr(results_module, "snakemake")

                # Verify generator was called correctly
                mock_generator.generate_final_results.assert_called_once_with(
                    mock_loaded_skills
                )

                # Verify output file was created
                assert temp_output.exists()

                # Verify output contents
                with open(temp_output) as f:
                    result = json.load(f)

                assert result == mock_final_results

                # Verify console output
                mock_print.assert_any_call(
                    "Generating final results from loaded skills..."
                )
                mock_print.assert_any_call("Generated final results with 1 skills")
                mock_print.assert_any_call(f"Saved final results to {temp_output}")

    def test_main_file_not_found_error(self):
        """Test main function handling of missing input files."""
        mock_snakemake = Mock()
        mock_snakemake.input.skills = "/nonexistent/skills.json"
        mock_snakemake.output = ["/path/to/final_results.json"]

        # Inject snakemake object into the module's globals
        import scripts.generate_final_results as results_module

        results_module.snakemake = mock_snakemake

        try:
            with pytest.raises(FileNotFoundError):
                main()
        finally:
            # Clean up
            if hasattr(results_module, "snakemake"):
                delattr(results_module, "snakemake")

    def test_main_json_decode_error(self):
        """Test main function handling of malformed JSON files."""
        mock_snakemake = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_skills = Path(temp_dir) / "skills.json"

            # Write malformed JSON
            with open(temp_skills, "w") as f:
                f.write("invalid json {")

            mock_snakemake.input.skills = str(temp_skills)
            mock_snakemake.output = ["/path/to/results.json"]

            # Inject snakemake object into the module's globals
            import scripts.generate_final_results as results_module

            results_module.snakemake = mock_snakemake

            try:
                with pytest.raises(json.JSONDecodeError):
                    main()
            finally:
                # Clean up
                if hasattr(results_module, "snakemake"):
                    delattr(results_module, "snakemake")
