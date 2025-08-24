"""Generate final results JSON with all skills in EvalConfigTiny format."""

import json
import os
from pathlib import Path
from typing import Any


class FinalResultsGenerator:
    """Handles generation of final results from loaded skills data."""

    def load_individual_skill_files(
        self, loaded_skills_data: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Load individual skill configuration files.

        Args:
            loaded_skills_data: The loaded skills summary data

        Returns:
            Dict mapping skill eval_id to skill configuration

        Raises:
            FileNotFoundError: If a skill file is not found
            json.JSONDecodeError: If a skill file contains invalid JSON
        """
        skills = {}

        for _skill_category, skill_info in loaded_skills_data.get("skills", {}).items():
            skill_path = Path(skill_info["path"])

            for eval_id in skill_info.get("eval_ids", []):
                skill_file = skill_path / f"{eval_id}.json"

                if not skill_file.exists():
                    raise FileNotFoundError(f"Skill file not found: {skill_file}")

                with open(skill_file) as f:
                    skill_config = json.load(f)
                    skills[eval_id] = skill_config

        return skills

    def validate_evalconfig_schema(self, skill: dict[str, Any]) -> bool:
        """Validate that a skill configuration matches EvalConfigTiny schema.

        Args:
            skill: The skill configuration to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required top-level fields
            required_fields = ["id", "name", "chain", "judge"]
            for field in required_fields:
                if field not in skill:
                    return False

            # Validate chain structure
            if not isinstance(skill["chain"], list) or len(skill["chain"]) < 1:
                return False

            for step in skill["chain"]:
                if not isinstance(step, dict):
                    return False
                if "id" not in step or "prompt" not in step:
                    return False

            # Validate judge structure
            judge = skill["judge"]
            if not isinstance(judge, dict):
                return False
            if "prompt" not in judge or "view" not in judge:
                return False

            # Validate judge view structure
            view = judge["view"]
            if not isinstance(view, dict):
                return False
            if "A" not in view or "B" not in view:
                return False

            # Validate intermediaries structure if present
            if "intermediaries" in skill:
                intermediaries = skill["intermediaries"]
                if not isinstance(intermediaries, list):
                    return False

                for intermediary in intermediaries:
                    if not isinstance(intermediary, dict):
                        return False
                    if "id" not in intermediary or "prompt" not in intermediary:
                        return False

            return True

        except (TypeError, KeyError):
            return False

    def generate_final_results(
        self, loaded_skills_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Generate final results by aggregating all skill configurations.

        Args:
            loaded_skills_data: The loaded skills summary data

        Returns:
            List of skill configurations in EvalConfigTiny format

        Raises:
            ValueError: If any skill fails schema validation
        """
        # Load all individual skill files
        skills = self.load_individual_skill_files(loaded_skills_data)

        # Validate each skill against the schema
        validated_skills = []
        for skill_id, skill_config in skills.items():
            if not self.validate_evalconfig_schema(skill_config):
                raise ValueError(
                    f"Skill '{skill_id}' does not match EvalConfigTiny schema"
                )
            validated_skills.append(skill_config)

        return validated_skills


def main():
    """Main function for Snakemake integration."""
    if "snakemake" in globals():
        # Called by Snakemake
        skills_path = Path(snakemake.input.skills)
        output_path = Path(snakemake.output[0])
    else:
        # Called directly - MUST provide data_dir via environment variable
        data_dir_env = os.getenv("AFBENCH_DATA_DIR")
        if not data_dir_env:
            raise ValueError(
                "🚨 SAFETY: generate_final_results.py requires explicit data directory.\n"
                "Set AFBENCH_DATA_DIR environment variable or run via Snakemake."
            )

        data_dir = Path(data_dir_env)
        skills_path = data_dir / "loaded_skills.json"
        output_path = data_dir / "final_results.json"

    print("Generating final results from loaded skills...")

    # Load input data
    with open(skills_path) as f:
        loaded_skills_data = json.load(f)

    # Generate final results
    generator = FinalResultsGenerator()
    final_results = generator.generate_final_results(loaded_skills_data)

    # Save final results
    with open(output_path, "w") as f:
        json.dump(final_results, f, indent=2)

    print(f"Generated final results with {len(final_results)} skills")
    print(f"Saved final results to {output_path}")


if __name__ == "__main__":
    main()
