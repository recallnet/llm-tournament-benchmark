"""
Data processing rules for AFBench workflow
"""

rule load_models:
    output:
        DATA_DIR / "loaded_models.json"
    params:
        pool_name=config.get("model_pool", {}).get("default_pool", "test"),
        pools_dir=config.get("model_pool", {}).get("pools_dir", "model_pools")
    script:
        "../scripts/load_models.py"

rule load_judges:
    output:
        DATA_DIR / "loaded_judges.json"
    params:
        pool_name=config.get("judge_pool", {}).get("default_pool", "test"),
        pools_dir=config.get("judge_pool", {}).get("pools_dir", "judge_pools")
    script:
        "../scripts/load_judges.py"

rule load_skills:
    output:
        DATA_DIR / "loaded_skills.json"
    params:
        skills_dir=config.get("skills", {}).get("skills_dir", "skills"),
        selected_skills=config.get("skills", {}).get("selected_skills", None)
    script:
        "../scripts/load_skills.py"

rule generate_data:
    input:
        DATA_DIR / "loaded_models.json",
        DATA_DIR / "loaded_judges.json",
        DATA_DIR / "loaded_skills.json"
    output:
        DATA_DIR / "raw_data.csv"
    params:
        n_samples=config.get("n_samples", 1000),
        random_seed=config.get("random_seed", 42)
    script:
        "../scripts/generate_data.py"

rule process_data:
    input:
        DATA_DIR / "raw_data.csv"
    output:
        DATA_DIR / "processed_data.csv"
    params:
        processing_params=config.get("processing", {})
    script:
        "../scripts/process_data.py"