"""
Utility functions for tests to get correct judge cache paths dynamically.
This prevents hardcoded paths from breaking when architecture changes.
"""

from pathlib import Path


def get_judge_cache_dir():
    """Get the correct judge cache directory from JudgeExecutor."""
    try:
        from scripts.run_tournaments import JudgeExecutor

        judge_executor = JudgeExecutor()
        return Path(judge_executor.cache_dir)
    except Exception:
        # Fallback for tests that can't import JudgeExecutor
        return Path("data/testonly/judge_cache")


def get_tournaments_json_path():
    """Get the correct tournaments.json path."""
    return Path("data/testonly/tournaments.json")


def verify_no_cache_conflicts():
    """Verify judge cache doesn't conflict with tournaments.json."""
    judge_cache = get_judge_cache_dir()
    tournaments_json = get_tournaments_json_path()

    if str(judge_cache) == str(tournaments_json.parent):
        raise ValueError(f"Judge cache {judge_cache} conflicts with tournaments.json parent {tournaments_json.parent}")

    return True
