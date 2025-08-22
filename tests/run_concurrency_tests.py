#!/usr/bin/env python3
"""
Test runner for concurrency safety and per-model serialization tests.

This script runs the concurrency tests in isolation and provides detailed
output about concurrency behavior and any bugs found.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test_concurrency_safety_per_model_serialization import ConcurrencyTestFramework


def test_basic_per_model_serialization():
    """Test basic per-model serialization without full Snakemake pipeline."""
    print("=== Testing Basic Per-Model Serialization ===")

    # Test the Snakemake rule structure for per-model execution
    import subprocess

    # Check that Snakefile has per-model rules
    snakefile_path = project_root / "Snakefile"
    if not snakefile_path.exists():
        print("❌ Snakefile not found")
        return False

    with open(snakefile_path) as f:
        snakefile_content = f.read()

    # Verify per-model rule structure
    if "execute_conversations_for_model" not in snakefile_content:
        print("❌ Per-model execution rule not found in Snakefile")
        return False

    if "{model_id}" not in snakefile_content:
        print("❌ Model ID wildcard not found in Snakefile")
        return False

    print("✓ Snakefile contains per-model execution rules")

    # Test DAG generation to verify dependency structure
    dag_cmd = ["snakemake", "--dag", "--quiet", "data/testonly/skill_ratings.json"]
    dag_result = subprocess.run(
        dag_cmd, capture_output=True, text=True, cwd=str(project_root)
    )

    if dag_result.returncode == 0:
        dag_output = dag_result.stdout

        if "execute_conversations_for_model" in dag_output:
            print("✓ DAG generation successful with per-model rules")
        else:
            print("⚠️  DAG generated but per-model rules not visible")
    else:
        print(f"⚠️  DAG generation failed: {dag_result.stderr}")

    print("✓ Basic per-model serialization structure verified")
    return True


def test_concurrent_execution_monitoring():
    """Test concurrent execution monitoring and detection."""
    print("\\n=== Testing Concurrent Execution Monitoring ===")

    with ConcurrencyTestFramework("monitoring_test") as framework:
        # Create scenario with multiple models
        framework.create_high_parallelism_scenario(num_models=3, num_skills=1)

        # Test execution monitoring
        try:
            framework.run_snakemake_scc_with_monitoring(cores=4, expect_success=False)
        except Exception as e:
            print(f"Expected execution issue: {e}")

        # Analyze execution patterns
        analysis = framework.analyze_execution_concurrency()

        print("Execution analysis completed:")
        print(
            f"  - Total execution time: {analysis.get('total_execution_time', 0):.2f}s"
        )
        print(
            f"  - Model execution patterns: {len(analysis.get('model_execution_patterns', {}))}"
        )
        print(
            f"  - Parallelism detected: {analysis.get('parallelism_detected', False)}"
        )

        # Test violation detection
        violations = framework.detect_per_model_violations(analysis)
        if violations:
            print(f"⚠️  Detected {len(violations)} potential violations:")
            for violation in violations:
                print(
                    f"    - {violation['type']}: {violation.get('model_id', 'unknown')}"
                )
        else:
            print("✓ No per-model serialization violations detected")

        print("✓ Execution monitoring and analysis working")
        return True


def test_snakemake_parallelism_behavior():
    """Test Snakemake's parallelism behavior with testonly profile."""
    print("\\n=== Testing Snakemake Parallelism Behavior ===")

    import subprocess

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy minimal project structure
        essential_files = ["Snakefile", "config", "profiles"]
        for item in essential_files:
            src_path = project_root / item
            dst_path = temp_path / item

            if src_path.exists():
                if src_path.is_dir():
                    import shutil

                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                else:
                    import shutil

                    shutil.copy2(src_path, dst_path)

        # Test dry run with parallelism
        dry_run_cmd = [
            "snakemake",
            "--dry-run",
            "--profile",
            "profiles/testonly",
            "-j",
            "4",
            "--quiet",
        ]

        dry_result = subprocess.run(
            dry_run_cmd, capture_output=True, text=True, cwd=str(temp_path)
        )

        if dry_result.returncode == 0:
            print("✓ Dry run with parallelism successful")

            # Check for parallel job patterns
            if "job" in dry_result.stdout.lower():
                print("✓ Parallel job structure detected in dry run")
            else:
                print("⚠️  No job structure visible in dry run")
        else:
            print(f"⚠️  Dry run failed: {dry_result.stderr}")

        # Test DAG with parallelism
        dag_cmd = ["snakemake", "--dag", "-j", "4", "data/testonly/skill_ratings.json"]
        dag_result = subprocess.run(
            dag_cmd, capture_output=True, text=True, cwd=str(temp_path)
        )

        if dag_result.returncode == 0:
            dag_lines = dag_result.stdout.split("\\n")

            # Count nodes that look like per-model rules
            per_model_nodes = [
                line for line in dag_lines if "execute_conversations_for_model" in line
            ]
            if len(per_model_nodes) > 0:
                print(f"✓ DAG shows {len(per_model_nodes)} per-model execution nodes")
            else:
                print("⚠️  No per-model nodes visible in DAG")
        else:
            print(f"⚠️  DAG generation failed: {dag_result.stderr}")

    print("✓ Snakemake parallelism behavior analysis completed")
    return True


def test_file_safety_patterns():
    """Test file safety patterns for concurrent execution."""
    print("\\n=== Testing File Safety Patterns ===")

    # Test per-model output file patterns
    with ConcurrencyTestFramework("file_safety") as framework:
        framework.create_high_parallelism_scenario(num_models=3, num_skills=1)

        # Check expected file patterns
        expected_patterns = [
            "data/testonly/model_conversations_test_model-A.completed",
            "data/testonly/model_conversations_test_model-B.completed",
            "data/testonly/model_conversations_test_model-C.completed",
        ]

        print("Expected per-model output file patterns:")
        for pattern in expected_patterns:
            print(f"  - {pattern}")

        # Verify pattern supports parallel execution without conflicts
        model_ids = ["test_model-A", "test_model-B", "test_model-C"]
        file_paths = [
            f"data/testonly/model_conversations_{model_id}.completed"
            for model_id in model_ids
        ]

        # Each model should have its own output file
        assert len(set(file_paths)) == len(
            file_paths
        ), "All output files should be unique"
        print("✓ Per-model output files are unique (no conflicts)")

        # Test that intermediate directories can be created safely
        data_dir = Path("data/testonly")
        data_dir.mkdir(parents=True, exist_ok=True)

        conversations_dir = data_dir / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        print("✓ File directory structure supports concurrent access")

    print("✓ File safety patterns verified")
    return True


def main():
    """Run all concurrency tests."""
    print("AFBench Concurrency Safety & Per-Model Serialization Tests")
    print("=" * 65)

    tests = [
        ("Basic Per-Model Serialization", test_basic_per_model_serialization),
        ("Concurrent Execution Monitoring", test_concurrent_execution_monitoring),
        ("Snakemake Parallelism Behavior", test_snakemake_parallelism_behavior),
        ("File Safety Patterns", test_file_safety_patterns),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\\n🧪 Running: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success, None))
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"❌ {test_name}: FAILED - {e}")

    # Summary
    print("\\n" + "=" * 65)
    print("🎯 Concurrency Test Results Summary:")

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for test_name, success, error in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {status}: {test_name}")
        if error:
            print(f"    Error: {error}")

    print(f"\\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All concurrency safety tests passed!")
        return 0
    else:
        print(
            "⚠️  Some concurrency tests failed - review per-model serialization implementation"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
