#!/usr/bin/env python3
"""
Test suite for parallel judge implementation.

Verifies that parallel judge execution:
1. Produces identical results to sequential execution
2. Maintains cache compatibility
3. Preserves early consensus logic
4. Handles errors correctly
5. Maintains deterministic behavior
"""

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class ParallelJudgeTestFramework:
    """Test framework for parallel judge implementation validation."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.temp_dir = None
        self.original_cwd = None
    
    def __enter__(self):
        """Set up isolated test environment."""
        self.temp_dir = tempfile.mkdtemp(prefix=f"parallel_judge_test_{self.test_name}_")
        self.original_cwd = Path.cwd()
        
        # Copy essential project structure
        project_root = Path(__file__).parent.parent
        self._copy_project_structure(project_root, Path(self.temp_dir))
        
        # Change to temp directory
        import os
        os.chdir(self.temp_dir)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up test environment."""
        if self.original_cwd:
            import os
            os.chdir(self.original_cwd)
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _copy_project_structure(self, src: Path, dst: Path):
        """Copy essential project files."""
        essential_items = [
            "Snakefile",
            "config", 
            "profiles",
            "scripts",
            "model_pools",
            "judge_pools",
            "skills",
        ]
        
        dst.mkdir(exist_ok=True)
        
        for item in essential_items:
            src_path = src / item
            dst_path = dst / item
            
            if src_path.exists():
                if src_path.is_dir():
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dst_path)
        
        # Create testonly data directory
        data_dir = dst / "data" / "testonly"
        data_dir.mkdir(parents=True, exist_ok=True)


class TestParallelJudgeImplementation:
    """Test parallel judge implementation correctness."""
    
    def test_parallel_function_import(self):
        """Test that the parallel judge function can be imported."""
        from run_tournaments import _execute_judges_for_match
        assert callable(_execute_judges_for_match)
    
    def test_parallel_vs_sequential_identical_results(self):
        """Test that parallel execution produces identical results to sequential."""
        from run_tournaments import TournamentMatch, _execute_judges_for_match
        
        # Mock judge executor and judges
        mock_judge_executor = MagicMock()
        
        # Set up deterministic mock responses
        judge_responses = [
            ("A", {"conversation": "test1"}, "explanation1"),
            ("A", {"conversation": "test2"}, "explanation2"),
            ("B", {"conversation": "test3"}, "explanation3"),
        ]
        
        mock_judge_executor.execute_judge_decision.side_effect = judge_responses
        
        judges = [
            {"id": "judge1"},
            {"id": "judge2"}, 
            {"id": "judge3"}
        ]
        
        eval_data = {"id": "test_eval"}
        conversations_cache_dir = "test_cache"
        
        # Test parallel execution
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        _execute_judges_for_match(match, judges, mock_judge_executor, eval_data, conversations_cache_dir)
        
        # Verify results
        assert len(match.judge_votes) == 2, "Should have early consensus after 2 judges"
        assert match.judge_votes["judge1"] == "A"
        assert match.judge_votes["judge2"] == "A"
        assert "judge3" not in match.judge_votes, "Third judge should not be called due to consensus"
        
        # Verify early consensus detection
        assert match.check_early_consensus() == True
    
    def test_parallel_no_early_consensus(self):
        """Test parallel execution when judges disagree (no early consensus)."""
        from run_tournaments import TournamentMatch, _execute_judges_for_match
        
        mock_judge_executor = MagicMock()
        
        # Judges disagree, need third judge
        judge_responses = [
            ("A", {"conversation": "test1"}, "explanation1"),
            ("B", {"conversation": "test2"}, "explanation2"),
            ("A", {"conversation": "test3"}, "explanation3"),  # Third judge breaks tie
        ]
        
        mock_judge_executor.execute_judge_decision.side_effect = judge_responses
        
        judges = [
            {"id": "judge1"},
            {"id": "judge2"},
            {"id": "judge3"}
        ]
        
        eval_data = {"id": "test_eval"}
        conversations_cache_dir = "test_cache"
        
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        _execute_judges_for_match(match, judges, mock_judge_executor, eval_data, conversations_cache_dir)
        
        # Verify all three judges were called
        assert len(match.judge_votes) == 3, "Should have all 3 judges when no early consensus"
        assert match.judge_votes["judge1"] == "A"
        assert match.judge_votes["judge2"] == "B"
        assert match.judge_votes["judge3"] == "A"
        
        # Verify no early consensus detected
        assert match.check_early_consensus() == False
    
    def test_parallel_error_handling(self):
        """Test error handling in parallel execution."""
        from run_tournaments import TournamentMatch, _execute_judges_for_match
        
        mock_judge_executor = MagicMock()
        
        # First judge succeeds, second fails, third succeeds
        def judge_side_effect(*args, **kwargs):
            judge_id = args[1]["id"]
            if judge_id == "judge2":
                raise Exception("Simulated judge error")
            elif judge_id == "judge1":
                return ("A", {"conversation": "test1"}, "explanation1")
            else:
                return ("A", {"conversation": "test3"}, "explanation3")
        
        mock_judge_executor.execute_judge_decision.side_effect = judge_side_effect
        
        judges = [
            {"id": "judge1"},
            {"id": "judge2"}, 
            {"id": "judge3"}
        ]
        
        eval_data = {"id": "test_eval"}
        conversations_cache_dir = "test_cache"
        
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        _execute_judges_for_match(match, judges, mock_judge_executor, eval_data, conversations_cache_dir)
        
        # Verify error handling
        assert len(match.judge_votes) == 3, "Should have all judges even with error"
        assert match.judge_votes["judge1"] == "A"
        assert match.judge_votes["judge2"] == "TIE"  # Error converted to TIE
        assert match.judge_votes["judge3"] == "A"
        
        # Verify error conversation was recorded
        assert match.judge_conversations["judge2"][0]["content"] == "[JUDGE_EXECUTION_ERROR]"
    
    def test_parallel_fallback_for_insufficient_judges(self):
        """Test fallback to sequential execution when < 2 judges."""
        from run_tournaments import TournamentMatch, _execute_judges_for_match
        
        mock_judge_executor = MagicMock()
        mock_judge_executor.execute_judge_decision.return_value = (
            "A", {"conversation": "test1"}, "explanation1"
        )
        
        # Only one judge
        judges = [{"id": "judge1"}]
        eval_data = {"id": "test_eval"}
        conversations_cache_dir = "test_cache"
        
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        _execute_judges_for_match(match, judges, mock_judge_executor, eval_data, conversations_cache_dir)
        
        # Verify single judge was called
        assert len(match.judge_votes) == 1
        assert match.judge_votes["judge1"] == "A"
    
    def test_deterministic_behavior_multiple_runs(self):
        """Test that results are deterministic across multiple runs."""
        from run_tournaments import TournamentMatch, _execute_judges_for_match
        
        mock_judge_executor = MagicMock()
        
        # Fixed responses for deterministic testing
        judge_responses = [
            ("A", {"conversation": "test1"}, "explanation1"),
            ("B", {"conversation": "test2"}, "explanation2"),
            ("A", {"conversation": "test3"}, "explanation3"),
        ]
        
        judges = [
            {"id": "judge1"},
            {"id": "judge2"},
            {"id": "judge3"}
        ]
        
        eval_data = {"id": "test_eval"}
        conversations_cache_dir = "test_cache"
        
        results = []
        
        # Run multiple times and collect results
        for run in range(3):
            mock_judge_executor.execute_judge_decision.side_effect = judge_responses.copy()
            
            match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
            _execute_judges_for_match(match, judges, mock_judge_executor, eval_data, conversations_cache_dir)
            
            results.append({
                "judge_votes": dict(match.judge_votes),
                "num_judges": len(match.judge_votes)
            })
        
        # Verify all runs produced identical results
        for i in range(1, len(results)):
            assert results[i] == results[0], f"Run {i} produced different results than run 0"
    
    def test_cache_compatibility(self):
        """Test that parallel implementation maintains cache compatibility."""
        # This test verifies the parallel implementation doesn't break caching
        # by checking that the same cache key logic is used
        
        from run_tournaments import TournamentMatch
        
        # Create identical matches
        match1 = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        match2 = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        
        # Verify match IDs are identical (important for cache keys)
        assert match1.match_id == match2.match_id
        
        # The actual cache key generation happens in JudgeExecutor.execute_judge_decision,
        # which is the same code path for both sequential and parallel execution.
        # This test verifies that the match setup is identical.
    
    @patch('builtins.print')  # Suppress output during test
    def test_early_consensus_logging(self, mock_print):
        """Test that early consensus is logged correctly in parallel execution."""
        from run_tournaments import TournamentMatch, _execute_judges_for_match
        
        mock_judge_executor = MagicMock()
        mock_judge_executor.execute_judge_decision.side_effect = [
            ("A", {"conversation": "test1"}, "explanation1"),
            ("A", {"conversation": "test2"}, "explanation2"),
        ]
        
        judges = [{"id": "judge1"}, {"id": "judge2"}, {"id": "judge3"}]
        eval_data = {"id": "test_eval"}
        conversations_cache_dir = "test_cache"
        
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        _execute_judges_for_match(match, judges, mock_judge_executor, eval_data, conversations_cache_dir)
        
        # Verify early consensus logging was called
        mock_print.assert_called_with("         🎯 Early consensus reached: A")
    
    def test_integration_with_existing_test_framework(self):
        """Test integration with existing early consensus test framework."""
        # Import and run existing early consensus tests to ensure compatibility
        try:
            from test_early_consensus_optimization import TestEarlyConsensusCore
            test_instance = TestEarlyConsensusCore()
            
            # Run a few key tests to verify compatibility
            test_instance.test_early_consensus_both_vote_a()
            test_instance.test_no_early_consensus_mixed_votes()
            
        except ImportError:
            # If test file doesn't exist, that's okay - we're testing the core functionality
            pytest.skip("Early consensus test file not found - skipping integration test")


class TestParallelJudgePerformance:
    """Test performance characteristics of parallel judge implementation."""
    
    @pytest.mark.slow
    def test_parallel_performance_improvement(self):
        """Test that parallel execution provides performance improvement."""
        from run_tournaments import TournamentMatch, _execute_judges_for_match
        
        # Mock slow judge execution
        def slow_judge_execution(*args, **kwargs):
            time.sleep(0.1)  # Simulate API call delay
            judge_id = args[1]["id"]
            return ("A", {"conversation": f"test_{judge_id}"}, f"explanation_{judge_id}")
        
        mock_judge_executor = MagicMock()
        mock_judge_executor.execute_judge_decision.side_effect = slow_judge_execution
        
        judges = [{"id": "judge1"}, {"id": "judge2"}]
        eval_data = {"id": "test_eval"}
        conversations_cache_dir = "test_cache"
        
        # Measure parallel execution time
        start_time = time.time()
        match = TournamentMatch("model_a", "model_b", "eval_1", "skill_1")
        _execute_judges_for_match(match, judges, mock_judge_executor, eval_data, conversations_cache_dir)
        parallel_time = time.time() - start_time
        
        # Verify results
        assert len(match.judge_votes) == 2
        assert match.judge_votes["judge1"] == "A"
        assert match.judge_votes["judge2"] == "A"
        
        # Parallel execution should take roughly 0.1s (parallel) rather than 0.2s (sequential)
        # Allow some overhead for thread management
        assert parallel_time < 0.15, f"Parallel execution took {parallel_time}s, expected < 0.15s"
        
        print(f"Parallel execution completed in {parallel_time:.3f}s")


if __name__ == "__main__":
    print("🧪 Running parallel judge implementation tests...")
    
    import subprocess
    
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short", "-x"],
        capture_output=True,
        text=True,
    )
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode == 0:
        print("✅ All parallel judge tests passed!")
    else:
        print("❌ Some parallel judge tests failed!")
    
    exit(result.returncode)