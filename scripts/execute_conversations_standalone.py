#!/usr/bin/env python3
"""
Standalone wrapper for executing conversations for a single model.

This is a command-line wrapper around execute_conversations_single_model functionality.
Implements per-model file locking to ensure serialization.
"""

import os
import sys
import time
from pathlib import Path


def main():
    if len(sys.argv) != 7:
        print(
            "Usage: execute_conversations_standalone.py <models_file> <skills_file> <judges_file> <model_id> <conversations_dir> <intermediaries_dir>"
        )
        sys.exit(1)

    models_file = sys.argv[1]
    skills_file = sys.argv[2]
    judges_file = sys.argv[3]
    model_id = sys.argv[4]
    conversations_dir = sys.argv[5]
    intermediaries_dir = sys.argv[6]

    # Import the function from the existing module
    sys.path.insert(0, str(Path(__file__).parent))
    from execute_conversations_single_model import (
        execute_conversations_for_model_cache_only,
    )

    # CRITICAL: Implement per-model file locking for serialization
    # Lock must be acquired BEFORE any retry logic to prevent concurrent same-model execution
    lock_dir = Path(conversations_dir).parent / ".locks"
    lock_dir.mkdir(exist_ok=True)

    # Sanitize model_id for filename
    sanitized_model_id = model_id.replace("/", "_").replace(":", "_")
    lock_file_path = lock_dir / f"{sanitized_model_id}.lock"

    def execute_with_lock():
        """Execute conversations while holding exclusive model lock using robust file locking."""
        print(
            f"🔒 Attempting to acquire exclusive lock for model {model_id} (PID: {os.getpid()})..."
        )

        # Use a more robust locking mechanism with retry and better error handling
        max_lock_attempts = 30  # 30 seconds timeout
        lock_attempt = 0

        while lock_attempt < max_lock_attempts:
            try:
                # Try to create lock file with exclusive creation (fails if exists)
                lock_fd = os.open(
                    lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
                )

                try:
                    # Write process info
                    lock_info = f"PID: {os.getpid()}\nModel: {model_id}\nStarted: {time.time()}\nAttempt: {lock_attempt}\n"
                    os.write(lock_fd, lock_info.encode())
                    os.fsync(lock_fd)  # Force write to disk

                    print(
                        f"✅ EXCLUSIVE lock acquired for model {model_id} (PID: {os.getpid()}, attempt {lock_attempt})"
                    )

                    # Execute conversations while holding the lock
                    try:
                        success = execute_conversations_for_model_cache_only(
                            models_file,
                            skills_file,
                            judges_file,
                            model_id,
                            conversations_dir,
                            intermediaries_dir,
                        )
                        return success
                    finally:
                        # Always cleanup lock file
                        print(
                            f"🔓 Releasing lock for model {model_id} (PID: {os.getpid()})"
                        )

                finally:
                    # Close file descriptor and remove lock file
                    os.close(lock_fd)
                    try:
                        os.remove(lock_file_path)
                    except FileNotFoundError:
                        pass  # Lock file already removed

                break  # Successfully acquired and released lock

            except FileExistsError:
                # Lock file already exists - another process has the lock
                lock_attempt += 1
                if lock_attempt == 1:
                    print(
                        f"⏳ Lock held by another process for model {model_id}, waiting..."
                    )

                if lock_attempt >= max_lock_attempts:
                    raise TimeoutError(
                        f"Failed to acquire lock for model {model_id} after {max_lock_attempts} seconds"
                    )

                time.sleep(1)  # Wait 1 second before retrying

            except Exception as e:
                print(f"💥 Error acquiring lock for {model_id}: {e}")
                raise

    try:
        # Execute with proper locking
        success = execute_with_lock()

        if success:
            print(f"✅ Model {model_id} conversations completed successfully")
            sys.exit(0)
        else:
            print(f"❌ Model {model_id} conversations failed")
            sys.exit(1)

    except Exception as e:
        print(f"💥 Fatal error executing conversations for {model_id}: {e}")
        import traceback

        print("Traceback:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
