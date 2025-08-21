#!/usr/bin/env python3
"""
Tournament Restart Detection - Fix the restart loop bug

The core issue: Tournament system was config-driven (only processes skills in loaded_skills.json)
but should be data-driven (process any skills that have conversations but no tournaments).

This fixes the restart loop where:
1. Pipeline processes all conversations
2. Completes tournaments for one skill
3. Fails on next step
4. On restart, doesn't see remaining work because config was changed
"""

import json
from pathlib import Path
from typing import Set


class TournamentRestartDetector:
    """Detects unprocessed tournament work from filesystem state."""

    def __init__(self, conversations_dir: Path, tournaments_file: Path):
        self.conversations_dir = conversations_dir
        self.tournaments_file = tournaments_file

    def get_skills_with_conversations(self) -> Set[str]:
        """Find all skills that have conversation files."""
        skills_with_conversations = set()

        if not self.conversations_dir.exists():
            return skills_with_conversations

        for skill_dir in self.conversations_dir.iterdir():
            if skill_dir.is_dir():
                # Check if skill directory has any conversation files
                conv_files = list(skill_dir.glob("*.json"))
                if conv_files:
                    skills_with_conversations.add(skill_dir.name)

        return skills_with_conversations

    def get_skills_with_tournaments(self) -> Set[str]:
        """Find all skills that have completed tournaments."""
        skills_with_tournaments = set()

        if not self.tournaments_file.exists():
            return skills_with_tournaments

        try:
            with open(self.tournaments_file) as f:
                tournaments_data = json.load(f)

            for tournament in tournaments_data.get("tournaments", []):
                skill_id = tournament.get("skill_id")
                if skill_id:
                    skills_with_tournaments.add(skill_id)

        except (json.JSONDecodeError, OSError):
            # If file is corrupted, assume no tournaments completed
            pass

        return skills_with_tournaments

    def get_unprocessed_skills(self) -> Set[str]:
        """
        Find skills that have conversations but no tournaments.

        This is the key detection that fixes the restart loop bug.
        """
        conversations_skills = self.get_skills_with_conversations()
        tournament_skills = self.get_skills_with_tournaments()

        unprocessed = conversations_skills - tournament_skills
        return unprocessed

    def should_run_tournaments(self) -> bool:
        """Determine if tournament system should run based on unprocessed work."""
        unprocessed_skills = self.get_unprocessed_skills()
        return len(unprocessed_skills) > 0

    def get_restart_status(self) -> dict:
        """Get detailed status for debugging restart issues."""
        conversations_skills = self.get_skills_with_conversations()
        tournament_skills = self.get_skills_with_tournaments()
        unprocessed_skills = self.get_unprocessed_skills()

        return {
            "conversations_skills": sorted(list(conversations_skills)),
            "tournament_skills": sorted(list(tournament_skills)),
            "unprocessed_skills": sorted(list(unprocessed_skills)),
            "total_conversations_skills": len(conversations_skills),
            "total_tournament_skills": len(tournament_skills),
            "total_unprocessed": len(unprocessed_skills),
            "should_run_tournaments": self.should_run_tournaments(),
            "restart_detection_working": len(unprocessed_skills) > 0 or len(conversations_skills) == 0,
        }


def detect_tournament_restart_work(conversations_dir: str, tournaments_file: str) -> dict:
    """
    Main function to detect if tournament work needs to be done.

    This replaces the broken config-driven approach with data-driven detection.
    """
    detector = TournamentRestartDetector(Path(conversations_dir), Path(tournaments_file))

    return detector.get_restart_status()


def main():
    """CLI interface for debugging tournament restart detection."""
    import sys

    conversations_dir = sys.argv[1] if len(sys.argv) > 1 else "data/conversations"
    tournaments_file = sys.argv[2] if len(sys.argv) > 2 else "data/tournaments.json"

    status = detect_tournament_restart_work(conversations_dir, tournaments_file)

    print("🔍 Tournament Restart Detection Status:")
    print("=" * 50)
    print(f"📁 Conversations directory: {conversations_dir}")
    print(f"🏆 Tournaments file: {tournaments_file}")
    print()
    print(f"Skills with conversations: {status['conversations_skills']}")
    print(f"Skills with tournaments: {status['tournament_skills']}")
    print(f"Unprocessed skills: {status['unprocessed_skills']}")
    print()
    print(f"Total conversations skills: {status['total_conversations_skills']}")
    print(f"Total tournament skills: {status['total_tournament_skills']}")
    print(f"Total unprocessed: {status['total_unprocessed']}")
    print()
    print(f"Should run tournaments: {status['should_run_tournaments']}")
    print(f"Restart detection working: {status['restart_detection_working']}")

    if status["total_unprocessed"] > 0:
        print("\n⚠️  TOURNAMENT RESTART NEEDED")
        print(f"   {status['total_unprocessed']} skills need tournament processing")
    else:
        print("\n✅ NO TOURNAMENT RESTART NEEDED")
        print("   All skills with conversations have completed tournaments")


if __name__ == "__main__":
    main()
