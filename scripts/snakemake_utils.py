"""
Utility functions for Snakemake workflow parallelization.

Provides model ID extraction, sanitization, and other utilities
needed for per-model parallel execution.
"""

import json
import re
from pathlib import Path


def get_model_ids(models_file: str) -> list[str]:
    """
    Extract model IDs from loaded models JSON file for Snakemake wildcards.

    Args:
        models_file: Path to loaded_models.json file

    Returns:
        List of model IDs that can be used in Snakemake expand() calls
    """
    models_path = Path(models_file)

    if not models_path.exists():
        raise FileNotFoundError(f"Models file not found: {models_file}")

    with open(models_path) as f:
        models_data = json.load(f)

    if "models" not in models_data:
        raise ValueError("Invalid models file format: missing 'models' key")

    model_ids = []
    for model in models_data["models"]:
        if "id" not in model:
            raise ValueError(f"Model missing 'id' field: {model}")
        model_ids.append(model["id"])

    return model_ids


def sanitize_model_id_for_filename(model_id: str) -> str:
    """
    Sanitize model ID for use in filenames.

    Converts problematic characters like '/' and ':' to underscores
    to create valid filenames for per-model conversation files.

    Args:
        model_id: Original model ID (e.g., "openai/gpt-4")

    Returns:
        Sanitized ID safe for filenames (e.g., "openai_gpt-4")
    """
    # Replace problematic characters with underscores
    sanitized = re.sub(r'[/\\:*?"<>|]', "_", model_id)

    # Replace dots with underscores to avoid confusion with file extensions
    sanitized = sanitized.replace(".", "_")

    # Remove any double underscores that might have been created
    sanitized = re.sub(r"_+", "_", sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")

    return sanitized


def reverse_sanitize_model_id(sanitized_id: str) -> str:
    """
    Attempt to reverse model ID sanitization.

    Note: This is a best-effort reversal and may not be perfect
    for all cases. The original mapping should be maintained elsewhere
    for critical applications.

    Args:
        sanitized_id: Sanitized model ID from filename

    Returns:
        Likely original model ID (best effort)
    """
    # This is a simple heuristic-based reversal
    # For production use, consider maintaining a bidirectional mapping

    # Common patterns to reverse
    if sanitized_id.count("_") == 1:
        # Likely "author_model" -> "author/model"
        return sanitized_id.replace("_", "/", 1)
    elif "_" in sanitized_id and ":" not in sanitized_id:
        # Could be "author_model_tag" -> "author/model:tag"
        parts = sanitized_id.split("_")
        if len(parts) >= 3:
            # Assume first part is author, rest form model:tag
            author = parts[0]
            model_parts = parts[1:]
            # Try to detect where model ends and tag begins
            # This is heuristic and may not always be correct
            return f"{author}/{model_parts[0]}:{model_parts[1]}" if len(model_parts) >= 2 else f"{author}/{model_parts[0]}"

    # Fallback: just replace first underscore with slash
    return sanitized_id.replace("_", "/", 1) if "_" in sanitized_id else sanitized_id


def get_sanitized_model_ids(models_file: str) -> list[str]:
    """
    Get sanitized model IDs for use in Snakemake filenames.

    Args:
        models_file: Path to loaded_models.json file

    Returns:
        List of sanitized model IDs safe for use in filenames
    """
    original_ids = get_model_ids(models_file)
    return [sanitize_model_id_for_filename(model_id) for model_id in original_ids]


if __name__ == "__main__":
    # Test the functions
    import sys

    if len(sys.argv) > 1:
        models_file = sys.argv[1]
        try:
            model_ids = get_model_ids(models_file)
            print("Original model IDs:")
            for model_id in model_ids:
                print(f"  {model_id}")

            print("\nSanitized model IDs:")
            for model_id in model_ids:
                sanitized = sanitize_model_id_for_filename(model_id)
                print(f"  {model_id} -> {sanitized}")

        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        print("Usage: python snakemake_utils.py <models_file>")
        print("Example: python snakemake_utils.py data/loaded_models.json")
