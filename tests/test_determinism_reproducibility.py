"""
Test Suite for Determinism & Reproducibility (TESTS.md Section 1)

Tests the Single-Command Contract (SCC) with profiles/testonly:
- All tests use only: snakemake --unlock && snakemake --profile profiles/testonly -j <k>
- No targeted rule runs
- Isolated workspace with deterministic fixtures
- Fixed seeds for reproducible results

Test Categories:
- D1: Repeatable runs (byte-for-byte identical outputs)
- D2: Seed stability (identical conversation IDs across runs)
- D3: Clock neutrality (wall time doesn't affect outputs)
"""

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest


class TestDeterminismReproducibility:
    """Test determinism and reproducibility using Single-Command Contract (SCC)."""

    @pytest.fixture(autouse=True)
    def setup_isolated_workspace(self, tmp_path):
        """
        Create isolated workspace for each test with immutable fixture copies.

        Follows the pattern:
        1. Copy canonical fixtures to temp workspace
        2. Apply mutations there as needed
        3. Cleanup automatically via pytest tmp_path
        """
        self.workspace = tmp_path
        self.original_cwd = Path.cwd()

        # Copy entire AFBench structure to isolated workspace
        afbench_root = Path(__file__).parent.parent
        for item in [
            "Snakefile",
            "config",
            "profiles",
            "scripts",
            "model_pools",
            "judge_pools",
            "skills",
        ]:
            src = afbench_root / item
            dst = self.workspace / item
            if src.exists():
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

        # Change to isolated workspace for test execution
        import os

        os.chdir(self.workspace)

        yield self.workspace

        # Cleanup: return to original directory
        os.chdir(self.original_cwd)

    def run_scc(
        self, profile: str = "testonly", jobs: int = 1, timeout: int = 300
    ) -> subprocess.CompletedProcess:
        """
        Execute Single-Command Contract (SCC).

        Args:
            profile: Profile to use (default: testonly)
            jobs: Number of parallel jobs
            timeout: Command timeout in seconds

        Returns:
            CompletedProcess with stdout, stderr, returncode
        """
        # Always unlock first, then run with specified profile and jobs
        unlock_cmd = ["snakemake", "--unlock"]
        unlock_result = subprocess.run(
            unlock_cmd, capture_output=True, text=True, timeout=timeout
        )

        # If unlock fails, return early
        if unlock_result.returncode != 0:
            return unlock_result

        # Run main pipeline
        run_cmd = ["snakemake", f"--profile=profiles/{profile}", f"-j{jobs}"]
        return subprocess.run(run_cmd, capture_output=True, text=True, timeout=timeout)

    def get_artifact_checksums(self, data_dir: Path) -> dict[str, str]:
        """
        Calculate checksums for all artifacts in data directory.

        Args:
            data_dir: Path to data directory (e.g., data/testonly)

        Returns:
            Dict mapping relative file paths to MD5 checksums
        """
        checksums = {}

        if not data_dir.exists():
            return checksums

        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                # Skip log files and explicit timestamp fields
                if (
                    file_path.suffix in [".log", ".lock"]
                    or "timestamp" in file_path.name.lower()
                ):
                    continue

                try:
                    content = file_path.read_bytes()
                    # For JSON files, normalize timestamp fields to enable comparison
                    if file_path.suffix == ".json":
                        try:
                            data = json.loads(content.decode())
                            # Recursively remove timestamp fields
                            self._remove_timestamps(data)
                            content = json.dumps(data, sort_keys=True).encode()
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # If not valid JSON, use raw content
                            pass

                    checksum = hashlib.md5(content).hexdigest()
                    rel_path = file_path.relative_to(data_dir)
                    checksums[str(rel_path)] = checksum
                except (OSError, PermissionError):
                    # Skip files that can't be read
                    continue

        return checksums

    def _remove_timestamps(self, obj):
        """Recursively remove timestamp fields from dict/list structures."""
        if isinstance(obj, dict):
            # Remove common timestamp field names
            timestamp_keys = [
                k
                for k in obj.keys()
                if "timestamp" in k.lower()
                or k in ["created", "modified", "generated_at"]
            ]
            for key in timestamp_keys:
                obj.pop(key, None)
            # Recurse into remaining values
            for value in obj.values():
                self._remove_timestamps(value)
        elif isinstance(obj, list):
            for item in obj:
                self._remove_timestamps(item)

    def get_conversation_ids(self, data_dir: Path) -> set[str]:
        """
        Extract conversation IDs from conversations directory.

        Args:
            data_dir: Path to data directory

        Returns:
            Set of conversation file names (deterministic ordering test)
        """
        conversations_dir = data_dir / "conversations"
        conversation_ids = set()

        if conversations_dir.exists():
            for conv_file in conversations_dir.rglob("*.json"):
                conversation_ids.add(conv_file.name)

        return conversation_ids

    def assert_no_work_done(self, result: subprocess.CompletedProcess):
        """Assert that SCC run performed no work (cached run)."""
        output = result.stdout + result.stderr
        # Look for Snakemake's standard "nothing to be done" indicators
        no_work_indicators = [
            "Nothing to be done",
            "all requested files are present and up to date",
        ]

        assert any(
            indicator in output for indicator in no_work_indicators
        ), f"Expected no-work run, but got output: {output}"

    # =============================================================================
    # Test D1 – Repeatable run
    # =============================================================================

    def test_d1_repeatable_run_j1(self):
        """
        D1: Given identical inputs and config, repeated runs produce identical artifacts.
        Test with -j 1 (serial execution).
        """
        data_dir = self.workspace / "data" / "testonly"

        # First run
        result1 = self.run_scc(profile="testonly", jobs=1)
        assert result1.returncode == 0, f"First run failed: {result1.stderr}"

        checksums1 = self.get_artifact_checksums(data_dir)
        assert len(checksums1) > 0, "No artifacts produced in first run"

        # Second run (should be no-op)
        result2 = self.run_scc(profile="testonly", jobs=1)
        assert result2.returncode == 0, f"Second run failed: {result2.stderr}"

        # Verify second run did no work
        self.assert_no_work_done(result2)

        # Verify artifacts are byte-for-byte identical
        checksums2 = self.get_artifact_checksums(data_dir)
        assert (
            checksums1 == checksums2
        ), f"Artifacts changed between runs. Diff: {set(checksums1.items()) ^ set(checksums2.items())}"

    def test_d1_repeatable_run_j5(self):
        """
        D1: Same as above but with -j 5 (parallel execution).
        Ensures determinism holds under parallelism.
        """
        data_dir = self.workspace / "data" / "testonly"

        # First run with parallelism
        result1 = self.run_scc(profile="testonly", jobs=5)
        assert result1.returncode == 0, f"First parallel run failed: {result1.stderr}"

        checksums1 = self.get_artifact_checksums(data_dir)
        assert len(checksums1) > 0, "No artifacts produced in first parallel run"

        # Second run (should be no-op)
        result2 = self.run_scc(profile="testonly", jobs=5)
        assert result2.returncode == 0, f"Second parallel run failed: {result2.stderr}"

        # Verify second run did no work
        self.assert_no_work_done(result2)

        # Verify artifacts are byte-for-byte identical
        checksums2 = self.get_artifact_checksums(data_dir)
        assert (
            checksums1 == checksums2
        ), f"Parallel artifacts changed between runs. Diff: {set(checksums1.items()) ^ set(checksums2.items())}"

    def test_d1_serial_vs_parallel_identical(self):
        """
        D1: Verify that -j 1 and -j 5 produce identical results.
        Tests determinism across different parallelism levels.
        """
        # Run serial first
        result_serial = self.run_scc(profile="testonly", jobs=1)
        assert (
            result_serial.returncode == 0
        ), f"Serial run failed: {result_serial.stderr}"

        checksums_serial = self.get_artifact_checksums(
            self.workspace / "data" / "testonly"
        )

        # Clean workspace and run parallel
        shutil.rmtree(self.workspace / "data" / "testonly", ignore_errors=True)

        result_parallel = self.run_scc(profile="testonly", jobs=5)
        assert (
            result_parallel.returncode == 0
        ), f"Parallel run failed: {result_parallel.stderr}"

        checksums_parallel = self.get_artifact_checksums(
            self.workspace / "data" / "testonly"
        )

        # Results should be identical regardless of parallelism
        assert (
            checksums_serial == checksums_parallel
        ), f"Serial vs parallel results differ. Diff: {set(checksums_serial.items()) ^ set(checksums_parallel.items())}"

    # =============================================================================
    # Test D2 – Seed stability
    # =============================================================================

    def test_d2_conversation_ids_identical_across_runs(self):
        """
        D2: Given fixed random seeds, conversation IDs are identical across runs.
        """
        data_dir = self.workspace / "data" / "testonly"

        # First clean run
        result1 = self.run_scc(profile="testonly", jobs=1)
        assert result1.returncode == 0, f"First run failed: {result1.stderr}"

        conversation_ids1 = self.get_conversation_ids(data_dir)
        assert len(conversation_ids1) > 0, "No conversations generated in first run"

        # Clean workspace completely
        shutil.rmtree(data_dir, ignore_errors=True)

        # Second clean run
        result2 = self.run_scc(profile="testonly", jobs=1)
        assert result2.returncode == 0, f"Second run failed: {result2.stderr}"

        conversation_ids2 = self.get_conversation_ids(data_dir)

        # Conversation IDs should be identical due to fixed seeds
        assert (
            conversation_ids1 == conversation_ids2
        ), f"Conversation IDs differ between runs. Run1: {conversation_ids1}, Run2: {conversation_ids2}"

    def test_d2_seed_determinism_parallel(self):
        """
        D2: Seed stability holds under parallel execution.
        """
        data_dir = self.workspace / "data" / "testonly"

        # First parallel run
        result1 = self.run_scc(profile="testonly", jobs=5)
        assert result1.returncode == 0, f"First parallel run failed: {result1.stderr}"

        conversation_ids1 = self.get_conversation_ids(data_dir)

        # Clean and run again
        shutil.rmtree(data_dir, ignore_errors=True)

        result2 = self.run_scc(profile="testonly", jobs=5)
        assert result2.returncode == 0, f"Second parallel run failed: {result2.stderr}"

        conversation_ids2 = self.get_conversation_ids(data_dir)

        # Should be identical even under parallelism
        assert (
            conversation_ids1 == conversation_ids2
        ), f"Parallel conversation IDs differ. Run1: {conversation_ids1}, Run2: {conversation_ids2}"

    # =============================================================================
    # Test D3 – Clock neutrality
    # =============================================================================

    def test_d3_wall_time_independence(self):
        """
        D3: Runs at different wall times produce identical outputs.
        Tests that wall clock time doesn't affect deterministic outputs.
        """
        data_dir = self.workspace / "data" / "testonly"

        # First run
        result1 = self.run_scc(profile="testonly", jobs=1)
        assert result1.returncode == 0, f"First timed run failed: {result1.stderr}"

        checksums1 = self.get_artifact_checksums(data_dir)

        # Wait to ensure different wall time, then clean and re-run
        time.sleep(2)
        shutil.rmtree(data_dir, ignore_errors=True)

        result2 = self.run_scc(profile="testonly", jobs=1)
        assert result2.returncode == 0, f"Second timed run failed: {result2.stderr}"

        checksums2 = self.get_artifact_checksums(data_dir)

        # Results should be identical despite different wall times
        # (timestamp fields are excluded from checksum calculation)
        assert (
            checksums1 == checksums2
        ), f"Wall time affected results. Diff: {set(checksums1.items()) ^ set(checksums2.items())}"

    def test_d3_timestamp_field_exclusion(self):
        """
        D3: Explicit timestamp fields are excluded from determinism checks.
        Verifies that only timestamp metadata changes between runs.
        """
        data_dir = self.workspace / "data" / "testonly"

        # First run
        result1 = self.run_scc(profile="testonly", jobs=1)
        assert result1.returncode == 0, f"Timestamp test run 1 failed: {result1.stderr}"

        # Wait and run again (without cleaning - should be no-op)
        time.sleep(1)
        result2 = self.run_scc(profile="testonly", jobs=1)
        assert result2.returncode == 0, f"Timestamp test run 2 failed: {result2.stderr}"

        # Should be no-op despite time passing
        self.assert_no_work_done(result2)

        # Look for timestamp fields in JSON files to verify they exist
        timestamp_found = False
        for json_file in data_dir.rglob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                if self._contains_timestamp_field(data):
                    timestamp_found = True
                    break
            except (json.JSONDecodeError, OSError):
                continue

        # This verifies our test setup includes timestamp fields
        # (if none found, test setup may need adjustment)
        assert (
            timestamp_found
        ), "No timestamp fields found in outputs - test setup may need timestamp fields"

    def _contains_timestamp_field(self, obj) -> bool:
        """Check if object contains timestamp-like fields."""
        if isinstance(obj, dict):
            for key in obj.keys():
                if "timestamp" in key.lower() or key in [
                    "created",
                    "modified",
                    "generated_at",
                ]:
                    return True
            for value in obj.values():
                if self._contains_timestamp_field(value):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if self._contains_timestamp_field(item):
                    return True
        return False

    # =============================================================================
    # Integration Tests
    # =============================================================================

    def test_determinism_full_matrix(self):
        """
        Integration test covering the full SCC matrix:
        - Both -j 1 and -j 5
        - Clean runs and repeat runs
        - Verifies all determinism properties together
        """
        scenarios = [{"jobs": 1, "name": "serial"}, {"jobs": 5, "name": "parallel"}]

        results = {}

        for scenario in scenarios:
            jobs = scenario["jobs"]
            name = scenario["name"]
            data_dir = self.workspace / "data" / "testonly"

            # Clean run
            shutil.rmtree(data_dir, ignore_errors=True)
            clean_result = self.run_scc(profile="testonly", jobs=jobs)
            assert (
                clean_result.returncode == 0
            ), f"{name} clean run failed: {clean_result.stderr}"

            clean_checksums = self.get_artifact_checksums(data_dir)
            clean_conversations = self.get_conversation_ids(data_dir)

            # Repeat run (should be no-op)
            repeat_result = self.run_scc(profile="testonly", jobs=jobs)
            assert (
                repeat_result.returncode == 0
            ), f"{name} repeat run failed: {repeat_result.stderr}"

            self.assert_no_work_done(repeat_result)

            repeat_checksums = self.get_artifact_checksums(data_dir)

            # Store results for cross-scenario comparison
            results[name] = {
                "checksums": clean_checksums,
                "conversations": clean_conversations,
                "repeat_identical": clean_checksums == repeat_checksums,
            }

            # Verify repeat run was identical
            assert results[name][
                "repeat_identical"
            ], f"{name} repeat run produced different artifacts"

        # Cross-scenario verification: serial and parallel should produce identical results
        assert (
            results["serial"]["checksums"] == results["parallel"]["checksums"]
        ), "Serial and parallel runs produced different artifacts"

        assert (
            results["serial"]["conversations"] == results["parallel"]["conversations"]
        ), "Serial and parallel runs produced different conversation sets"


# =============================================================================
# Test Runner and Utilities
# =============================================================================


def run_determinism_tests():
    """
    Convenience function to run all determinism tests.
    Can be called directly or via pytest.
    """
    import sys

    # Run with verbose output and exit on first failure for faster debugging
    exit_code = pytest.main(
        [__file__, "-v", "--tb=short", "-x"]
    )  # Stop on first failure

    sys.exit(exit_code)


if __name__ == "__main__":
    run_determinism_tests()
