#!/usr/bin/env python3
"""
Real concurrency violation detection tests.

This module implements actual process monitoring and concurrent execution testing
to detect per-model serialization violations, not just log parsing.
"""

import os
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


class RealConcurrencyTester:
    """
    Real concurrency tester that uses actual process monitoring and file system
    operations to detect concurrency violations.
    """

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.temp_dir = None
        self.execution_log = []
        self.lock_monitoring = {}

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix=f"real_concurrency_{self.test_name}_")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def setup_test_environment(self, num_models: int = 3):
        """Set up a test environment with models and skills for concurrent testing."""
        temp_path = Path(self.temp_dir)

        # Create model pool
        model_pool_file = temp_path / "model_pools" / "testonly.csv"
        model_pool_file.parent.mkdir(parents=True, exist_ok=True)

        models = ["id,author,slug,context_window,pricing,endpoint,max_tokens"]
        for i in range(num_models):
            model_id = f"test/concurrent-model-{i}"
            models.append(
                f"{model_id},TestCorp,model-{i},4096,input:0.0001|output:0.0001,mock,1000"
            )

        with open(model_pool_file, "w") as f:
            f.write("\\n".join(models))

        # Create skills with multiple evals per model (to force potential concurrency)
        skills_dir = temp_path / "skills" / "testonly"
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = skills_dir / "concurrent_test_skill"
        skill_dir.mkdir(exist_ok=True)

        # Multiple evals to increase concurrency pressure
        for eval_idx in range(3):
            eval_file = skill_dir / f"eval_{eval_idx}.json"
            eval_data = {
                "id": f"concurrent_test_eval_{eval_idx}",
                "task_description": f"Concurrent test eval {eval_idx}",
                "chain": [
                    {
                        "id": "main_prompt",
                        "prompt": f"Test prompt {eval_idx}: Say 'Hello from concurrent test {eval_idx}'",
                    }
                ],
                "_metadata": {
                    "skill": "concurrent_test_skill",
                    "eval": f"eval_{eval_idx}",
                },
            }

            import json

            with open(eval_file, "w") as f:
                json.dump(eval_data, f, indent=2)

        # Create judge pool
        judge_pool_file = temp_path / "judge_pools" / "testonly.csv"
        judge_pool_file.parent.mkdir(parents=True, exist_ok=True)

        judges = ["id,author,slug,context_window,pricing,endpoint,max_tokens"]
        judges.append(
            "test/concurrent-judge,TestCorp,concurrent-judge,4096,input:0.0001|output:0.0001,mock,1000"
        )

        with open(judge_pool_file, "w") as f:
            f.write("\\n".join(judges))

        # CRITICAL: Create the loaded JSON files that execute_conversations_standalone.py expects
        import json

        # loaded_models.json
        models_data = {
            "models": [
                {
                    "id": f"test/concurrent-model-{i}",
                    "author": "TestCorp",
                    "slug": f"model-{i}",
                    "context_window": 4096,
                    "pricing": {"input": 0.0001, "output": 0.0001},
                    "endpoint": "mock",
                    "max_tokens": 1000,
                }
                for i in range(num_models)
            ]
        }
        with open(temp_path / "loaded_models.json", "w") as f:
            json.dump(models_data, f, indent=2)

        # loaded_skills.json
        skills_data = {
            "evals": [
                {
                    "id": f"concurrent_test_eval_{i}",
                    "name": f"Concurrent Test Eval {i}",
                    "chain": [
                        {
                            "id": "main_prompt",
                            "prompt": f"Test prompt {i}: Say 'Hello from concurrent test {i}'",
                        }
                    ],
                    "_metadata": {"skill": "concurrent_test_skill"},
                }
                for i in range(3)
            ]
        }
        with open(temp_path / "loaded_skills.json", "w") as f:
            json.dump(skills_data, f, indent=2)

        # loaded_judges.json
        judges_data = {
            "judges": [
                {
                    "id": "test/concurrent-judge",
                    "author": "TestCorp",
                    "slug": "concurrent-judge",
                    "context_window": 4096,
                    "pricing": {"input": 0.0001, "output": 0.0001},
                    "endpoint": "mock",
                    "max_tokens": 1000,
                }
            ]
        }
        with open(temp_path / "loaded_judges.json", "w") as f:
            json.dump(judges_data, f, indent=2)

        return temp_path

    def monitor_lock_files(
        self, lock_dir: Path, duration: float = 10.0
    ) -> dict[str, list]:
        """
        Monitor lock files to detect concurrent access violations.

        Returns:
            Dictionary mapping model_id to list of (timestamp, pid, action) tuples
        """
        monitoring_data = {}
        start_time = time.time()

        def monitor():
            while time.time() - start_time < duration:
                if lock_dir.exists():
                    for lock_file in lock_dir.glob("*.lock"):
                        model_id = lock_file.stem

                        if model_id not in monitoring_data:
                            monitoring_data[model_id] = []

                        try:
                            if lock_file.exists():
                                with open(lock_file) as f:
                                    content = f.read()
                                    if "PID:" in content:
                                        pid = content.split("PID: ")[1].split("\\n")[0]
                                        monitoring_data[model_id].append(
                                            {
                                                "timestamp": time.time(),
                                                "pid": pid,
                                                "action": "lock_exists",
                                                "file": str(lock_file),
                                            }
                                        )
                        except (FileNotFoundError, IndexError):
                            # Lock file disappeared or malformed - that's fine
                            pass

                time.sleep(0.1)  # Check every 100ms

        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.daemon = True
        monitor_thread.start()

        return monitoring_data

    def run_concurrent_model_execution(
        self, model_ids: list[str], temp_path: Path
    ) -> list[dict]:
        """
        Run multiple model executions concurrently and capture results.

        Returns:
            List of execution results with timing and PID information
        """
        results = []

        # Create necessary input files
        conversations_dir = temp_path / "conversations"
        conversations_dir.mkdir(exist_ok=True)

        lock_dir = temp_path / ".locks"

        # Start lock monitoring
        lock_monitoring = self.monitor_lock_files(lock_dir, duration=30.0)

        def execute_model(model_id: str) -> dict:
            """Execute conversations for a single model."""
            start_time = time.time()
            pid = os.getpid()

            # Simulate the conversation execution script call
            script_path = (
                Path(__file__).parent.parent
                / "scripts"
                / "execute_conversations_standalone.py"
            )

            cmd = [
                "python",
                str(script_path),
                str(temp_path / "loaded_models.json"),
                str(temp_path / "loaded_skills.json"),
                str(temp_path / "loaded_judges.json"),
                model_id,
                str(conversations_dir),
                str(temp_path / "intermediaries"),
            ]

            # Set environment for mock testing
            env = os.environ.copy()
            env["AFBENCH_TESTING"] = "true"

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30, env=env
                )
                end_time = time.time()

                # Extract lock acquisition info from stdout
                lock_acquired = False
                had_to_wait = False
                for line in result.stdout.split("\n"):
                    if "EXCLUSIVE lock acquired" in line:
                        lock_acquired = True
                    elif "Lock held by another process" in line or "waiting..." in line:
                        had_to_wait = True

                return {
                    "model_id": model_id,
                    "pid": pid,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": end_time - start_time,
                    "lock_acquired": lock_acquired,
                    "had_to_wait": had_to_wait,
                    "return_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "success": result.returncode == 0,
                }
            except subprocess.TimeoutExpired:
                return {
                    "model_id": model_id,
                    "pid": pid,
                    "start_time": start_time,
                    "end_time": time.time(),
                    "duration": 30.0,
                    "lock_acquired": False,
                    "had_to_wait": False,
                    "return_code": -1,
                    "stdout": "",
                    "stderr": "Timeout",
                    "success": False,
                }

        # Run concurrent executions
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Submit multiple jobs for the same model to test serialization
            futures = []

            # Test 1: Multiple executions of the same model (should be serialized)
            same_model = model_ids[0] if model_ids else "test/concurrent-model-0"
            for _i in range(3):
                future = executor.submit(execute_model, same_model)
                futures.append(future)

            # Test 2: Different models (should run in parallel)
            for model_id in model_ids[1:]:
                future = executor.submit(execute_model, model_id)
                futures.append(future)

            # Collect results
            for future in as_completed(futures, timeout=60):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(
                        {"model_id": "unknown", "error": str(e), "success": False}
                    )

        # Store lock monitoring data
        self.lock_monitoring = lock_monitoring

        return results

    def analyze_concurrency_violations(self, results: list[dict]) -> dict:
        """
        Analyze execution results to detect concurrency violations.

        Returns:
            Analysis report with detected violations
        """
        analysis = {
            "total_executions": len(results),
            "successful_executions": sum(1 for r in results if r.get("success", False)),
            "same_model_executions": {},
            "concurrent_violations": [],
            "timing_analysis": {},
            "lock_analysis": {},
        }

        # Group executions by model
        by_model = {}
        for result in results:
            model_id = result.get("model_id", "unknown")
            if model_id not in by_model:
                by_model[model_id] = []
            by_model[model_id].append(result)

        # Analyze same-model executions for serialization violations
        for model_id, executions in by_model.items():
            if len(executions) > 1:
                analysis["same_model_executions"][model_id] = len(executions)

                # Check for violations using logical analysis instead of timing
                lock_acquired_executions = [
                    e for e in executions if e.get("lock_acquired")
                ]
                waiting_executions = [e for e in executions if e.get("had_to_wait")]

                # GOOD: If we have multiple executions and some had to wait, serialization is working
                if len(lock_acquired_executions) > 1 and len(waiting_executions) > 0:
                    analysis["timing_analysis"][model_id] = {
                        "total_executions": len(executions),
                        "lock_acquired": len(lock_acquired_executions),
                        "had_to_wait": len(waiting_executions),
                        "serialization_working": True,
                    }

                # BAD: If multiple processes got locks immediately (no waiting), that's a violation
                immediate_acquisitions = [
                    e
                    for e in executions
                    if e.get("lock_acquired") and not e.get("had_to_wait")
                ]
                if len(immediate_acquisitions) > 1:
                    analysis["concurrent_violations"].append(
                        {
                            "type": "multiple_immediate_lock_acquisitions",
                            "model_id": model_id,
                            "count": len(immediate_acquisitions),
                            "description": f"{len(immediate_acquisitions)} processes acquired locks without waiting",
                        }
                    )

                # SUSPICIOUS: Multiple successful executions might indicate caching vs real concurrency control
                successful_executions = [e for e in executions if e.get("success")]
                if len(successful_executions) > 1:
                    # This is actually OK if they're serialized - the lock ensures they run one after another
                    analysis["timing_analysis"][f"{model_id}_success_pattern"] = {
                        "multiple_successes": len(successful_executions),
                        "note": "Multiple successes are OK if serialized (which waiting indicates)",
                    }

        # Analyze lock monitoring data
        for model_id, lock_events in self.lock_monitoring.items():
            if len(lock_events) > 1:
                # Check for multiple PIDs holding locks simultaneously
                pids_by_time = {}
                for event in lock_events:
                    timestamp = event["timestamp"]
                    pid = event["pid"]

                    time_bucket = int(timestamp * 10) / 10  # 100ms buckets
                    if time_bucket not in pids_by_time:
                        pids_by_time[time_bucket] = set()
                    pids_by_time[time_bucket].add(pid)

                # Check for multiple PIDs in same time bucket
                for time_bucket, pids in pids_by_time.items():
                    if len(pids) > 1:
                        analysis["concurrent_violations"].append(
                            {
                                "type": "multiple_lock_holders",
                                "model_id": model_id,
                                "time_bucket": time_bucket,
                                "pids": list(pids),
                            }
                        )

        return analysis


def test_real_per_model_serialization():
    """Test actual per-model serialization using real process execution."""
    print("=== Real Per-Model Serialization Test ===")

    with RealConcurrencyTester("real_serialization") as tester:
        # Set up test environment
        temp_path = tester.setup_test_environment(num_models=3)

        # Model IDs for testing
        model_ids = [
            "test/concurrent-model-0",
            "test/concurrent-model-1",
            "test/concurrent-model-2",
        ]

        print(f"Running concurrent executions for models: {model_ids}")
        print(f"Test environment: {temp_path}")

        # Run concurrent model executions
        results = tester.run_concurrent_model_execution(model_ids, temp_path)

        # Analyze for violations
        analysis = tester.analyze_concurrency_violations(results)

        print("\\nExecution Results:")
        print(f"  Total executions: {analysis['total_executions']}")
        print(f"  Successful executions: {analysis['successful_executions']}")
        print(f"  Same-model executions: {analysis['same_model_executions']}")

        # Check for violations
        violations = analysis["concurrent_violations"]
        if violations:
            print(f"\\n❌ CONCURRENCY VIOLATIONS DETECTED ({len(violations)}):")
            for violation in violations:
                print(f"  - {violation['type']}: {violation}")
            return False
        else:
            print("\\n✅ No concurrency violations detected")

        # Verify that lock files were created
        lock_dir = temp_path / ".locks"
        if lock_dir.exists() and list(lock_dir.glob("*.lock")):
            print("✅ Lock files were created (serialization mechanism active)")
        else:
            print("⚠️  No lock files found (serialization mechanism may not be working)")

        return True


def test_file_locking_mechanism():
    """Test the file locking mechanism directly."""
    print("\\n=== File Locking Mechanism Test ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        lock_dir = temp_path / ".locks"
        lock_dir.mkdir(exist_ok=True)

        model_id = "test/file-lock-model"
        sanitized = model_id.replace("/", "_").replace(":", "_")
        lock_file_path = lock_dir / f"{sanitized}.lock"

        def acquire_lock(process_id: int, hold_time: float = 2.0) -> dict:
            """Simulate acquiring a lock from a separate process."""
            import fcntl

            result = {
                "process_id": process_id,
                "acquired": False,
                "held_duration": 0,
                "error": None,
            }

            try:
                with open(lock_file_path, "w") as lock_file:
                    lock_file.write(f"Process: {process_id}\\nTime: {time.time()}\\n")
                    lock_file.flush()

                    # Try to acquire lock
                    fcntl.flock(
                        lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                    )  # Non-blocking
                    result["acquired"] = True

                    # Hold lock for specified time
                    time.sleep(hold_time)
                    result["held_duration"] = hold_time

            except BlockingIOError:
                result["error"] = "Lock already held by another process"
            except Exception as e:
                result["error"] = str(e)

            return result

        # Test concurrent lock acquisition
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []

            # Submit 3 concurrent lock attempts
            for i in range(3):
                future = executor.submit(acquire_lock, i, 1.0)
                futures.append(future)

            results = []
            for future in as_completed(futures, timeout=10):
                results.append(future.result())

        # Analyze results
        acquired_count = sum(1 for r in results if r["acquired"])
        blocked_count = sum(
            1 for r in results if "already held" in str(r.get("error", ""))
        )

        print("Lock acquisition results:")
        print(f"  Successfully acquired: {acquired_count}")
        print(f"  Blocked by lock: {blocked_count}")
        print(f"  Other errors: {len(results) - acquired_count - blocked_count}")

        # Should have exactly 1 successful acquisition and 2 blocked
        if acquired_count == 1 and blocked_count == 2:
            print("✅ File locking mechanism working correctly")
            return True
        else:
            print("❌ File locking mechanism not working as expected")
            for result in results:
                print(f"  Process {result['process_id']}: {result}")
            return False


def main():
    """Run all real concurrency tests."""
    print("AFBench Real Concurrency Violation Detection Tests")
    print("=" * 55)

    tests = [
        ("File Locking Mechanism", test_file_locking_mechanism),
        ("Real Per-Model Serialization", test_real_per_model_serialization),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\\n🧪 Running: {test_name}")
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")

    print(f"\\n{'='*55}")
    print(f"Real Concurrency Tests: {passed}/{total} passed")

    if passed == total:
        print("🎉 All real concurrency tests passed!")
        return 0
    else:
        print("⚠️  Some real concurrency tests failed - serialization may be broken")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
