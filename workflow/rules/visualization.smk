"""
Visualization rules for AFBench workflow
"""

rule create_plots:
    input:
        DATA_DIR / "processed_data.csv",
        RESULTS_DIR / "analysis_results.json"
    output:
        PLOTS_DIR / "summary_plot.png"
    params:
        plot_params=config.get("plotting", {})
    script:
        "../scripts/create_plots.py"