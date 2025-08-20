import pandas as pd
import numpy as np
from pathlib import Path

def main():
    # Access Snakemake parameters
    output_path = Path(snakemake.output[0])
    n_samples = snakemake.params.n_samples
    random_seed = snakemake.params.random_seed
    
    # Set random seed for reproducibility
    np.random.seed(random_seed)
    
    # Generate synthetic data
    data = {
        'id': range(1, n_samples + 1),
        'feature_1': np.random.normal(0, 1, n_samples),
        'feature_2': np.random.exponential(2, n_samples),
        'feature_3': np.random.uniform(-5, 5, n_samples),
        'target': np.random.choice(['A', 'B', 'C'], n_samples, p=[0.4, 0.35, 0.25])
    }
    
    df = pd.DataFrame(data)
    
    # Add some correlation between features and target
    df.loc[df['target'] == 'A', 'feature_1'] += 0.5
    df.loc[df['target'] == 'B', 'feature_2'] += 1.0
    df.loc[df['target'] == 'C', 'feature_3'] += 2.0
    
    # Save to output
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} samples and saved to {output_path}")

if __name__ == "__main__":
    main()