import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def create_summary_plot(df, analysis_results, plot_params):
    """Create a comprehensive summary plot"""
    fig, axes = plt.subplots(2, 2, figsize=plot_params.get('figure_size', [12, 10]))
    fig.suptitle('AFBench Data Analysis Summary', fontsize=16)
    
    # Feature distributions
    ax1 = axes[0, 0]
    for i, col in enumerate(['feature_1', 'feature_2', 'feature_3']):
        ax1.hist(df[col], alpha=0.7, label=col, bins=30)
    ax1.set_title('Feature Distributions')
    ax1.set_xlabel('Value')
    ax1.set_ylabel('Frequency')
    ax1.legend()
    
    # Target distribution
    ax2 = axes[0, 1]
    target_counts = df['target'].value_counts()
    ax2.pie(target_counts.values, labels=target_counts.index, autopct='%1.1f%%')
    ax2.set_title('Target Distribution')
    
    # Correlation heatmap
    ax3 = axes[1, 0]
    numeric_cols = ['feature_1', 'feature_2', 'feature_3']
    corr_matrix = df[numeric_cols].corr()
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0, ax=ax3)
    ax3.set_title('Feature Correlation Matrix')
    
    # Feature importance
    ax4 = axes[1, 1]
    if 'ml_analysis' in analysis_results and 'feature_importance' in analysis_results['ml_analysis']:
        importance = analysis_results['ml_analysis']['feature_importance']
        features = list(importance.keys())
        values = list(importance.values())
        ax4.bar(features, values)
        ax4.set_title('Feature Importance (Random Forest)')
        ax4.set_xlabel('Features')
        ax4.set_ylabel('Importance')
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    return fig

def main():
    # Access Snakemake parameters
    data_path = Path(snakemake.input[0])
    analysis_path = Path(snakemake.input[1])
    output_path = Path(snakemake.output[0])
    plot_params = snakemake.params.plot_params
    
    # Load data and results
    df = pd.read_csv(data_path)
    with open(analysis_path, 'r') as f:
        analysis_results = json.load(f)
    
    print(f"Creating plots for {len(df)} samples")
    
    # Set style
    plt.style.use(plot_params.get('style', 'default'))
    
    # Create summary plot
    fig = create_summary_plot(df, analysis_results, plot_params)
    
    # Save plot
    dpi = plot_params.get('dpi', 300)
    fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
    plt.close()
    
    print(f"Summary plot saved to {output_path}")

if __name__ == "__main__":
    main()