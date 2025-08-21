"""Fetch OpenRouter models and filter to match our model/judge pools."""

import json
from pathlib import Path

import requests


class OpenRouterModelsFetcher:
    """Handles fetching and filtering OpenRouter models data."""

    def __init__(self):
        self.api_url = "https://openrouter.ai/api/v1/models"
        self.headers = {
            "HTTP-Referer": "https://github.com/anthropics/afbench",
        }

    def fetch_openrouter_models(self):
        """Fetch the full list of models from OpenRouter API.

        Returns:
            dict: The full OpenRouter API response with all models

        Raises:
            requests.RequestException: If the API request fails
            requests.HTTPError: If the API returns an error status
        """
        response = requests.get(self.api_url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_model_ids_from_pools(self, models_data, judges_data):
        """Extract model IDs from loaded model and judge pools.

        Args:
            models_data (dict): Loaded models data from load_models.py
            judges_data (dict): Loaded judges data from load_judges.py

        Returns:
            set: Set of model IDs that are in our pools
        """
        model_ids = set()

        # Add model pool IDs
        for model in models_data.get("models", []):
            model_ids.add(model.get("id"))

        # Add judge pool IDs
        for judge in judges_data.get("models", []):
            model_ids.add(judge.get("id"))

        return model_ids

    def filter_openrouter_models(self, openrouter_data, pool_model_ids):
        """Filter OpenRouter data to only include models in our pools.

        Args:
            openrouter_data (dict): Full OpenRouter API response
            pool_model_ids (set): Set of model IDs from our pools

        Returns:
            dict: Filtered OpenRouter data in the same format as the original
        """
        filtered_models = []

        for model in openrouter_data.get("data", []):
            if model.get("id") in pool_model_ids:
                filtered_models.append(model)

        return {"data": filtered_models}

    def process_models(self, models_data, judges_data):
        """Process models: fetch from OpenRouter and filter to our pools.

        Args:
            models_data (dict): Loaded models data
            judges_data (dict): Loaded judges data

        Returns:
            tuple: (full_openrouter_data, filtered_openrouter_data)
        """
        # Fetch full OpenRouter data
        full_data = self.fetch_openrouter_models()

        # Get model IDs from our pools
        pool_model_ids = self.get_model_ids_from_pools(models_data, judges_data)

        # Filter to only models in our pools
        filtered_data = self.filter_openrouter_models(full_data, pool_model_ids)

        return full_data, filtered_data


def main():
    """Main function for Snakemake integration."""
    if "snakemake" in globals():
        # Called by Snakemake
        models_path = Path(snakemake.input.models)
        judges_path = Path(snakemake.input.judges)
        full_output_path = Path(snakemake.output[0])
        filtered_output_path = Path(snakemake.output[1])
    else:
        # Called directly - MUST provide data_dir via environment variable
        data_dir_env = os.getenv("AFBENCH_DATA_DIR")
        if not data_dir_env:
            raise ValueError(
                "🚨 SAFETY: fetch_openrouter_models.py requires explicit data directory.\n"
                "Set AFBENCH_DATA_DIR environment variable or run via Snakemake."
            )

        data_dir = Path(data_dir_env)
        models_path = data_dir / "loaded_models.json"
        judges_path = data_dir / "loaded_judges.json"
        full_output_path = data_dir / "openrouter_models_full.json"
        filtered_output_path = data_dir / "openrouter_models_filtered.json"

    print("Fetching OpenRouter models...")

    # Load input data
    with open(models_path) as f:
        models_data = json.load(f)

    with open(judges_path) as f:
        judges_data = json.load(f)

    # Process models
    fetcher = OpenRouterModelsFetcher()
    full_data, filtered_data = fetcher.process_models(models_data, judges_data)

    # Save full OpenRouter data
    with open(full_output_path, "w") as f:
        json.dump(full_data, f, indent=2)
    print(f"Saved full OpenRouter data to {full_output_path}")

    # Save filtered OpenRouter data
    with open(filtered_output_path, "w") as f:
        json.dump(filtered_data, f, indent=2)
    print(f"Saved filtered OpenRouter data to {filtered_output_path}")

    # Print summary
    total_models = len(full_data.get("data", []))
    filtered_models = len(filtered_data.get("data", []))
    print(f"Total OpenRouter models: {total_models}")
    print(f"Models in our pools: {filtered_models}")


if __name__ == "__main__":
    main()
