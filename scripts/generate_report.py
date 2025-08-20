import json
from datetime import datetime
from pathlib import Path

import pandas as pd


def generate_summary_statistics(analysis_results):
    """Generate summary statistics from analysis results"""
    summary = {}

    if "statistical_analysis" in analysis_results:
        stats_data = analysis_results["statistical_analysis"]

        # Extract key statistics
        if "descriptive_stats" in stats_data:
            desc_stats = stats_data["descriptive_stats"]
            summary["feature_means"] = {col: desc_stats[col]["mean"] for col in desc_stats}
            summary["feature_std"] = {col: desc_stats[col]["std"] for col in desc_stats}

        # ANOVA significance
        if "anova_tests" in stats_data:
            significant_features = [feature for feature, test in stats_data["anova_tests"].items() if test["significant"]]
            summary["significant_features"] = significant_features

    if "ml_analysis" in analysis_results:
        ml_data = analysis_results["ml_analysis"]
        summary["model_accuracy"] = ml_data.get("accuracy", 0)

        # Most important feature
        if "feature_importance" in ml_data:
            importance = ml_data["feature_importance"]
            most_important = max(importance, key=importance.get)
            summary["most_important_feature"] = {"name": most_important, "importance": importance[most_important]}

    return summary


def main():
    # Access Snakemake parameters
    analysis_path = Path(snakemake.input[0])
    plot_path = Path(snakemake.input[1])
    output_path = Path(snakemake.output[0])
    report_params = snakemake.params.report_params

    # Load analysis results
    with open(analysis_path) as f:
        analysis_results = json.load(f)

    print("Generating final report")

    # Generate report
    report = {
        "metadata": {
            "generation_time": datetime.now().isoformat(),
            "analysis_file": str(analysis_path),
            "plot_file": str(plot_path) if report_params.get("include_plots", True) else None,
        },
        "summary": generate_summary_statistics(analysis_results),
        "detailed_results": analysis_results,
    }

    # Add timestamp if requested
    if report_params.get("timestamp", True):
        report["timestamp"] = pd.Timestamp.now().isoformat()

    # Save report
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Final report saved to {output_path}")

    # Print summary to console
    summary = report["summary"]
    print("\n=== Analysis Summary ===")
    if "model_accuracy" in summary:
        print(f"Model Accuracy: {summary['model_accuracy']:.3f}")
    if "most_important_feature" in summary:
        feat = summary["most_important_feature"]
        print(f"Most Important Feature: {feat['name']} (importance: {feat['importance']:.3f})")
    if "significant_features" in summary:
        print(f"Statistically Significant Features: {', '.join(summary['significant_features'])}")


if __name__ == "__main__":
    main()
