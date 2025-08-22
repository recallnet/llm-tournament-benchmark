#!/usr/bin/env python3
"""
Execute conversations for a single model across all evals.

This script is designed for Snakemake parallelization - it processes
only one model instead of all models, allowing parallel execution.
"""

import json
import sys
import time
from typing import Any

# Import the original ConversationExecutor and utility functions
try:
    from scripts.execute_conversations import ConversationExecutor, cleanup_stale_cache
except ModuleNotFoundError:
    # When running standalone, scripts prefix may not work
    from execute_conversations import ConversationExecutor, cleanup_stale_cache


def execute_conversations_for_model_cache_only(
    models_file: str,
    skills_file: str,
    judges_file: str,
    target_model_id: str,
    cache_dir: str = None,
    intermediary_cache_dir: str = None,
    max_retries: int = 3,
) -> bool:
    """
    Execute conversations for a single model and cache them (no JSON output).
    Includes retry logic with exponential backoff for transient failures.

    Args:
        models_file: Path to loaded models JSON
        skills_file: Path to loaded skills JSON
        judges_file: Path to loaded judges JSON
        target_model_id: ID of the specific model to process
        cache_dir: Custom cache directory (optional)
        intermediary_cache_dir: Custom intermediary cache directory (optional)
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        bool: True if successful, False otherwise

    Raises:
        Exception: After all retries are exhausted, raises the last exception with detailed context
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                # Exponential backoff: 2^attempt seconds (2s, 4s, 8s)
                backoff_time = 2**attempt
                print(
                    f"🔄 Retry attempt {attempt + 1}/{max_retries} for {target_model_id} (waiting {backoff_time}s)"
                )
                time.sleep(backoff_time)

            result = execute_conversations_for_model(
                models_file,
                skills_file,
                judges_file,
                target_model_id,
                cache_dir,
                intermediary_cache_dir,
            )

            # Check if execution was successful based on whether we had any successful conversations
            # and no fatal failures (some failures are expected for problematic evals)
            exec_info = result["execution_info"]
            total = exec_info["total_conversations"]
            successful = exec_info["successful_conversations"]
            failed = exec_info["failed_conversations"]

            # Consider successful ONLY if we had at least some successful conversations
            # If ALL conversations failed, that's a critical error that should halt the pipeline
            is_successful = total > 0 and successful > 0

            # print(f"🔍 Success check: total={total}, successful={successful}, failed={failed}, is_successful={is_successful}")  # Debug output

            if is_successful:
                if attempt > 0:
                    print(
                        f"✅ Successfully completed {target_model_id} after {attempt + 1} attempts"
                    )
                return True
            else:
                error_msg = f"Model {target_model_id} failed: {successful}/{total} conversations successful, {failed} failed"
                last_exception = RuntimeError(error_msg)
                if attempt < max_retries - 1:
                    print(f"⚠️  {error_msg} - will retry")

        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                print(
                    f"❌ Attempt {attempt + 1} failed for {target_model_id}: {e} - will retry"
                )
            else:
                print(f"❌ Final attempt failed for {target_model_id}: {e}")

    # All retries exhausted - raise detailed exception
    error_context = (
        f"Model '{target_model_id}' failed after {max_retries} attempts. "
        f"This indicates a persistent issue (API authentication, rate limiting, or model availability). "
        f"Last error: {last_exception}"
    )
    raise RuntimeError(error_context) from last_exception


def execute_conversations_for_model(
    models_file: str,
    skills_file: str,
    judges_file: str,
    target_model_id: str,
    cache_dir: str = None,
    intermediary_cache_dir: str = None,
) -> dict[str, Any]:
    """
    Execute conversations for a single model across all evals.

    Args:
        models_file: Path to loaded models JSON
        skills_file: Path to loaded skills JSON
        judges_file: Path to loaded judges JSON
        target_model_id: ID of the specific model to process

    Returns:
        Dictionary in same format as original execute_conversations.py
    """
    # Load input data
    with open(models_file) as f:
        models_data = json.load(f)

    with open(skills_file) as f:
        skills_data = json.load(f)

    with open(judges_file) as f:
        judges_data = json.load(f)

    models = models_data["models"]
    evals = skills_data["evals"]
    judges = judges_data["judges"]

    # Filter to target model only
    target_model = None
    for model in models:
        if model["id"] == target_model_id:
            target_model = model
            break

    if target_model is None:
        # Return empty but valid structure for non-existent models
        return create_empty_result(target_model_id, len(evals), len(judges))

    print(f"🎯 Executing conversations for model: {target_model_id}")
    print(f"📝 Processing {len(evals)} evals")
    print(f"🧑‍⚖️ Using {len(judges)} judge models for intermediaries")

    # Initialize executor with custom cache directories if provided
    from pathlib import Path

    cache_dir_path = Path(cache_dir) if cache_dir else None
    intermediary_cache_dir_path = (
        Path(intermediary_cache_dir) if intermediary_cache_dir else None
    )
    executor = ConversationExecutor(
        cache_dir=cache_dir_path, intermediary_cache_dir=intermediary_cache_dir_path
    )

    # Clean stale cache entries
    cleanup_stale_cache(
        models, judges, executor.cache_dir, executor.intermediary_cache_dir
    )

    # Execute conversations for this model only
    results = []
    intermediary_results = []
    total_conversations = len(evals)
    completed = 0
    successful_conversations = 0
    failed_conversations = 0
    successful_intermediaries = 0
    failed_intermediaries = 0
    total_intermediaries = 0

    for eval_data in evals:
        skill_id = eval_data["_metadata"]["skill"]
        eval_id = eval_data["id"]
        has_intermediaries = (
            "intermediaries" in eval_data and eval_data["intermediaries"]
        )

        completed += 1
        print(
            f"\n[{completed}/{total_conversations}] Processing {skill_id}/{eval_id} x {target_model['id']}"
        )

        try:
            # Execute main conversation
            conversation_result = executor.execute_conversation(
                target_model, skill_id, eval_data
            )
            results.append(conversation_result)

            # Check if conversation actually succeeded
            if (
                conversation_result.get("execution_info", {}).get("status")
                == "completed"
            ):
                successful_conversations += 1
            else:
                failed_conversations += 1
                print(
                    f"   ❌ Conversation marked as failed: {conversation_result.get('metadata', {}).get('error', 'Unknown error')}"
                )

            # Execute intermediaries if they exist
            if has_intermediaries and judges:
                intermediary_data_list = eval_data["intermediaries"]
                total_intermediaries += len(intermediary_data_list)

                for intermediary_data in intermediary_data_list:
                    try:
                        intermediary_result = executor.execute_intermediary(
                            intermediary_data,
                            conversation_result,
                            judges[0],
                            skill_id,
                            eval_id,
                        )
                        intermediary_results.append(intermediary_result)
                        successful_intermediaries += 1

                    except Exception as e:
                        print(f"   ❌ Intermediary failed: {e}")
                        failed_intermediaries += 1

        except Exception as e:
            print(f"   ❌ Conversation failed: {e}")
            failed_conversations += 1

    # Create result in same format as original script
    result = {
        "execution_info": {
            "total_conversations": total_conversations,
            "successful_conversations": successful_conversations,
            "failed_conversations": failed_conversations,
            "total_intermediaries": total_intermediaries,
            "successful_intermediaries": successful_intermediaries,
            "failed_intermediaries": failed_intermediaries,
            "timestamp": (
                conversation_result.get("metadata", {}).get("timestamp", "")
                if results
                else ""
            ),
            "models_count": 1,  # Only one model processed
            "evals_count": len(evals),
            "judges_count": len(judges),
        },
        "conversations": results,
        "intermediaries": intermediary_results,
    }

    return result


def create_empty_result(
    model_id: str, evals_count: int, judges_count: int
) -> dict[str, Any]:
    """Create empty but valid result structure for missing models."""
    from datetime import datetime

    return {
        "execution_info": {
            "total_conversations": 0,
            "successful_conversations": 0,
            "failed_conversations": 0,
            "total_intermediaries": 0,
            "successful_intermediaries": 0,
            "failed_intermediaries": 0,
            "timestamp": datetime.now().isoformat(),
            "models_count": 0,
            "evals_count": evals_count,
            "judges_count": judges_count,
        },
        "conversations": [],
        "intermediaries": [],
    }


def main():
    """Main function for command-line usage."""
    if len(sys.argv) != 5:
        print(
            "Usage: python execute_conversations_single_model.py <models_file> <skills_file> <judges_file> <target_model_id>"
        )
        print(
            "Example: python execute_conversations_single_model.py data/loaded_models.json data/loaded_skills.json data/loaded_judges.json 'openai/gpt-4'"
        )
        sys.exit(1)

    models_file, skills_file, judges_file, target_model_id = sys.argv[1:]

    print("🚀 Starting single-model conversation execution")
    print(f"🎯 Target model: {target_model_id}")

    try:
        result = execute_conversations_for_model(
            models_file, skills_file, judges_file, target_model_id
        )

        # Output result as JSON to stdout for Snakemake capture
        # or write to a file based on usage pattern
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
