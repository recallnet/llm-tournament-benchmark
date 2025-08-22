#!/usr/bin/env python3
"""
Test pipeline resume behavior to ensure minimal reruns when interrupted.
This validates Snakemake's caching and resume capabilities.
"""

import json
from pathlib import Path


def test_conversation_cache_state():
    """Test current conversation cache state and what would resume."""
    print("🧪 Testing conversation cache state for resume...")

    # Count existing conversation files
    conversation_files = list(Path("data/testonly/conversations").glob("*/*.json"))
    print(f"📊 Found {len(conversation_files)} cached conversation files")

    # Load models and skills to calculate expected total
    with open("data/testonly/loaded_models.json") as f:
        models = json.load(f)["models"]

    with open("data/testonly/loaded_skills.json") as f:
        skills = json.load(f)["evals"]

    total_expected = len(models) * len(skills)
    print(f"📊 Expected total: {total_expected} conversations")
    print(
        f"📊 Progress: {len(conversation_files)}/{total_expected} ({len(conversation_files)/total_expected*100:.1f}%)"
    )

    if len(conversation_files) == total_expected:
        print("✅ All conversations cached - should skip generation entirely")
        return True, "complete"
    elif len(conversation_files) > 0:
        print("⏸️ Partial progress - should resume from where left off")
        return True, "partial"
    else:
        print("🚀 No conversations cached - will start from beginning")
        return True, "empty"


def test_snakemake_resume_efficiency():
    """Test that Snakemake won't rerun completed work."""
    print("\n🧪 Testing Snakemake resume efficiency...")

    # Check if conversations.json exists and is valid
    conv_file = Path("data/testonly/conversations.json")
    if conv_file.exists():
        try:
            with open(conv_file) as f:
                data = json.load(f)

            convs = data.get("conversations", [])
            if len(convs) > 0:
                print(f"✅ conversations.json exists with {len(convs)} conversations")
                print("💡 Snakemake should skip conversation generation entirely")
                return True
            else:
                print("⚠️ conversations.json exists but has 0 conversations")
                print("💡 Snakemake may regenerate this file")
                return False
        except json.JSONDecodeError:
            print("❌ conversations.json is corrupted")
            print("💡 Snakemake will regenerate this file")
            return False
    else:
        print("⏸️ conversations.json missing")
        print("💡 Snakemake will generate from cached conversation files")
        return False


def test_tournament_resume_readiness():
    """Test if tournaments can resume from existing state."""
    print("\n🧪 Testing tournament resume readiness...")

    # Check tournament files
    tournament_files = list(Path("data/testonly/tournaments").glob("*/*.json"))
    print(f"📊 Found {len(tournament_files)} tournament files")

    # Count tournaments by skill
    skills_with_tournaments = set()
    for tournament_file in tournament_files:
        skill = tournament_file.parent.name
        skills_with_tournaments.add(skill)

    print(f"📊 Skills with tournaments: {sorted(skills_with_tournaments)}")

    # Check if tournaments.json exists
    tournaments_json = Path("data/testonly/tournaments.json")
    if tournaments_json.exists():
        print("✅ tournaments.json exists - may skip tournament generation")
        return True
    else:
        print(
            "⏸️ tournaments.json missing - will generate from individual tournament files"
        )
        return False


def test_expected_resume_behavior():
    """Test expected resume behavior for the full pipeline."""
    print("\n🧪 Testing expected resume behavior...")

    cache_state, cache_type = test_conversation_cache_state()
    snakemake_efficient = test_snakemake_resume_efficiency()
    tournament_ready = test_tournament_resume_readiness()

    print("\n📋 Resume Analysis:")
    print(f"   Conversation cache: {cache_type}")
    print(
        f"   Snakemake efficiency: {'✅ efficient' if snakemake_efficient else '⚠️ may rerun'}"
    )
    print(
        f"   Tournament readiness: {'✅ ready' if tournament_ready else '⏸️ needs generation'}"
    )

    # Predict what will happen on resume
    if cache_type == "complete" and snakemake_efficient:
        print("\n🎯 EXPECTED RESUME BEHAVIOR:")
        print("   ✅ Skip conversation generation entirely (all cached)")
        print("   🏟️ Run tournaments if needed")
        print("   📊 Calculate skill ratings")
        print("   📋 Print results table")
        estimated_time = "2-5 minutes"
    elif cache_type == "partial":
        cached_count = len(list(Path("data/testonly/conversations").glob("*/*.json")))
        remaining = 88 - cached_count
        print("\n🎯 EXPECTED RESUME BEHAVIOR:")
        print(f"   ⏸️ Resume conversation generation ({remaining} remaining)")
        print("   🏟️ Run tournaments")
        print("   📊 Calculate skill ratings")
        print("   📋 Print results table")
        estimated_time = f"{remaining * 10} seconds + tournament time"
    else:
        print("\n🎯 EXPECTED RESUME BEHAVIOR:")
        print("   🚀 Full conversation generation (88 conversations)")
        print("   🏟️ Run tournaments")
        print("   📊 Calculate skill ratings")
        print("   📋 Print results table")
        estimated_time = "15-20 minutes"

    print(f"   ⏰ Estimated time: {estimated_time}")

    return cache_type, estimated_time


def test_cache_invalidation_scenarios():
    """Test scenarios that would force cache invalidation."""
    print("\n🧪 Testing cache invalidation scenarios...")

    scenarios = []

    # Check if model pool changed
    try:
        with open("data/testonly/loaded_models.json") as f:
            current_models = set(model["id"] for model in json.load(f)["models"])

        # Check conversation cache for different models
        cached_models = set()
        for conv_file in Path("data/testonly/conversations").glob("*/*.json"):
            if "_" in conv_file.stem:
                model_part = conv_file.stem.split("_")[
                    -2
                ]  # Extract model from filename
                cached_models.add(model_part)

        if cached_models - current_models:
            scenarios.append(
                "Stale model cache detected - some cached conversations for removed models"
            )

        if current_models - cached_models:
            scenarios.append(
                "New models detected - will need conversations for new models"
            )

    except Exception as e:
        scenarios.append(f"Cannot analyze model cache: {e}")

    # Check if skills changed
    try:
        with open("data/testonly/loaded_skills.json") as f:
            current_skills = set(skill["id"] for skill in json.load(f)["evals"])

        # Check conversation cache for different skills
        cached_skills = set()
        for conv_file in Path("data/testonly/conversations").glob("*/*.json"):
            skill_dir = conv_file.parent.name
            cached_skills.add(skill_dir)

        if cached_skills - current_skills:
            scenarios.append(
                "Stale skill cache detected - some cached conversations for removed skills"
            )

        if current_skills - cached_skills:
            scenarios.append(
                "New skills detected - will need conversations for new skills"
            )

    except Exception as e:
        scenarios.append(f"Cannot analyze skill cache: {e}")

    if scenarios:
        print("⚠️ Cache invalidation scenarios detected:")
        for scenario in scenarios:
            print(f"   - {scenario}")
        return False
    else:
        print("✅ No cache invalidation issues detected")
        return True


if __name__ == "__main__":
    print("🧪 Testing pipeline resume behavior...")

    cache_type, estimated_time = test_expected_resume_behavior()
    cache_valid = test_cache_invalidation_scenarios()

    print("\n📋 RESUME READINESS SUMMARY:")
    print(f"   Cache type: {cache_type}")
    print(f"   Cache valid: {'✅ yes' if cache_valid else '⚠️ issues detected'}")
    print(f"   Estimated resume time: {estimated_time}")

    if cache_type == "complete" and cache_valid:
        print("\n✅ OPTIMAL RESUME CONDITIONS")
        print("💡 Pipeline should complete very quickly")
    elif cache_type == "partial" and cache_valid:
        print("\n⏸️ PARTIAL RESUME CONDITIONS")
        print("💡 Pipeline will complete remaining work efficiently")
    else:
        print("\n🚀 FULL REGENERATION NEEDED")
        print("💡 Pipeline will run from scratch - expect longer time")
