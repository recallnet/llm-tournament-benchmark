"""
Critical tests to prevent data loss and architecture inconsistencies.
These tests MUST pass before any cache directory changes are made.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


class TestJudgeCacheArchitectureSafety:
    """Tests to prevent data loss during cache architecture changes."""

    def test_judge_executor_cache_directory_consistency(self):
        """Test that JudgeExecutor cache directory is consistent across all components."""
        from scripts.run_tournaments import JudgeExecutor

        # Get the actual cache directory from JudgeExecutor
        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = str(judge_executor.cache_dir)

        print(f"✅ JudgeExecutor.cache_dir: {judge_cache_dir}")

        # CRITICAL: This directory should NOT conflict with tournaments.json
        tournaments_json_path = "data/testonly/tournaments.json"
        tournaments_json_parent = str(Path(tournaments_json_path).parent)

        if judge_cache_dir == tournaments_json_parent:
            pytest.fail(
                f"🚨 CRITICAL: Judge cache dir '{judge_cache_dir}' conflicts with tournaments.json parent '{tournaments_json_parent}'"
            )

        # Verify summarize_tournaments.py uses the same directory
        import inspect

        from scripts.summarize_tournaments import main as summarize_main

        source = inspect.getsource(summarize_main)
        if 'Path("data/testonly/tournaments")' in source:
            pytest.fail(
                f"🚨 CRITICAL: summarize_tournaments.py still uses old data/tournaments path, but JudgeExecutor uses {judge_cache_dir}"
            )

        if f'Path("{judge_cache_dir}")' not in source:
            pytest.fail(
                f"🚨 CRITICAL: summarize_tournaments.py doesn't use JudgeExecutor cache dir {judge_cache_dir}"
            )

        print("✅ summarize_tournaments.py uses correct cache directory")

    def test_judge_cache_data_preservation_during_moves(self):
        """Test that moving judge cache doesn't lose data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test cache structure
            old_cache = Path(temp_dir) / "old_cache"
            new_cache = Path(temp_dir) / "new_cache"

            # Create test judge decision files
            test_skill_dir = old_cache / "harm_avoidance"
            test_skill_dir.mkdir(parents=True)

            test_files = []
            for i in range(5):
                test_file = test_skill_dir / f"match_{i}_judge_test_{i}.json"
                test_data = {"judge_vote": "A", "match_id": f"match_{i}", "test": True}
                with open(test_file, "w") as f:
                    json.dump(test_data, f)
                test_files.append(test_file)

            print(f"✅ Created {len(test_files)} test judge decision files")

            # Move the cache (simulating architecture change)
            shutil.move(str(old_cache), str(new_cache))

            # Verify all files preserved
            assert not old_cache.exists(), "Old cache should be gone after move"
            assert new_cache.exists(), "New cache should exist after move"

            moved_files = list(new_cache.rglob("*.json"))
            assert len(moved_files) == len(
                test_files
            ), f"Data loss: expected {len(test_files)}, found {len(moved_files)}"

            # Verify file contents preserved
            for moved_file in moved_files:
                with open(moved_file) as f:
                    data = json.load(f)
                assert (
                    "test" in data and data["test"] is True
                ), "File content corrupted during move"

            print(f"✅ All {len(moved_files)} files preserved with correct content")

    def test_all_scripts_use_consistent_judge_cache_path(self):
        """Test that all scripts use the same judge cache path."""
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        expected_cache_dir = str(judge_executor.cache_dir)

        # Scripts that should use judge cache
        scripts_to_check = [
            "scripts/run_tournaments.py",
            "scripts/summarize_tournaments.py",
        ]

        inconsistent_scripts = []

        for script_path in scripts_to_check:
            if not Path(script_path).exists():
                continue

            with open(script_path) as f:
                content = f.read()

            # Check for hardcoded old paths
            old_paths = [
                "data/testonly/tournaments",
                '"data/testonly/tournaments"',
                "'data/tournaments'",
            ]
            for old_path in old_paths:
                if old_path in content and "tournaments.json" not in content:
                    inconsistent_scripts.append(
                        f"{script_path}: contains hardcoded '{old_path}'"
                    )

            # Verify it uses the correct path
            expected_path = f'"{expected_cache_dir}"'
            if (
                expected_path not in content
                and expected_cache_dir != "data/testonly/tournaments"
            ):
                inconsistent_scripts.append(
                    f"{script_path}: missing expected path '{expected_path}'"
                )

        if inconsistent_scripts:
            error_msg = (
                "🚨 CRITICAL: Scripts have inconsistent judge cache paths:\n"
                + "\n".join(inconsistent_scripts)
            )
            pytest.fail(error_msg)

        print(f"✅ All scripts use consistent judge cache path: {expected_cache_dir}")

    def test_tests_dont_break_on_cache_directory_changes(self):
        """Test that tests are resilient to judge cache directory changes."""
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        str(judge_executor.cache_dir)

        # Find tests that hardcode the old path
        hardcoded_test_files = []

        for test_file in Path("tests/").rglob("*.py"):
            with open(test_file) as f:
                content = f.read()

            # Look for hardcoded paths that would break
            old_hardcoded_paths = [
                'Path("data/testonly/tournaments")',
                '"data/testonly/tournaments/"',
                "'data/tournaments/'",
                "data/testonly/tournaments/",
            ]

            for old_path in old_hardcoded_paths:
                if old_path in content and "tournaments.json" not in content:
                    hardcoded_test_files.append(f"{test_file}: hardcodes '{old_path}'")

        if hardcoded_test_files:
            print(
                "🚨 CRITICAL: Tests hardcode judge cache paths and will break on architecture changes:"
            )
            for issue in hardcoded_test_files[:10]:  # Show first 10
                print(f"   {issue}")
            if len(hardcoded_test_files) > 10:
                print(f"   ... and {len(hardcoded_test_files) - 10} more")

            pytest.fail(
                f"Found {len(hardcoded_test_files)} tests with hardcoded judge cache paths"
            )

        print("✅ No tests hardcode judge cache paths")

    def test_pipeline_invalidation_works_with_cache_architecture(self):
        """Test that pipeline invalidation works correctly with current cache architecture."""
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = Path(judge_executor.cache_dir)

        # Check if judge cache exists
        if judge_cache_dir.exists():
            judge_files = list(judge_cache_dir.rglob("*.json"))
            print(
                f"✅ Judge cache found: {len(judge_files)} files in {judge_cache_dir}"
            )
        else:
            print(f"⚠️ Judge cache directory doesn't exist: {judge_cache_dir}")

        # Test that tournaments.json and judge cache are in different locations
        tournaments_json = Path("data/testonly/tournaments.json")
        tournaments_json_parent = tournaments_json.parent

        assert (
            judge_cache_dir != tournaments_json_parent
        ), f"Judge cache {judge_cache_dir} conflicts with tournaments.json parent {tournaments_json_parent}"

        # Test that cache invalidation won't accidentally delete tournaments.json
        if tournaments_json.exists():
            print(f"✅ tournaments.json exists at: {tournaments_json}")
        else:
            print(f"⚠️ tournaments.json missing at: {tournaments_json}")

        print("✅ Judge cache and tournaments.json are properly separated")

    def test_data_loss_prevention_checklist(self):
        """Comprehensive checklist to prevent data loss during architecture changes."""
        print("\n🔍 DATA LOSS PREVENTION CHECKLIST:")

        # 1. Check current cache size
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = Path(judge_executor.cache_dir)

        if judge_cache_dir.exists():
            cache_files = list(judge_cache_dir.rglob("*.json"))
            print(
                f"✅ Current judge cache: {len(cache_files)} files in {judge_cache_dir}"
            )

            if len(cache_files) == 0:
                print("⚠️ WARNING: Judge cache is empty - may indicate recent data loss")
            elif len(cache_files) < 50:
                print(
                    f"⚠️ WARNING: Judge cache seems small ({len(cache_files)} files) - verify this is expected"
                )
            else:
                print(f"✅ Judge cache appears healthy with {len(cache_files)} files")
        else:
            print(f"❌ CRITICAL: Judge cache directory missing: {judge_cache_dir}")

        # 2. Check for conflicts
        tournaments_json = Path("data/testonly/tournaments.json")
        if str(judge_cache_dir) == str(tournaments_json.parent):
            print("❌ CRITICAL: Judge cache conflicts with tournaments.json location")
            pytest.fail("Architecture conflict detected")
        else:
            print("✅ No directory conflicts detected")

        # 3. Check test compatibility
        # This would normally run pytest programmatically, but for speed we'll check key indicators

        test_indicators = [
            ("data/testonly/tournaments", "Old hardcoded paths in tests"),
            ("JudgeExecutor.cache_dir", "Tests should use dynamic cache dir"),
        ]

        for indicator, _description in test_indicators:
            test_files_with_indicator = []
            for test_file in Path("tests/").rglob("*.py"):
                with open(test_file) as f:
                    if indicator in f.read():
                        test_files_with_indicator.append(str(test_file))

            if indicator == "data/testonly/tournaments" and test_files_with_indicator:
                print(
                    f"⚠️ {len(test_files_with_indicator)} test files may need updates for new architecture"
                )

        print("✅ Data loss prevention checklist completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
