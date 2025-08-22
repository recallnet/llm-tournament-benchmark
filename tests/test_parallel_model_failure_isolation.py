#!/usr/bin/env python3
"""
Test suite for parallel model job failure isolation.

This tests that when multiple models run in parallel and one fails,
the system handles the failure gracefully without cascading errors
or infinite retry loops.

Key scenarios:
1. One model fails after retries - others should complete or halt cleanly
2. No cascading error loops when one model has an invalid ID
3. Proper error propagation without affecting running jobs
4. Clean shutdown of parallel execution on critical failures
"""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch


class ParallelModelFailureTestFramework:
    """Framework for testing parallel model failure isolation."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.temp_dir = None
        self.afbench_root = None
        
    def __enter__(self):
        # Create isolated test environment
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"parallel_failure_test_{self.test_name}_"))
        self.afbench_root = Path(__file__).parent.parent
        
        # Copy minimal AFBench structure
        self._setup_minimal_test_workspace()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
    def _setup_minimal_test_workspace(self):
        """Set up minimal isolated test workspace."""
        temp_path = self.temp_dir
        
        # Copy only essential files for parallel execution testing
        essential_files = [
            "Snakefile",
            "scripts/execute_conversations_standalone.py", 
            "scripts/execute_conversations_single_model.py",
            "scripts/load_models.py",
            "scripts/load_judges.py", 
            "scripts/load_skills.py"
        ]
        
        for src_file in essential_files:
            src_path = self.afbench_root / src_file
            dst_path = temp_path / src_file
            
            if src_path.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                if src_path.is_file():
                    shutil.copy2(src_path, dst_path)
                    
        # Create test configuration
        config_dir = temp_path / "config"
        config_dir.mkdir(exist_ok=True)
        
        # Minimal config for failure testing
        test_config = {
            "data_dir": "data/failure_test",
            "model_pool": {"default_pool": "failure_test", "pools_dir": "model_pools"},
            "judge_pool": {"default_pool": "failure_test", "pools_dir": "judge_pools"},
            "skills": {"skills_dir": "skills", "selected_skills": []}
        }
        
        with open(config_dir / "config.yaml", "w") as f:
            import yaml
            yaml.dump(test_config, f)
            
        # Create profile for failure testing
        profile_dir = temp_path / "profiles" / "failure_test"
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        profile_config = {
            "cores": 4,
            "keep-going": False,  # Important: should halt on failure
            "configfiles": ["config/config.yaml"]
        }
        
        with open(profile_dir / "config.yaml", "w") as f:
            yaml.dump(profile_config, f)
            
    def create_test_model_pools(self, valid_models: list, invalid_models: list):
        """Create model pools with mix of valid and invalid models."""
        temp_path = self.temp_dir
        
        # Create model pool directory
        model_pools_dir = temp_path / "model_pools"
        model_pools_dir.mkdir(exist_ok=True)
        
        # Create test model pool with valid and invalid models
        model_lines = ["id,author,slug,context_window,pricing,endpoint,max_tokens"]
        
        # Add valid models
        for model_id in valid_models:
            safe_id = model_id.replace("/", "_").replace(":", "_")
            model_lines.append(f"{model_id},test,{safe_id},32768,0.0,openrouter,4000")
            
        # Add invalid models (these should cause 400 errors)
        for model_id in invalid_models:
            safe_id = model_id.replace("/", "_").replace(":", "_") 
            model_lines.append(f"{model_id},test,{safe_id},32768,0.0,openrouter,4000")
            
        with open(model_pools_dir / "failure_test.csv", "w") as f:
            f.write("\n".join(model_lines))
            
        # Create minimal judge pool
        judge_pools_dir = temp_path / "judge_pools"
        judge_pools_dir.mkdir(exist_ok=True)
        
        judge_lines = ["id,author,slug,context_window,pricing,endpoint,max_tokens"]
        judge_lines.append("test/mock-judge,test,mock_judge,32768,0.0,openrouter,4000")
        
        with open(judge_pools_dir / "failure_test.csv", "w") as f:
            f.write("\n".join(judge_lines))
            
    def create_minimal_test_skill(self):
        """Create minimal test skill for failure testing."""
        temp_path = self.temp_dir
        skills_dir = temp_path / "skills" / "failure_test_skill"
        skills_dir.mkdir(parents=True, exist_ok=True)
        
        # Simple test eval that will trigger API calls
        test_eval = {
            "id": "failure_test_eval",
            "name": "Failure Test Evaluation", 
            "chain": [{
                "id": "test_step",
                "prompt": "Say 'hello world' in response to this test."
            }],
            "_metadata": {"skill": "failure_test_skill"}
        }
        
        with open(skills_dir / "failure_test_eval.json", "w") as f:
            json.dump(test_eval, f, indent=2)
            
    def run_parallel_model_test_with_failure_injection(self, timeout: int = 60) -> dict:
        """Run parallel model test with controlled failure injection."""
        temp_path = self.temp_dir
        original_cwd = os.getcwd()
        
        try:
            os.chdir(temp_path)
            
            # Set test environment
            env = os.environ.copy()
            env["AFBENCH_TESTING"] = "true"
            
            # Run snakemake with parallel execution
            cmd = [
                "snakemake", 
                "--profile", "profiles/failure_test",
                "-j4",  # 4 parallel jobs
                "--verbose"
            ]
            
            start_time = time.time()
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                env=env,
                timeout=timeout
            )
            end_time = time.time()
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr, 
                "duration": end_time - start_time,
                "timed_out": False
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Test timed out after {timeout}s",
                "duration": timeout,
                "timed_out": True
            }
        finally:
            os.chdir(original_cwd)
            
    def analyze_failure_behavior(self, result: dict) -> dict:
        """Analyze the failure behavior from test results."""
        analysis = {
            "cascading_errors": False,
            "infinite_retry_loop": False,
            "clean_failure_handling": False,
            "parallel_jobs_halted": False,
            "error_patterns": [],
            "retry_attempts": 0
        }
        
        full_output = result["stdout"] + "\n" + result["stderr"]
        
        # Check for cascading error patterns
        error_400_count = full_output.count("400 Client Error")
        if error_400_count > 10:  # Arbitrary threshold for "too many"
            analysis["cascading_errors"] = True
            
        # Check for retry loop indicators
        retry_count = full_output.count("Retry attempt")
        analysis["retry_attempts"] = retry_count
        if retry_count > 20:  # Arbitrary threshold
            analysis["infinite_retry_loop"] = True
            
        # Check if execution timed out (indicates possible infinite loop)
        if result["timed_out"]:
            analysis["infinite_retry_loop"] = True
            
        # Check for clean shutdown indicators
        if not result["timed_out"] and result["returncode"] != 0:
            analysis["clean_failure_handling"] = True
            
        # Look for parallel job coordination
        if "Shutting down" in full_output or "Exiting because a job execution failed" in full_output:
            analysis["parallel_jobs_halted"] = True
            
        # Collect unique error patterns
        import re
        error_patterns = re.findall(r"❌.*?(?=\n)", full_output)
        analysis["error_patterns"] = list(set(error_patterns))
        
        return analysis


def test_parallel_model_failure_isolation():
    """
    Test that parallel model execution handles individual model failures gracefully.
    
    Scenario: 4 models run in parallel, 1 has invalid ID causing 400 errors.
    Expected: System should fail cleanly without cascading errors or infinite loops.
    """
    print("=== Test: Parallel Model Failure Isolation ===")
    
    with ParallelModelFailureTestFramework("parallel_failure_isolation") as framework:
        print(f"Test workspace: {framework.temp_dir}")
        
        # Create model pool with 3 valid models + 1 invalid 
        valid_models = ["test/valid-model-1", "test/valid-model-2", "test/valid-model-3"]
        invalid_models = ["anthropic/claude-opus-4.0"]  # This should cause 400 error
        
        framework.create_test_model_pools(valid_models, invalid_models)
        framework.create_minimal_test_skill()
        
        print("--- Running parallel execution with failure injection ---")
        result = framework.run_parallel_model_test_with_failure_injection(timeout=30)
        
        print(f"Execution completed: success={result['success']}, duration={result['duration']:.2f}s")
        
        # Analyze failure behavior
        analysis = framework.analyze_failure_behavior(result)
        
        print("\n--- Failure Analysis ---")
        print(f"Cascading errors detected: {analysis['cascading_errors']}")
        print(f"Infinite retry loop: {analysis['infinite_retry_loop']}")
        print(f"Clean failure handling: {analysis['clean_failure_handling']}")
        print(f"Parallel jobs halted properly: {analysis['parallel_jobs_halted']}")
        print(f"Total retry attempts: {analysis['retry_attempts']}")
        print(f"Unique error patterns: {len(analysis['error_patterns'])}")
        
        # Test assertions
        assert not analysis["infinite_retry_loop"], "System should not get stuck in infinite retry loops"
        assert not analysis["cascading_errors"], "Should not cascade the same error across all models repeatedly"
        
        if not result["success"]:
            assert analysis["clean_failure_handling"], "Failed execution should fail cleanly"
            assert analysis["parallel_jobs_halted"], "Parallel jobs should be shut down properly on failure"
            
        print("✅ Parallel model failure isolation test passed")
        

def test_retry_limit_enforcement():
    """
    Test that retry limits are enforced to prevent infinite loops.
    
    Scenario: Model with permanent failure (invalid ID) should retry limited times then stop.
    Expected: Fixed number of retries, then clean failure.
    """
    print("\n=== Test: Retry Limit Enforcement ===")
    
    with ParallelModelFailureTestFramework("retry_limit_enforcement") as framework:
        print(f"Test workspace: {framework.temp_dir}")
        
        # Use only invalid models to trigger consistent failures
        valid_models = []
        invalid_models = ["fake/nonexistent-model", "invalid/model-id"]
        
        framework.create_test_model_pools(valid_models, invalid_models)  
        framework.create_minimal_test_skill()
        
        print("--- Running with models that will always fail ---")
        result = framework.run_parallel_model_test_with_failure_injection(timeout=20)
        
        analysis = framework.analyze_failure_behavior(result)
        
        print(f"Total retry attempts across all models: {analysis['retry_attempts']}")
        print(f"System timed out: {result['timed_out']}")
        
        # Check that system handles failures without infinite loops
        # (Retry attempts might be 0 in test environment, but that's ok)
        assert analysis["retry_attempts"] < 50, "Should not have excessive retry attempts" 
        assert not result["timed_out"], "Should not timeout (infinite loop)"
        assert not analysis["cascading_errors"], "Should not have cascading errors"
        
        print("✅ Retry limit enforcement test passed")


def main():
    """Run all parallel model failure tests."""
    print("AFBench Parallel Model Failure Isolation Tests")
    print("=" * 60)
    
    tests = [
        ("Parallel Model Failure Isolation", test_parallel_model_failure_isolation),
        ("Retry Limit Enforcement", test_retry_limit_enforcement),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            test_func()
            passed += 1
            print(f"✅ {test_name}: PASSED")
        except Exception as e:
            print(f"❌ {test_name}: FAILED - {e}")
            import traceback
            traceback.print_exc()
            
    print(f"\n{'='*60}")
    print(f"Parallel Model Failure Tests: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All parallel model failure tests passed!")
        return 0
    else:
        print("⚠️  Some parallel model failure tests failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())