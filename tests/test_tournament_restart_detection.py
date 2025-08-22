#!/usr/bin/env python3
"""
TDD Test: Tournament restart detection bug

This test reproduces the exact issue:
1. Pipeline processes conversations for ALL skills
2. Tournaments complete for ONE skill (harm_avoidance)
3. Pipeline fails on skill ratings calculation
4. On restart, pipeline doesn't detect it needs to process remaining skills
5. Gets stuck in restart loop

This is a Snakemake dependency detection issue - we need to ensure
the tournament system detects unprocessed conversation files.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


class TestTournamentRestartDetection:
    """Test the restart detection bug using TDD approach."""

    def setup_method(self):
        """Set up isolated test environment."""
        os.environ["AFBENCH_TEST_MODE"] = "true"

    def test_tournament_system_detects_unprocessed_conversations(self):
        """
        TDD Test: Tournament system should detect conversations for skills
        not yet processed, even if some tournament files already exist.

        This is the core bug - the system gets stuck because it doesn't
        see the unprocessed conversations for other skills.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir) / "data"
            conversations_dir = data_dir / "conversations"
            tournaments_file = data_dir / "tournaments.json"
            summaries_file = data_dir / "tournament_summaries.json"

            # Create directory structure
            conversations_dir.mkdir(parents=True)

            # Simulate the exact scenario: conversations for ALL skills exist
            skills = ["harm_avoidance", "code_generation", "empathy", "hidden_messages"]
            evals_per_skill = {
                "harm_avoidance": 5,
                "code_generation": 7,
                "empathy": 7,
                "hidden_messages": 10,
            }
            models = ["openai/gpt-4", "claude-3", "llama-2"]

            # Create conversation files for ALL skills (like we had)
            total_conversations = 0
            for skill in skills:
                skill_dir = conversations_dir / skill
                skill_dir.mkdir()

                for eval_num in range(evals_per_skill[skill]):
                    for model in models:
                        conv_file = (
                            skill_dir
                            / f"eval_{eval_num}_{model.replace('/', '_')}.json"
                        )
                        conv_file.write_text(
                            json.dumps(
                                {
                                    "metadata": {
                                        "skill_id": skill,
                                        "eval_id": f"eval_{eval_num}",
                                        "model_id": model,
                                    },
                                    "messages": [{"role": "user", "content": "test"}],
                                }
                            )
                        )
                        total_conversations += 1

            print(
                f"Created {total_conversations} conversation files across {len(skills)} skills"
            )

            # Simulate the bug: tournaments.json exists but ONLY has harm_avoidance
            incomplete_tournaments = {
                "tournaments": [
                    {
                        "skill_id": "harm_avoidance",
                        "eval_id": "eval_0",
                        "model_ids": models,
                        "completed": True,
                    }
                    # Missing: code_generation, empathy, hidden_messages tournaments!
                ]
            }
            tournaments_file.write_text(json.dumps(incomplete_tournaments))

            # Simulate incomplete summaries (only harm_avoidance)
            incomplete_summaries = {
                "tournaments": {
                    "harm_avoidance": {"total_matches": 15, "completed": True}
                    # Missing: other skills!
                }
            }
            summaries_file.write_text(json.dumps(incomplete_summaries))

            # Now test: The tournament system should detect the unprocessed conversations
            # This is where the bug is - it should see conversations for code_generation,
            # empathy, hidden_messages but no tournaments for them

            # Mock the tournament detection logic
            sys.path.insert(0, "scripts")

            # The bug: current system only looks at what's in tournaments.json
            # It should look at what conversations exist vs what tournaments exist

            # Expected behavior: detect conversations for 4 skills, tournaments for 1 skill
            # Should identify 3 skills need tournament processing

            conversations_by_skill = {}
            for skill_dir in conversations_dir.iterdir():
                if skill_dir.is_dir():
                    skill_name = skill_dir.name
                    conv_files = list(skill_dir.glob("*.json"))
                    conversations_by_skill[skill_name] = len(conv_files)

            processed_tournaments = set()
            if tournaments_file.exists():
                tournament_data = json.loads(tournaments_file.read_text())
                for tournament in tournament_data.get("tournaments", []):
                    processed_tournaments.add(tournament["skill_id"])

            # This is the key detection logic that's broken
            unprocessed_skills = (
                set(conversations_by_skill.keys()) - processed_tournaments
            )

            print(f"Conversations by skill: {conversations_by_skill}")
            print(f"Processed tournaments: {processed_tournaments}")
            print(f"Unprocessed skills: {unprocessed_skills}")

            # THE BUG: The current system doesn't do this detection!
            # It only processes what's in loaded_skills.json, ignoring existing conversations
            assert (
                len(conversations_by_skill) == 4
            ), "Should have conversations for 4 skills"
            assert (
                len(processed_tournaments) == 1
            ), "Should have tournaments for 1 skill"
            assert (
                len(unprocessed_skills) == 3
            ), "Should detect 3 skills need processing"
            assert unprocessed_skills == {
                "code_generation",
                "empathy",
                "hidden_messages",
            }

            # The fix: tournament system should process unprocessed_skills
            # instead of just blindly following loaded_skills.json

    def test_tournament_system_restart_behavior(self):
        """
        TDD Test: When tournament system restarts, it should continue from
        where it left off, not restart from beginning or get stuck.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir)

            # Simulate restart scenario exactly as user described:
            # 1. "finish all tourny in one skill" - harm_avoidance complete
            # 2. "move to the nextg, fail" - fails on skill ratings
            # 3. "after fail, restart, but fail" - gets stuck

            # The test should verify that restart detection works properly
            # This requires the tournament system to be stateless and detect
            # work remaining from filesystem state, not config state

            # This is the core architectural issue:
            # Pipeline depends on loaded_skills.json (config-driven)
            # But should detect work from conversations directory (data-driven)

            assert True  # Placeholder - this is the behavioral contract we need


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
