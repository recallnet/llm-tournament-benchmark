import json
from pathlib import Path

import pandas as pd


def validate_model_pool(df, pool_name):
    """Validate that model pool has required columns and data"""
    required_columns = [
        "id",
        "author",
        "slug",
        "context_window",
        "pricing",
        "endpoint",
        "max_tokens",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Model pool '{pool_name}' missing required columns: {missing_columns}"
        )

    # Check for empty required fields
    for col in required_columns:
        if df[col].isna().any():
            raise ValueError(
                f"Model pool '{pool_name}' has empty values in column '{col}'"
            )

    # Validate numeric columns (allowing string pricing for flexible formats)
    numeric_columns = ["context_window", "max_tokens"]
    for col in numeric_columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            try:
                df[col] = pd.to_numeric(df[col])
            except ValueError:
                raise ValueError(
                    f"Column '{col}' in pool '{pool_name}' contains non-numeric values"
                )

    # Pricing can be string or numeric (to allow formats like "input:0.001")
    # Just validate it's not empty
    if df["pricing"].isna().any() or (df["pricing"] == "").any():
        raise ValueError(
            f"Column 'pricing' in pool '{pool_name}' contains empty values"
        )

    return df


def load_model_pool(pool_path):
    """Load and validate a single model pool CSV"""
    pool_name = pool_path.stem

    try:
        df = pd.read_csv(pool_path)
        df = validate_model_pool(df, pool_name)

        print(f"Loaded model pool '{pool_name}' with {len(df)} models")
        return {
            "name": pool_name,
            "path": str(pool_path),
            "model_count": len(df),
            "models": df.to_dict("records"),
        }
    except Exception as e:
        print(f"Error loading model pool '{pool_name}': {e}")
        raise


def main():
    # Access Snakemake parameters
    output_path = Path(snakemake.output[0])
    pool_name = snakemake.params.get("pool_name", "test")
    pools_dir = Path(snakemake.params.get("pools_dir", "model_pools"))

    print(f"Loading model pool: {pool_name}")

    # Construct pool file path
    pool_path = pools_dir / f"{pool_name}.csv"

    if not pool_path.exists():
        raise FileNotFoundError(f"Model pool file not found: {pool_path}")

    # Load the specified model pool
    pool_data = load_model_pool(pool_path)

    # Create summary information
    models_df = pd.DataFrame(pool_data["models"])

    # Calculate statistics for numeric pricing only
    numeric_pricing = pd.to_numeric(models_df["pricing"], errors="coerce").dropna()

    summary = {
        "pool_info": {
            "name": pool_data["name"],
            "path": pool_data["path"],
            "model_count": pool_data["model_count"],
            "timestamp": pd.Timestamp.now().isoformat(),
        },
        "statistics": {
            "authors": models_df["author"].value_counts().to_dict(),
            "avg_context_window": float(models_df["context_window"].mean()),
            "avg_max_tokens": float(models_df["max_tokens"].mean()),
            "context_window_range": {
                "min": int(models_df["context_window"].min()),
                "max": int(models_df["context_window"].max()),
            },
        },
        "models": pool_data["models"],
    }

    # Add pricing statistics only if we have numeric pricing data
    if len(numeric_pricing) > 0:
        summary["statistics"]["avg_pricing"] = float(numeric_pricing.mean())
        summary["statistics"]["price_range"] = {
            "min": float(numeric_pricing.min()),
            "max": float(numeric_pricing.max()),
        }

    # Save loaded models data
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Model pool data saved to {output_path}")

    # Print summary statistics
    print("\n=== Model Pool Summary ===")
    print(f"Pool: {pool_data['name']}")
    print(f"Total models: {pool_data['model_count']}")
    print(f"Authors: {', '.join(summary['statistics']['authors'].keys())}")
    if "avg_pricing" in summary["statistics"]:
        print(f"Average pricing: ${summary['statistics']['avg_pricing']:.2f}")
    else:
        print("Pricing: Mixed formats (non-numeric)")
    print(
        f"Context window range: {summary['statistics']['context_window_range']['min']:,} - {summary['statistics']['context_window_range']['max']:,}"
    )


if __name__ == "__main__":
    main()
