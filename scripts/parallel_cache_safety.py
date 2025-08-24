#!/usr/bin/env python3
"""
Parallel cache safety utilities to prevent race conditions during concurrent tournament execution.

This module provides file locking and safe cleanup mechanisms to prevent production data
destruction when multiple tournament processes run simultaneously.
"""

import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator


class CacheLockError(Exception):
    """Raised when cache locking operations fail."""
    pass


@contextmanager
def exclusive_cache_lock(cache_dir: Path, operation: str = "cache operation", timeout: int = 30) -> Generator[None, None, None]:
    """
    Acquire an exclusive lock for cache operations to prevent race conditions.
    
    This implementation uses file locking that works across processes and threads.
    The lock is based on creating/removing a lockfile atomically.
    
    Args:
        cache_dir: The cache directory to lock
        operation: Description of the operation (for logging)
        timeout: Maximum time to wait for lock (seconds)
        
    Yields:
        None when lock is acquired
        
    Raises:
        CacheLockError: If lock cannot be acquired within timeout
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock_file_path = cache_dir / ".cache_lock"
    temp_lock_path = cache_dir / f".cache_lock.tmp.{os.getpid()}.{int(time.time() * 1000000)}"
    
    lock_acquired = False
    start_time = time.time()
    
    try:
        while time.time() - start_time < timeout:
            try:
                # Try to create lock file atomically
                # Step 1: Create temp file with process info
                process_info = {
                    "pid": os.getpid(),
                    "operation": operation,
                    "timestamp": time.time(),
                    "locked_by": f"afbench_tournament_{os.getpid()}"
                }
                
                with open(temp_lock_path, "w") as f:
                    json.dump(process_info, f, indent=2)
                
                # Step 2: Atomically move temp file to lock file (this will fail if lock exists)
                try:
                    # On Unix, this is atomic and will fail if target exists
                    os.link(str(temp_lock_path), str(lock_file_path))
                    lock_acquired = True
                    print(f"🔒 Acquired cache lock for: {operation} (PID: {os.getpid()})")
                    break
                    
                except FileExistsError:
                    # Lock is held by another process
                    pass
                except OSError as e:
                    # Handle systems that don't support atomic link
                    if e.errno == 17:  # EEXIST
                        pass
                    else:
                        # Try alternative approach for systems without atomic link
                        try:
                            with open(lock_file_path, "x") as f:  # Create exclusively
                                json.dump(process_info, f, indent=2)
                            lock_acquired = True
                            print(f"🔒 Acquired cache lock for: {operation} (PID: {os.getpid()})")
                            break
                        except FileExistsError:
                            pass
                
            except (OSError, IOError) as e:
                if time.time() - start_time >= timeout:
                    break
            
            finally:
                # Clean up temp file
                try:
                    temp_lock_path.unlink(missing_ok=True)
                except (OSError, FileNotFoundError):
                    pass
            
            # Check if existing lock is stale (older than 5 minutes)
            if lock_file_path.exists():
                try:
                    with open(lock_file_path) as f:
                        existing_lock_info = json.load(f)
                    
                    lock_age = time.time() - existing_lock_info.get("timestamp", time.time())
                    if lock_age > 300:  # 5 minutes
                        print(f"   🧹 Removing stale lock (age: {lock_age:.1f}s)")
                        try:
                            lock_file_path.unlink()
                        except (OSError, FileNotFoundError):
                            pass
                        continue
                        
                except (json.JSONDecodeError, OSError, KeyError):
                    # Corrupted lock file, remove it
                    try:
                        lock_file_path.unlink()
                    except (OSError, FileNotFoundError):
                        pass
                    continue
            
            # Wait before retrying
            time.sleep(0.1)
        
        if not lock_acquired:
            raise CacheLockError(
                f"Could not acquire cache lock for {operation} after {timeout}s. "
                f"Another process may be holding the lock."
            )
        
        yield
        
    finally:
        # Clean up lock file if we acquired it
        if lock_acquired:
            try:
                lock_file_path.unlink(missing_ok=True)
                print(f"🔓 Released cache lock for: {operation} (PID: {os.getpid()})")
            except (OSError, FileNotFoundError):
                pass


def safe_remove_directory_tree(dir_path: Path, reason: str) -> bool:
    """
    Safely remove a directory tree with proper checking and logging.
    
    Args:
        dir_path: Directory to remove
        reason: Reason for removal (for logging)
        
    Returns:
        True if directory was removed, False if it was already gone or removal failed
    """
    if not dir_path.exists():
        return False
    
    try:
        import shutil
        print(f"   🗑️  Removing directory: {dir_path} ({reason})")
        shutil.rmtree(dir_path)
        return True
    except (OSError, FileNotFoundError) as e:
        # Directory might have been removed by another process (race condition)
        if not dir_path.exists():
            print(f"   ℹ️  Directory already removed by another process: {dir_path}")
            return False
        else:
            print(f"   ⚠️  Failed to remove directory {dir_path}: {e}")
            return False


def safe_remove_file(file_path: Path, reason: str) -> bool:
    """
    Safely remove a file with proper checking and logging.
    
    Args:
        file_path: File to remove  
        reason: Reason for removal (for logging)
        
    Returns:
        True if file was removed, False if it was already gone or removal failed
    """
    if not file_path.exists():
        return False
    
    try:
        print(f"   🗑️  Removing file: {file_path.name} ({reason})")
        file_path.unlink()
        return True
    except (OSError, FileNotFoundError) as e:
        # File might have been removed by another process (race condition)
        if not file_path.exists():
            print(f"   ℹ️  File already removed by another process: {file_path.name}")
            return False
        else:
            print(f"   ⚠️  Failed to remove file {file_path}: {e}")
            return False


def get_cache_cleanup_marker_file(cache_dir: Path) -> Path:
    """Get the path to the cache cleanup marker file."""
    return cache_dir / ".cache_cleaned"


def should_skip_cache_cleanup(cache_dir: Path, models: list, judges: list, evals: list) -> bool:
    """
    Check if cache cleanup should be skipped because it was recently done with the same configuration.
    
    Args:
        cache_dir: Cache directory
        models: Current models list
        judges: Current judges list  
        evals: Current evals list
        
    Returns:
        True if cleanup should be skipped, False if cleanup is needed
    """
    marker_file = get_cache_cleanup_marker_file(cache_dir)
    
    if not marker_file.exists():
        return False
    
    try:
        with open(marker_file) as f:
            cleanup_info = json.load(f)
        
        # Check if current configuration matches what was last cleaned
        current_config = {
            "model_ids": sorted([model["id"] for model in models]),
            "judge_ids": sorted([judge["id"] for judge in judges]),
            "eval_ids": sorted([eval_data["id"] for eval_data in evals]),
            "skill_ids": sorted([eval_data["_metadata"]["skill"] for eval_data in evals])
        }
        
        last_config = cleanup_info.get("configuration", {})
        
        # Skip if configuration hasn't changed and cleanup was recent (within 1 hour)
        config_unchanged = (
            current_config["model_ids"] == last_config.get("model_ids", []) and
            current_config["judge_ids"] == last_config.get("judge_ids", []) and  
            current_config["eval_ids"] == last_config.get("eval_ids", []) and
            current_config["skill_ids"] == last_config.get("skill_ids", [])
        )
        
        last_cleanup_time = cleanup_info.get("timestamp", 0)
        time_since_cleanup = time.time() - last_cleanup_time
        cleanup_recent = time_since_cleanup < 3600  # 1 hour
        
        if config_unchanged and cleanup_recent:
            print(f"   ⏭️  Skipping cache cleanup - done {time_since_cleanup:.1f}s ago with same configuration")
            return True
        
        return False
        
    except (json.JSONDecodeError, KeyError, OSError):
        # Corrupted marker file, need to cleanup
        return False


def mark_cache_cleanup_complete(cache_dir: Path, models: list, judges: list, evals: list, cleaned_count: int) -> None:
    """
    Mark cache cleanup as complete with current configuration.
    
    Args:
        cache_dir: Cache directory
        models: Models that were processed
        judges: Judges that were processed  
        evals: Evals that were processed
        cleaned_count: Number of items cleaned
    """
    marker_file = get_cache_cleanup_marker_file(cache_dir)
    
    cleanup_info = {
        "timestamp": time.time(),
        "cleaned_count": cleaned_count,
        "configuration": {
            "model_ids": sorted([model["id"] for model in models]),
            "judge_ids": sorted([judge["id"] for judge in judges]),
            "eval_ids": sorted([eval_data["id"] for eval_data in evals]),
            "skill_ids": sorted([eval_data["_metadata"]["skill"] for eval_data in evals])
        },
        "process_info": {
            "pid": os.getpid(),
            "hostname": os.environ.get("HOSTNAME", "unknown")
        }
    }
    
    try:
        with open(marker_file, "w") as f:
            json.dump(cleanup_info, f, indent=2)
    except OSError:
        # Failed to write marker - not critical
        pass