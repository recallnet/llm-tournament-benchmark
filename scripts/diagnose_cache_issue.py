#!/usr/bin/env python3
"""
Diagnose cache invalidation issues.
Run this when cache unexpectedly gets invalidated.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path


def analyze_cache_state():
    """Analyze current cache state and identify issues."""
    print("🔍 CACHE DIAGNOSTIC REPORT")
    print("=" * 50)

    # Check data directory structure
    data_dir = Path("data")
    if not data_dir.exists():
        print("❌ CRITICAL: data/ directory missing")
        return

    print(f"📁 Data directory: {data_dir.absolute()}")

    # Check loaded files
    loaded_files = {
        "models": data_dir / "loaded_models.json",
        "judges": data_dir / "loaded_judges.json",
        "skills": data_dir / "loaded_skills.json",
    }

    print("\n📋 LOADED FILES STATUS:")
    for name, path in loaded_files.items():
        if path.exists():
            stat = path.stat()
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime)
            print(f"  ✅ {name}: {size:,} bytes, modified {mtime}")

            # Check content
            try:
                data = json.loads(path.read_text())
                if name == "models":
                    count = data.get("pool_info", {}).get("model_count", 0)
                    print(f"     📊 {count} models loaded")
                elif name == "judges":
                    count = data.get("pool_info", {}).get("judge_count", 0)
                    print(f"     📊 {count} judges loaded")
                elif name == "skills":
                    count = len(data.get("evals", []))
                    print(f"     📊 {count} skills loaded")
            except json.JSONDecodeError as e:
                print(f"     ❌ JSON ERROR: {e}")
        else:
            print(f"  ❌ {name}: MISSING")

    # Check conversation cache
    print("\n💬 CONVERSATION CACHE:")
    cache_markers = list(data_dir.glob("conversations_cache_*.done"))
    if cache_markers:
        print(f"  ✅ Found {len(cache_markers)} conversation cache markers:")
        for marker in cache_markers:
            print(f"     📄 {marker.name}")
    else:
        print("  ❌ No conversation cache markers found")

    # Check judge cache
    print("\n🧑‍⚖️ JUDGE CACHE:")
    judge_cache_dir = data_dir / "judge_cache"
    if judge_cache_dir.exists():
        skills_cached = list(judge_cache_dir.iterdir())
        total_cache_files = 0

        print(f"  📁 Skills with judge cache: {len(skills_cached)}")
        for skill_dir in skills_cached:
            if skill_dir.is_dir():
                cache_files = list(skill_dir.glob("*.json"))
                total_cache_files += len(cache_files)
                print(f"     📂 {skill_dir.name}: {len(cache_files)} cache files")

        print(f"  📊 Total judge cache files: {total_cache_files}")
    else:
        print("  ❌ No judge cache directory found")

    # Check output files
    print("\n📤 OUTPUT FILES:")
    output_files = [
        "tournaments.json",
        "tournament_summaries.json",
        "skill_ratings.json",
    ]

    for output_file in output_files:
        path = data_dir / output_file
        if path.exists():
            stat = path.stat()
            size = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime)
            print(f"  ✅ {output_file}: {size:,} bytes, modified {mtime}")
        else:
            print(f"  ❌ {output_file}: MISSING")

    # Check for cache invalidation signs
    print("\n🚨 CACHE INVALIDATION ANALYSIS:")

    # Check if loaded files are newer than cache
    if loaded_files["models"].exists() and loaded_files["judges"].exists():
        models_mtime = loaded_files["models"].stat().st_mtime
        judges_mtime = loaded_files["judges"].stat().st_mtime

        if judge_cache_dir.exists():
            newest_cache_mtime = 0
            for cache_file in judge_cache_dir.rglob("*.json"):
                cache_mtime = cache_file.stat().st_mtime
                newest_cache_mtime = max(newest_cache_mtime, cache_mtime)

            if models_mtime > newest_cache_mtime:
                print("  🚨 MODELS FILE NEWER THAN CACHE - cache invalidated")
            if judges_mtime > newest_cache_mtime:
                print("  🚨 JUDGES FILE NEWER THAN CACHE - cache invalidated")
            if newest_cache_mtime > 0:
                cache_age = datetime.now().timestamp() - newest_cache_mtime
                print(f"  📅 Cache age: {cache_age/3600:.1f} hours")

    # Generate cache fingerprint
    print("\n🔐 CACHE FINGERPRINT:")
    try:
        fingerprint_data = {}

        for name, path in loaded_files.items():
            if path.exists():
                content = path.read_text()
                fingerprint_data[name] = hashlib.md5(content.encode()).hexdigest()[:8]

        cache_fingerprint = hashlib.md5(str(fingerprint_data).encode()).hexdigest()[:8]
        print(f"  🔑 Current fingerprint: {cache_fingerprint}")
        print(f"     Models: {fingerprint_data.get('models', 'MISSING')}")
        print(f"     Judges: {fingerprint_data.get('judges', 'MISSING')}")
        print(f"     Skills: {fingerprint_data.get('skills', 'MISSING')}")

    except Exception as e:
        print(f"  ❌ Error generating fingerprint: {e}")


def check_pipeline_health():
    """Check if pipeline is in a healthy state to run."""
    print("\n🏥 PIPELINE HEALTH CHECK:")

    issues = []

    # Check required files
    required_files = [
        "data/loaded_models.json",
        "data/loaded_judges.json",
        "data/loaded_skills.json",
    ]

    for req_file in required_files:
        if not Path(req_file).exists():
            issues.append(f"Missing required file: {req_file}")

    # Check conversation cache consistency
    cache_markers = list(Path("data").glob("conversations_cache_*.done"))
    if cache_markers:
        # Extract model IDs from cache markers
        cached_models = set()
        for marker in cache_markers:
            model_id = marker.name.replace("conversations_cache_", "").replace(
                ".done", ""
            )
            cached_models.add(model_id)

        # Check against loaded models
        if Path("data/loaded_models.json").exists():
            try:
                models_data = json.loads(Path("data/loaded_models.json").read_text())
                loaded_model_ids = set()
                for model in models_data.get("models", []):
                    model_id = model["id"].replace("/", "_").replace(":", "_")
                    loaded_model_ids.add(model_id)

                if cached_models != loaded_model_ids:
                    issues.append(
                        f"Cache/models mismatch: cached={cached_models}, loaded={loaded_model_ids}"
                    )

            except Exception as e:
                issues.append(f"Error checking model consistency: {e}")

    if issues:
        print("  🚨 ISSUES FOUND:")
        for issue in issues:
            print(f"     ❌ {issue}")
        print("\n  💡 RECOMMENDED ACTION:")
        print("     snakemake --unlock")
        print("     snakemake --forcerun load_models load_judges load_skills")
        print("     snakemake afbench --profile profiles/test")
    else:
        print("  ✅ Pipeline appears healthy")
        print("  💡 SAFE TO RUN:")
        print("     snakemake afbench --profile profiles/test")


if __name__ == "__main__":
    analyze_cache_state()
    check_pipeline_health()
    print("\n" + "=" * 50)
