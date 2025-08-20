from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


def remove_outliers(df, columns, threshold=3.0):
    """Remove outliers using z-score method"""
    df_clean = df.copy()
    for col in columns:
        if df[col].dtype in ["float64", "int64"]:
            z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
            df_clean = df_clean[z_scores < threshold]
    return df_clean


def main():
    # Access Snakemake parameters
    input_path = Path(snakemake.input[0])
    output_path = Path(snakemake.output[0])
    params = snakemake.params.processing_params

    # Load data
    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} rows from {input_path}")

    # Remove outliers if specified
    if params.get("remove_outliers", False):
        threshold = params.get("outlier_threshold", 3.0)
        numeric_cols = ["feature_1", "feature_2", "feature_3"]
        df = remove_outliers(df, numeric_cols, threshold)
        print(f"After outlier removal: {len(df)} rows remaining")

    # Normalize features if specified
    if params.get("normalize", False):
        scaler = StandardScaler()
        numeric_cols = ["feature_1", "feature_2", "feature_3"]
        df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
        print("Features normalized")

    # Save processed data
    df.to_csv(output_path, index=False)
    print(f"Processed data saved to {output_path}")


if __name__ == "__main__":
    main()
