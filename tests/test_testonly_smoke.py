"""
Smoke Test for testonly Profile

Quick verification that the testonly profile and fixtures work with the pipeline.
This is a minimal test to validate the test setup before running the full determinism suite.
"""

import subprocess
from pathlib import Path

import pytest


def test_testonly_profile_runs():
    """
    Smoke test: Verify testonly profile can execute SCC successfully.

    This is a basic integration test to ensure:
    1. testonly profile configuration is valid
    2. testonly fixtures (models, judges, skills) work
    3. Pipeline can complete end-to-end with test data
    """
    # Use SCC (Single-Command Contract)
    unlock_cmd = ["snakemake", "--unlock"]
    run_cmd = ["snakemake", "--profile=profiles/testonly", "-j1"]

    # Execute unlock first
    unlock_result = subprocess.run(
        unlock_cmd, capture_output=True, text=True, timeout=60
    )

    if unlock_result.returncode != 0:
        pytest.fail(f"Snakemake unlock failed: {unlock_result.stderr}")

    # Execute main pipeline
    run_result = subprocess.run(
        run_cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minutes should be enough for minimal test data
    )

    # Check if run was successful
    if run_result.returncode != 0:
        pytest.fail(
            f"Testonly profile run failed:\\n"
            f"STDOUT: {run_result.stdout}\\n"
            f"STDERR: {run_result.stderr}"
        )

    # Verify basic outputs were created
    data_dir = Path("data/testonly")
    expected_outputs = [
        "loaded_models.json",
        "loaded_judges.json",
        "loaded_skills.json",
    ]

    missing_outputs = []
    for output in expected_outputs:
        if not (data_dir / output).exists():
            missing_outputs.append(output)

    if missing_outputs:
        pytest.fail(f"Missing expected outputs: {missing_outputs}")

    print("✅ Testonly profile smoke test passed")


def test_testonly_profile_no_op_repeat():
    """
    Smoke test: Verify repeated runs are no-ops.

    This tests basic caching behavior with testonly profile.
    """
    # First run already completed in previous test
    run_cmd = ["snakemake", "--profile=profiles/testonly", "-j1"]

    repeat_result = subprocess.run(run_cmd, capture_output=True, text=True, timeout=120)

    if repeat_result.returncode != 0:
        pytest.fail(f"Testonly repeat run failed: {repeat_result.stderr}")

    # Should be a no-op run
    output = repeat_result.stdout + repeat_result.stderr
    no_work_indicators = [
        "Nothing to be done",
        "all requested files are present and up to date",
    ]

    if not any(indicator in output for indicator in no_work_indicators):
        pytest.fail(f"Expected no-work repeat run, got: {output}")

    print("✅ Testonly profile no-op repeat test passed")


if __name__ == "__main__":
    # Run smoke tests directly
    pytest.main([__file__, "-v"])
