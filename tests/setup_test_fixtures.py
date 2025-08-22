#!/usr/bin/env python3
"""
Test Fixtures Setup Script

Creates all necessary fixtures for the AFBench test suite:
- profiles/testonly configuration
- Minimal model and judge pools
- Deterministic test skills and evaluations
- Mock implementations for external calls

This script ensures a clean, reproducible test environment.
"""

import json
from pathlib import Path


def create_testonly_profile():
    """Create the testonly profile configuration."""
    profile_dir = Path("profiles/testonly")
    profile_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "# AFBench Testonly Profile Configuration": None,
        "# Minimal, deterministic, fast configuration for testing pipeline behavior": None,
        "data_dir": "data/testonly",
        "model_pool": {"default_pool": "testonly", "pools_dir": "model_pools"},
        "judge_pool": {"default_pool": "testonly", "pools_dir": "judge_pools"},
        "skills": {"skills_dir": "testonly/skills", "selected_skills": []},
        "n_samples": 10,
        "random_seed": 12345,
        "processing": {
            "remove_outliers": False,
            "outlier_threshold": 3.0,
            "normalize": True,
        },
        "analysis": {
            "statistical_tests": False,
            "correlation_analysis": False,
            "significance_level": 0.05,
        },
        "plotting": {"figure_size": [6, 4], "dpi": 100, "style": "default"},
        "report": {"include_plots": False, "format": "json", "timestamp": True},
    }

    # Write YAML-style config (simplified)
    config_file = profile_dir / "config.yaml"
    with open(config_file, "w") as f:
        f.write("# AFBench Testonly Profile Configuration\n")
        f.write(
            "# Minimal, deterministic, fast configuration for testing pipeline behavior\n\n"
        )

        f.write(f"data_dir: \"{config['data_dir']}\"\n\n")

        f.write("model_pool:\n")
        f.write(f"  default_pool: \"{config['model_pool']['default_pool']}\"\n")
        f.write(f"  pools_dir: \"{config['model_pool']['pools_dir']}\"\n\n")

        f.write("judge_pool:\n")
        f.write(f"  default_pool: \"{config['judge_pool']['default_pool']}\"\n")
        f.write(f"  pools_dir: \"{config['judge_pool']['pools_dir']}\"\n\n")

        f.write("skills:\n")
        f.write(f"  skills_dir: \"{config['skills']['skills_dir']}\"\n")
        f.write(f"  selected_skills: {config['skills']['selected_skills']}\n\n")

        f.write(f"n_samples: {config['n_samples']}\n")
        f.write(f"random_seed: {config['random_seed']}\n\n")

        f.write("processing:\n")
        f.write(
            f"  remove_outliers: {str(config['processing']['remove_outliers']).lower()}\n"
        )
        f.write(f"  outlier_threshold: {config['processing']['outlier_threshold']}\n")
        f.write(f"  normalize: {str(config['processing']['normalize']).lower()}\n\n")

        f.write("analysis:\n")
        f.write(
            f"  statistical_tests: {str(config['analysis']['statistical_tests']).lower()}\n"
        )
        f.write(
            f"  correlation_analysis: {str(config['analysis']['correlation_analysis']).lower()}\n"
        )
        f.write(f"  significance_level: {config['analysis']['significance_level']}\n\n")

        f.write("plotting:\n")
        f.write(f"  figure_size: {config['plotting']['figure_size']}\n")
        f.write(f"  dpi: {config['plotting']['dpi']}\n")
        f.write(f"  style: \"{config['plotting']['style']}\"\n\n")

        f.write("report:\n")
        f.write(f"  include_plots: {str(config['report']['include_plots']).lower()}\n")
        f.write(f"  format: \"{config['report']['format']}\"\n")
        f.write(f"  timestamp: {str(config['report']['timestamp']).lower()}\n")

    print(f"✅ Created {config_file}")


def create_model_pool():
    """Create minimal testonly model pool."""
    models = [
        {
            "id": "test/model-alpha",
            "author": "TestCorp",
            "slug": "model-alpha",
            "context_window": 4096,
            "pricing": "input:0.0001",
            "endpoint": "mock",
            "max_tokens": 1000,
        },
        {
            "id": "test/model-beta",
            "author": "TestCorp",
            "slug": "model-beta",
            "context_window": 8192,
            "pricing": "input:0.0002",
            "endpoint": "mock",
            "max_tokens": 2000,
        },
    ]

    pool_file = Path("model_pools/testonly.csv")
    pool_file.parent.mkdir(exist_ok=True)

    with open(pool_file, "w") as f:
        f.write("id,author,slug,context_window,pricing,endpoint,max_tokens\n")
        for model in models:
            f.write(
                f"{model['id']},{model['author']},{model['slug']},{model['context_window']},{model['pricing']},{model['endpoint']},{model['max_tokens']}\n"
            )

    print(f"✅ Created {pool_file} with {len(models)} models")


def create_judge_pool():
    """Create minimal testonly judge pool."""
    judges = [
        {
            "id": "test/judge-gamma",
            "author": "TestCorp",
            "slug": "judge-gamma",
            "context_window": 4096,
            "pricing": "input:0.0001",
            "endpoint": "mock",
            "max_tokens": 1000,
        },
        {
            "id": "test/judge-delta",
            "author": "TestCorp",
            "slug": "judge-delta",
            "context_window": 4096,
            "pricing": "input:0.0001",
            "endpoint": "mock",
            "max_tokens": 1000,
        },
    ]

    pool_file = Path("judge_pools/testonly.csv")
    pool_file.parent.mkdir(exist_ok=True)

    with open(pool_file, "w") as f:
        f.write("id,author,slug,context_window,pricing,endpoint,max_tokens\n")
        for judge in judges:
            f.write(
                f"{judge['id']},{judge['author']},{judge['slug']},{judge['context_window']},{judge['pricing']},{judge['endpoint']},{judge['max_tokens']}\n"
            )

    print(f"✅ Created {pool_file} with {len(judges)} judges")


def create_test_skills():
    """Create deterministic test skills and evaluations."""
    skills_dir = Path("testonly/skills/test_skill")
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Eval 1: Simple deterministic response
    eval_one = {
        "id": "eval_one",
        "description": "First deterministic test evaluation",
        "skill": "test_skill",
        "version": "1.0.0",
        "metadata": {
            "author": "TestSuite",
            "created": "2025-01-01",
            "difficulty": "easy",
            "tags": ["test", "deterministic"],
        },
        "steps": [
            {
                "type": "user_message",
                "content": "Hello! Please respond with exactly: 'Test response from eval_one with fixed seed 12345'",
            },
            {
                "type": "assistant_message",
                "content": "Test response from eval_one with fixed seed 12345",
            },
        ],
        "evaluation": {
            "type": "exact_match",
            "expected": "Test response from eval_one with fixed seed 12345",
        },
    }

    # Eval 2: Counting task
    eval_two = {
        "id": "eval_two",
        "description": "Second deterministic test evaluation",
        "skill": "test_skill",
        "version": "1.0.0",
        "metadata": {
            "author": "TestSuite",
            "created": "2025-01-01",
            "difficulty": "easy",
            "tags": ["test", "deterministic"],
        },
        "steps": [
            {
                "type": "user_message",
                "content": "Please count from 1 to 3 with deterministic seed 12345",
            },
            {"type": "assistant_message", "content": "1, 2, 3 (seed: 12345)"},
        ],
        "evaluation": {"type": "exact_match", "expected": "1, 2, 3 (seed: 12345)"},
    }

    # Write eval files
    eval_files = [
        (skills_dir / "eval_one.json", eval_one),
        (skills_dir / "eval_two.json", eval_two),
    ]

    for file_path, eval_data in eval_files:
        with open(file_path, "w") as f:
            json.dump(eval_data, f, indent=2)
        print(f"✅ Created {file_path}")


def create_fixture_variants():
    """Create fixture variants for mutation testing."""
    variants_dir = Path("tests/fixtures/variants")
    variants_dir.mkdir(parents=True, exist_ok=True)

    # Variant: Additional model
    extra_model = {
        "id": "test/model-gamma",
        "author": "TestCorp",
        "slug": "model-gamma",
        "context_window": 16384,
        "pricing": "input:0.0003",
        "endpoint": "mock",
        "max_tokens": 3000,
    }

    with open(variants_dir / "extra_model.json", "w") as f:
        json.dump(extra_model, f, indent=2)

    # Variant: Modified eval
    modified_eval = {
        "id": "eval_two",
        "description": "Modified second test evaluation",
        "skill": "test_skill",
        "version": "1.1.0",
        "metadata": {
            "author": "TestSuite",
            "created": "2025-01-01",
            "difficulty": "easy",
            "tags": ["test", "deterministic", "modified"],
        },
        "steps": [
            {
                "type": "user_message",
                "content": "Please count from 1 to 5 with deterministic seed 12345",
            },
            {"type": "assistant_message", "content": "1, 2, 3, 4, 5 (seed: 12345)"},
        ],
        "evaluation": {
            "type": "exact_match",
            "expected": "1, 2, 3, 4, 5 (seed: 12345)",
        },
    }

    with open(variants_dir / "modified_eval_two.json", "w") as f:
        json.dump(modified_eval, f, indent=2)

    print(f"✅ Created fixture variants in {variants_dir}")


def main():
    """Set up all test fixtures."""
    print("🏗️ Setting up AFBench test fixtures...")

    # Create all fixtures
    create_testonly_profile()
    create_model_pool()
    create_judge_pool()
    create_test_skills()
    create_fixture_variants()

    print("\n✅ Test fixture setup complete!")
    print("\n📋 Created fixtures:")
    print("   - profiles/testonly/config.yaml")
    print("   - model_pools/testonly.csv (2 models)")
    print("   - judge_pools/testonly.csv (2 judges)")
    print("   - testonly/skills/test_skill/ (2 evals)")
    print("   - tests/fixtures/variants/ (mutation variants)")

    print("\n🧪 Ready to run determinism tests:")
    print("   python tests/run_determinism_suite.py")


if __name__ == "__main__":
    main()
