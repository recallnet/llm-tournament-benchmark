"""
TDD tests for cache invalidation scenarios and pipeline recovery.

Tests that the pipeline can handle various invalidation states and only
regenerate what's needed to get to a valid final state.
"""

from pathlib import Path

import pytest


class TestCacheInvalidationRecovery:
    """Test cache invalidation scenarios and pipeline recovery."""

    def setup_method(self):
        """Set up test state tracking."""
        self.pipeline_files = {
            "inputs": [
                "data/testonly/loaded_models.json",
                "data/testonly/loaded_judges.json",
                "data/testonly/loaded_skills.json",
            ],
            "cache_markers": [
                "data/testonly/conversations_cache_thedrummer_unslopnemo-12b.done",
                "data/testonly/conversations_cache_openai_gpt-oss-120b.done",
                "data/testonly/conversations_cache_inception_mercury.done",
                "data/testonly/conversations_cache_openai_gpt-oss-20b.done",
            ],
            "outputs": [
                "data/testonly/tournaments.json",
                "data/testonly/tournament_summaries.json",
                "data/testonly/skill_ratings.json",
            ],
            "caches": ["data/testonly/conversations/", "data/testonly/tournaments/"],
        }

    def get_file_states(self, file_paths):
        """Get current state of files (exists, mtime, size)."""
        states = {}
        for file_path in file_paths:
            path = Path(file_path)
            if path.exists():
                if path.is_file():
                    states[file_path] = {
                        "exists": True,
                        "mtime": path.stat().st_mtime,
                        "size": path.stat().st_size,
                    }
                elif path.is_dir():
                    # For directories, get aggregate info
                    files = list(path.rglob("*"))
                    file_files = [f for f in files if f.is_file()]
                    states[file_path] = {
                        "exists": True,
                        "mtime": (
                            max(f.stat().st_mtime for f in file_files)
                            if file_files
                            else 0
                        ),
                        "size": sum(f.stat().st_size for f in file_files),
                        "file_count": len(file_files),
                    }
            else:
                states[file_path] = {"exists": False, "mtime": 0, "size": 0}
        return states

    def test_current_pipeline_state_assessment(self):
        """Test assessment of current pipeline state to identify what needs regeneration."""
        print("\n🔍 TESTING: Current pipeline state assessment")

        all_files = (
            self.pipeline_files["inputs"]
            + self.pipeline_files["cache_markers"]
            + self.pipeline_files["outputs"]
            + self.pipeline_files["caches"]
        )

        states = self.get_file_states(all_files)

        # Categorize files by status
        missing_files = [f for f, s in states.items() if not s["exists"]]
        existing_files = [f for f, s in states.items() if s["exists"]]

        print("   📊 File Status Summary:")
        print(f"   ✅ Existing: {len(existing_files)}")
        print(f"   ❌ Missing: {len(missing_files)}")

        # Check specific categories
        missing_inputs = [
            f for f in self.pipeline_files["inputs"] if not states[f]["exists"]
        ]
        missing_markers = [
            f for f in self.pipeline_files["cache_markers"] if not states[f]["exists"]
        ]
        missing_outputs = [
            f for f in self.pipeline_files["outputs"] if not states[f]["exists"]
        ]

        print(f"   Missing inputs: {len(missing_inputs)}")
        print(f"   Missing cache markers: {len(missing_markers)}")
        print(f"   Missing outputs: {len(missing_outputs)}")

        # Identify what needs to be regenerated
        needs_regeneration = []

        if missing_inputs:
            needs_regeneration.append("Load phase (models/judges/skills)")

        if missing_markers:
            needs_regeneration.append("Conversation execution phase")

        if missing_outputs:
            needs_regeneration.append("Tournament/rating calculation phase")

        print(f"   🎯 Phases needing regeneration: {needs_regeneration}")

        # Check for inconsistent states
        inconsistencies = []

        # If markers exist but no outputs, tournaments failed
        if not missing_markers and missing_outputs:
            inconsistencies.append(
                "Conversation cache complete but tournaments missing"
            )

        # If outputs exist without inputs, impossible state
        if not missing_outputs and missing_inputs:
            inconsistencies.append("Outputs exist without inputs")

        # If downstream exists without upstream
        tournaments_exists = states["data/testonly/tournaments.json"]["exists"]
        summaries_exists = states["data/testonly/tournament_summaries.json"]["exists"]
        ratings_exists = states["data/testonly/skill_ratings.json"]["exists"]

        if summaries_exists and not tournaments_exists:
            inconsistencies.append("Summaries exist without tournaments")
        if ratings_exists and not summaries_exists:
            inconsistencies.append("Ratings exist without summaries")

        if inconsistencies:
            print("   🚨 INCONSISTENT STATES:")
            for inconsistency in inconsistencies:
                print(f"      ⚠️  {inconsistency}")

        # This test documents the current state - it might fail until we fix the pipeline
        if missing_outputs and not missing_markers:
            pytest.fail(
                "Pipeline in broken state: cache markers exist but outputs missing"
            )

    def test_tournaments_json_only_invalidation(self):
        """Test scenario where only tournaments.json is missing/invalid."""
        print("\n🔍 TESTING: tournaments.json only invalidation scenario")

        # Check current state
        tournaments_path = Path("data/testonly/tournaments.json")
        summaries_path = Path("data/testonly/tournament_summaries.json")
        ratings_path = Path("data/testonly/skill_ratings.json")

        tournaments_exists = tournaments_path.exists()
        summaries_exists = summaries_path.exists()
        ratings_exists = ratings_path.exists()

        print(f"   tournaments.json exists: {tournaments_exists}")
        print(f"   tournament_summaries.json exists: {summaries_exists}")
        print(f"   skill_ratings.json exists: {ratings_exists}")

        if not tournaments_exists and (summaries_exists or ratings_exists):
            print("   🎯 SCENARIO: Only tournaments.json is missing")
            print(
                "   Expected behavior: Pipeline should regenerate tournaments.json and downstream"
            )

            # Check if conversation cache is intact
            conversations_dir = Path("data/testonly/conversations")
            if conversations_dir.exists():
                conv_files = list(conversations_dir.rglob("*.json"))
                print(f"   Conversation cache: {len(conv_files)} files available")

                if len(conv_files) > 0:
                    print(
                        "   ✅ Conversation cache available for tournament regeneration"
                    )

                    # Test what Snakemake would do
                    cache_markers = self.pipeline_files["cache_markers"]
                    all_markers_exist = all(Path(m).exists() for m in cache_markers)

                    if all_markers_exist:
                        print("   ✅ All cache markers exist")
                        print(
                            "   🎯 Pipeline should regenerate tournaments.json → summaries → ratings"
                        )

                        # This represents the ideal fix
                        pytest.fail(
                            "tournaments.json missing with valid cache - pipeline should regenerate"
                        )

    def test_full_cache_invalidation_scenario(self):
        """Test scenario where all caches need to be invalidated and regenerated."""
        print("\n🔍 TESTING: Full cache invalidation scenario")

        # This tests what happens if we invalidate everything
        print("   🎯 SCENARIO: Testing complete pipeline regeneration from scratch")

        # Check if we have the basic inputs needed
        basic_inputs = [
            "data/testonly/loaded_models.json",
            "data/testonly/loaded_judges.json",
            "data/testonly/loaded_skills.json",
        ]

        inputs_available = all(Path(inp).exists() for inp in basic_inputs)
        print(f"   Basic inputs available: {inputs_available}")

        if inputs_available:
            print("   ✅ Basic inputs exist - pipeline could regenerate everything")

            # Check conversation source data
            conversations_dir = Path("data/testonly/conversations")
            if conversations_dir.exists():
                conv_files = list(conversations_dir.rglob("*.json"))
                print(f"   Conversation cache: {len(conv_files)} files")

                # Group by skill to see coverage
                skills_with_cache = set()
                for conv_file in conv_files:
                    skill = conv_file.parent.name
                    skills_with_cache.add(skill)

                print(f"   Skills with conversation cache: {sorted(skills_with_cache)}")
                expected_skills = [
                    "harm_avoidance",
                    "hidden_messages",
                    "document_summarization",
                    "empathy",
                    "respect_no_em_dash_requests",
                    "code_generation",
                    "persuasiveness",
                    "ethical_loopholes",
                ]

                missing_skills = set(expected_skills) - skills_with_cache
                if missing_skills:
                    print(
                        f"   ❌ Skills missing conversation cache: {sorted(missing_skills)}"
                    )
                else:
                    print("   ✅ All skills have conversation cache")

        print(
            "   🎯 Full regeneration test: Pipeline should be able to regenerate all outputs"
        )

    def test_partial_cache_invalidation_scenarios(self):
        """Test various partial cache invalidation scenarios."""
        print("\n🔍 TESTING: Partial cache invalidation scenarios")

        scenarios = [
            {
                "name": "Missing one cache marker",
                "missing": [
                    "data/testonly/conversations_cache_thedrummer_unslopnemo-12b.done"
                ],
                "expected": "Should regenerate conversations for one model and downstream",
            },
            {
                "name": "Missing tournament summaries only",
                "missing": ["data/testonly/tournament_summaries.json"],
                "expected": "Should regenerate summaries and ratings but keep tournaments",
            },
            {
                "name": "Missing skill ratings only",
                "missing": ["data/testonly/skill_ratings.json"],
                "expected": "Should regenerate ratings only",
            },
        ]

        for scenario in scenarios:
            print(f"\n   📋 Scenario: {scenario['name']}")

            missing_files = scenario["missing"]
            files_actually_missing = [f for f in missing_files if not Path(f).exists()]

            print(f"   Files that should be missing: {missing_files}")
            print(f"   Files actually missing: {files_actually_missing}")
            print(f"   Expected behavior: {scenario['expected']}")

            # For each scenario, document what the pipeline should do
            if files_actually_missing:
                print("   ✅ Scenario conditions met")
            else:
                print("   ❌ Scenario conditions not met (files exist)")

    def test_pipeline_dependency_chain_integrity(self):
        """Test that pipeline dependency chain is logically consistent."""
        print("\n🔍 TESTING: Pipeline dependency chain integrity")

        # Define the expected dependency chain
        dependency_chain = [
            {
                "rule": "load_models/judges/skills",
                "inputs": ["model_pools/", "judge_pools/", "skills/"],
                "outputs": [
                    "data/testonly/loaded_models.json",
                    "data/testonly/loaded_judges.json",
                    "data/testonly/loaded_skills.json",
                ],
            },
            {
                "rule": "execute_conversations_for_model",
                "inputs": [
                    "data/testonly/loaded_models.json",
                    "data/testonly/loaded_judges.json",
                    "data/testonly/loaded_skills.json",
                ],
                "outputs": [
                    "data/testonly/conversations_cache_*.done",
                    "data/testonly/conversations/",
                ],
            },
            {
                "rule": "run_tournaments",
                "inputs": [
                    "data/testonly/conversations_cache_*.done",
                    "data/testonly/loaded_*.json",
                ],
                "outputs": ["data/testonly/tournaments.json"],
            },
            {
                "rule": "summarize_tournaments",
                "inputs": ["data/testonly/tournaments.json"],
                "outputs": ["data/testonly/tournament_summaries.json"],
            },
            {
                "rule": "calculate_skill_ratings",
                "inputs": ["data/testonly/tournament_summaries.json"],
                "outputs": ["data/testonly/skill_ratings.json"],
            },
        ]

        print(f"   📊 Checking {len(dependency_chain)} dependency rules...")

        broken_dependencies = []

        for rule in dependency_chain:
            rule_name = rule["rule"]
            inputs = rule["inputs"]
            outputs = rule["outputs"]

            # Check if outputs exist without inputs (impossible)
            inputs_exist = []
            outputs_exist = []

            for inp in inputs:
                if "*" in inp:
                    # Handle wildcard patterns
                    if "conversations_cache_" in inp:
                        markers = self.pipeline_files["cache_markers"]
                        inputs_exist.append(any(Path(m).exists() for m in markers))
                    else:
                        inputs_exist.append(True)  # Assume source files exist
                else:
                    inputs_exist.append(Path(inp).exists())

            for out in outputs:
                if "*" in out:
                    if "conversations_cache_" in out:
                        markers = self.pipeline_files["cache_markers"]
                        outputs_exist.append(all(Path(m).exists() for m in markers))
                    else:
                        outputs_exist.append(True)  # Handle wildcards
                else:
                    outputs_exist.append(Path(out).exists())

            all_inputs_exist = all(inputs_exist)
            any_outputs_exist = any(outputs_exist)
            all_outputs_exist = all(outputs_exist)

            print(f"   📋 {rule_name}:")
            print(f"      Inputs exist: {all_inputs_exist}")
            print(f"      Outputs exist: {all_outputs_exist}")

            # Check for broken dependency patterns
            if any_outputs_exist and not all_inputs_exist:
                broken_dependencies.append(f"{rule_name}: outputs exist without inputs")

            if all_inputs_exist and not any_outputs_exist:
                broken_dependencies.append(f"{rule_name}: inputs exist but no outputs")

        if broken_dependencies:
            print("   🚨 BROKEN DEPENDENCIES:")
            for broken in broken_dependencies:
                print(f"      ⚠️  {broken}")

            print("   🎯 These indicate pipeline execution failures that need fixing")

    def test_atomic_cache_invalidation_design(self):
        """Test design for atomic cache invalidation to prevent inconsistent states."""
        print("\n🔍 TESTING: Atomic cache invalidation design")

        print("   🎯 DESIGN TEST: Atomic cache invalidation requirements")

        # Define atomic invalidation groups
        invalidation_groups = [
            {
                "name": "Conversation Phase",
                "files": [
                    "data/testonly/conversations/",
                    "data/testonly/conversations_cache_*.done",
                ],
                "description": "If conversations are invalid, remove all conversation cache",
            },
            {
                "name": "Tournament Phase",
                "files": [
                    "data/testonly/tournaments.json",
                    "data/testonly/tournament_summaries.json",
                    "data/testonly/skill_ratings.json",
                    "data/testonly/tournaments/",
                ],
                "description": "If tournaments are invalid, remove all tournament results",
            },
            {
                "name": "Complete Pipeline",
                "files": ["*"],
                "description": "Nuclear option: remove all generated files",
            },
        ]

        print(f"   📊 Defined {len(invalidation_groups)} atomic invalidation groups:")

        for group in invalidation_groups:
            print(f"   📋 {group['name']}:")
            print(f"      Files: {group['files']}")
            print(f"      Purpose: {group['description']}")

        # Test current state against atomic groups
        current_state = self.get_file_states(
            [
                "data/testonly/tournaments.json",
                "data/testonly/tournament_summaries.json",
                "data/testonly/skill_ratings.json",
            ]
        )

        tournaments_exists = current_state["data/testonly/tournaments.json"]["exists"]
        summaries_exists = current_state["data/testonly/tournament_summaries.json"][
            "exists"
        ]
        ratings_exists = current_state["data/testonly/skill_ratings.json"]["exists"]

        # Check if Tournament Phase group is in inconsistent state
        tournament_group_state = [tournaments_exists, summaries_exists, ratings_exists]

        if not all(tournament_group_state) and any(tournament_group_state):
            print("   🚨 ATOMIC VIOLATION: Tournament group in inconsistent state")
            print(f"   tournaments.json: {tournaments_exists}")
            print(f"   tournament_summaries.json: {summaries_exists}")
            print(f"   skill_ratings.json: {ratings_exists}")

            print("   🎯 SOLUTION: Implement atomic invalidation for Tournament Phase")
            print("   Either ALL files in group exist or NONE exist")

            pytest.fail(
                "Tournament phase files in non-atomic state - need atomic invalidation"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
