import json
from pathlib import Path

import jsonschema
import pandas as pd

# JSON Schema for validation based on EvalConfigTiny
EVAL_SCHEMA = {
    "title": "EvalConfigTiny",
    "type": "object",
    "required": ["id", "name", "chain", "judge"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "chain": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "prompt"],
                "properties": {
                    "id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "inputs": {"type": "object"},
                    "depends_on": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                    "carry": {"type": "string", "enum": ["full", "final", "none"]},
                },
                "additionalProperties": False,
            },
        },
        "intermediaries": {
            "type": "array",
            "description": "Optional middle stages; not part of chain or judge themselves.",
            "items": {
                "type": "object",
                "required": ["id", "prompt"],
                "properties": {
                    "id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "inputs": {"type": "object"},
                    "from": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["step", "part", "as"],
                            "properties": {
                                "step": {"type": "string", "description": "chain step id"},
                                "part": {"type": "string", "enum": ["final", "history"]},
                                "as": {"type": "string", "description": "variable name exposed to the prompt"},
                            },
                            "additionalProperties": False,
                        },
                    },
                },
                "additionalProperties": False,
            },
        },
        "judge": {
            "type": "object",
            "required": ["prompt", "view"],
            "properties": {
                "system": {"type": "string"},
                "prompt": {"type": "string", "description": "Use {{A}} and {{B}} placeholders."},
                "view": {
                    "type": "object",
                    "required": ["A", "B"],
                    "properties": {"A": {"$ref": "#/$defs/ViewList"}, "B": {"$ref": "#/$defs/ViewList"}},
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
    },
    "$defs": {
        "ViewList": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["kind", "id", "part"],
                "properties": {
                    "kind": {"type": "string", "enum": ["step", "intermediary"]},
                    "id": {"type": "string", "description": "step id (from chain) or intermediary id"},
                    "part": {"type": "string", "enum": ["final", "history"]},
                    "label": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }
    },
    "additionalProperties": False,
}


def validate_eval_json(eval_data, eval_path):
    """Validate eval JSON against schema - fail fast on validation errors"""
    try:
        jsonschema.validate(eval_data, EVAL_SCHEMA)
        return True
    except jsonschema.ValidationError as e:
        error_msg = f"Validation error in {eval_path}:\n  {e.message}"
        if e.absolute_path:
            error_msg += f"\n  Path: {' -> '.join(str(p) for p in e.absolute_path)}"
        if e.context:
            error_msg += f"\n  Context: {e.context[0].message if e.context else 'None'}"
        raise ValueError(error_msg) from e
    except Exception as e:
        raise ValueError(f"Schema validation failed for {eval_path}: {e}") from e


def load_skill_evals(skill_dir):
    """Load all eval JSON files from a skill directory - FAIL FAST ON ANY ERROR"""
    skill_name = skill_dir.name
    evals = []

    # Find all JSON files in the skill directory
    json_files = list(skill_dir.glob("*.json"))

    if not json_files:
        error_msg = f"🚨 RED ALARM: No JSON files found in skill '{skill_name}' at {skill_dir}"
        print(error_msg)
        raise ValueError(error_msg)

    print(f"📂 Processing skill '{skill_name}' with {len(json_files)} eval files...")

    for json_file in json_files:
        try:
            print(f"   📄 Loading: {json_file.name}")

            with open(json_file) as f:
                eval_data = json.load(f)

            # Validate against schema - this will raise an exception if validation fails
            validate_eval_json(eval_data, json_file)

            # Additional validation checks
            if "id" not in eval_data or not eval_data["id"]:
                raise ValueError("Eval missing required 'id' field")
            if "name" not in eval_data or not eval_data["name"]:
                raise ValueError("Eval missing required 'name' field")

            # Add metadata
            eval_data["_metadata"] = {"skill": skill_name, "file_path": str(json_file), "file_name": json_file.name}

            evals.append(eval_data)
            print(f"   ✅ Successfully loaded eval '{eval_data['id']}'")

        except json.JSONDecodeError as e:
            error_msg = f"🚨 RED ALARM: Invalid JSON in {json_file}\n   Error: {e}\n   Line: {e.lineno if hasattr(e, 'lineno') else 'Unknown'}"
            print(error_msg)
            raise ValueError(error_msg) from e
        except Exception as e:
            error_msg = f"🚨 RED ALARM: Failed to load eval {json_file}\n   Error: {e}"
            print(error_msg)
            raise ValueError(error_msg) from e

    print(f"✅ Skill '{skill_name}' loaded successfully: {len(evals)} evals")
    return evals


def analyze_eval_chain(eval_data):
    """Analyze the eval chain for statistics"""
    chain = eval_data["chain"]

    # Count steps and dependencies
    step_count = len(chain)
    dependencies = sum(1 for step in chain if step.get("depends_on"))

    # Analyze carry patterns
    carry_types = [step.get("carry", "none") for step in chain]
    carry_stats = {carry: carry_types.count(carry) for carry in set(carry_types)}

    # Check for inputs
    has_custom_inputs = any(step.get("inputs") for step in chain)

    return {
        "step_count": step_count,
        "dependencies": dependencies,
        "carry_stats": carry_stats,
        "has_custom_inputs": has_custom_inputs,
        "step_ids": [step["id"] for step in chain],
    }


def main():
    # Access Snakemake parameters
    output_path = Path(snakemake.output[0])
    skills_dir = Path(snakemake.params.get("skills_dir", "skills"))
    selected_skills = snakemake.params.get("selected_skills", None)  # None means load all

    print("🎯 ===== SKILLS & EVALS LOADING SYSTEM =====")
    print(f"📁 Skills directory: {skills_dir}")

    if not skills_dir.exists():
        error_msg = f"🚨 RED ALARM: Skills directory not found: {skills_dir}"
        print(error_msg)
        raise FileNotFoundError(error_msg)

    # Get list of skill directories
    skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]

    if selected_skills:
        # Filter to only selected skills
        missing_skills = [s for s in selected_skills if s not in [d.name for d in skill_dirs]]
        if missing_skills:
            error_msg = f"🚨 RED ALARM: Selected skills not found: {missing_skills}"
            print(error_msg)
            raise ValueError(error_msg)

        skill_dirs = [d for d in skill_dirs if d.name in selected_skills]
        print(f"🎯 Loading selected skills: {selected_skills}")
    else:
        print(f"🔍 Found {len(skill_dirs)} skill directories: {[d.name for d in skill_dirs]}")

    if not skill_dirs:
        error_msg = f"🚨 RED ALARM: No skill directories found in {skills_dir}"
        print(error_msg)
        raise ValueError(error_msg)

    # Load all evals from all skills - FAIL FAST ON ANY ERROR
    all_evals = []
    skill_summary = {}
    total_files_processed = 0

    print(f"\n🚀 Starting to process {len(skill_dirs)} skills...")

    for i, skill_dir in enumerate(skill_dirs, 1):
        print(f"\n📋 [{i}/{len(skill_dirs)}] Processing skill: {skill_dir.name}")

        try:
            skill_evals = load_skill_evals(skill_dir)
            all_evals.extend(skill_evals)
            total_files_processed += len(skill_evals)

            # Create skill summary
            skill_summary[skill_dir.name] = {
                "eval_count": len(skill_evals),
                "eval_ids": [eval_data["id"] for eval_data in skill_evals],
                "path": str(skill_dir),
            }

        except Exception as e:
            error_msg = f"🚨 RED ALARM: Critical failure in skill '{skill_dir.name}': {e}"
            print(error_msg)
            raise ValueError(error_msg) from e

    print(f"\n🔍 Analyzing {len(all_evals)} loaded evals...")

    # Validate eval ID uniqueness
    eval_ids = [eval_data["id"] for eval_data in all_evals]
    duplicate_ids = [id for id in set(eval_ids) if eval_ids.count(id) > 1]
    if duplicate_ids:
        error_msg = f"🚨 RED ALARM: Duplicate eval IDs found: {duplicate_ids}"
        print(error_msg)
        raise ValueError(error_msg)

    # Analyze all evals
    eval_analysis = {}
    for eval_data in all_evals:
        try:
            eval_analysis[eval_data["id"]] = analyze_eval_chain(eval_data)
        except Exception as e:
            error_msg = f"🚨 RED ALARM: Failed to analyze eval '{eval_data['id']}': {e}"
            print(error_msg)
            raise ValueError(error_msg) from e

    # Create comprehensive summary
    summary = {
        "load_info": {
            "skills_dir": str(skills_dir),
            "total_skills": len(skill_dirs),
            "total_evals": len(all_evals),
            "total_files_processed": total_files_processed,
            "timestamp": pd.Timestamp.now().isoformat(),
            "validation_status": "ALL_PASSED",
        },
        "skills": skill_summary,
        "eval_statistics": {
            "total_steps": sum(analysis["step_count"] for analysis in eval_analysis.values()),
            "avg_steps_per_eval": (
                sum(analysis["step_count"] for analysis in eval_analysis.values()) / len(all_evals) if all_evals else 0
            ),
            "evals_with_dependencies": sum(1 for analysis in eval_analysis.values() if analysis["dependencies"] > 0),
            "evals_with_custom_inputs": sum(1 for analysis in eval_analysis.values() if analysis["has_custom_inputs"]),
        },
        "eval_analysis": eval_analysis,
        "evals": all_evals,
    }

    # Save loaded skills data
    try:
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"💾 Skills data saved to {output_path}")
    except Exception as e:
        error_msg = f"🚨 RED ALARM: Failed to save skills data to {output_path}: {e}"
        print(error_msg)
        raise ValueError(error_msg) from e

    # Print comprehensive success summary
    print("\n🎉 ===== LOADING COMPLETE - ALL SYSTEMS GREEN =====")
    print(f"✅ Total skills processed: {len(skill_dirs)}")
    print(f"✅ Total evals loaded: {len(all_evals)}")
    print(f"✅ Total files processed: {total_files_processed}")
    print(f"✅ Skills loaded: {', '.join(skill_summary.keys())}")
    print(f"✅ Average steps per eval: {summary['eval_statistics']['avg_steps_per_eval']:.1f}")
    print(f"✅ Evals with dependencies: {summary['eval_statistics']['evals_with_dependencies']}")
    print("✅ All schema validations: PASSED")
    print("✅ All eval IDs: UNIQUE")
    print("✅ No critical errors detected")
    print("🚀 Ready for benchmarking!")


if __name__ == "__main__":
    main()
