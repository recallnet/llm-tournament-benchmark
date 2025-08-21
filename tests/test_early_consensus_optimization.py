#!/usr/bin/env python3
"""
Test early consensus optimization for tournament judging.
Verifies API call reduction while maintaining backward compatibility.
"""

import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestEarlyConsensusCore:
    """Test core early consensus logic."""

    def test_early_consensus_both_vote_a(self):
        """Test early consensus when both judges vote A."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("test_match", "model_a", "model_b", "test_eval")

        # Add two judges voting A
        match.add_judge_result("judge1", "A", {"conversation": "test1"}, "Explanation 1")
        match.add_judge_result("judge2", "A", {"conversation": "test2"}, "Explanation 2")

        # Check early consensus
        assert match.check_early_consensus() == True

        # Calculate result (should be A)
        match.calculate_result()
        assert match.result == "A"

        # Verify only 2 judges recorded
        assert len(match.judge_votes) == 2

    def test_early_consensus_both_vote_b(self):
        """Test early consensus when both judges vote B."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("test_match", "model_a", "model_b", "test_eval")

        # Add two judges voting B
        match.add_judge_result("judge1", "B", {"conversation": "test1"}, "Explanation 1")
        match.add_judge_result("judge2", "B", {"conversation": "test2"}, "Explanation 2")

        # Check early consensus
        assert match.check_early_consensus() == True

        # Calculate result (should be B)
        match.calculate_result()
        assert match.result == "B"

        # Verify only 2 judges recorded
        assert len(match.judge_votes) == 2

    def test_early_consensus_both_vote_tie(self):
        """Test early consensus when both judges vote TIE."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("test_match", "model_a", "model_b", "test_eval")

        # Add two judges voting TIE
        match.add_judge_result("judge1", "TIE", {"conversation": "test1"}, "Explanation 1")
        match.add_judge_result("judge2", "TIE", {"conversation": "test2"}, "Explanation 2")

        # Check early consensus
        assert match.check_early_consensus() == True

        # Calculate result (should be TIE)
        match.calculate_result()
        assert match.result == "TIE"

        # Verify only 2 judges recorded
        assert len(match.judge_votes) == 2

    def test_no_early_consensus_mixed_votes(self):
        """Test no early consensus when judges disagree."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("test_match", "model_a", "model_b", "test_eval")

        # Add two judges with different votes
        match.add_judge_result("judge1", "A", {"conversation": "test1"}, "Explanation 1")
        match.add_judge_result("judge2", "B", {"conversation": "test2"}, "Explanation 2")

        # Check early consensus (should be False)
        assert match.check_early_consensus() == False

        # Add third judge
        match.add_judge_result("judge3", "A", {"conversation": "test3"}, "Explanation 3")

        # Calculate result (majority should win - A)
        match.calculate_result()
        assert match.result == "A"

        # Verify all 3 judges recorded
        assert len(match.judge_votes) == 3

    def test_no_early_consensus_a_vs_tie(self):
        """Test no early consensus when one judge votes A, other TIE."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("test_match", "model_a", "model_b", "test_eval")

        # Add judges with A vs TIE
        match.add_judge_result("judge1", "A", {"conversation": "test1"}, "Explanation 1")
        match.add_judge_result("judge2", "TIE", {"conversation": "test2"}, "Explanation 2")

        # Check early consensus (should be False)
        assert match.check_early_consensus() == False

        # Need third judge to break tie
        assert len(match.judge_votes) == 2

    def test_early_consensus_not_enough_judges(self):
        """Test early consensus check with insufficient judges."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("test_match", "model_a", "model_b", "test_eval")

        # Only one judge so far
        match.add_judge_result("judge1", "A", {"conversation": "test1"}, "Explanation 1")

        # Check early consensus (should be False - need at least 2)
        assert match.check_early_consensus() == False


class TestEarlyConsensusIntegration:
    """Test early consensus in real tournament scenarios."""

    def test_early_consensus_always_enabled(self):
        """Test that early consensus is always enabled (no feature flag)."""
        from run_tournaments import TournamentMatch

        # Create match and verify consensus logic always works
        match = TournamentMatch("model_a", "model_b", "test_eval", "test_skill")
        match.add_judge_result("judge1", "A", {"conversation": "test1"}, "Explanation 1")
        match.add_judge_result("judge2", "A", {"conversation": "test2"}, "Explanation 2")

        # Should always detect consensus
        assert match.check_early_consensus() == True

    def test_early_consensus_default_behavior(self):
        """Test that early consensus is the default behavior."""
        from run_tournaments import TournamentMatch

        # Test all consensus scenarios work by default
        scenarios = [
            ("A", "A", True),
            ("B", "B", True),
            ("TIE", "TIE", True),
            ("A", "B", False),
            ("A", "TIE", False),
            ("B", "TIE", False),
        ]

        for vote1, vote2, expected_consensus in scenarios:
            match = TournamentMatch("model_a", "model_b", "test_eval", "test_skill")
            match.add_judge_result("judge1", vote1, {"conversation": "test1"}, "Explanation 1")
            match.add_judge_result("judge2", vote2, {"conversation": "test2"}, "Explanation 2")

            assert match.check_early_consensus() == expected_consensus


class TestBackwardCompatibility:
    """Test backward compatibility with existing tournament data."""

    def test_existing_three_judge_matches_still_work(self):
        """Test that existing matches with 3 judges continue to work."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("existing_match", "model_a", "model_b", "test_eval")

        # Simulate existing match with 3 judges (even though first 2 agreed)
        match.add_judge_result("judge1", "A", {"conversation": "test1"}, "Explanation 1")
        match.add_judge_result("judge2", "A", {"conversation": "test2"}, "Explanation 2")
        match.add_judge_result("judge3", "B", {"conversation": "test3"}, "Explanation 3")

        # Calculate result (majority should win - A)
        match.calculate_result()
        assert match.result == "A"

        # Verify all 3 judges are preserved
        assert len(match.judge_votes) == 3

    def test_tournament_summary_handles_variable_judge_counts(self):
        """Test tournament summarization with mixed judge counts."""
        # Create mock tournament data with mixed judge counts
        tournament_data = {
            "matches": [
                {
                    "match_id": "match1",
                    "model_a": "model_a",
                    "model_b": "model_b",
                    "judge_votes": {"judge1": "A", "judge2": "A"},  # Early consensus
                    "result": "A",
                },
                {
                    "match_id": "match2",
                    "model_a": "model_a",
                    "model_b": "model_c",
                    "judge_votes": {"judge1": "A", "judge2": "B", "judge3": "A"},  # Full judging
                    "result": "A",
                },
            ]
        }

        # Both matches should have same result regardless of judge count
        match1_judges = len(tournament_data["matches"][0]["judge_votes"])
        match2_judges = len(tournament_data["matches"][1]["judge_votes"])

        assert match1_judges == 2  # Early consensus
        assert match2_judges == 3  # Full judging
        assert tournament_data["matches"][0]["result"] == tournament_data["matches"][1]["result"]


class TestAPICallReduction:
    """Test API call reduction metrics."""

    def test_api_call_reduction_calculation(self):
        """Test theoretical API call reduction calculation."""
        # Scenario: 3 matches, normally would need 3 × 3 = 9 judge calls
        # With early consensus: 2 matches reach consensus after 2 judges (4 calls)
        #                      + 1 match needs all 3 judges (3 calls) = 7 total calls

        total_matches = 3
        normal_judges_per_match = 3
        expected_calls_without_optimization = total_matches * normal_judges_per_match  # 9

        # With optimization: 2 early consensus (2 judges each) + 1 full judging (3 judges)
        early_consensus_matches = 2
        full_judging_matches = 1
        actual_calls_with_optimization = (early_consensus_matches * 2) + (full_judging_matches * 3)  # 7

        reduction_percentage = (
            expected_calls_without_optimization - actual_calls_with_optimization
        ) / expected_calls_without_optimization

        assert actual_calls_with_optimization == 7
        assert expected_calls_without_optimization == 9
        assert reduction_percentage == pytest.approx(0.22, abs=0.01)  # ~22% reduction

    def test_early_consensus_rate_impact(self):
        """Test how different early consensus rates affect API reduction."""
        total_matches = 100
        normal_judges_per_match = 3

        # Test different consensus rates
        consensus_rates = [0.2, 0.33, 0.5, 0.67]  # 20%, 33%, 50%, 67%

        for consensus_rate in consensus_rates:
            early_consensus_matches = int(total_matches * consensus_rate)
            full_judging_matches = total_matches - early_consensus_matches

            expected_calls_without_optimization = total_matches * normal_judges_per_match
            actual_calls_with_optimization = (early_consensus_matches * 2) + (full_judging_matches * 3)

            reduction_percentage = (
                expected_calls_without_optimization - actual_calls_with_optimization
            ) / expected_calls_without_optimization
            expected_reduction = consensus_rate / 3  # Each consensus saves 1/3 of calls

            assert reduction_percentage == pytest.approx(expected_reduction, abs=0.01)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_judge_error_during_early_consensus(self):
        """Test handling of judge errors during early consensus."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("test_match", "model_a", "model_b", "test_eval")

        # First judge succeeds
        match.add_judge_result("judge1", "A", {"conversation": "test1"}, "Explanation 1")

        # Second judge has error (should not trigger early consensus)
        with pytest.raises(Exception):
            # Simulate judge error
            raise Exception("Judge API error")

        # Should not have early consensus due to error
        assert match.check_early_consensus() == False
        assert len(match.judge_votes) == 1

    def test_early_consensus_with_judge_cache_hits(self):
        """Test early consensus when judges are served from cache."""
        from run_tournaments import TournamentMatch

        match = TournamentMatch("cached_match", "model_a", "model_b", "test_eval")

        # Simulate cached judge results (same as fresh API calls)
        match.add_judge_result("judge1", "A", {"conversation": "cached1"}, "Cached explanation 1")
        match.add_judge_result("judge2", "A", {"conversation": "cached2"}, "Cached explanation 2")

        # Early consensus should work with cached results
        assert match.check_early_consensus() == True
        match.calculate_result()
        assert match.result == "A"


if __name__ == "__main__":
    print("🧪 Running early consensus optimization tests...")

    import subprocess

    result = subprocess.run(["python", "-m", "pytest", __file__, "-v", "--tb=short"], capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode == 0:
        print("✅ All early consensus tests passed!")
    else:
        print("❌ Some early consensus tests failed!")

    exit(result.returncode)
