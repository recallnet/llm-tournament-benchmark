"""
Global pytest configuration and fixtures for safe testing.

CRITICAL SAFETY: This file prevents tests from accidentally destroying production cache data.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def isolated_judge_cache():
    """Provide an isolated temporary cache directory for judge executor tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir) / "judge_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        yield cache_dir


@pytest.fixture
def isolated_skill_cache():
    """Provide an isolated temporary cache directory for skill ratings tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir) / "skill_ratings"
        cache_dir.mkdir(parents=True, exist_ok=True)
        yield cache_dir


@pytest.fixture
def isolated_conversations_cache():
    """Provide an isolated temporary cache directory for conversation executor tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conversations_dir = Path(temp_dir) / "conversations"
        intermediaries_dir = Path(temp_dir) / "intermediaries"
        conversations_dir.mkdir(parents=True, exist_ok=True)
        intermediaries_dir.mkdir(parents=True, exist_ok=True)
        yield {"conversations": conversations_dir, "intermediaries": intermediaries_dir}


@pytest.fixture(autouse=True)
def production_data_safety_guard(monkeypatch):
    """
    PRODUCTION DATA SAFETY: Block access to data/ and data/production directories.

    Tests should use tests/data (default config) or isolated temp directories.
    This prevents accidental production data destruction.
    """
    import shutil

    # Production paths that tests must never touch
    forbidden_paths = [
        Path("data").absolute(),
        Path("data/production").absolute(),
        Path("data/quick").absolute(),  # Profile paths are also forbidden in tests
    ]

    def is_forbidden_path(path_str):
        """Check if path touches forbidden production directories."""
        try:
            path = Path(path_str).resolve()
            return any(forbidden in path.parents or path == forbidden for forbidden in forbidden_paths)
        except (ValueError, OSError):
            # Fallback string check
            path_str = str(path_str)
            return (
                path_str.startswith(("data/", "./data/")) or "data/production" in path_str or "data/quick" in path_str
            ) and not path_str.startswith("data/testonly/")

    # Block dangerous operations on production paths
    original_rmtree = shutil.rmtree

    def safe_rmtree(path, *args, **kwargs):
        if is_forbidden_path(path):
            raise PermissionError(f"🔒 PRODUCTION DATA SAFETY: Tests cannot delete {path}")
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", safe_rmtree)

    # Block Path operations on production data
    original_path_mkdir = Path.mkdir

    def safe_path_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        if is_forbidden_path(self):
            raise PermissionError(f"🔒 PRODUCTION DATA SAFETY: Tests cannot create {self}")
        return original_path_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", safe_path_mkdir)


# Global safety check - run once per test session
def pytest_sessionstart(session):
    """
    Session-level safety check to ensure we're not accidentally running tests
    that could destroy production data.
    """
    print("\n🔒 AFBench Test Safety Check: Production data access blocked")
    print("   Tests will use isolated temporary directories only")


def pytest_collection_modifyitems(config, items):
    """
    Add safety markers to all tests that might access production data.
    """
    for item in items:
        # Mark any test that might use production data paths
        if any(keyword in str(item.fspath) for keyword in ["judge", "cache", "conversation", "tournament"]):
            item.add_marker(pytest.mark.production_safety)
