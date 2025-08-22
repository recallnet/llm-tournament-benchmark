#!/usr/bin/env python3
"""
Test that Snakefile DAG construction doesn't hang or fail.
Critical regression test for lambda function issues.
"""

import os
import subprocess
import time
from pathlib import Path


def test_dag_construction_does_not_hang():
    """Test that snakemake --dry-run completes within reasonable time."""
    start_time = time.time()

    try:
        # Set environment for testing
        env = os.environ.copy()
        env["AFBENCH_TESTING"] = "true"

        # This should complete quickly (< 30 seconds, increased from 10)
        result = subprocess.run(
            ["snakemake", "--profile", "profiles/testonly", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,  # Increased timeout for more reliable testing
            cwd=Path(__file__).parent.parent,
            env=env,
        )

        elapsed = time.time() - start_time

        # Should complete successfully
        assert result.returncode == 0, f"DAG construction failed: {result.stderr}"

        # Should complete within reasonable time
        assert elapsed < 30, f"DAG construction took too long: {elapsed}s"

        # Check that specific rules we care about don't have "Shell command: None"
        # Rules using "run:" blocks legitimately show "Shell command: None" - that's fine
        lines = result.stdout.split("\n")

        problem_rules = []
        for i, line in enumerate(lines):
            if (
                "rule run_tournaments:" in line
                or "rule summarize_tournaments:" in line
                or "rule calculate_skill_ratings:" in line
            ):
                # Look ahead for Shell command line
                for j in range(i + 1, min(i + 10, len(lines))):
                    if "Shell command:" in lines[j]:
                        if "Shell command: None" in lines[j]:
                            rule_name = line.split("rule ")[1].split(":")[0]
                            problem_rules.append(rule_name)
                        break

        assert not problem_rules, f"These rules have no shell command: {problem_rules}"

        print(f"✅ DAG construction completed in {elapsed:.2f}s")

    except subprocess.TimeoutExpired:
        raise AssertionError(
            "DAG construction hung - likely lambda function issue in Snakefile"
        )


def test_no_lambda_functions_with_file_dependencies():
    """Test that no lambda functions call file-dependent functions."""
    snakefile_path = Path(__file__).parent.parent / "Snakefile"

    with open(snakefile_path) as f:
        content = f.read()

    # Check for problematic lambda patterns
    problematic_patterns = [
        "lambda.*get_model_ids",
        "lambda.*get_judge_ids",
        "lambda.*load_",
        "lambda.*read_",
    ]

    for pattern in problematic_patterns:
        import re

        if re.search(pattern, content):
            raise AssertionError(
                f"Snakefile contains problematic lambda pattern: {pattern}"
            )

    print("✅ No problematic lambda functions found")


if __name__ == "__main__":
    test_dag_construction_does_not_hang()
    test_no_lambda_functions_with_file_dependencies()
    print("🎉 All DAG construction tests passed")
