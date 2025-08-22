#!/usr/bin/env python3
"""
Determinism Test Suite Runner

Executes all determinism and reproducibility tests using the Single-Command Contract.
This runner provides detailed output and handles the testonly profile setup.

Usage:
    python tests/run_determinism_suite.py [--verbose] [--stop-on-fail]

Requirements:
    - profiles/testonly/ configured
    - model_pools/testonly.csv available
    - judge_pools/testonly.csv available
    - testonly/skills/ directory with test evals
"""

import argparse
import subprocess
import sys
from pathlib import Path


def check_testonly_setup():
    """
    Verify testonly profile and fixtures are available.

    Returns:
        bool: True if setup is complete, False otherwise
    """
    required_files = [
        "profiles/testonly/config.yaml",
        "model_pools/testonly.csv",
        "judge_pools/testonly.csv",
        "testonly/skills",
    ]

    missing = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing.append(file_path)

    if missing:
        print("❌ Missing testonly setup files:")
        for file_path in missing:
            print(f"   - {file_path}")
        print("\nRun the full test setup first:")
        print("   python tests/setup_test_fixtures.py")
        return False

    print("✅ Testonly profile setup verified")
    return True


def run_test_suite(verbose=False, stop_on_fail=False):
    """
    Run the complete determinism test suite.

    Args:
        verbose: Enable verbose pytest output
        stop_on_fail: Stop on first test failure
    """
    if not check_testonly_setup():
        return 1

    # Build pytest command
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/test_determinism_reproducibility.py",
        "--tb=short",  # Shorter tracebacks for readability
    ]

    if verbose:
        cmd.append("-v")

    if stop_on_fail:
        cmd.append("-x")

    # Add color output if terminal supports it
    cmd.extend(["--color=auto"])

    print("🧪 Running Determinism & Reproducibility Test Suite")
    print(f"📋 Command: {' '.join(cmd)}")
    print("-" * 60)

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n⚠️ Test suite interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Failed to run test suite: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Run AFBench Determinism & Reproducibility Tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tests/run_determinism_suite.py
    python tests/run_determinism_suite.py --verbose --stop-on-fail
        """,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose test output"
    )

    parser.add_argument(
        "--stop-on-fail", "-x", action="store_true", help="Stop on first test failure"
    )

    args = parser.parse_args()

    # Change to project root directory
    project_root = Path(__file__).parent.parent
    import os

    os.chdir(project_root)

    exit_code = run_test_suite(verbose=args.verbose, stop_on_fail=args.stop_on_fail)

    if exit_code == 0:
        print("\n✅ All determinism tests passed!")
    else:
        print(f"\n❌ Test suite failed with exit code {exit_code}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
