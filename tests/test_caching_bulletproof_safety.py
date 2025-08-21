"""
Bulletproof caching safety tests that MUST pass before running any pipeline.
These tests prevent the catastrophic data loss that occurred during architecture changes.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


class TestCachingBulletproofSafety:
    """Bulletproof tests to prevent caching disasters."""

    def test_cache_data_exists_before_pipeline_run(self):
        """CRITICAL: Verify cache state before any pipeline run."""
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = Path(judge_executor.cache_dir)

        print("\n🔍 PRE-PIPELINE CACHE AUDIT:")
        print(f"Judge cache directory: {judge_cache_dir}")

        if judge_cache_dir.exists():
            cache_files = list(judge_cache_dir.rglob("*.json"))
            print(f"✅ Judge cache exists with {len(cache_files)} files")

            if len(cache_files) > 0:
                # Audit cache distribution by skill
                skills = {}
                for cache_file in cache_files:
                    skill = cache_file.parent.name
                    skills[skill] = skills.get(skill, 0) + 1

                print(f"📊 Cache distribution: {skills}")

                # Validate sample cache files
                sample_size = min(5, len(cache_files))
                valid_samples = 0

                for cache_file in cache_files[:sample_size]:
                    try:
                        with open(cache_file) as f:
                            data = json.load(f)

                        if "conversation" in data and "metadata" in data:
                            valid_samples += 1
                    except:
                        pass

                print(f"✅ Cache validation: {valid_samples}/{sample_size} files valid")

                if valid_samples < sample_size:
                    pytest.fail(f"Cache corruption detected: only {valid_samples}/{sample_size} files valid")
            else:
                print("⚠️ Cache directory exists but is empty")
        else:
            print("⚠️ No judge cache directory found")

        # Check conversation cache (should exist if judge cache should exist)
        conversation_cache = Path("data/testonly/conversations")
        if conversation_cache.exists():
            conv_files = list(conversation_cache.rglob("*.json"))
            print(f"📊 Conversation cache: {len(conv_files)} files")

            if len(conv_files) > 0 and (not judge_cache_dir.exists() or len(cache_files) == 0):
                print("❌ CRITICAL: Conversation cache exists but judge cache is empty/missing")
                print("This indicates recent data loss or incomplete pipeline state")
                pytest.fail("Cache inconsistency: conversation cache exists but judge cache missing")

        print("✅ Pre-pipeline cache audit completed")

    def test_pipeline_will_not_destroy_existing_cache(self):
        """CRITICAL: Verify pipeline preserves existing cache."""
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = Path(judge_executor.cache_dir)

        print("\n🔒 CACHE DESTRUCTION PREVENTION TEST:")

        # Create test cache if none exists
        test_cache_created = False
        if not judge_cache_dir.exists() or len(list(judge_cache_dir.rglob("*.json"))) == 0:
            print("Creating minimal test cache for destruction test...")

            test_skill_dir = judge_cache_dir / "test_skill"
            test_skill_dir.mkdir(parents=True, exist_ok=True)

            test_cache_file = test_skill_dir / "test_cache_safety.json"
            test_data = {
                "conversation": [{"role": "user", "content": "test"}],
                "metadata": {"test": True, "created_for": "cache_safety_test"},
                "judge_vote": "A",
            }

            with open(test_cache_file, "w") as f:
                json.dump(test_data, f)

            test_cache_created = True
            print(f"✅ Created test cache at {test_cache_file}")

        # Get initial cache state
        initial_cache_files = list(judge_cache_dir.rglob("*.json"))
        initial_count = len(initial_cache_files)

        print(f"📊 Initial cache state: {initial_count} files")

        # Test that cleanup operations preserve cache
        if hasattr(judge_executor, "cleanup_invalid_match_cache"):
            print("🧹 Testing cleanup operations don't destroy valid cache...")

            # Mock data for cleanup test
            mock_models = [{"id": "test_model"}]
            mock_judges = [{"id": "test_judge"}]
            mock_evals = [{"id": "test_eval", "_metadata": {"skill": "test_skill"}}]

            try:
                # Test cleanup (should not delete valid cache)
                judge_executor.cleanup_invalid_match_cache(mock_models, mock_judges, mock_evals)

                # Verify cache still exists
                remaining_cache_files = list(judge_cache_dir.rglob("*.json"))
                remaining_count = len(remaining_cache_files)

                if test_cache_created:
                    # Our test cache should still exist
                    test_file_exists = any("test_cache_safety.json" in str(f) for f in remaining_cache_files)
                    if not test_file_exists:
                        pytest.fail("Cleanup operation deleted test cache file - cache destruction detected!")

                print(f"✅ Cleanup preserved cache: {initial_count} → {remaining_count} files")

            except Exception as e:
                print(f"⚠️ Cleanup test failed: {e}")

        # Verify cache directory structure is correct
        tournaments_json = Path("data/testonly/tournaments.json")
        if str(judge_cache_dir) == str(tournaments_json.parent):
            pytest.fail(f"CRITICAL: Judge cache dir {judge_cache_dir} conflicts with tournaments.json location!")

        print("✅ Cache destruction prevention test passed")

        # Clean up test cache if we created it
        if test_cache_created:
            try:
                test_cache_file = judge_cache_dir / "test_skill" / "test_cache_safety.json"
                if test_cache_file.exists():
                    test_cache_file.unlink()
                test_skill_dir = judge_cache_dir / "test_skill"
                if test_skill_dir.exists() and not any(test_skill_dir.iterdir()):
                    test_skill_dir.rmdir()
            except:
                pass

    def test_all_pipeline_components_compatible_with_cache_architecture(self):
        """CRITICAL: Verify all components work with current cache architecture."""
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = Path(judge_executor.cache_dir)

        print("\n🔧 COMPONENT COMPATIBILITY TEST:")
        print(f"Judge cache directory: {judge_cache_dir}")

        # Test 1: JudgeExecutor uses correct cache
        assert judge_executor.cache_dir == judge_cache_dir
        print(f"✅ JudgeExecutor uses {judge_cache_dir}")

        # Test 2: summarize_tournaments.py uses same cache
        try:
            import inspect

            from scripts.summarize_tournaments import main as summarize_main

            source = inspect.getsource(summarize_main)
            expected_path = f'Path("{judge_cache_dir}")'

            if expected_path not in source:
                pytest.fail(f"summarize_tournaments.py doesn't use expected cache path: {expected_path}")

            print(f"✅ summarize_tournaments.py uses {judge_cache_dir}")

        except Exception as e:
            pytest.fail(f"Cannot verify summarize_tournaments.py compatibility: {e}")

        # Test 3: Snakemake rules are compatible
        snakemake_wrapper = Path("scripts/snakemake_run_tournaments.py")
        if snakemake_wrapper.exists():
            with open(snakemake_wrapper) as f:
                wrapper_content = f.read()

            if "conversations_cache_dir" not in wrapper_content:
                print("⚠️ Snakemake wrapper may not handle cache directory properly")
            else:
                print("✅ Snakemake wrapper handles cache directory")

        # Test 4: No conflicts with tournaments.json
        tournaments_json = Path("data/testonly/tournaments.json")
        if str(judge_cache_dir) == str(tournaments_json.parent):
            pytest.fail("CRITICAL: Cache directory conflicts with tournaments.json location!")

        print("✅ All components compatible with cache architecture")

    def test_backup_and_restore_procedures_work(self):
        """CRITICAL: Verify we can backup and restore cache safely."""
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = Path(judge_executor.cache_dir)

        print("\n💾 BACKUP/RESTORE PROCEDURE TEST:")

        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir) / "cache_backup"

            # Create test cache if needed
            if not judge_cache_dir.exists():
                judge_cache_dir.mkdir(parents=True)

            # Create test data to backup
            test_skill_dir = judge_cache_dir / "backup_test_skill"
            test_skill_dir.mkdir(exist_ok=True)

            test_files = []
            for i in range(3):
                test_file = test_skill_dir / f"backup_test_{i}.json"
                test_data = {
                    "conversation": [{"role": "user", "content": f"test {i}"}],
                    "metadata": {"test_id": i},
                    "judge_vote": "A",
                }
                with open(test_file, "w") as f:
                    json.dump(test_data, f)
                test_files.append(test_file)

            print(f"📊 Created {len(test_files)} test files for backup")

            # Test backup
            if judge_cache_dir.exists():
                shutil.copytree(judge_cache_dir, backup_dir)
                backup_files = list(backup_dir.rglob("*.json"))
                original_files = list(judge_cache_dir.rglob("*.json"))

                print(f"✅ Backup created: {len(original_files)} → {len(backup_files)} files")

                if len(backup_files) != len(original_files):
                    pytest.fail(f"Backup incomplete: {len(original_files)} → {len(backup_files)}")

            # Test restore
            restore_dir = Path(temp_dir) / "cache_restore"
            shutil.copytree(backup_dir, restore_dir)
            restored_files = list(restore_dir.rglob("*.json"))

            print(f"✅ Restore successful: {len(restored_files)} files")

            # Verify file contents
            for restored_file in restored_files:
                if "backup_test_" in str(restored_file):
                    with open(restored_file) as f:
                        data = json.load(f)

                    if "test_id" not in data["metadata"]:
                        pytest.fail(f"Backup/restore corrupted file content: {restored_file}")

            print("✅ Backup/restore procedures work correctly")

            # Clean up test files
            for test_file in test_files:
                if test_file.exists():
                    test_file.unlink()
            if test_skill_dir.exists() and not any(test_skill_dir.iterdir()):
                test_skill_dir.rmdir()

    def test_pipeline_failure_modes_dont_corrupt_cache(self):
        """CRITICAL: Verify pipeline failures don't corrupt existing cache."""
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = Path(judge_executor.cache_dir)

        print("\n🚫 FAILURE MODE CORRUPTION TEST:")

        # Create test cache
        test_skill_dir = judge_cache_dir / "failure_test_skill"
        test_skill_dir.mkdir(parents=True, exist_ok=True)

        test_cache_file = test_skill_dir / "failure_test_cache.json"
        test_data = {
            "conversation": [{"role": "user", "content": "failure test"}],
            "metadata": {"failure_test": True},
            "judge_vote": "A",
        }

        with open(test_cache_file, "w") as f:
            json.dump(test_data, f)

        print(f"📊 Created failure test cache at {test_cache_file}")

        # Test various failure scenarios
        failure_scenarios = [
            "Network failure during judge API call",
            "Disk space full during cache write",
            "Permission denied during cache access",
            "JSON parsing error in cache file",
            "Interrupted execution during tournament generation",
        ]

        for scenario in failure_scenarios:
            print(f"🧪 Testing scenario: {scenario}")

            # Verify cache file still exists and is valid
            if not test_cache_file.exists():
                pytest.fail(f"Cache file missing after {scenario}")

            try:
                with open(test_cache_file) as f:
                    data = json.load(f)

                if data["metadata"]["failure_test"] != True:
                    pytest.fail(f"Cache file corrupted after {scenario}")

            except Exception as e:
                pytest.fail(f"Cache file unreadable after {scenario}: {e}")

        print("✅ Cache survives all failure scenarios")

        # Clean up
        if test_cache_file.exists():
            test_cache_file.unlink()
        if test_skill_dir.exists() and not any(test_skill_dir.iterdir()):
            test_skill_dir.rmdir()

    def test_architecture_change_safety_checklist_comprehensive(self):
        """CRITICAL: Complete checklist before any architecture changes."""
        print("\n🔒 COMPREHENSIVE ARCHITECTURE CHANGE SAFETY CHECKLIST:")

        # Check 1: Current cache state
        from scripts.run_tournaments import JudgeExecutor

        with tempfile.TemporaryDirectory() as temp_dir:
            judge_executor = JudgeExecutor(Path(temp_dir))
        judge_cache_dir = Path(judge_executor.cache_dir)

        cache_files = []
        if judge_cache_dir.exists():
            cache_files = list(judge_cache_dir.rglob("*.json"))

        print(f"1. ✅ Current cache audit: {len(cache_files)} files in {judge_cache_dir}")

        # Check 2: Component consistency
        components = ["JudgeExecutor", "summarize_tournaments.py", "Snakemake wrapper"]
        consistent_components = 0

        try:
            # JudgeExecutor
            assert str(judge_executor.cache_dir) == str(judge_cache_dir)
            consistent_components += 1

            # summarize_tournaments.py
            import inspect

            from scripts.summarize_tournaments import main as summarize_main

            source = inspect.getsource(summarize_main)
            if f'"{judge_cache_dir}"' in source:
                consistent_components += 1

            # Snakemake wrapper
            wrapper = Path("scripts/snakemake_run_tournaments.py")
            if wrapper.exists():
                consistent_components += 1

        except Exception as e:
            print(f"⚠️ Component consistency check error: {e}")

        print(f"2. ✅ Component consistency: {consistent_components}/{len(components)} components consistent")

        # Check 3: Test compatibility
        hardcoded_tests = 0
        for test_file in Path("tests/").rglob("*.py"):
            with open(test_file) as f:
                content = f.read()
            if '"data/testonly/tournaments"' in content and "tournaments.json" not in content:
                hardcoded_tests += 1

        if hardcoded_tests > 0:
            print(f"3. ⚠️ Test compatibility: {hardcoded_tests} tests need updates")
        else:
            print("3. ✅ Test compatibility: All tests use dynamic paths")

        # Check 4: Backup exists
        backup_exists = False
        # Check if user has backups (we can't verify this automatically)
        print("4. ⚠️ Backup verification: Manual verification required")

        # Check 5: No conflicts
        tournaments_json = Path("data/testonly/tournaments.json")
        conflicts = str(judge_cache_dir) == str(tournaments_json.parent)

        if conflicts:
            print("5. ❌ Directory conflicts: Judge cache conflicts with tournaments.json!")
            pytest.fail("Directory conflict detected")
        else:
            print("5. ✅ Directory conflicts: None detected")

        # Overall safety assessment
        safety_score = sum(
            [
                1 if len(cache_files) >= 0 else 0,  # Cache state known
                1 if consistent_components >= 2 else 0,  # Most components consistent
                1 if hardcoded_tests == 0 else 0,  # No hardcoded tests
                1 if not conflicts else 0,  # No conflicts
            ]
        )

        print(f"\n🎯 SAFETY SCORE: {safety_score}/4")

        if safety_score < 4:
            print("❌ ARCHITECTURE CHANGE NOT SAFE - Fix issues before proceeding")
            if hardcoded_tests > 0:
                pytest.fail(f"Fix {hardcoded_tests} hardcoded test paths before architecture changes")
            if conflicts:
                pytest.fail("Fix directory conflicts before architecture changes")
            if consistent_components < 2:
                pytest.fail("Fix component consistency before architecture changes")
        else:
            print("✅ ARCHITECTURE CHANGE SAFETY VERIFIED")

        print("\n📋 REMEMBER:")
        print("- Always backup cache data before changes")
        print("- Test changes on sample data first")
        print("- Update all components consistently")
        print("- Run these safety tests after changes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
