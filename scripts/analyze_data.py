import json
from pathlib import Path

import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split


def statistical_analysis(df):
    """Perform statistical analysis on the data"""
    results = {}

    # Basic statistics
    numeric_cols = ["feature_1", "feature_2", "feature_3"]
    results["descriptive_stats"] = df[numeric_cols].describe().to_dict()

    # Correlation analysis
    correlation_matrix = df[numeric_cols].corr()
    results["correlation_matrix"] = correlation_matrix.to_dict()

    # ANOVA test for each feature against target
    results["anova_tests"] = {}
    for col in numeric_cols:
        groups = [df[df["target"] == target][col] for target in df["target"].unique()]
        f_stat, p_value = stats.f_oneway(*groups)
        results["anova_tests"][col] = {
            "f_statistic": float(f_stat),
            "p_value": float(p_value),
            "significant": bool(p_value < 0.05),
        }

    return results


def machine_learning_analysis(df):
    """Perform machine learning analysis"""
    # Prepare features and target
    X = df[["feature_1", "feature_2", "feature_3"]]
    y = df["target"]

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Train Random Forest
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)

    # Predictions
    y_pred = rf.predict(X_test)

    # Feature importance
    feature_importance = dict(zip(X.columns, rf.feature_importances_, strict=False))

    # Classification report
    report = classification_report(y_test, y_pred, output_dict=True)

    return {
        "feature_importance": {k: float(v) for k, v in feature_importance.items()},
        "classification_report": report,
        "accuracy": float(rf.score(X_test, y_test)),
    }


def main():
    # Access Snakemake parameters
    input_path = Path(snakemake.input[0])
    output_path = Path(snakemake.output[0])
    params = snakemake.params.analysis_params

    # Load processed data
    df = pd.read_csv(input_path)
    print(f"Analyzing {len(df)} rows from {input_path}")

    results = {"data_shape": df.shape, "timestamp": pd.Timestamp.now().isoformat()}

    # Statistical analysis
    if params.get("statistical_tests", True):
        results["statistical_analysis"] = statistical_analysis(df)
        print("Statistical analysis completed")

    # Machine learning analysis
    results["ml_analysis"] = machine_learning_analysis(df)
    print("Machine learning analysis completed")

    # Save results
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Analysis results saved to {output_path}")


if __name__ == "__main__":
    main()
