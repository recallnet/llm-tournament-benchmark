"""
Aggregate per-model conversation results into unified format.

Takes multiple per-model conversation JSON files and combines them
into the same format as the original execute_conversations.py output.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def aggregate_conversation_results(per_model_results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregate multiple per-model conversation results into unified format.

    Args:
        per_model_results: List of per-model conversation result dictionaries

    Returns:
        Unified conversation results matching original format
    """
    if not per_model_results:
        # Return empty but valid structure
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
                "evals_count": 0,
                "judges_count": 0,
            },
            "conversations": [],
            "intermediaries": [],
        }

    # Aggregate execution_info statistics with safe defaults
    total_conversations = sum(result["execution_info"].get("total_conversations", 0) for result in per_model_results)
    successful_conversations = sum(result["execution_info"].get("successful_conversations", 0) for result in per_model_results)
    failed_conversations = sum(result["execution_info"].get("failed_conversations", 0) for result in per_model_results)
    total_intermediaries = sum(result["execution_info"].get("total_intermediaries", 0) for result in per_model_results)
    successful_intermediaries = sum(
        result["execution_info"].get("successful_intermediaries", 0) for result in per_model_results
    )
    failed_intermediaries = sum(result["execution_info"].get("failed_intermediaries", 0) for result in per_model_results)

    # Use latest timestamp with safe default
    timestamps = [result["execution_info"].get("timestamp", datetime.now().isoformat()) for result in per_model_results]
    latest_timestamp = max(timestamps) if timestamps else datetime.now().isoformat()

    # Count unique models (should equal number of input results for per-model execution)
    all_model_ids = set()
    for result in per_model_results:
        for conversation in result.get("conversations", []):
            if "metadata" in conversation and "model_id" in conversation["metadata"]:
                all_model_ids.add(conversation["metadata"]["model_id"])

    models_count = len(all_model_ids)

    # Get eval and judge counts from first result (should be same across all)
    evals_count = per_model_results[0]["execution_info"].get("evals_count", 0) if per_model_results else 0
    judges_count = per_model_results[0]["execution_info"].get("judges_count", 0) if per_model_results else 0

    # Combine conversations and intermediaries
    all_conversations = []
    all_intermediaries = []

    for result in per_model_results:
        all_conversations.extend(result["conversations"])
        all_intermediaries.extend(result.get("intermediaries", []))

    return {
        "execution_info": {
            "total_conversations": total_conversations,
            "successful_conversations": successful_conversations,
            "failed_conversations": failed_conversations,
            "total_intermediaries": total_intermediaries,
            "successful_intermediaries": successful_intermediaries,
            "failed_intermediaries": failed_intermediaries,
            "timestamp": latest_timestamp,
            "models_count": models_count,
            "evals_count": evals_count,
            "judges_count": judges_count,
        },
        "conversations": all_conversations,
        "intermediaries": all_intermediaries,
    }


def load_conversation_files(file_paths: list[str]) -> list[dict[str, Any]]:
    """
    Load multiple conversation JSON files.

    Args:
        file_paths: List of paths to per-model conversation files

    Returns:
        List of loaded conversation dictionaries
    """
    results = []

    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            print(f"Warning: File not found: {file_path}")
            continue

        try:
            with open(path) as f:
                data = json.load(f)
            results.append(data)
        except json.JSONDecodeError as e:
            print(f"Error loading {file_path}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error loading {file_path}: {e}")
            continue

    return results


def main(input_files: list[str], output_file: str) -> None:
    """
    Main aggregation function for command-line usage.

    Args:
        input_files: List of per-model conversation file paths
        output_file: Path to write aggregated output
    """
    print(f"Aggregating {len(input_files)} conversation files...")

    # Load all per-model results
    per_model_results = load_conversation_files(input_files)

    if not per_model_results:
        print("Error: No valid conversation files found")
        sys.exit(1)

    print(f"Successfully loaded {len(per_model_results)} files")

    # Aggregate results
    aggregated = aggregate_conversation_results(per_model_results)

    # Write output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(aggregated, f, indent=2)

    print(f"Aggregated output written to: {output_file}")
    print(f"Total conversations: {aggregated['execution_info']['total_conversations']}")
    print(f"Total models: {aggregated['execution_info']['models_count']}")
    print(f"Total intermediaries: {aggregated['execution_info']['total_intermediaries']}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python aggregate_conversations.py <output_file> <input_file1> [input_file2] ...")
        print("Example: python aggregate_conversations.py data/conversations.json data/conversations_*.json")
        sys.exit(1)

    output_file = sys.argv[1]
    input_files = sys.argv[2:]

    main(input_files, output_file)
