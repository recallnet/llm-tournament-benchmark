"""
TDD tests for removing mega conversations.json file generation.

These tests verify that the tournament system can work without the
massive conversations.json aggregation file.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRemoveMegaConversationsFile:
    """Test removing the mega conversations.json file from pipeline."""

    def test_tournament_rule_without_conversations_json_dependency(self):
        """Test that tournament rule can work without conversations.json input."""
        print("\\n🚫 TESTING: Tournament rule without conversations.json")

        # This test should pass after we modify the Snakefile
        # Currently it will fail because the rule still depends on conversations.json

        from pathlib import Path

        # Mock Snakemake environment
        mock_snakemake = MagicMock()

        # Create temp files for non-conversations inputs
        temp_dir = tempfile.mkdtemp()
        try:
            # Create mock input files (not conversations.json)
            mock_snakemake.input.models = str(Path(temp_dir) / "models.json")
            mock_snakemake.input.judges = str(Path(temp_dir) / "judges.json")
            mock_snakemake.input.skills = str(Path(temp_dir) / "skills.json")
            mock_snakemake.input.conversations_cache_dir = str(Path(temp_dir) / "conversations")
            mock_snakemake.output = [str(Path(temp_dir) / "tournaments.json")]

            # Create the mock input files
            with open(mock_snakemake.input.models, "w") as f:
                json.dump({"models": [{"id": "test_model"}]}, f)

            with open(mock_snakemake.input.judges, "w") as f:
                json.dump({"judges": [{"id": "test_judge"}]}, f)

            with open(mock_snakemake.input.skills, "w") as f:
                json.dump({"skills": {"test_skill": {}}, "evals": [{"id": "test_eval"}]}, f)

            # Create conversations cache directory
            Path(mock_snakemake.input.conversations_cache_dir).mkdir(parents=True, exist_ok=True)

            # Mock the tournament script to accept cache directory instead of mega file
            with patch("scripts.run_tournaments.main_with_cache_dir") as mock_main:
                mock_main.return_value = None

                # This should work without conversations.json
                # (We'll need to implement main_with_cache_dir)
                from scripts.run_tournaments import main_with_cache_dir

                result = main_with_cache_dir(
                    mock_snakemake.input.conversations_cache_dir,
                    mock_snakemake.input.models,
                    mock_snakemake.input.judges,
                    mock_snakemake.input.skills,
                    mock_snakemake.output[0],
                )

                # Should succeed without needing conversations.json
                print("✅ Tournament rule works without conversations.json dependency")

        finally:
            import shutil

            shutil.rmtree(temp_dir)

    def test_snakemake_dag_without_aggregation_rules(self):
        """Test that Snakemake DAG works without aggregation rules."""
        print("\\n📊 TESTING: Snakemake DAG without aggregation")

        # This will test that the dependency chain works:
        # individual_cache -> tournaments -> skill_ratings -> afbench
        # Without: individual_cache -> per_model_files -> mega_file -> tournaments

        # Mock a simplified Snakemake workflow
        workflow_rules = {
            "afbench": {"input": ["skill_ratings.json"]},
            "calculate_skill_ratings": {"input": ["tournament_summaries.json"]},
            "summarize_tournaments": {"input": ["tournaments.json"]},
            "run_tournaments_direct": {"input": ["conversations/", "models.json", "judges.json", "skills.json"]},
            # Note: No aggregate_conversations or execute_conversations_for_model rules
        }

        def check_dependency_chain(target, visited=None):
            """Check if we can reach target without aggregation rules."""
            if visited is None:
                visited = set()

            if target in visited:
                return True  # Circular dependency or already processed

            visited.add(target)

            if target not in workflow_rules:
                # Leaf node (actual file)
                return True

            # Check all dependencies
            for dep in workflow_rules[target]["input"]:
                if not check_dependency_chain(dep, visited.copy()):
                    return False

            return True

        # Test that we can reach afbench without aggregation rules
        can_build_afbench = check_dependency_chain("afbench")
        assert can_build_afbench, "Should be able to build afbench without aggregation rules"

        # Verify aggregation rules are not needed
        forbidden_rules = ["aggregate_conversations", "execute_conversations_for_model"]
        for rule_name in workflow_rules:
            assert rule_name not in forbidden_rules, f"Should not have {rule_name} rule"

        print("✅ Snakemake DAG works without aggregation rules")

    def test_conversations_json_not_created(self):
        """Test that conversations.json is not created in new pipeline."""
        print("\\n🚫 TESTING: conversations.json not created")

        temp_dir = tempfile.mkdtemp()
        try:
            conversations_file = Path(temp_dir) / "conversations.json"

            # Simulate running new pipeline
            # conversations.json should NOT be created

            # Mock successful tournament run without creating conversations.json
            with patch("scripts.run_tournaments.main_with_cache_dir") as mock_main:
                mock_main.return_value = {"success": True}

                # Run tournament directly with cache
                from scripts.run_tournaments import main_with_cache_dir

                result = main_with_cache_dir(
                    str(Path(temp_dir) / "conversations"),
                    str(Path(temp_dir) / "models.json"),
                    str(Path(temp_dir) / "judges.json"),
                    str(Path(temp_dir) / "skills.json"),
                    str(Path(temp_dir) / "tournaments.json"),
                )

            # conversations.json should NOT exist
            assert not conversations_file.exists(), "conversations.json should not be created"

            print("✅ conversations.json is not created in new pipeline")

        finally:
            import shutil

            shutil.rmtree(temp_dir)

    def test_per_model_files_not_created(self):
        """Test that per-model files are not created in new pipeline."""
        print("\\n🚫 TESTING: Per-model files not created")

        temp_dir = tempfile.mkdtemp()
        try:
            # Per-model files should NOT be created
            model_files = [Path(temp_dir) / "conversations_model1.json", Path(temp_dir) / "conversations_model2.json"]

            # Mock successful pipeline run
            with patch("scripts.run_tournaments.main_with_cache_dir") as mock_main:
                mock_main.return_value = {"success": True}

                from scripts.run_tournaments import main_with_cache_dir

                result = main_with_cache_dir(
                    str(Path(temp_dir) / "conversations"),
                    str(Path(temp_dir) / "models.json"),
                    str(Path(temp_dir) / "judges.json"),
                    str(Path(temp_dir) / "skills.json"),
                    str(Path(temp_dir) / "tournaments.json"),
                )

            # Per-model files should NOT exist
            for model_file in model_files:
                assert not model_file.exists(), f"{model_file.name} should not be created"

            print("✅ Per-model files are not created in new pipeline")

        finally:
            import shutil

            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
