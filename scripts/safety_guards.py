"""
Critical safety guards to prevent production data destruction during testing.

This module provides runtime checks that block access to production data
when tests are running, preventing costly cache destruction.
"""

import os
from pathlib import Path
from typing import NoReturn


class ProductionDataAccessError(Exception):
    """Raised when test code attempts to access production data directories."""

    pass


def check_production_data_access(path: str | Path, operation: str = "access") -> None:
    """
    Check if code is attempting to access production data during testing.

    Args:
        path: The path being accessed
        operation: Description of the operation (for error message)

    Raises:
        ProductionDataAccessError: If test code tries to access production data
    """
    if os.getenv("AFBENCH_TEST_MODE") != "true":
        return  # Allow normal access outside test mode

    path_obj = Path(path).resolve()

    # Block access to production data directories during testing
    production_paths = [
        Path("data").resolve(),
        Path("data/conversations").resolve(),
        Path("data/judge_cache").resolve(),
        Path("data/skill_ratings").resolve(),
        Path("data/intermediaries").resolve(),
    ]

    for prod_path in production_paths:
        if prod_path.exists() and (path_obj == prod_path or prod_path in path_obj.parents):
            raise ProductionDataAccessError(
                f"BLOCKED: Test attempted {operation} on production data path: {path_obj}\n"
                f"Production data access is forbidden during testing to prevent data loss.\n"
                f"Tests should use isolated temporary directories instead."
            )


def block_production_file_access(filepath: str | Path, operation: str = "file access") -> None:
    """
    Block access to production data files during testing.

    Args:
        filepath: The file path being accessed
        operation: Description of the operation

    Raises:
        ProductionDataAccessError: If test code tries to access production files
    """
    if os.getenv("AFBENCH_TEST_MODE") != "true":
        return

    filepath_obj = Path(filepath).resolve()

    # Block access to specific production data files
    if (
        filepath_obj.name
        in [
            "loaded_models.json",
            "loaded_judges.json",
            "loaded_skills.json",
            "tournaments.json",
            "tournament_summaries.json",
            "skill_ratings.json",
            "conversations.json",  # Legacy file
            "conversations_legacy.json",
        ]
        and "data" in filepath_obj.parts
    ):
        raise ProductionDataAccessError(
            f"BLOCKED: Test attempted {operation} on production data file: {filepath_obj}\n"
            f"Tests should create their own data files in temporary directories."
        )


def ensure_test_mode_for_cache_operations() -> None:
    """
    Ensure that cache operations are only performed in test mode with safe directories.

    This should be called by cache cleanup and invalidation functions.
    """
    if os.getenv("AFBENCH_TEST_MODE") == "true":
        return  # Safe - we're in test mode with isolated directories

    # Check if we're in a testing context but somehow missed the test mode flag
    import sys
    import tempfile

    if "pytest" in sys.modules:
        # Additional check: if we're using temporary directories, that's also safe
        # Get the current stack to find cache directory paths being used
        import inspect

        for frame in inspect.stack():
            frame_locals = frame.frame.f_locals
            # Check if any cache directory variables point to temp directories
            for var_name, var_value in frame_locals.items():
                if "cache" in var_name.lower() and hasattr(var_value, "__fspath__"):
                    cache_path = str(var_value)
                    if cache_path.startswith(tempfile.gettempdir()):
                        return  # Safe - using temporary directory
                elif var_name == "self" and hasattr(var_value, "cache_dir"):
                    cache_path = str(var_value.cache_dir)
                    if cache_path.startswith(tempfile.gettempdir()):
                        return  # Safe - using temporary directory

        raise ProductionDataAccessError(
            "CRITICAL: Cache operation detected during testing without AFBENCH_TEST_MODE set!\n"
            "This indicates a safety system failure. Tests should never operate on production cache."
        )
