"""
Analysis rules for AFBench workflow
"""

rule analyze_data:
    input:
        DATA_DIR / "processed_data.csv"
    output:
        RESULTS_DIR / "analysis_results.json"
    params:
        analysis_params=config.get("analysis", {})
    threads: 2
    script:
        "../scripts/analyze_data.py"