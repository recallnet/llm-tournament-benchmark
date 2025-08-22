#!/usr/bin/env python3
"""
Test runner for tournament logic and judge consensus tests.

This script runs the tournament tests in isolation and provides detailed
output about tournament behavior and any bugs found.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_basic_tournament_generation():
    """Test basic tournament generation without full Snakemake pipeline."""
    print("=== Testing Basic Tournament Generation ===")

    # Import tournament classes directly
    sys.path.insert(0, str(project_root / "scripts"))
    from run_tournaments import SwissTournament, TournamentMatch

    # Create test models
    models = [
        {"id": f"test/model-{chr(65 + i)}", "name": f"Model {chr(65 + i)}"}
        for i in range(4)
    ]

    # Create tournament
    tournament = SwissTournament("test_skill", "test_eval", models)

    print(f"Created tournament with {len(models)} models")
    print(f"Tournament ID: {tournament.tournament_id}")
    print(f"Calculated rounds needed: {tournament._calculate_rounds_needed()}")

    # Test pairing generation
    round_0_pairings = tournament._get_pairings_for_round(0)
    print(f"Round 0 pairings: {round_0_pairings}")

    # Verify pairing constraints
    paired_models = set()
    for model_a, model_b in round_0_pairings:
        assert model_a != model_b, f"Self-pairing found: {model_a}"
        assert model_a not in paired_models, f"Duplicate model {model_a} in round"
        assert model_b not in paired_models, f"Duplicate model {model_b} in round"
        paired_models.add(model_a)
        paired_models.add(model_b)

    print("✓ Pairing constraints verified")

    # Test match creation
    if round_0_pairings:
        model_a, model_b = round_0_pairings[0]
        match = TournamentMatch(model_a, model_b, "test_eval", "test_skill")
        print(f"Created match: {match.match_id}")

        # Test judge voting
        match.add_judge_result("judge1", "A", [], "Test explanation")
        match.add_judge_result("judge2", "A", [], "Test explanation")

        # Test early consensus
        early_consensus = match.check_early_consensus()
        print(f"Early consensus check: {early_consensus}")
        assert early_consensus, "Expected early consensus with matching votes"

        # Test result calculation
        result = match.calculate_result()
        print(f"Match result: {result}")
        assert result == "A", f"Expected result A, got {result}"

        print("✓ Judge consensus logic verified")

    print("✓ Basic tournament generation test passed")


def test_judge_consensus_scenarios():
    """Test different judge consensus scenarios."""
    print("\\n=== Testing Judge Consensus Scenarios ===")

    sys.path.insert(0, str(project_root / "scripts"))
    from run_tournaments import TournamentMatch

    # Scenario 1: Early consensus (A, A)
    print("Scenario 1: Early consensus")
    match1 = TournamentMatch("model_a", "model_b", "eval1", "skill1")
    match1.add_judge_result("judge1", "A", [], "Vote A")
    match1.add_judge_result("judge2", "A", [], "Vote A")

    assert match1.check_early_consensus(), "Should have early consensus"
    result1 = match1.calculate_result()
    assert result1 == "A", f"Expected A, got {result1}"
    print("✓ Early consensus works")

    # Scenario 2: Disagreement requiring third judge (A, B, A)
    print("Scenario 2: Disagreement with third judge")
    match2 = TournamentMatch("model_a", "model_b", "eval2", "skill2")
    match2.add_judge_result("judge1", "A", [], "Vote A")
    match2.add_judge_result("judge2", "B", [], "Vote B")

    assert not match2.check_early_consensus(), "Should not have early consensus"

    match2.add_judge_result("judge3", "A", [], "Vote A")
    result2 = match2.calculate_result()
    assert result2 == "A", f"Expected A (2-1 majority), got {result2}"
    print("✓ Three-judge resolution works")

    # Scenario 3: True tie (A, B, TIE)
    print("Scenario 3: True tie resolution")
    match3 = TournamentMatch("model_a", "model_b", "eval3", "skill3")
    match3.add_judge_result("judge1", "A", [], "Vote A")
    match3.add_judge_result("judge2", "B", [], "Vote B")
    match3.add_judge_result("judge3", "TIE", [], "Vote TIE")

    result3 = match3.calculate_result()
    assert result3 == "TIE", f"Expected TIE (no clear majority), got {result3}"
    print("✓ Tie resolution works")

    print("✓ All judge consensus scenarios verified")


def test_swiss_pairing_constraints():
    """Test Swiss tournament pairing constraints."""
    print("\\n=== Testing Swiss Pairing Constraints ===")

    sys.path.insert(0, str(project_root / "scripts"))
    from run_tournaments import SwissTournament

    # Test with 6 models for multiple rounds
    models = [
        {"id": f"test/model-{chr(65 + i)}", "name": f"Model {chr(65 + i)}"}
        for i in range(6)
    ]

    tournament = SwissTournament("test_skill", "test_eval", models)

    # Simulate multiple rounds
    all_pairings = []

    for round_num in range(3):  # 3 rounds
        print(f"\\nRound {round_num}:")
        pairings = tournament._get_pairings_for_round(round_num)
        print(f"  Pairings: {pairings}")

        # Verify no self-pairings
        for model_a, model_b in pairings:
            assert model_a != model_b, f"Self-pairing in round {round_num}: {model_a}"

        # Record pairings for duplicate check
        normalized_pairings = [tuple(sorted([a, b])) for a, b in pairings]
        all_pairings.extend(normalized_pairings)

        # Simulate match results to update scores for next round
        for model_a, model_b in pairings:
            # Simulate random results for pairing algorithm
            import random

            result = random.choice(["A", "B", "TIE"])
            if result == "A":
                tournament.scores[model_a] += 1.0
            elif result == "B":
                tournament.scores[model_b] += 1.0
            else:  # TIE
                tournament.scores[model_a] += 0.5
                tournament.scores[model_b] += 0.5

        print(f"  Scores after round: {tournament.scores}")

    # Check for duplicate pairings
    pairing_counts = {}
    for pairing in all_pairings:
        pairing_counts[pairing] = pairing_counts.get(pairing, 0) + 1

    duplicates = {p: count for p, count in pairing_counts.items() if count > 1}
    if duplicates:
        print(f"❌ SWISS PAIRING BUG: Duplicate pairings found: {duplicates}")
        raise AssertionError(
            f"Swiss tournament constraint violated: duplicate pairings {duplicates}"
        )
    else:
        print("✓ No duplicate pairings (strict Swiss adherence)")

    print(f"✓ Swiss pairing test completed ({len(all_pairings)} total pairings)")


def main():
    """Run all tournament tests."""
    print("AFBench Tournament Logic & Judge Consensus Tests")
    print("=" * 50)

    try:
        test_basic_tournament_generation()
        test_judge_consensus_scenarios()
        test_swiss_pairing_constraints()

        print("\\n" + "=" * 50)
        print("🎉 All tournament tests passed!")
        return 0

    except Exception as e:
        print(f"\\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
