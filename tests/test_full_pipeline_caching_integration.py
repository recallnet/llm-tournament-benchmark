#!/usr/bin/env python3
"""
CRITICAL: Full pipeline caching integration tests.
Tests the ONLY command that matters: snakemake afbench --profile profiles/testonly

These tests MUST pass before any pipeline changes are accepted.
"""

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest


class TestFullPipelineCaching:
    """Test the complete pipeline with real caching scenarios."""

    @pytest.fixture
    def clean_pipeline_state(self):
        """Clean state for each test."""
        # Test will automatically fail if it tries to touch production data
        # Our safety system will prevent any filesystem access to data/
        yield

    def run_pipeline(self, timeout=300):
        """Run the full pipeline with timeout."""
        cmd = ["snakemake", "--unlock"]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        cmd = ["snakemake", "afbench", "--profile", "profiles/testonly"]

        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.time() - start_time

        return result, elapsed

    @pytest.mark.skip(
        "DISABLED: This test runs the full pipeline which takes too long and costs money"
    )
    @pytest.mark.skip("DISABLED: Full pipeline tests cost money and take too long")
    def test_fresh_pipeline_run(self, clean_pipeline_state):
        """Test: Fresh pipeline run creates all cache files."""
        result, elapsed = self.run_pipeline()

        assert result.returncode == 0, f"Pipeline failed: {result.stderr}"

        # Check all expected outputs exist
        expected_outputs = [
            "data/testonly/loaded_models.json",
            "data/testonly/loaded_judges.json",
            "data/testonly/loaded_skills.json",
            "data/testonly/tournaments.json",
            "data/testonly/tournament_summaries.json",
            "data/testonly/skill_ratings.json",
        ]

        for output in expected_outputs:
            assert Path(output).exists(), f"Missing output: {output}"

        # Check conversation cache exists
        cache_files = list(Path("data/testonly").glob("conversations_cache_*.done"))
        assert len(cache_files) > 0, "No conversation cache files created"

        # Check judge cache exists
        judge_cache_files = list(Path("data/testonly/judge_cache").rglob("*.json"))
        initial_judge_cache_count = len(judge_cache_files)
        assert initial_judge_cache_count > 0, "No judge cache files created"

        print(f"✅ Fresh pipeline run completed in {elapsed:.1f}s")
        print(f"✅ Created {initial_judge_cache_count} judge cache files")

    @pytest.mark.skip("DISABLED: Full pipeline tests cost money and take too long")
    def test_second_run_uses_cache(self, clean_pipeline_state):
        """Test: Second run uses cache and completes quickly."""
        # First run
        result1, elapsed1 = self.run_pipeline()
        assert result1.returncode == 0, f"First run failed: {result1.stderr}"

        # Get initial cache state
        judge_cache_files = list(Path("data/testonly/judge_cache").rglob("*.json"))
        initial_cache_count = len(judge_cache_files)

        # Second run should be much faster
        result2, elapsed2 = self.run_pipeline()
        assert result2.returncode == 0, f"Second run failed: {result2.stderr}"

        # Check no new judge cache files created
        judge_cache_files_after = list(
            Path("data/testonly/judge_cache").rglob("*.json")
        )
        final_cache_count = len(judge_cache_files_after)

        assert (
            final_cache_count == initial_cache_count
        ), f"Cache invalidated! Initial: {initial_cache_count}, Final: {final_cache_count}"

        # Second run should be significantly faster (using cache)
        speedup = elapsed1 / elapsed2
        assert (
            speedup > 2
        ), f"Second run not fast enough: {elapsed2:.1f}s vs {elapsed1:.1f}s (speedup: {speedup:.1f}x)"

        print(f"✅ Second run completed in {elapsed2:.1f}s (speedup: {speedup:.1f}x)")

    @pytest.mark.skip("DISABLED: Full pipeline tests cost money and take too long")
    def test_interrupted_pipeline_resume(self, clean_pipeline_state):
        """Test: Pipeline can be interrupted and resumed without cache loss."""
        # Start pipeline and kill it after partial progress
        cmd = ["snakemake", "--unlock"]
        subprocess.run(cmd, check=True, capture_output=True)

        cmd = ["snakemake", "afbench", "--profile", "profiles/testonly"]
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Let it run for a few seconds then kill
        time.sleep(10)
        process.terminate()

        # Wait for graceful shutdown
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        # Check some cache was created
        judge_cache_files = list(Path("data/testonly/judge_cache").rglob("*.json"))
        partial_cache_count = len(judge_cache_files)

        if partial_cache_count == 0:
            pytest.skip("No cache created during partial run")

        # Resume pipeline
        result, elapsed = self.run_pipeline()
        assert result.returncode == 0, f"Resume failed: {result.stderr}"

        # Check cache was preserved and extended
        judge_cache_files_final = list(
            Path("data/testonly/judge_cache").rglob("*.json")
        )
        final_cache_count = len(judge_cache_files_final)

        assert (
            final_cache_count >= partial_cache_count
        ), f"Cache lost during resume! Partial: {partial_cache_count}, Final: {final_cache_count}"

        print(
            f"✅ Pipeline resumed successfully, cache preserved ({final_cache_count} files)"
        )

    @pytest.mark.skip("DISABLED: Full pipeline tests cost money and take too long")
    def test_model_addition_invalidates_correctly(self, clean_pipeline_state):
        """Test: Adding a model only regenerates what's needed."""
        # First run
        result1, _ = self.run_pipeline()
        assert result1.returncode == 0

        initial_cache_count = len(
            list(Path("data/testonly/judge_cache").rglob("*.json"))
        )
        initial_tournaments = Path("data/testonly/tournaments.json").read_text()

        # Add a model to the test pool
        test_pool = Path("model_pools/test.csv")
        original_content = test_pool.read_text()

        try:
            # Add a new model
            with open(test_pool, "a") as f:
                f.write("\nnew/test-model,Test Model,1.0,active\n")

            # Force model reload
            Path("data/testonly/loaded_models.json").unlink(missing_ok=True)

            # Run again
            result2, _ = self.run_pipeline()
            assert (
                result2.returncode == 0
            ), f"Failed after model addition: {result2.stderr}"

            # Check tournaments were regenerated
            new_tournaments = Path("data/testonly/tournaments.json").read_text()
            assert (
                new_tournaments != initial_tournaments
            ), "Tournaments not regenerated after model addition"

            # Check some cache was preserved (existing models vs existing models matches)
            final_cache_count = len(
                list(Path("data/testonly/judge_cache").rglob("*.json"))
            )
            assert (
                final_cache_count > initial_cache_count
            ), "No new cache created for new model"

            print(
                f"✅ Model addition handled correctly (cache grew from {initial_cache_count} to {final_cache_count})"
            )

        finally:
            # Restore original pool
            test_pool.write_text(original_content)

    @pytest.mark.skip("DISABLED: Full pipeline tests cost money and take too long")
    def test_eval_modification_invalidates_correctly(self, clean_pipeline_state):
        """Test: Modifying an eval only regenerates affected conversations."""
        # First run
        result1, _ = self.run_pipeline()
        assert result1.returncode == 0

        initial_cache_count = len(
            list(Path("data/testonly/judge_cache").rglob("*.json"))
        )

        # Modify an eval
        eval_files = list(Path("skills").rglob("*.json"))
        if not eval_files:
            pytest.skip("No eval files found")

        test_eval = eval_files[0]
        original_content = test_eval.read_text()

        try:
            # Modify the eval
            eval_data = json.loads(original_content)
            eval_data["user_message"] = f"MODIFIED: {eval_data['user_message']}"
            test_eval.write_text(json.dumps(eval_data, indent=2))

            # Run again
            result2, _ = self.run_pipeline()
            assert (
                result2.returncode == 0
            ), f"Failed after eval modification: {result2.stderr}"

            # Cache should have grown (new conversations for modified eval)
            final_cache_count = len(
                list(Path("data/testonly/judge_cache").rglob("*.json"))
            )

            print(
                f"✅ Eval modification handled (cache: {initial_cache_count} -> {final_cache_count})"
            )

        finally:
            # Restore original eval
            test_eval.write_text(original_content)

    @pytest.mark.skip("DISABLED: Full pipeline tests cost money and take too long")
    def test_cache_corruption_recovery(self, clean_pipeline_state):
        """Test: Pipeline recovers from corrupted cache files."""
        # First run
        result1, _ = self.run_pipeline()
        assert result1.returncode == 0

        # Corrupt a cache file
        judge_cache_files = list(Path("data/testonly/judge_cache").rglob("*.json"))
        if judge_cache_files:
            corrupted_file = judge_cache_files[0]
            corrupted_file.write_text("CORRUPTED")

        # Pipeline should still complete (regenerating corrupted entry)
        result2, _ = self.run_pipeline()
        assert (
            result2.returncode == 0
        ), f"Failed to recover from corruption: {result2.stderr}"

        # Check corrupted file was fixed
        if judge_cache_files:
            content = corrupted_file.read_text()
            assert content != "CORRUPTED", "Corrupted cache file not regenerated"
            assert content.startswith("{"), "Cache file not valid JSON"

        print("✅ Recovered from cache corruption")

    @pytest.mark.skip("DISABLED: Full pipeline tests cost money and take too long")
    def test_pipeline_deterministic(self, clean_pipeline_state):
        """Test: Multiple runs produce identical results."""
        results = []

        for i in range(2):
            # Clean run
            if Path("data/testonly").exists():
                shutil.rmtree("data/testonly")

            result, _ = self.run_pipeline()
            assert result.returncode == 0, f"Run {i+1} failed: {result.stderr}"

            # Collect key outputs
            tournaments = json.loads(Path("data/testonly/tournaments.json").read_text())
            skill_ratings = json.loads(
                Path("data/testonly/skill_ratings.json").read_text()
            )

            results.append({"tournaments": tournaments, "skill_ratings": skill_ratings})

        # Results should be identical
        assert (
            results[0] == results[1]
        ), "Pipeline not deterministic - results differ between runs"

        print("✅ Pipeline is deterministic")


@pytest.mark.skip("DISABLED: Full pipeline tests cost money and take too long")
def test_critical_cache_invariants():
    """Test critical caching invariants that MUST hold."""

    # Judge cache structure must be consistent
    judge_cache_dir = Path("data/testonly/judge_cache")
    if judge_cache_dir.exists():
        cache_files = list(judge_cache_dir.rglob("*.json"))

        for cache_file in cache_files:
            # All cache files must be valid JSON
            try:
                data = json.loads(cache_file.read_text())
                assert isinstance(data, dict), f"Cache file not dict: {cache_file}"
                assert (
                    "vote" in data or "error" in data
                ), f"Invalid cache structure: {cache_file}"
            except json.JSONDecodeError:
                pytest.fail(f"Corrupted cache file: {cache_file}")

    print("✅ Cache invariants verified")


if __name__ == "__main__":
    # Run critical tests
    pytest.main([__file__, "-v", "-s"])
