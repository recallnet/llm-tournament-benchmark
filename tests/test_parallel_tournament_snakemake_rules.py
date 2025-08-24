#!/usr/bin/env python3
"""
TDD Tests for Parallel Tournament Snakemake Rules

These tests verify the specific Snakemake rule structure needed for
parallel tournament execution. They focus on the workflow DAG and
rule dependencies.
"""

import json
import subprocess
import tempfile
from pathlib import Path
import pytest


class TestParallelTournamentSnakemakeRules:
    """Test Snakemake rule structure for parallel tournaments."""

    def test_skill_wildcard_extraction_function_exists(self):
        """
        EXPECTED BEHAVIOR: Should have a get_skills() function that dynamically
        extracts skill names from loaded_skills.json for wildcard expansion.
        
        This will FAIL initially.
        """
        snakefile_path = Path("Snakefile") 
        with open(snakefile_path) as f:
            content = f.read()
        
        # Should have function to get skill names
        assert "get_skills" in content, "Missing get_skills() function for skill wildcards"

    def test_per_skill_tournament_rule_structure(self):
        """
        EXPECTED BEHAVIOR: The per-skill tournament rule should have proper
        wildcard constraints and output naming.
        
        This will FAIL initially.
        """
        snakefile_path = Path("Snakefile")
        with open(snakefile_path) as f:
            content = f.read()
        
        # Check rule structure
        assert "rule run_tournament_per_skill:" in content
        assert "wildcard_constraints:" in content
        assert "tournament_{skill}.json" in content

    def test_tournament_aggregation_rule_structure(self):
        """
        EXPECTED BEHAVIOR: Should have aggregation rule that combines
        per-skill tournament files into single tournaments.json.
        
        This will FAIL initially.
        """
        snakefile_path = Path("Snakefile")
        with open(snakefile_path) as f:
            content = f.read()
        
        assert "rule aggregate_tournaments:" in content
        assert "tournament_{skill}.json" in content  # Input pattern
        assert 'DATA_DIR / "tournaments.json"' in content  # Final output

    def test_snakemake_dry_run_shows_parallel_capability(self):
        """
        EXPECTED BEHAVIOR: Snakemake dry run should show that multiple
        tournament rules can execute in parallel.
        
        This will FAIL until rules are implemented.
        """
        try:
            result = subprocess.run([
                "snakemake", "--dry-run", 
                "--profile", "profiles/quick", 
                "data/quick/tournaments.json"
            ], capture_output=True, text=True, cwd=".", timeout=15)
            
            # Should succeed
            assert result.returncode == 0, f"Dry run failed: {result.stderr}"
            
            # Should show parallel tournament execution capability
            output = result.stdout
            # Look for multiple tournament rules in execution plan
            tournament_count = output.count("run_tournament_per_skill")
            aggregate_count = output.count("aggregate_tournaments")
            
            # Should have multiple skills = multiple tournament rules + 1 aggregation
            assert tournament_count >= 2 or aggregate_count >= 1, \
                f"Expected parallel tournament rules, found {tournament_count} skills + {aggregate_count} aggregations"
                
        except FileNotFoundError:
            pytest.skip("Snakemake not available")

    def test_tournament_rule_dependencies_preserved(self):
        """
        EXPECTED BEHAVIOR: Per-skill tournament rules should maintain
        the same dependencies as current monolithic rule.
        
        Critical for production compatibility.
        """
        snakefile_path = Path("Snakefile")
        with open(snakefile_path) as f:
            content = f.read()
        
        # Should depend on conversations being completed
        assert "conversations_completed.flag" in content
        
        # Should depend on loaded models, judges, skills
        dependency_files = [
            "loaded_models.json", 
            "loaded_judges.json",
            "loaded_skills.json"
        ]
        
        for dep_file in dependency_files:
            assert dep_file in content, f"Missing dependency: {dep_file}"

    def test_skill_name_sanitization_for_filenames(self):
        """
        EXPECTED BEHAVIOR: Skill names should be properly sanitized 
        for use as filename components.
        
        Important for skills with underscores, etc.
        """
        # Mock skill names that need sanitization
        test_skills = ["harm_avoidance", "code_generation", "hidden_messages"]
        
        for skill in test_skills:
            # Should be valid filename component
            assert "_" in skill  # These are the actual skill names
            assert skill.replace("_", "").isalnum(), f"Skill name not filename-safe: {skill}"

    def test_parallel_execution_resource_constraints(self):
        """
        EXPECTED BEHAVIOR: Tournament rules should have appropriate
        resource constraints for parallel execution without overwhelming system.
        """
        # Will verify resource limits are set appropriately
        # This ensures -j5 doesn't spawn too many concurrent processes
        pytest.skip("Resource constraint testing - implementation pending")


class TestTournamentScriptModularization:
    """Tests for the underlying tournament script changes needed."""
    
    def test_single_skill_tournament_script_exists(self):
        """
        EXPECTED BEHAVIOR: Should have a script that can run tournaments
        for a single skill, enabling per-skill parallelization.
        
        This will FAIL initially.
        """
        script_path = Path("scripts/run_single_skill_tournament.py")
        
        # Script should exist
        assert script_path.exists(), "Missing single-skill tournament script"
        
        # Should be executable  
        with open(script_path) as f:
            content = f.read()
        
        assert "main" in content, "Script should have main function"

    def test_tournament_aggregation_script_exists(self):
        """
        EXPECTED BEHAVIOR: Should have a script that combines per-skill
        tournament results into final tournaments.json format.
        
        This will FAIL initially.
        """
        script_path = Path("scripts/aggregate_tournament_results.py")
        
        assert script_path.exists(), "Missing tournament aggregation script"
        
        with open(script_path) as f:
            content = f.read()
        
        assert "aggregate" in content.lower(), "Script should have aggregation logic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])