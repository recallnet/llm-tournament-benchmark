"""
TDD tests to detect why tournaments are only generated for harm_avoidance skill.

These tests verify that the tournament system generates tournaments for ALL skills
and ALL evals, not just a subset.
"""

import json
import tempfile
from pathlib import Path

import pytest


class TestTournamentGenerationCoverage:
    """Test complete tournament generation across all skills."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.tournaments_file = Path(self.temp_dir) / "tournaments.json"

        # Expected skills based on actual skill directory structure
        self.expected_skills = [
            "harm_avoidance",
            "hidden_messages",
            "document_summarization",
            "empathy",
            "respect_no_em_dash_requests",
            "code_generation",
            "persuasiveness",
            "ethical_loopholes",
        ]

        # Expected eval counts per skill (approximate)
        self.expected_eval_counts = {
            "harm_avoidance": 5,
            "hidden_messages": 10,
            "document_summarization": 5,
            "empathy": 7,
            "respect_no_em_dash_requests": 3,
            "code_generation": 7,
            "persuasiveness": 5,
            "ethical_loopholes": 3,
        }

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_tournaments_generated_for_all_skills(self):
        """Test that tournaments are generated for ALL 8 skills, not just harm_avoidance."""
        print("\n🎯 TESTING: Tournaments for ALL skills")

        # Load actual tournament results from pipeline run
        tournaments_file = Path("data/testonly/tournaments.json")

        if not tournaments_file.exists():
            pytest.skip("No tournaments.json found - run pipeline first")

        with open(tournaments_file) as f:
            tournaments_data = json.load(f)

        tournaments = tournaments_data.get("tournaments", [])

        # Extract unique skills from tournament results
        found_skills = set()
        if isinstance(tournaments, list):
            for tournament in tournaments:
                skill_id = tournament.get("skill_id")
                if skill_id:
                    found_skills.add(skill_id)
        elif isinstance(tournaments, dict):
            # Handle dict format
            found_skills = set(tournaments.keys())

        print(f"   Expected skills: {sorted(self.expected_skills)}")
        print(f"   Found skills: {sorted(found_skills)}")

        # This test will FAIL and show us exactly which skills are missing
        missing_skills = set(self.expected_skills) - found_skills
        extra_skills = found_skills - set(self.expected_skills)

        if missing_skills:
            print(f"   ❌ Missing skills: {sorted(missing_skills)}")
        if extra_skills:
            print(f"   ⚠️  Extra skills: {sorted(extra_skills)}")

        assert not missing_skills, f"Missing tournaments for skills: {sorted(missing_skills)}"
        assert len(found_skills) == len(
            self.expected_skills
        ), f"Expected {len(self.expected_skills)} skills, got {len(found_skills)}"

        print("   ✅ All skills have tournaments")

    def test_tournament_eval_coverage_per_skill(self):
        """Test that each skill has tournaments for all its evals."""
        print("\n📊 TESTING: Tournament eval coverage per skill")

        tournaments_file = Path("data/testonly/tournaments.json")

        if not tournaments_file.exists():
            pytest.skip("No tournaments.json found - run pipeline first")

        with open(tournaments_file) as f:
            tournaments_data = json.load(f)

        tournaments = tournaments_data.get("tournaments", [])

        # Group tournaments by skill
        tournaments_by_skill = {}
        if isinstance(tournaments, list):
            for tournament in tournaments:
                skill_id = tournament.get("skill_id")
                if skill_id not in tournaments_by_skill:
                    tournaments_by_skill[skill_id] = []
                tournaments_by_skill[skill_id].append(tournament)

        # Check eval coverage for each skill
        for skill in self.expected_skills:
            if skill not in tournaments_by_skill:
                print(f"   ❌ No tournaments found for skill: {skill}")
                continue

            skill_tournaments = tournaments_by_skill[skill]
            eval_ids = {t.get("eval_id") for t in skill_tournaments}

            print(f"   📝 {skill}: {len(eval_ids)} evals")

            # We expect multiple evals per skill
            expected_min_evals = self.expected_eval_counts.get(skill, 1)
            assert (
                len(eval_ids) >= expected_min_evals
            ), f"Skill {skill} has only {len(eval_ids)} evals, expected at least {expected_min_evals}"

        print("   ✅ All skills have adequate eval coverage")

    def test_tournament_structure_consistency(self):
        """Test that tournament data structure is consistent across all skills."""
        print("\n🏗️  TESTING: Tournament structure consistency")

        tournaments_file = Path("data/testonly/tournaments.json")

        if not tournaments_file.exists():
            pytest.skip("No tournaments.json found - run pipeline first")

        with open(tournaments_file) as f:
            tournaments_data = json.load(f)

        tournaments = tournaments_data.get("tournaments", [])

        if not tournaments:
            pytest.fail("No tournaments found in tournaments.json")

        # Test structure of each tournament
        required_fields = ["tournament_id", "skill_id", "eval_id", "model_ids", "rounds", "scores", "completed"]

        for i, tournament in enumerate(tournaments):
            print(f"   🔍 Tournament {i+1}: {tournament.get('skill_id', 'UNKNOWN')}/{tournament.get('eval_id', 'UNKNOWN')}")

            for field in required_fields:
                assert field in tournament, f"Tournament {i} missing required field: {field}"

            # Check that tournament has actual match data
            rounds = tournament.get("rounds", [])
            assert len(rounds) > 0, f"Tournament {i} has no rounds"

            # Check that each round has matches
            for round_num, round_matches in enumerate(rounds):
                assert len(round_matches) > 0, f"Tournament {i} round {round_num} has no matches"

        print("   ✅ All tournaments have consistent structure")

    def test_missing_skills_root_cause_detection(self):
        """Detect why certain skills might be missing from tournament generation."""
        print("\n🔍 TESTING: Root cause analysis for missing skills")

        # Load actual skills data
        skills_file = Path("data/testonly/loaded_skills.json")

        if not skills_file.exists():
            pytest.skip("No loaded_skills.json found")

        with open(skills_file) as f:
            skills_data = json.load(f)

        evals = skills_data.get("evals", [])

        # Group evals by skill
        evals_by_skill = {}
        for eval_data in evals:
            skill_id = eval_data.get("_metadata", {}).get("skill")
            if skill_id:
                if skill_id not in evals_by_skill:
                    evals_by_skill[skill_id] = []
                evals_by_skill[skill_id].append(eval_data)

        print(f"   📋 Skills found in loaded_skills.json: {sorted(evals_by_skill.keys())}")

        # Compare with expected skills
        missing_from_loaded = set(self.expected_skills) - set(evals_by_skill.keys())
        if missing_from_loaded:
            print(f"   ⚠️  Skills missing from loaded_skills.json: {sorted(missing_from_loaded)}")

        # Now check if tournaments exist for loaded skills
        tournaments_file = Path("data/testonly/tournaments.json")
        if tournaments_file.exists():
            with open(tournaments_file) as f:
                tournaments_data = json.load(f)

            tournaments = tournaments_data.get("tournaments", [])
            tournament_skills = {t.get("skill_id") for t in tournaments if isinstance(tournaments, list)}

            loaded_but_no_tournaments = set(evals_by_skill.keys()) - tournament_skills
            if loaded_but_no_tournaments:
                print(f"   🚨 Skills loaded but NO tournaments generated: {sorted(loaded_but_no_tournaments)}")
                print("      This indicates a problem in the tournament generation logic!")

                # This is likely the root cause - skills are loaded but tournaments aren't generated
                pytest.fail(f"Tournament generation failed for loaded skills: {sorted(loaded_but_no_tournaments)}")

        print("   ✅ Root cause analysis complete")

    def test_conversation_cache_availability_for_all_skills(self):
        """Test that conversation cache exists for all skills."""
        print("\n💾 TESTING: Conversation cache availability for all skills")

        conversations_dir = Path("data/testonly/conversations")

        if not conversations_dir.exists():
            pytest.skip("No conversations cache directory found")

        # Check which skills have cached conversations
        cached_skills = []
        for skill_dir in conversations_dir.iterdir():
            if skill_dir.is_dir():
                # Count conversation files in this skill
                conversation_files = list(skill_dir.glob("*.json"))
                if conversation_files:
                    cached_skills.append(skill_dir.name)
                    print(f"   📁 {skill_dir.name}: {len(conversation_files)} cached conversations")

        missing_cache = set(self.expected_skills) - set(cached_skills)
        if missing_cache:
            print(f"   ❌ Skills with no cached conversations: {sorted(missing_cache)}")
            # This could explain why tournaments aren't generated

        print(f"   💾 Skills with cached conversations: {sorted(cached_skills)}")

        # If we have cached conversations but no tournaments, that's the problem
        tournaments_file = Path("data/testonly/tournaments.json")
        if tournaments_file.exists():
            with open(tournaments_file) as f:
                tournaments_data = json.load(f)

            tournaments = tournaments_data.get("tournaments", [])
            tournament_skills = {t.get("skill_id") for t in tournaments if isinstance(tournaments, list)}

            cached_but_no_tournaments = set(cached_skills) - tournament_skills
            if cached_but_no_tournaments:
                print(f"   🚨 CRITICAL: Skills with cache but NO tournaments: {sorted(cached_but_no_tournaments)}")
                print("      This confirms the tournament generation is broken!")

        print("   ✅ Cache availability check complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
