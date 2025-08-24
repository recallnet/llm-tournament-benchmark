#!/usr/bin/env python3
"""
Tests for parallel cache safety mechanisms.

These tests verify that the cache cleanup system prevents race conditions
when multiple tournament processes run simultaneously.
"""

import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.parallel_cache_safety import (
    CacheLockError,
    exclusive_cache_lock,
    get_cache_cleanup_marker_file,
    mark_cache_cleanup_complete,
    safe_remove_directory_tree,
    safe_remove_file,
    should_skip_cache_cleanup,
)


class TestParallelCacheSafety:
    """Tests for parallel cache safety utilities."""

    def test_exclusive_cache_lock_single_process(self):
        """Test that exclusive cache lock works for single process."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "cache"
            
            # Should be able to acquire lock
            with exclusive_cache_lock(cache_dir, "test_operation"):
                assert cache_dir.exists()
                lock_file = cache_dir / ".cache_lock"
                assert lock_file.exists()
                
                # Lock file should contain process info
                with open(lock_file) as f:
                    lock_info = json.load(f)
                assert lock_info["operation"] == "test_operation"
                assert lock_info["pid"] == os.getpid()
            
            # Lock file should be cleaned up after context exit
            assert not lock_file.exists()

    def test_exclusive_cache_lock_prevents_concurrent_access(self):
        """Test that exclusive lock prevents concurrent access."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "cache"
            
            # Test concurrent access by simulating the exact scenario that caused production issues:
            # Multiple processes calling cache cleanup simultaneously
            
            # First, test that lock acquisition works sequentially
            results = []
            
            def try_acquire_lock_sequential(process_id: int):
                """Try to acquire lock sequentially."""
                try:
                    with exclusive_cache_lock(cache_dir, f"process_{process_id}", timeout=1):
                        results.append(f"process_{process_id}_success")
                        return True
                except CacheLockError:
                    results.append(f"process_{process_id}_blocked")
                    return False
            
            # Test sequential access first (both should succeed)
            assert try_acquire_lock_sequential(1) is True
            assert try_acquire_lock_sequential(2) is True
            
            # Now test the critical scenario: what happens when two threads try to acquire
            # the lock at nearly the same time (simulating the race condition)
            results = []
            lock_times = []
            
            def try_acquire_lock_concurrent(process_id: int):
                """Try to acquire lock and record timing."""
                start_time = time.time()
                try:
                    with exclusive_cache_lock(cache_dir, f"process_{process_id}", timeout=3):
                        # Record when we got the lock
                        lock_acquired_time = time.time()
                        lock_times.append((process_id, lock_acquired_time))
                        
                        # Hold lock briefly to ensure other thread has to wait
                        time.sleep(0.2)
                        results.append(f"process_{process_id}_success")
                        return True
                except CacheLockError:
                    results.append(f"process_{process_id}_blocked")
                    return False
            
            # Run two threads concurrently with very short delay
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Start both threads nearly simultaneously
                future1 = executor.submit(try_acquire_lock_concurrent, 1)
                future2 = executor.submit(try_acquire_lock_concurrent, 2)
                
                # Wait for completion
                result1 = future1.result()
                result2 = future2.result()
            
            # Both threads should succeed, but they should have acquired locks at different times
            success_count = len([r for r in results if "success" in r])
            assert success_count == 2, f"Expected 2 sequential successes: {results}"
            
            # Verify that locks were acquired sequentially (not simultaneously)
            if len(lock_times) >= 2:
                lock_times.sort(key=lambda x: x[1])  # Sort by acquisition time
                time_diff = lock_times[1][1] - lock_times[0][1]
                # The second lock should be acquired at least 0.15s after the first
                # (accounting for the 0.2s hold time minus some timing variance)
                assert time_diff >= 0.1, f"Locks acquired too close together: {time_diff:.3f}s"

    def test_safe_remove_directory_tree_handles_race_conditions(self):
        """Test that safe_remove_directory_tree handles concurrent deletion."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_dir = Path(tmp_dir) / "test_remove"
            test_dir.mkdir()
            (test_dir / "file1.txt").write_text("test")
            (test_dir / "file2.txt").write_text("test")
            
            # Should successfully remove existing directory
            result = safe_remove_directory_tree(test_dir, "test removal")
            assert result is True
            assert not test_dir.exists()
            
            # Should handle attempting to remove already-deleted directory
            result = safe_remove_directory_tree(test_dir, "already deleted")
            assert result is False

    def test_safe_remove_file_handles_race_conditions(self):
        """Test that safe_remove_file handles concurrent deletion."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("test content")
            
            # Should successfully remove existing file
            result = safe_remove_file(test_file, "test removal")
            assert result is True
            assert not test_file.exists()
            
            # Should handle attempting to remove already-deleted file
            result = safe_remove_file(test_file, "already deleted")
            assert result is False

    def test_should_skip_cache_cleanup_with_same_config(self):
        """Test that cache cleanup is skipped when configuration hasn't changed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            
            # Mock data
            models = [{"id": "model_a"}, {"id": "model_b"}]
            judges = [{"id": "judge_1"}]
            evals = [
                {"id": "eval_1", "_metadata": {"skill": "skill_1"}},
                {"id": "eval_2", "_metadata": {"skill": "skill_2"}}
            ]
            
            # Initial cleanup - should not be skipped
            assert not should_skip_cache_cleanup(cache_dir, models, judges, evals)
            
            # Mark cleanup as complete
            mark_cache_cleanup_complete(cache_dir, models, judges, evals, 5)
            
            # Same configuration - should be skipped
            assert should_skip_cache_cleanup(cache_dir, models, judges, evals)

    def test_should_skip_cache_cleanup_with_changed_config(self):
        """Test that cache cleanup is NOT skipped when configuration changes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            
            # Initial data
            models = [{"id": "model_a"}, {"id": "model_b"}]
            judges = [{"id": "judge_1"}]
            evals = [{"id": "eval_1", "_metadata": {"skill": "skill_1"}}]
            
            # Mark cleanup as complete with initial config
            mark_cache_cleanup_complete(cache_dir, models, judges, evals, 3)
            
            # Change models - should not be skipped
            changed_models = [{"id": "model_c"}, {"id": "model_d"}]
            assert not should_skip_cache_cleanup(cache_dir, changed_models, judges, evals)
            
            # Change judges - should not be skipped  
            changed_judges = [{"id": "judge_2"}]
            assert not should_skip_cache_cleanup(cache_dir, models, changed_judges, evals)
            
            # Change evals - should not be skipped
            changed_evals = [{"id": "eval_2", "_metadata": {"skill": "skill_2"}}]
            assert not should_skip_cache_cleanup(cache_dir, models, judges, changed_evals)

    def test_cache_cleanup_marker_file_operations(self):
        """Test cache cleanup marker file creation and reading."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            
            models = [{"id": "model_a"}]
            judges = [{"id": "judge_1"}]
            evals = [{"id": "eval_1", "_metadata": {"skill": "skill_1"}}]
            
            # Mark cleanup complete
            mark_cache_cleanup_complete(cache_dir, models, judges, evals, 10)
            
            # Verify marker file exists and has correct content
            marker_file = get_cache_cleanup_marker_file(cache_dir)
            assert marker_file.exists()
            
            with open(marker_file) as f:
                cleanup_info = json.load(f)
            
            assert cleanup_info["cleaned_count"] == 10
            assert cleanup_info["configuration"]["model_ids"] == ["model_a"]
            assert cleanup_info["configuration"]["judge_ids"] == ["judge_1"]
            assert cleanup_info["configuration"]["eval_ids"] == ["eval_1"]
            assert cleanup_info["configuration"]["skill_ids"] == ["skill_1"]
            assert cleanup_info["process_info"]["pid"] == os.getpid()

    def test_should_skip_cache_cleanup_with_old_timestamp(self):
        """Test that old cleanup markers don't prevent new cleanup."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            
            models = [{"id": "model_a"}]
            judges = [{"id": "judge_1"}]
            evals = [{"id": "eval_1", "_metadata": {"skill": "skill_1"}}]
            
            # Create old cleanup marker (older than 1 hour)
            marker_file = get_cache_cleanup_marker_file(cache_dir)
            marker_file.parent.mkdir(parents=True, exist_ok=True)
            
            old_cleanup_info = {
                "timestamp": time.time() - 7200,  # 2 hours ago
                "cleaned_count": 5,
                "configuration": {
                    "model_ids": ["model_a"],
                    "judge_ids": ["judge_1"], 
                    "eval_ids": ["eval_1"],
                    "skill_ids": ["skill_1"]
                }
            }
            
            with open(marker_file, "w") as f:
                json.dump(old_cleanup_info, f)
            
            # Should not be skipped because timestamp is old
            assert not should_skip_cache_cleanup(cache_dir, models, judges, evals)

    def test_cache_lock_timeout_handling(self):
        """Test that cache lock timeout works correctly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "cache"
            
            def hold_lock_briefly():
                """Hold lock for a short time."""
                with exclusive_cache_lock(cache_dir, "holder", timeout=5):
                    time.sleep(2)  # Hold lock for 2 seconds
                    return "holder_done"
            
            def try_acquire_with_short_timeout():
                """Try to acquire with very short timeout."""
                try:
                    with exclusive_cache_lock(cache_dir, "waiter", timeout=1):
                        return "waiter_success"
                except CacheLockError:
                    return "waiter_timeout"
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Start lock holder
                holder_future = executor.submit(hold_lock_briefly)
                
                # Wait a bit, then try to acquire with short timeout
                time.sleep(0.5)
                waiter_future = executor.submit(try_acquire_with_short_timeout)
                
                # Get results
                holder_result = holder_future.result()
                waiter_result = waiter_future.result()
            
            assert holder_result == "holder_done"
            assert waiter_result == "waiter_timeout"


class TestCacheCleanupIntegration:
    """Integration tests for cache cleanup with parallel safety."""
    
    def test_concurrent_cache_cleanup_prevention(self):
        """Test that concurrent cache cleanup is properly prevented."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            from scripts.run_tournaments import JudgeExecutor
            
            cache_dir = Path(tmp_dir) / "judge_cache"
            
            # Create test cache structure
            skill_dir = cache_dir / "test_skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "cache1.json").write_text('{"metadata": {}}')
            (skill_dir / "cache2.json").write_text('{"metadata": {}}')
            
            # Mock data
            models = [{"id": "model_a"}]
            judges = [{"id": "judge_1"}]
            evals = [{"id": "eval_1", "_metadata": {"skill": "test_skill"}}]
            
            cleanup_results = []
            
            def run_cleanup(process_id: int):
                """Run cache cleanup and record results."""
                try:
                    executor = JudgeExecutor(cache_dir)
                    executor.cleanup_invalid_match_cache(models, judges, evals)
                    cleanup_results.append(f"process_{process_id}_completed")
                    return True
                except Exception as e:
                    cleanup_results.append(f"process_{process_id}_error_{type(e).__name__}")
                    return False
            
            # Run cleanup from multiple processes simultaneously
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(run_cleanup, i) 
                    for i in range(3)
                ]
                
                for future in as_completed(futures):
                    future.result()
            
            # All processes should complete without errors
            completed_count = len([r for r in cleanup_results if "completed" in r])
            error_count = len([r for r in cleanup_results if "error" in r])
            
            assert completed_count >= 1, f"Expected at least 1 completion: {cleanup_results}"
            assert error_count == 0, f"Expected no errors: {cleanup_results}"
            
            # Cache files should still be accessible (not corrupted by race conditions)
            assert skill_dir.exists()
            cache_files = list(skill_dir.glob("*.json"))
            # Files should exist and be readable
            for cache_file in cache_files:
                with open(cache_file) as f:
                    json.load(f)  # Should not raise exception


if __name__ == "__main__":
    pytest.main([__file__, "-v"])