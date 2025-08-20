"""
Reporting rules for AFBench workflow
"""

rule generate_report:
    input:
        RESULTS_DIR / "analysis_results.json",
        PLOTS_DIR / "summary_plot.png"
    output:
        RESULTS_DIR / "final_report.json"
    params:
        report_params=config.get("report", {})
    script:
        "../scripts/generate_report.py"