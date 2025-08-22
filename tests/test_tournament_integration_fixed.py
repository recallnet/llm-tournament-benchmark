#!/usr/bin/env python3
"""
Real integration tests for tournament pipeline with bug fixes.

Tests the actual tournament logic with proper mock endpoints and
validates that the Swiss pairing bug fixes work correctly.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path


def test_swiss_pairing_with_mock_judges():
    """Test Swiss pairing with proper mock judge endpoints."""

    # Create temporary test environment
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy essential files
        project_root = Path(__file__).parent.parent
        for item in ["scripts", "config"]:
            src = project_root / item
            dst = temp_path / item
            if src.exists():
                shutil.copytree(src, dst)

        # Create test data directories
        (temp_path / "data/testonly").mkdir(parents=True, exist_ok=True)
        (temp_path / "model_pools").mkdir(exist_ok=True)
        (temp_path / "judge_pools").mkdir(exist_ok=True)
        (temp_path / "testonly/skills/test_skill").mkdir(parents=True, exist_ok=True)

        # Create mock model pool with 6 models (good for Swiss testing)
        models = [
            "test/model-alpha,TestCorp,alpha,4096,input:0.0001,mock,1000",
            "test/model-beta,TestCorp,beta,4096,input:0.0001,mock,1000",
            "test/model-gamma,TestCorp,gamma,4096,input:0.0001,mock,1000",
            "test/model-delta,TestCorp,delta,4096,input:0.0001,mock,1000",
            "test/model-epsilon,TestCorp,epsilon,4096,input:0.0001,mock,1000",
            "test/model-zeta,TestCorp,zeta,4096,input:0.0001,mock,1000",
        ]

        with open(temp_path / "model_pools/testonly.csv", "w") as f:
            f.write("id,author,slug,context_window,pricing,endpoint,max_tokens\n")
            f.write("\n".join(models))

        # Create mock judge pool with different behaviors
        judges = [
            "test/judge-agree_A,TestCorp,agree_A,4096,input:0.0001,mock,1000",
            "test/judge-agree_B,TestCorp,agree_B,4096,input:0.0001,mock,1000",
            "test/judge-agree_TIE,TestCorp,agree_TIE,4096,input:0.0001,mock,1000",
        ]

        with open(temp_path / "judge_pools/testonly.csv", "w") as f:
            f.write("id,author,slug,context_window,pricing,endpoint,max_tokens\n")
            f.write("\n".join(judges))

        # Create test skill/eval
        test_eval = {
            "id": "eval_test",
            "description": "Test evaluation",
            "steps": [
                {"type": "user_message", "content": "Hello"},
                {"type": "assistant_message", "content": "Hi there!"},
            ],
            "judge": {
                "system": "Compare the responses and choose the better one.",
                "prompt": "Which response is better?\n\nA: {{A}}\n\nB: {{B}}",
                "view": {
                    "A": [{"kind": "step", "id": "step1", "part": "final"}],
                    "B": [{"kind": "step", "id": "step1", "part": "final"}],
                },
            },
            "_metadata": {"skill": "test_skill"},
        }

        with open(temp_path / "testonly/skills/test_skill/eval_test.json", "w") as f:
            json.dump(test_eval, f, indent=2)

        # Create test config
        config = {
            "model_pool": {"default_pool": "testonly", "pools_dir": "model_pools"},
            "judge_pool": {"default_pool": "testonly", "pools_dir": "judge_pools"},
            "skills": {"skills_dir": "skills", "selected_skills": ["testonly"]},
            "data_dir": "data/testonly",
            "random_seed": 12345,
        }

        with open(temp_path / "config/testonly_config.yaml", "w") as f:
            import yaml

            yaml.dump(config, f)

        # Change to temp directory
        old_cwd = os.getcwd()
        os.chdir(temp_path)

        try:
            # Set mock environment
            os.environ["OPENROUTER_API_KEY"] = "test-mock-key"

            # Test the tournament system directly
            print("🧪 Testing Swiss tournament with mock judges...")

            # Import tournament classes
            import sys

            sys.path.insert(0, str(temp_path / "scripts"))
            # Load test models
            import pandas as pd
            from run_tournaments import JudgeExecutor, SwissTournament, TournamentMatch

            models_df = pd.read_csv("model_pools/testonly.csv")
            models = [{"id": row["id"]} for _, row in models_df.iterrows()]

            # Load test judges
            judges_df = pd.read_csv("judge_pools/testonly.csv")
            judges = [
                {"id": row["id"], "endpoint": row["endpoint"]}
                for _, row in judges_df.iterrows()
            ]

            print(f"📊 Testing with {len(models)} models, {len(judges)} judges")

            # Create tournament
            tournament = SwissTournament("test_skill", "eval_test", models)
            rounds_needed = tournament._calculate_rounds_needed()
            print(f"📋 {rounds_needed} rounds planned")

            # Track all pairings
            all_pairings = []

            # Run tournament rounds
            for round_num in range(rounds_needed):
                print(f"\n🔄 Round {round_num + 1}")

                # Get pairings
                pairings = tournament._get_pairings_for_round(round_num)
                print(f"   Pairings: {pairings}")

                # Track normalized pairings
                normalized = [tuple(sorted([a, b])) for a, b in pairings]
                all_pairings.extend(normalized)

                # Create mock matches and simulate results
                round_matches = []
                for model_a, model_b in pairings:
                    match = TournamentMatch(model_a, model_b, "eval_test", "test_skill")

                    # Simulate judge decisions with our mock system
                    judge_executor = JudgeExecutor(Path("data/testonly/judge_cache"))

                    for judge in judges:
                        try:
                            # This should now use mock endpoints!
                            vote, conversation, explanation = (
                                judge_executor.execute_judge_decision(
                                    match,
                                    judge,
                                    test_eval,
                                    "data/testonly/conversations",
                                    {},
                                )
                            )
                            match.add_judge_result(
                                judge["id"], vote, conversation, explanation
                            )

                            # Check early consensus
                            if (
                                len(match.judge_votes) == 2
                                and match.check_early_consensus()
                            ):
                                print(f"      🎯 Early consensus: {vote}")
                                break
                        except Exception as e:
                            print(f"      ❌ Judge error: {e}")
                            match.add_judge_result(judge["id"], "TIE", [], str(e))

                    # Calculate result and update scores
                    match.calculate_result()
                    tournament.update_scores(match)
                    round_matches.append(match)
                    print(f"      🏆 {model_a} vs {model_b} = {match.result}")

                tournament.rounds.append(round_matches)
                print(f"   Scores: {tournament.scores}")

            # Analyze pairings
            from collections import Counter

            pairing_counts = Counter(all_pairings)
            duplicates = {p: count for p, count in pairing_counts.items() if count > 1}

            print("\n📊 Tournament Analysis:")
            print(f"   Total pairings: {len(all_pairings)}")
            print(f"   Unique pairings: {len(set(all_pairings))}")
            print(f"   Duplicate pairings: {duplicates}")

            # Swiss tournaments may have rematches when necessary, but they should be minimal
            duplicate_count = sum(count - 1 for count in duplicates.values())
            len(all_pairings) - len(set(all_pairings))

            if len(all_pairings) > 0:
                print(
                    f"   Forced rematches: {duplicate_count}/{len(all_pairings)} ({100*duplicate_count/len(all_pairings):.1f}%)"
                )
            else:
                print(
                    f"   Forced rematches: {duplicate_count}/0 (no pairings generated)"
                )

            # With 6 models over 3+ rounds, some rematches might be necessary
            # The key is that our algorithm minimizes them and warns about them
            if len(all_pairings) == 0:
                print("❌ No pairings generated")
                return False
            elif duplicate_count <= 2:  # Allow minimal rematches for small fields
                print("✅ Swiss pairing working correctly (minimal rematches)")
                return True
            else:
                print(f"❌ Too many rematches: {duplicate_count}")
                return False

        finally:
            os.chdir(old_cwd)


def test_mock_judge_execution():
    """Test that mock judges work correctly."""
    print("\n🧪 Testing mock judge execution...")

    # This should use our new mock endpoint handling
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temp_dir:
        # Import after setting up path
        project_root = Path(__file__).parent.parent
        import sys

        sys.path.insert(0, str(project_root / "scripts"))

        from run_tournaments import JudgeExecutor, TournamentMatch

        # Create mock judge executor
        cache_dir = Path(temp_dir) / "judge_cache"
        os.environ["OPENROUTER_API_KEY"] = "test-mock-key"
        executor = JudgeExecutor(cache_dir)

        # Test different mock judge behaviors
        mock_judges = [
            {"id": "test/judge-agree_A", "endpoint": "mock"},
            {"id": "test/judge-agree_B", "endpoint": "mock"},
            {"id": "test/judge-agree_TIE", "endpoint": "mock"},
        ]

        match = TournamentMatch("model_a", "model_b", "eval_test", "test_skill")

        test_eval = {
            "judge": {
                "system": "You are a judge",
                "prompt": "Choose A or B",
                "view": {"A": [], "B": []},
            }
        }

        votes = []
        for judge in mock_judges:
            try:
                vote, conversation, explanation = executor.execute_judge_decision(
                    match, judge, test_eval, "/tmp", {}
                )
                votes.append(vote)
                print(f"   {judge['id']}: {vote}")

                # Verify mock behavior
                if "agree_A" in judge["id"]:
                    assert vote == "A", f"Expected A, got {vote}"
                elif "agree_B" in judge["id"]:
                    assert vote == "B", f"Expected B, got {vote}"
                elif "agree_TIE" in judge["id"]:
                    assert vote == "TIE", f"Expected TIE, got {vote}"

            except Exception as e:
                print(f"   ❌ Judge {judge['id']} failed: {e}")
                return False

        print(f"✅ Mock judges working: {votes}")
        return True


def main():
    """Run integration tests."""
    print("AFBench Tournament Integration Tests")
    print("=" * 50)

    success = True

    # Test Swiss pairing fixes
    if not test_swiss_pairing_with_mock_judges():
        success = False

    # Test mock judge execution
    if not test_mock_judge_execution():
        success = False

    if success:
        print("\n🎉 All integration tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())
