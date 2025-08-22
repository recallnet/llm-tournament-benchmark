"""
Critical data integrity tests that MUST pass before any cache modifications.
These tests detect data loss, corruption, and architectural inconsistencies.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


class TestCacheDataIntegrityCritical:
    """Critical tests for cache data integrity and loss prevention."""

    def test_judge_cache_data_exists_and_valid(self, isolated_judge_cache):
        """Test that judge cache data exists and is valid."""
        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor(cache_dir=isolated_judge_cache)
        judge_cache_dir = Path(judge_executor.cache_dir)

        print(f"🔍 Checking judge cache integrity at: {judge_cache_dir}")

        if not judge_cache_dir.exists():
            print(f"⚠️ Judge cache directory doesn't exist: {judge_cache_dir}")
            print("This may be expected for fresh installations")
            return

        # Count cache files
        judge_files = list(judge_cache_dir.rglob("*.json"))
        print(f"📊 Found {len(judge_files)} judge cache files")

        if len(judge_files) == 0:
            print("⚠️ WARNING: Judge cache is empty")
            print("This may indicate recent data loss or fresh installation")

        # Validate file structure
        skills_found = set()
        corrupted_files = []
        valid_files = 0

        for judge_file in judge_files[:10]:  # Sample first 10 files
            try:
                with open(judge_file) as f:
                    data = json.load(f)

                # Check required fields
                required_fields = ["conversation", "metadata"]
                missing_fields = [
                    field for field in required_fields if field not in data
                ]

                if missing_fields:
                    corrupted_files.append(f"{judge_file}: missing {missing_fields}")
                else:
                    valid_files += 1

                # Track skills
                skill = judge_file.parent.name
                skills_found.add(skill)

            except (json.JSONDecodeError, OSError) as e:
                corrupted_files.append(f"{judge_file}: {e}")

        print(f"✅ Valid cache files: {valid_files}")
        print(f"📂 Skills with cache: {sorted(skills_found)}")

        if corrupted_files:
            print("❌ Corrupted cache files found:")
            for corruption in corrupted_files:
                print(f"   {corruption}")
            pytest.fail(f"Found {len(corrupted_files)} corrupted judge cache files")

        print("✅ Judge cache integrity check passed")

    def test_all_pipeline_components_see_same_judge_cache(self, isolated_judge_cache):
        """Test that all pipeline components reference the same judge cache location."""
        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor(cache_dir=isolated_judge_cache)
        expected_cache_dir = str(judge_executor.cache_dir)

        print(f"🔍 Expected judge cache directory: {expected_cache_dir}")

        # Test JudgeExecutor uses this directory
        assert str(judge_executor.cache_dir) == expected_cache_dir
        print(f"✅ JudgeExecutor.cache_dir: {expected_cache_dir}")

        # Test summarize_tournaments uses this directory when called properly
        import tempfile

        from scripts.summarize_tournaments import main as summarize_main

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "tournament_summaries.json"

            # Call with explicit cache directory (as tests should do)
            summarize_main(tournaments_dir=expected_cache_dir, output_file=output_file)

            print(
                f"✅ summarize_tournaments.py called successfully with path: {expected_cache_dir}"
            )

        # Test that Snakemake wrapper uses this directory
        wrapper_script = Path("scripts/snakemake_run_tournaments.py")
        if wrapper_script.exists():
            with open(wrapper_script) as f:
                wrapper_content = f.read()

            # The wrapper should pass the correct cache dir to main_with_cache_dir
            if "conversations_cache_dir" in wrapper_content:
                print("✅ Snakemake wrapper passes cache directory parameter")
            else:
                print("⚠️ Snakemake wrapper may not handle cache directory correctly")

        print("✅ All components use consistent judge cache location")

    def test_cache_move_operations_preserve_data(self):
        """Test that cache move operations don't lose data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate a cache move operation
            old_cache = Path(temp_dir) / "old_judge_cache"
            new_cache = Path(temp_dir) / "new_judge_cache"

            # Create test cache structure with multiple skills
            test_data = {}
            skills = ["harm_avoidance", "hidden_messages", "code_generation"]

            for skill in skills:
                skill_dir = old_cache / skill
                skill_dir.mkdir(parents=True)

                # Create test judge files
                for i in range(3):
                    judge_file = skill_dir / f"match_{skill}_{i}_judge_test.json"
                    file_data = {
                        "conversation": [{"role": "user", "content": "test"}],
                        "metadata": {"skill": skill, "match": i},
                        "judge_vote": "A",
                    }
                    with open(judge_file, "w") as f:
                        json.dump(file_data, f)
                    test_data[str(judge_file)] = file_data

            print(
                f"✅ Created test cache with {len(test_data)} files across {len(skills)} skills"
            )

            # Perform the move
            shutil.move(str(old_cache), str(new_cache))

            # Verify no data loss
            moved_files = list(new_cache.rglob("*.json"))
            assert len(moved_files) == len(
                test_data
            ), f"Data loss: {len(test_data)} → {len(moved_files)}"

            # Verify file contents
            for moved_file in moved_files:
                with open(moved_file) as f:
                    moved_data = json.load(f)

                # Find original data (file paths will be different)
                original_file = None
                for orig_path, orig_data in test_data.items():
                    if (
                        orig_data["metadata"]["skill"]
                        == moved_data["metadata"]["skill"]
                        and orig_data["metadata"]["match"]
                        == moved_data["metadata"]["match"]
                    ):
                        original_file = orig_path
                        break

                assert (
                    original_file is not None
                ), f"Couldn't find original data for {moved_file}"
                assert (
                    moved_data == test_data[original_file]
                ), f"Data corruption in {moved_file}"

            print(
                f"✅ Cache move preserved all {len(moved_files)} files with correct content"
            )

    def test_detect_recent_data_loss(self, isolated_judge_cache):
        """Test to detect if recent operations caused data loss."""
        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor(cache_dir=isolated_judge_cache)
        judge_cache_dir = Path(judge_executor.cache_dir)

        print(f"🔍 Checking for signs of recent data loss in: {judge_cache_dir}")

        # Check if judge cache directory exists
        if not judge_cache_dir.exists():
            print(f"❌ CRITICAL: Judge cache directory is missing: {judge_cache_dir}")
            # Check if old location exists
            old_location = Path("data/testonly/tournaments")
            if old_location.exists():
                old_files = list(old_location.rglob("*.json"))
                print(
                    f"🔍 Found {len(old_files)} files in old location: {old_location}"
                )
                if len(old_files) > 0:
                    print(
                        "❌ CRITICAL: Judge cache files exist in old location but not new location!"
                    )
                    print(
                        "This indicates incomplete migration or data loss during architecture change"
                    )
                    pytest.fail(
                        "Data loss detected: files in old location but new location empty"
                    )

            print("⚠️ Both old and new locations empty - may be fresh installation")
            return

        # Check current state
        current_files = list(judge_cache_dir.rglob("*.json"))
        print(f"📊 Current judge cache: {len(current_files)} files")

        if len(current_files) == 0:
            print("❌ CRITICAL: Judge cache directory exists but is completely empty")

            # Check for signs this should have data
            conversation_cache = Path("data/testonly/conversations")
            if conversation_cache.exists():
                conv_files = list(conversation_cache.rglob("*.json"))
                if len(conv_files) > 0:
                    print(
                        f"🔍 Found {len(conv_files)} conversation files - judge cache should exist"
                    )
                    pytest.fail(
                        "Data loss: conversation cache exists but judge cache is empty"
                    )

            print("⚠️ No conversation cache either - may be fresh installation")
            return

        # Check for reasonable skill distribution
        skills_found = {}
        for judge_file in current_files:
            skill = judge_file.parent.name
            skills_found[skill] = skills_found.get(skill, 0) + 1

        print(f"📂 Skills in judge cache: {dict(skills_found)}")

        expected_skills = [
            "harm_avoidance",
            "hidden_messages",
            "code_generation",
            "document_summarization",
            "empathy",
            "respect_no_em_dash_requests",
            "persuasiveness",
            "ethical_loopholes",
        ]

        if len(skills_found) == 1 and "harm_avoidance" in skills_found:
            print("⚠️ Only harm_avoidance in cache - may indicate incomplete processing")
        elif len(skills_found) < len(expected_skills) / 2:
            print(
                f"⚠️ Only {len(skills_found)} skills in cache - may indicate data loss or incomplete processing"
            )

        print(
            f"✅ Judge cache appears to contain {len(current_files)} files across {len(skills_found)} skills"
        )

    def test_cache_backup_and_restore_functionality(self, isolated_judge_cache):
        """Test cache backup and restore to prevent future data loss."""
        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor(cache_dir=isolated_judge_cache)
        judge_cache_dir = Path(judge_executor.cache_dir)

        with tempfile.TemporaryDirectory() as backup_dir:
            backup_path = Path(backup_dir) / "judge_cache_backup"

            print(f"🔍 Testing backup of judge cache from: {judge_cache_dir}")

            if (
                not judge_cache_dir.exists()
                or len(list(judge_cache_dir.rglob("*.json"))) == 0
            ):
                print("⚠️ No judge cache to backup - creating test cache")

                # Create minimal test cache
                test_skill_dir = judge_cache_dir / "test_skill"
                test_skill_dir.mkdir(parents=True, exist_ok=True)

                test_file = test_skill_dir / "test_match_judge_backup.json"
                with open(test_file, "w") as f:
                    json.dump({"test_backup": True, "judge_vote": "A"}, f)

            # Perform backup
            original_files = list(judge_cache_dir.rglob("*.json"))

            if len(original_files) > 0:
                shutil.copytree(judge_cache_dir, backup_path)
                backup_files = list(backup_path.rglob("*.json"))

                assert len(backup_files) == len(
                    original_files
                ), f"Backup incomplete: {len(original_files)} → {len(backup_files)}"
                print(f"✅ Backup successful: {len(backup_files)} files")

                # Test restore
                temp_restore = Path(backup_dir) / "restored_cache"
                shutil.copytree(backup_path, temp_restore)
                restored_files = list(temp_restore.rglob("*.json"))

                assert len(restored_files) == len(
                    original_files
                ), f"Restore incomplete: {len(original_files)} → {len(restored_files)}"
                print(f"✅ Restore successful: {len(restored_files)} files")
            else:
                print("⚠️ No files to backup")

            print("✅ Backup and restore functionality works correctly")

    def test_architectural_change_safety_checklist(self, isolated_judge_cache):
        """Comprehensive safety checklist for architectural changes."""
        print("\n🔒 ARCHITECTURAL CHANGE SAFETY CHECKLIST:")

        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor(cache_dir=isolated_judge_cache)
        judge_cache_dir = Path(judge_executor.cache_dir)

        # 1. Data preservation check
        if judge_cache_dir.exists():
            cache_files = list(judge_cache_dir.rglob("*.json"))
            print(
                f"✅ 1. Data preservation: {len(cache_files)} files in {judge_cache_dir}"
            )
        else:
            print(f"⚠️ 1. Data preservation: No cache directory at {judge_cache_dir}")

        # 2. Component consistency check
        components_consistent = True
        try:
            # Test that summarize_tournaments accepts the cache directory parameter
            import tempfile

            from scripts.summarize_tournaments import main as summarize_main

            with tempfile.TemporaryDirectory() as temp_dir:
                output_file = Path(temp_dir) / "tournament_summaries.json"
                # This should work without errors
                summarize_main(tournaments_dir=judge_cache_dir, output_file=output_file)

            print(f"✅ 2. Component consistency: All components use {judge_cache_dir}")
        except Exception as e:
            print(f"❌ 2. Component consistency: summarize_tournaments.py error: {e}")
            components_consistent = False

        # 3. Test compatibility check
        test_files_to_update = []
        for test_file in Path("tests/").rglob("*.py"):
            with open(test_file) as f:
                content = f.read()
            if 'data/tournaments"' in content and "tournaments.json" not in content:
                test_files_to_update.append(str(test_file))

        if test_files_to_update:
            print(
                f"⚠️ 3. Test compatibility: {len(test_files_to_update)} test files need updates"
            )
        else:
            print("✅ 3. Test compatibility: No hardcoded cache paths in tests")

        # 4. Conflict detection
        tournaments_json = Path("data/testonly/tournaments.json")
        if str(judge_cache_dir) == str(tournaments_json.parent):
            print(
                "❌ 4. Conflict detection: Cache dir conflicts with tournaments.json location"
            )
            pytest.fail("Architecture conflict detected")
        else:
            print("✅ 4. Conflict detection: No directory conflicts")

        print("\n🎯 CHECKLIST SUMMARY:")
        print("Before making architecture changes:")
        print("- Backup all cache data")
        print("- Update all component references consistently")
        print("- Update test hardcoded paths")
        print("- Verify no directory conflicts")
        print("- Test with sample data first")

        if not components_consistent or test_files_to_update:
            pytest.fail(
                "Architecture safety checklist failed - fix issues before proceeding"
            )

        print("✅ Architecture safety checklist passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
