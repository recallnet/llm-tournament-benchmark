#!/usr/bin/env python3
"""
Summary freshness test suite for AFBench.

Tests Section 10 from TESTS.md:
- U1: Upstream change triggers summaries - summaries regenerate automatically
- U2: Manual refresh - summaries rebuild on request without upstream changes

All tests use the Single-Command Contract (SCC):
snakemake --unlock && snakemake --profile profiles/testonly -j <cores>
"""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


class SummaryFreshnessTestFramework:
    """Framework for testing summary freshness and regeneration behavior."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.temp_dir = None
        self.afbench_root = None

    def __enter__(self):
        # Create temporary test environment
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"summary_test_{self.test_name}_"))
        self.afbench_root = Path(__file__).parent.parent

        # Set up isolated test environment
        self._setup_test_workspace()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _setup_test_workspace(self):
        """Set up isolated test workspace for summary freshness testing."""
        temp_path = self.temp_dir

        # Copy AFBench source files to test workspace
        source_files = [
            "Snakefile",
            "scripts/",
            "config/",
            "profiles/testonly/",
            "model_pools/testonly.csv",
            "judge_pools/testonly.csv",
            "testonly/skills/",
        ]

        for src_file in source_files:
            src_path = self.afbench_root / src_file
            dst_path = temp_path / src_file

            if src_path.is_file():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
            elif src_path.is_dir():
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

        return temp_path

    def run_snakemake_scc(
        self, cores: int = 1, extra_flags: list[str] = None, timeout: int = 300
    ) -> dict:
        """Run Snakemake using Single-Command Contract (SCC)."""
        temp_path = self.temp_dir
        extra_flags = extra_flags or []

        # Change to test workspace directory
        original_cwd = os.getcwd()

        try:
            os.chdir(temp_path)

            # Set environment for testing
            env = os.environ.copy()
            env["AFBENCH_TESTING"] = "true"

            # Run unlock first (part of SCC)
            unlock_cmd = ["snakemake", "--unlock"]
            unlock_result = subprocess.run(
                unlock_cmd, capture_output=True, text=True, env=env
            )

            # Run main pipeline (SCC)
            main_cmd = [
                "snakemake",
                "--profile",
                "profiles/testonly",
                "-j",
                str(cores),
            ] + extra_flags

            start_time = time.time()
            main_result = subprocess.run(
                main_cmd, capture_output=True, text=True, env=env, timeout=timeout
            )
            end_time = time.time()

            return {
                "success": main_result.returncode == 0,
                "returncode": main_result.returncode,
                "stdout": main_result.stdout,
                "stderr": main_result.stderr,
                "duration": end_time - start_time,
                "unlock_success": unlock_result.returncode == 0,
                "unlock_output": unlock_result.stdout + unlock_result.stderr,
                "command": " ".join(main_cmd),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Pipeline execution timed out after {timeout}s",
                "duration": timeout,
                "unlock_success": False,
                "unlock_output": "",
                "command": " ".join(main_cmd),
            }
        finally:
            os.chdir(original_cwd)

    def collect_summary_files(self) -> dict:
        """Collect summary/output files and their metadata."""
        temp_path = self.temp_dir
        data_dir = temp_path / "data" / "testonly"

        summary_info = {
            "summary_files": [],
            "timestamps": {},
            "file_sizes": {},
            "checksums": {},
        }

        if not data_dir.exists():
            return summary_info

        # Look for summary-like files (final outputs, aggregates, reports)
        summary_patterns = [
            "*.json",  # Tournament summaries, skill ratings, etc.
            "*summary*",  # Any files with "summary" in name
            "*rating*",  # Rating files
            "*tournament*",  # Tournament files
            "*report*",  # Report files
        ]

        summary_files = set()
        for pattern in summary_patterns:
            summary_files.update(data_dir.rglob(pattern))

        # Filter to likely summary files (not intermediate cache)
        likely_summaries = []
        for file_path in summary_files:
            if file_path.is_file():
                rel_path = file_path.relative_to(data_dir)
                rel_str = str(rel_path)

                # Skip cache files and intermediate artifacts
                if (
                    "cache" not in rel_str.lower()
                    and "conversation" not in rel_str.lower()
                    and not rel_str.startswith("judge_cache/")
                    and not rel_str.endswith(".completed")
                ):
                    likely_summaries.append(file_path)

        # Collect metadata for summary files
        for file_path in likely_summaries:
            rel_path = file_path.relative_to(data_dir)
            rel_str = str(rel_path)

            summary_info["summary_files"].append(rel_str)

            # Get file metadata
            stat = file_path.stat()
            summary_info["timestamps"][rel_str] = stat.st_mtime
            summary_info["file_sizes"][rel_str] = stat.st_size

            # Simple checksum (first few bytes)
            try:
                with open(file_path, "rb") as f:
                    first_bytes = f.read(1024)  # Read first 1KB for checksum
                    summary_info["checksums"][rel_str] = hash(first_bytes)
            except OSError:
                summary_info["checksums"][rel_str] = 0

        return summary_info

    def modify_upstream_input(self, modification_type: str = "model_pool") -> bool:
        """Modify an upstream input to trigger summary regeneration."""
        temp_path = self.temp_dir

        if modification_type == "model_pool":
            # Modify model pool to trigger upstream change
            model_pool_file = temp_path / "model_pools" / "testonly.csv"
            if model_pool_file.exists():
                with open(model_pool_file) as f:
                    content = f.read()

                # Change max_tokens to trigger rebuild
                modified_content = content.replace(",1000", ",1001")
                if modified_content == content:
                    modified_content = content.replace(",1001", ",1002")

                with open(model_pool_file, "w") as f:
                    f.write(modified_content)
                return True

        elif modification_type == "judge_pool":
            # Modify judge pool
            judge_pool_file = temp_path / "judge_pools" / "testonly.csv"
            if judge_pool_file.exists():
                with open(judge_pool_file) as f:
                    content = f.read()

                # Add a comment or modify a field
                if "# Modified for testing" not in content:
                    modified_content = content + "\n# Modified for testing\n"
                else:
                    modified_content = content.replace(
                        "# Modified for testing", "# Modified again"
                    )

                with open(judge_pool_file, "w") as f:
                    f.write(modified_content)
                return True

        elif modification_type == "config":
            # Modify configuration
            config_file = temp_path / "config" / "testonly_config.yaml"
            if config_file.exists():
                with open(config_file) as f:
                    content = f.read()

                # Change n_samples to trigger rebuild
                if "n_samples: 10" in content:
                    modified_content = content.replace("n_samples: 10", "n_samples: 11")
                elif "n_samples: 11" in content:
                    modified_content = content.replace("n_samples: 11", "n_samples: 12")
                else:
                    # Add a comment
                    modified_content = content + "\n# Modified for summary testing\n"

                with open(config_file, "w") as f:
                    f.write(modified_content)
                return True

        return False

    def compare_summary_states(self, before_state: dict, after_state: dict) -> dict:
        """Compare summary states to detect changes."""
        comparison = {
            "files_changed": [],
            "files_added": [],
            "files_removed": [],
            "timestamp_changes": {},
            "size_changes": {},
            "content_changes": {},
            "any_changes": False,
        }

        # Check for added/removed files
        before_files = set(before_state["summary_files"])
        after_files = set(after_state["summary_files"])

        comparison["files_added"] = list(after_files - before_files)
        comparison["files_removed"] = list(before_files - after_files)

        # Check for changes in common files
        common_files = before_files.intersection(after_files)

        for file_path in common_files:
            changed = False

            # Check timestamp
            before_time = before_state["timestamps"].get(file_path, 0)
            after_time = after_state["timestamps"].get(file_path, 0)
            if abs(after_time - before_time) > 1:  # Allow 1 second tolerance
                comparison["timestamp_changes"][file_path] = {
                    "before": before_time,
                    "after": after_time,
                }
                changed = True

            # Check size
            before_size = before_state["file_sizes"].get(file_path, 0)
            after_size = after_state["file_sizes"].get(file_path, 0)
            if before_size != after_size:
                comparison["size_changes"][file_path] = {
                    "before": before_size,
                    "after": after_size,
                }
                changed = True

            # Check content (via checksum)
            before_checksum = before_state["checksums"].get(file_path, 0)
            after_checksum = after_state["checksums"].get(file_path, 0)
            if before_checksum != after_checksum:
                comparison["content_changes"][file_path] = {
                    "before": before_checksum,
                    "after": after_checksum,
                }
                changed = True

            if changed:
                comparison["files_changed"].append(file_path)

        # Determine if any changes occurred
        comparison["any_changes"] = bool(
            comparison["files_changed"]
            or comparison["files_added"]
            or comparison["files_removed"]
        )

        return comparison

    def test_forced_refresh(self) -> dict:
        """Test manual refresh functionality by forcing summary regeneration."""
        # Try different approaches to force refresh
        force_methods = [
            ["--forceall"],  # Force all rules to re-run
            ["--force-rerun", "all"],  # Force specific rule to re-run
        ]

        for method in force_methods:
            result = self.run_snakemake_scc(cores=1, extra_flags=method)
            if result["success"]:
                return {"method_used": method, "success": True, "result": result}

        # If standard methods fail, return the last attempt
        return {
            "method_used": force_methods[-1] if force_methods else [],
            "success": False,
            "result": result if "result" in locals() else {},
        }


def test_upstream_change_triggers_summaries():
    """
    Test U1: Upstream change triggers summaries.

    When: Any upstream artifact changes
    Then: Summaries regenerate on the next run without manual nudges
    """
    print("=== Test U1: Upstream Change Triggers Summaries ===")

    with SummaryFreshnessTestFramework("upstream_change_triggers") as framework:
        temp_path = framework.temp_dir
        print(f"Test workspace: {temp_path}")

        # Step 1: Run baseline to establish summaries
        print("\n--- Step 1: Running baseline to establish summaries ---")
        baseline_result = framework.run_snakemake_scc(cores=1)

        if not baseline_result["success"]:
            print(f"❌ Baseline run failed: {baseline_result['stderr']}")
            assert False

        print("✅ Baseline run completed successfully")

        # Collect initial summary state
        initial_summaries = framework.collect_summary_files()
        print(f"Found {len(initial_summaries['summary_files'])} summary files:")
        for summary_file in initial_summaries["summary_files"][:5]:  # Show first 5
            print(f"  - {summary_file}")

        if len(initial_summaries["summary_files"]) == 0:
            print(
                "⚠️  No summary files found - may indicate pipeline doesn't generate summaries"
            )
            # Continue test but note this

        # Step 2: Modify upstream input
        print("\n--- Step 2: Modifying upstream input (model pool) ---")
        modification_made = framework.modify_upstream_input("model_pool")

        if not modification_made:
            print("❌ Failed to modify upstream input")
            assert False

        print("✅ Modified model pool to trigger upstream change")

        # Step 3: Run pipeline again and check if summaries regenerate
        print("\n--- Step 3: Running pipeline after upstream change ---")
        after_change_result = framework.run_snakemake_scc(cores=1)

        if not after_change_result["success"]:
            print(
                f"❌ Pipeline run after change failed: {after_change_result['stderr']}"
            )
            assert False

        print("✅ Pipeline run after change completed successfully")

        # Step 4: Compare summary states
        print("\n--- Step 4: Checking if summaries regenerated ---")
        after_summaries = framework.collect_summary_files()
        comparison = framework.compare_summary_states(
            initial_summaries, after_summaries
        )

        print(f"Files changed: {len(comparison['files_changed'])}")
        print(f"Files added: {len(comparison['files_added'])}")
        print(f"Files removed: {len(comparison['files_removed'])}")
        print(f"Any changes detected: {comparison['any_changes']}")

        # Show details of changes
        if comparison["files_changed"]:
            print("Changed files:")
            for file_path in comparison["files_changed"][:3]:  # Show first 3
                print(f"  - {file_path}")
                if file_path in comparison["timestamp_changes"]:
                    ts_change = comparison["timestamp_changes"][file_path]
                    print(
                        f"    Timestamp: {ts_change['before']:.1f} → {ts_change['after']:.1f}"
                    )

        # Verify summaries were regenerated
        if not comparison["any_changes"]:
            print("❌ No summary changes detected after upstream modification")
            print("This suggests summaries are 'sticky' and not regenerating properly")
            assert False

        print("✅ Summaries regenerated automatically after upstream change")

        # Step 5: Test multiple types of upstream changes
        print("\n--- Step 5: Testing other upstream change types ---")

        # Test judge pool modification
        judge_modification_made = framework.modify_upstream_input("judge_pool")
        if judge_modification_made:
            judge_result = framework.run_snakemake_scc(cores=1)
            if judge_result["success"]:
                judge_after_summaries = framework.collect_summary_files()
                judge_comparison = framework.compare_summary_states(
                    after_summaries, judge_after_summaries
                )

                if judge_comparison["any_changes"]:
                    print("✅ Judge pool changes also trigger summary regeneration")
                else:
                    print("⚠️  Judge pool changes didn't trigger summary regeneration")
            else:
                print("⚠️  Judge pool modification test failed")

        assert True


def test_manual_refresh():
    """
    Test U2: Manual refresh.

    When: A user requests a refresh run
    Then: Summaries rebuild even if no upstream change is detected
    """
    print("\n=== Test U2: Manual Refresh ===")

    with SummaryFreshnessTestFramework("manual_refresh") as framework:
        temp_path = framework.temp_dir
        print(f"Test workspace: {temp_path}")

        # Step 1: Run baseline
        print("\n--- Step 1: Running baseline ---")
        baseline_result = framework.run_snakemake_scc(cores=1)

        if not baseline_result["success"]:
            print(f"❌ Baseline run failed: {baseline_result['stderr']}")
            assert False

        print("✅ Baseline run completed successfully")

        # Step 2: Collect initial summary state
        initial_summaries = framework.collect_summary_files()
        print(f"Found {len(initial_summaries['summary_files'])} summary files")

        if len(initial_summaries["summary_files"]) == 0:
            print("⚠️  No summary files found for manual refresh test")

        # Step 3: Wait a bit to ensure timestamp differences
        print("\n--- Step 3: Waiting to ensure timestamp separation ---")
        time.sleep(2)

        # Step 4: Test manual refresh (forced rebuild)
        print("\n--- Step 4: Testing manual refresh (forced rebuild) ---")
        refresh_test = framework.test_forced_refresh()

        if not refresh_test["success"]:
            print(
                f"❌ Manual refresh failed: {refresh_test.get('result', {}).get('stderr', 'Unknown error')}"
            )
            assert False

        print(
            f"✅ Manual refresh completed using method: {refresh_test['method_used']}"
        )

        # Step 5: Check if summaries were regenerated
        print("\n--- Step 5: Verifying summaries were refreshed ---")
        refreshed_summaries = framework.collect_summary_files()
        refresh_comparison = framework.compare_summary_states(
            initial_summaries, refreshed_summaries
        )

        print(
            f"Files changed during refresh: {len(refresh_comparison['files_changed'])}"
        )
        print(f"Any changes detected: {refresh_comparison['any_changes']}")

        # Show refresh details
        if refresh_comparison["files_changed"]:
            print("Refreshed files:")
            for file_path in refresh_comparison["files_changed"][:3]:  # Show first 3
                print(f"  - {file_path}")
                if file_path in refresh_comparison["timestamp_changes"]:
                    ts_change = refresh_comparison["timestamp_changes"][file_path]
                    print(
                        f"    Timestamp: {ts_change['before']:.1f} → {ts_change['after']:.1f}"
                    )

        # Verify manual refresh worked
        if not refresh_comparison["any_changes"]:
            print("❌ Manual refresh did not regenerate summaries")
            print("This suggests the refresh mechanism is not working properly")
            assert False

        print("✅ Manual refresh successfully regenerated summaries")

        # Step 6: Verify no-op run behavior
        print("\n--- Step 6: Testing no-op run (should not change summaries) ---")
        noop_result = framework.run_snakemake_scc(cores=1)

        if not noop_result["success"]:
            print(f"⚠️  No-op run failed: {noop_result['stderr']}")
            # Don't fail the test as this is secondary
        else:
            noop_summaries = framework.collect_summary_files()
            noop_comparison = framework.compare_summary_states(
                refreshed_summaries, noop_summaries
            )

            if noop_comparison["any_changes"]:
                print("⚠️  No-op run unexpectedly changed summaries")
            else:
                print("✅ No-op run correctly preserved summaries")

        assert True


def main():
    """Run all summary freshness tests."""
    print("AFBench Summary Freshness Tests")
    print("=" * 45)

    tests = [
        ("Upstream Change Triggers Summaries", test_upstream_change_triggers_summaries),
        ("Manual Refresh", test_manual_refresh),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'='*45}")
    print(f"Summary Freshness Tests: {passed}/{total} passed")

    if passed == total:
        print("🎉 All summary freshness tests passed!")
        return 0
    else:
        print("⚠️  Some summary freshness tests failed")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
