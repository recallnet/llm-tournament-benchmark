#!/usr/bin/env python3
"""
Test to identify the EXACT location where tournament execution hangs.
This will instrument the tournament script to find the hanging line.
"""

import signal
import sys
import time
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError(f"Tournament execution timed out at line: {frame.f_lineno} in {frame.f_code.co_filename}")


def test_tournament_execution_with_instrumentation():
    """Test tournament execution with line-by-line instrumentation."""
    print("🧪 Testing tournament execution with instrumentation...")

    # Set 30-second timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)

    try:
        from run_tournaments import main

        print("📋 Calling tournament main() function...")
        start_time = time.time()

        # This should either complete or timeout with exact line info
        main()

        elapsed = time.time() - start_time
        signal.alarm(0)  # Cancel timeout

        print(f"✅ Tournament completed in {elapsed:.2f}s")
        return True

    except TimeoutError as e:
        print(f"❌ TIMEOUT: {e}")
        print("🎯 EXACT HANG LOCATION IDENTIFIED")
        return False

    except Exception as e:
        signal.alarm(0)
        print(f"❌ Tournament failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🧪 Finding exact tournament hang location...")

    success = test_tournament_execution_with_instrumentation()

    if not success:
        print("\n🎯 HANG LOCATION FOUND - check the line number above")
        print("💡 Now we can fix the exact issue instead of guessing")
        sys.exit(1)
    else:
        print("\n✅ Tournament execution completed successfully")
