#!/usr/bin/env python3
"""
Test tournament performance issues and validate the fix.
"""

import json
import tempfile
import time
from pathlib import Path


def test_cache_validation_performance():
    """Test that cache validation doesn't cause O(n²) performance issues."""
    print("🧪 Testing cache validation performance...")

    # Create a temporary directory with many cache files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        cache_dir = temp_path / "tournaments"
        skill_dir = cache_dir / "test_skill"
        skill_dir.mkdir(parents=True)

        # Create 100 mock cache files
        num_files = 100
        print(f"📊 Creating {num_files} mock cache files...")

        for i in range(num_files):
            cache_file = skill_dir / f"match_{i:03d}_judge_{i % 3}_hash.json"
            mock_data = {
                "metadata": {
                    "model_a_id": "model_a",
                    "model_b_id": "model_b",
                    "judge_id": f"judge_{i % 3}",
                    "eval_id": "test_eval",
                },
                "result": {"vote": "A"},
            }
            with open(cache_file, "w") as f:
                json.dump(mock_data, f)

        # Test current implementation performance
        start_time = time.time()

        # Simulate the cache validation logic from run_tournaments.py
        valid_models = {"model_a", "model_b"}
        valid_judges = {"judge_0", "judge_1", "judge_2"}
        valid_evals = {"test_eval"}

        files_processed = 0
        for cache_file in skill_dir.glob("*.json"):
            try:
                with open(cache_file) as f:
                    cached_data = json.load(f)
                metadata = cached_data.get("metadata", {})

                model_a = metadata.get("model_a_id")
                model_b = metadata.get("model_b_id")
                judge_id = metadata.get("judge_id")
                eval_id = metadata.get("eval_id")

                # Validation checks (same as original)
                if (
                    model_a in valid_models
                    and model_b in valid_models
                    and judge_id in valid_judges
                    and eval_id in valid_evals
                ):
                    files_processed += 1

            except (OSError, json.JSONDecodeError):
                pass

        elapsed_time = time.time() - start_time
        print(f"⏱️ Processed {files_processed} files in {elapsed_time:.3f} seconds")

        # Performance threshold: should process 100 files in under 0.5 seconds
        performance_ok = elapsed_time < 0.5

        if not performance_ok:
            print(
                f"❌ PERFORMANCE ISSUE: {elapsed_time:.3f}s is too slow for {num_files} files"
            )
            print(
                f"   This would take {elapsed_time * 4:.1f}s for 400 files (current benchmark size)"
            )
        else:
            print(
                f"✅ Performance acceptable: {elapsed_time:.3f}s for {num_files} files"
            )

        assert (
            performance_ok
        ), f"Performance issue: {elapsed_time:.3f}s is too slow for {num_files} files"


def test_optimized_cache_validation():
    """Test an optimized cache validation approach."""
    print("🧪 Testing optimized cache validation...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        cache_dir = temp_path / "tournaments"
        skill_dir = cache_dir / "test_skill"
        skill_dir.mkdir(parents=True)

        # Create files with predictable names that can be filtered without opening
        num_files = 100

        for i in range(num_files):
            # Some files have invalid eval names that can be filtered by filename
            eval_id = "test_eval" if i % 4 != 0 else "invalid_eval"
            cache_file = skill_dir / f"match_{i:03d}_judge_{i % 3}_{eval_id}_hash.json"

            mock_data = {
                "metadata": {
                    "model_a_id": "model_a",
                    "model_b_id": "model_b",
                    "judge_id": f"judge_{i % 3}",
                    "eval_id": eval_id,
                },
                "result": {"vote": "A"},
            }
            with open(cache_file, "w") as f:
                json.dump(mock_data, f)

        start_time = time.time()

        # OPTIMIZED APPROACH: Filter by filename patterns first
        files_processed = 0
        valid_eval_patterns = ["*test_eval*"]

        for eval_pattern in valid_eval_patterns:
            for cache_file in skill_dir.glob(f"{eval_pattern}.json"):
                # Only load files that pass filename filtering
                try:
                    with open(cache_file) as f:
                        json.load(f)
                    files_processed += 1
                except (OSError, json.JSONDecodeError):
                    pass

        elapsed_time = time.time() - start_time
        print(
            f"⏱️ OPTIMIZED: Processed {files_processed} valid files in {elapsed_time:.3f} seconds"
        )

        performance_ok = elapsed_time < 0.2  # Stricter threshold for optimized version

        if not performance_ok:
            print(f"❌ OPTIMIZED VERSION STILL SLOW: {elapsed_time:.3f}s")
        else:
            print(f"✅ Optimized performance good: {elapsed_time:.3f}s")

        assert performance_ok, f"Optimized version still too slow: {elapsed_time:.3f}s"


if __name__ == "__main__":
    print("🧪 Running tournament performance tests...")

    test1_passed = test_cache_validation_performance()
    test2_passed = test_optimized_cache_validation()

    if test1_passed:
        print("✅ Current implementation performance is acceptable")
    else:
        print("❌ Current implementation has performance issues")

    if test2_passed:
        print("✅ Optimized approach shows improvement")
    else:
        print("❌ Optimized approach needs more work")

    if not test1_passed and test2_passed:
        print("💡 Recommendation: Implement the optimized cache validation approach")
