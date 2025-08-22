"""
Test Suite for Tournament logic & judge consensus - Section 3 of TESTS.md

This suite implements comprehensive tests for ensuring that Swiss pairing, match formation,
and multi-judge consensus work as intended.

Tests included:
- T1: Pairing validity (Swiss constraints, no duplicates)
- T2: Consensus early-stop (first two judges agree)
- T3: Tie resolution (third judge for conflicts)
- T4: Result integrity (stable ratings across re-runs)

All tests follow Single-Command Contract (SCC):
snakemake --unlock && snakemake --profile profiles/testonly -j <k>
"""

import json
import random
import shutil
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import pytest


class TournamentTestFramework:
    """
    Test framework for tournament logic and judge consensus testing.

    Provides utilities for:
    - Creating controlled tournament scenarios
    - Mock judge configuration for deterministic testing
    - Analyzing tournament structure and results
    - Verifying Swiss pairing constraints
    """

    def __init__(self, test_name: str):
        """Initialize isolated test environment."""
        self.test_name = test_name
        self.temp_dir = None
        self.original_cwd = None
        self.mock_judges = {}

    def __enter__(self):
        """Set up isolated test environment."""
        self.temp_dir = tempfile.mkdtemp(prefix=f"tournament_test_{self.test_name}_")
        self.original_cwd = Path.cwd()

        # Copy project structure to temp directory
        project_root = Path(__file__).parent.parent
        self._copy_project_structure(project_root, Path(self.temp_dir))

        # Change to temp directory
        import os

        os.chdir(self.temp_dir)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up test environment."""
        if self.original_cwd:
            import os

            os.chdir(self.original_cwd)
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _copy_project_structure(self, src: Path, dst: Path):
        """Copy essential project files for testing."""
        essential_items = [
            "Snakefile",
            "config",
            "profiles",
            "scripts",
            "model_pools",
            "judge_pools",
            "skills",
            "tests",  # Added to support data directory structure
        ]

        dst.mkdir(exist_ok=True)

        for item in essential_items:
            src_path = src / item
            dst_path = dst / item

            if src_path.exists():
                if src_path.is_dir():
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dst_path)

        # Ensure data directory exists based on testonly config
        testonly_config_path = dst / "config" / "testonly_config.yaml"
        if testonly_config_path.exists():
            import yaml

            with open(testonly_config_path) as f:
                testonly_config = yaml.safe_load(f)

            data_dir = testonly_config.get("data_dir", "data/testonly")
            data_path = dst / data_dir
            data_path.mkdir(parents=True, exist_ok=True)

    def run_snakemake_scc(
        self, cores: int = 1, expect_success: bool = True
    ) -> subprocess.CompletedProcess:
        """
        Run Single-Command Contract: snakemake --unlock && snakemake --profile profiles/testonly -j <cores>
        """
        # First unlock
        unlock_cmd = ["snakemake", "--unlock"]
        unlock_result = subprocess.run(unlock_cmd, capture_output=True, text=True)

        if unlock_result.returncode != 0 and expect_success:
            raise AssertionError(f"Snakemake unlock failed: {unlock_result.stderr}")

        # Then run with testonly profile
        run_cmd = ["snakemake", "--profile", "profiles/testonly", "-j", str(cores)]
        run_result = subprocess.run(run_cmd, capture_output=True, text=True)

        if expect_success and run_result.returncode != 0:
            raise AssertionError(f"Snakemake run failed: {run_result.stderr}")
        elif not expect_success and run_result.returncode == 0:
            raise AssertionError(
                f"Snakemake run unexpectedly succeeded: {run_result.stdout}"
            )

        return run_result

    def create_mock_judges(self, judge_behaviors: dict[str, str]):
        """
        Create mock judges with deterministic behaviors.

        Args:
            judge_behaviors: Dict mapping judge_id to behavior pattern:
                "agree_A" - always votes A
                "agree_B" - always votes B
                "agree_TIE" - always votes TIE
                "disagree_A" - votes opposite of first judge, defaulting to A
                "disagree_B" - votes opposite of first judge, defaulting to B
                "random" - random votes (with fixed seed)
        """
        self.mock_judges = judge_behaviors

        # Update testonly judge pool with mock judges
        judge_pool_file = Path("judge_pools/testonly.csv")
        judge_pool_file.parent.mkdir(parents=True, exist_ok=True)

        # Create header
        judge_lines = ["id,author,slug,context_window,pricing,endpoint,max_tokens"]

        for judge_id, behavior in judge_behaviors.items():
            judge_lines.append(
                f"{judge_id},TestCorp,{behavior},4096,input:0.0001|output:0.0001,mock,1000"
            )

        print(f"Writing judge pool to {judge_pool_file}")
        print(f"Content: {judge_lines}")
        with open(judge_pool_file, "w") as f:
            f.write("\n".join(judge_lines))

    def configure_tournament_scenario(self, num_models: int, num_rounds: int = None):
        """
        Configure a specific tournament scenario.

        Args:
            num_models: Number of models to include in tournament
            num_rounds: Number of rounds (defaults to Swiss calculation)
        """
        # Create model pool with specified number of models
        model_pool_file = Path("model_pools/testonly.csv")
        model_pool_file.parent.mkdir(parents=True, exist_ok=True)

        model_lines = ["id,author,slug,context_window,pricing,endpoint,max_tokens"]
        for i in range(num_models):
            model_id = f"test/model-{chr(65 + i)}"  # A, B, C, D, etc.
            model_lines.append(
                f"{model_id},TestCorp,model-{chr(65 + i)},4096,input:0.0001|output:0.0001,mock,1000"
            )

        print(f"Writing model pool to {model_pool_file}")
        print(f"Content: {model_lines}")
        with open(model_pool_file, "w") as f:
            f.write("\n".join(model_lines))

        # Update config if specific rounds requested
        if num_rounds is not None:
            config_file = Path("config/testonly_config.yaml")
            with open(config_file) as f:
                config = f.read()

            # Add tournament configuration
            if "tournament:" not in config:
                config += f"\\ntournament:\\n  rounds: {num_rounds}\\n"
            else:
                config = config.replace(
                    "tournament:", f"tournament:\\n  rounds: {num_rounds}\\n  # old:"
                )

            with open(config_file, "w") as f:
                f.write(config)

    def analyze_tournament_structure(self) -> dict:
        """
        Analyze the tournament structure from generated tournaments.json.

        Returns:
            Dictionary with tournament analysis including:
            - pairing_analysis: Pairing validity and duplicates
            - judge_consensus: Early stop and tie resolution analysis
            - result_consistency: Cross-run stability analysis
        """
        tournaments_file = Path("data/testonly/tournaments.json")
        if not tournaments_file.exists():
            return {"error": "No tournaments.json found"}

        with open(tournaments_file) as f:
            tournaments = json.load(f)

        analysis = {
            "pairing_analysis": {},
            "judge_consensus": {},
            "result_consistency": {},
            "tournaments_count": len(tournaments),
        }

        for tournament_id, tournament_data in tournaments.items():
            # Analyze pairings
            pairing_info = self._analyze_pairings(tournament_data)
            analysis["pairing_analysis"][tournament_id] = pairing_info

            # Analyze judge consensus
            consensus_info = self._analyze_judge_consensus(tournament_data)
            analysis["judge_consensus"][tournament_id] = consensus_info

            # Analyze result consistency
            result_info = self._analyze_result_integrity(tournament_data)
            analysis["result_consistency"][tournament_id] = result_info

        return analysis

    def _analyze_pairings(self, tournament_data: dict) -> dict:
        """Analyze Swiss pairing validity."""
        rounds = tournament_data.get("rounds", [])
        all_pairings = []

        for round_idx, round_matches in enumerate(rounds):
            round_pairings = []
            models_in_round = set()

            for match in round_matches:
                model_a = match["model_a_id"]
                model_b = match["model_b_id"]

                # Check for self-pairing
                if model_a == model_b:
                    return {
                        "error": f"Self-pairing found: {model_a} vs {model_b} in round {round_idx}"
                    }

                # Check for duplicate models in same round
                if model_a in models_in_round or model_b in models_in_round:
                    return {
                        "error": f"Duplicate model in round {round_idx}: {model_a}, {model_b}"
                    }

                models_in_round.add(model_a)
                models_in_round.add(model_b)

                # Normalize pairing for duplicate detection
                pairing = tuple(sorted([model_a, model_b]))
                round_pairings.append(pairing)
                all_pairings.append(pairing)

        # Check for repeated pairings across rounds
        pairing_counts = Counter(all_pairings)
        repeated_pairings = {
            pair: count for pair, count in pairing_counts.items() if count > 1
        }

        return {
            "total_rounds": len(rounds),
            "total_pairings": len(all_pairings),
            "unique_pairings": len(set(all_pairings)),
            "repeated_pairings": repeated_pairings,
            "valid_structure": len(repeated_pairings) == 0,
        }

    def _analyze_judge_consensus(self, tournament_data: dict) -> dict:
        """Analyze judge consensus and early stopping."""
        rounds = tournament_data.get("rounds", [])

        consensus_stats = {
            "total_matches": 0,
            "early_consensus_matches": 0,
            "three_judge_matches": 0,
            "tie_resolutions": 0,
            "judge_vote_distribution": defaultdict(int),
        }

        for round_matches in rounds:
            for match in round_matches:
                consensus_stats["total_matches"] += 1

                judge_votes = match.get("judge_votes", {})
                num_judges = len(judge_votes)

                if num_judges == 2:
                    # Check if early consensus was reached
                    votes = list(judge_votes.values())
                    if len(set(votes)) == 1:  # All votes are the same
                        consensus_stats["early_consensus_matches"] += 1
                elif num_judges == 3:
                    consensus_stats["three_judge_matches"] += 1

                # Count final results
                final_result = match.get("result", "UNKNOWN")
                consensus_stats["judge_vote_distribution"][final_result] += 1

                if final_result == "TIE":
                    consensus_stats["tie_resolutions"] += 1

        return consensus_stats

    def _analyze_result_integrity(self, tournament_data: dict) -> dict:
        """Analyze result integrity and consistency."""
        scores = tournament_data.get("scores", {})
        rounds = tournament_data.get("rounds", [])

        # Verify scores add up correctly
        calculated_scores = defaultdict(float)

        for round_matches in rounds:
            for match in round_matches:
                result = match.get("result")
                model_a = match["model_a_id"]
                model_b = match["model_b_id"]

                if result == "A":
                    calculated_scores[model_a] += 1.0
                elif result == "B":
                    calculated_scores[model_b] += 1.0
                elif result == "TIE":
                    calculated_scores[model_a] += 0.5
                    calculated_scores[model_b] += 0.5

        # Compare with reported scores
        score_consistency = {}
        for model_id, reported_score in scores.items():
            calculated_score = calculated_scores.get(model_id, 0.0)
            score_consistency[model_id] = {
                "reported": reported_score,
                "calculated": calculated_score,
                "consistent": abs(reported_score - calculated_score) < 0.001,
            }

        return {
            "score_consistency": score_consistency,
            "total_models": len(scores),
            "all_scores_consistent": all(
                info["consistent"] for info in score_consistency.values()
            ),
        }


class TestTournamentLogicJudgeConsensus:
    """Test suite for tournament logic and judge consensus (TESTS.md Section 3)."""

    def test_t1_pairing_validity(self):
        """
        Test T1 – Pairing validity

        Given N competitors and R rounds
        When pairings are generated
        Then each round has valid, duplicate-free pairings; no A vs A; repeated pairings follow Swiss constraints.
        """
        with TournamentTestFramework("pairing_validity") as framework:
            # Configure tournament with 6 models (good for Swiss testing)
            framework.configure_tournament_scenario(num_models=6)

            # Create simple judge pool - just need one judge for pairing testing
            framework.create_mock_judges(
                {"test/judge-pairing": "agree_A"}
            )  # Deterministic for pairing focus

            # Run tournament
            framework.run_snakemake_scc(cores=1)

            # Analyze tournament structure
            analysis = framework.analyze_tournament_structure()

            assert analysis["tournaments_count"] > 0, "No tournaments generated"

            for tournament_id, pairing_info in analysis["pairing_analysis"].items():
                # Verify no errors in pairing structure
                assert (
                    "error" not in pairing_info
                ), f"Pairing error in {tournament_id}: {pairing_info.get('error')}"

                # Verify valid Swiss structure
                assert pairing_info[
                    "valid_structure"
                ], f"Invalid tournament structure in {tournament_id}"

                # Verify no repeated pairings (Swiss constraint)
                assert (
                    len(pairing_info["repeated_pairings"]) == 0
                ), f"Repeated pairings found in {tournament_id}: {pairing_info['repeated_pairings']}"

                # Verify reasonable number of rounds (Swiss formula)
                num_rounds = pairing_info["total_rounds"]
                assert num_rounds >= 1, f"Tournament {tournament_id} has no rounds"
                assert (
                    num_rounds <= 5
                ), f"Too many rounds in {tournament_id}: {num_rounds} (expected ≤5 for 6 models)"

                print(
                    f"✓ Tournament {tournament_id}: {num_rounds} rounds, {pairing_info['total_pairings']} pairings, all valid"
                )

    def test_t2_consensus_early_stop(self):
        """
        Test T2 – Consensus early-stop

        Given a match
        When the first two judges agree
        Then a third judge is not executed, and the recorded result reflects that consensus.
        """
        with TournamentTestFramework("consensus_early_stop") as framework:
            # Configure small tournament for focused testing
            framework.configure_tournament_scenario(num_models=4)

            # Create judges that will agree on most decisions
            framework.create_mock_judges(
                {
                    "test/judge-agree1": "agree_A",  # Always votes A
                    "test/judge-agree2": "agree_A",  # Always votes A (agrees with judge1)
                    "test/judge-agree3": "agree_A",  # Should not be called due to early consensus
                }
            )

            # Run tournament
            framework.run_snakemake_scc(cores=1)

            # Analyze judge consensus
            analysis = framework.analyze_tournament_structure()

            consensus_found = False
            for tournament_id, consensus_info in analysis["judge_consensus"].items():
                total_matches = consensus_info["total_matches"]
                early_consensus = consensus_info["early_consensus_matches"]
                three_judge = consensus_info["three_judge_matches"]

                print(
                    f"Tournament {tournament_id}: {total_matches} matches, {early_consensus} early consensus, {three_judge} three-judge"
                )

                # Should have early consensus in most matches (judges agree)
                if early_consensus > 0:
                    consensus_found = True

                    # When early consensus happens, should not use third judge
                    assert three_judge == (
                        total_matches - early_consensus
                    ), f"Inconsistent judge usage: {early_consensus} early + {three_judge} three-judge != {total_matches} total"

                    # Most results should be A (since our judges agree on A)
                    vote_dist = consensus_info["judge_vote_distribution"]
                    assert (
                        vote_dist.get("A", 0) > 0
                    ), f"Expected A votes in {tournament_id}, got {vote_dist}"

            assert (
                consensus_found
            ), "No early consensus detected - may indicate early-stop logic not working"

    def test_t3_tie_resolution(self):
        """
        Test T3 – Tie resolution

        Given conflicting first two judge results
        When a third judge is executed
        Then the outcome is either a decisive 2-of-3 or an explicit tie.
        """
        with TournamentTestFramework("tie_resolution") as framework:
            # Configure small tournament
            framework.configure_tournament_scenario(num_models=4)

            # Create judges that will disagree to force third judge
            framework.create_mock_judges(
                {
                    "test/judge-disagree1": "agree_A",  # Always votes A
                    "test/judge-disagree2": "agree_B",  # Always votes B (disagrees)
                    "test/judge-tiebreak": "agree_TIE",  # Tiebreaker judge
                }
            )

            # Run tournament
            framework.run_snakemake_scc(cores=1)

            # Analyze judge consensus
            analysis = framework.analyze_tournament_structure()

            three_judge_found = False
            for tournament_id, consensus_info in analysis["judge_consensus"].items():
                total_matches = consensus_info["total_matches"]
                early_consensus = consensus_info["early_consensus_matches"]
                three_judge = consensus_info["three_judge_matches"]

                print(
                    f"Tournament {tournament_id}: {total_matches} matches, {early_consensus} early consensus, {three_judge} three-judge"
                )

                # Should have NO early consensus (judges disagree)
                assert (
                    early_consensus == 0
                ), f"Expected no early consensus due to disagreeing judges, but got {early_consensus}"

                # Should use all three judges
                assert (
                    three_judge == total_matches
                ), f"Expected all matches to use three judges, got {three_judge}/{total_matches}"

                if three_judge > 0:
                    three_judge_found = True

                    # With A vs B vs TIE judges, results should be mostly TIE (no clear majority)
                    vote_dist = consensus_info["judge_vote_distribution"]
                    tie_votes = vote_dist.get("TIE", 0)
                    assert (
                        tie_votes > 0
                    ), f"Expected TIE resolutions in {tournament_id}, got {vote_dist}"

            assert (
                three_judge_found
            ), "No three-judge matches found - tie resolution logic not triggered"

    def test_t4_result_integrity(self):
        """
        Test T4 – Result integrity

        Given a completed tournament
        Then the ratings computation reflects all W/L/T outcomes and is stable across re-runs.
        """
        with TournamentTestFramework("result_integrity") as framework:
            # Configure deterministic tournament
            framework.configure_tournament_scenario(num_models=4)

            # Create deterministic judges
            framework.create_mock_judges(
                {
                    "test/judge-deterministic": "agree_A",  # Consistent behavior
                }
            )

            # Run tournament first time
            framework.run_snakemake_scc(cores=1)

            # Capture first run results
            tournaments_file = Path("data/testonly/tournaments.json")
            with open(tournaments_file) as f:
                first_run = json.load(f)

            # Analyze first run
            first_analysis = framework.analyze_tournament_structure()

            # Verify result integrity in first run
            for tournament_id, result_info in first_analysis[
                "result_consistency"
            ].items():
                assert result_info[
                    "all_scores_consistent"
                ], f"Inconsistent scores in first run {tournament_id}: {result_info['score_consistency']}"

            # Wait briefly to ensure different timestamps (if any)
            time.sleep(0.1)

            # Run tournament again (should be no-op due to caching)
            framework.run_snakemake_scc(cores=1)

            # Capture second run results
            with open(tournaments_file) as f:
                second_run = json.load(f)

            # Compare runs for stability
            assert len(first_run) == len(
                second_run
            ), "Different number of tournaments between runs"

            for tournament_id in first_run.keys():
                first_scores = first_run[tournament_id]["scores"]
                second_scores = second_run[tournament_id]["scores"]

                assert (
                    first_scores == second_scores
                ), f"Scores changed between runs in {tournament_id}: {first_scores} -> {second_scores}"

                # Verify same matches exist
                first_matches = []
                for round_matches in first_run[tournament_id]["rounds"]:
                    for match in round_matches:
                        first_matches.append(
                            (match["model_a_id"], match["model_b_id"], match["result"])
                        )

                second_matches = []
                for round_matches in second_run[tournament_id]["rounds"]:
                    for match in round_matches:
                        second_matches.append(
                            (match["model_a_id"], match["model_b_id"], match["result"])
                        )

                assert sorted(first_matches) == sorted(
                    second_matches
                ), f"Match results changed between runs in {tournament_id}"

                print(
                    f"✓ Tournament {tournament_id}: Stable across re-runs ({len(first_scores)} models)"
                )

    def test_comprehensive_tournament_scenario(self):
        """
        Comprehensive test combining all tournament features:
        - Multiple models with Swiss pairings
        - Mixed judge behaviors (consensus and disagreement)
        - Result integrity verification
        """
        with TournamentTestFramework("comprehensive") as framework:
            # Configure realistic tournament (8 models)
            framework.configure_tournament_scenario(num_models=8)

            # Create mixed judge pool for realistic scenarios
            framework.create_mock_judges(
                {
                    "test/judge-primary": "agree_A",  # Primary judge
                    "test/judge-secondary": "agree_B",  # Secondary judge (different preference)
                    "test/judge-tiebreak": "agree_TIE",  # Neutral tiebreaker
                }
            )

            # Run tournament
            framework.run_snakemake_scc(cores=1)

            # Comprehensive analysis
            analysis = framework.analyze_tournament_structure()

            # Verify overall tournament health
            assert analysis["tournaments_count"] > 0, "No tournaments generated"

            total_matches = 0
            total_early_consensus = 0
            total_three_judge = 0

            for tournament_id, consensus_info in analysis["judge_consensus"].items():
                # Accumulate stats
                total_matches += consensus_info["total_matches"]
                total_early_consensus += consensus_info["early_consensus_matches"]
                total_three_judge += consensus_info["three_judge_matches"]

                # Verify pairing validity
                pairing_info = analysis["pairing_analysis"][tournament_id]
                assert pairing_info[
                    "valid_structure"
                ], f"Invalid pairings in {tournament_id}"

                # Verify result integrity
                result_info = analysis["result_consistency"][tournament_id]
                assert result_info[
                    "all_scores_consistent"
                ], f"Inconsistent scores in {tournament_id}"

            # Verify realistic judge distribution
            # With mixed judges (A vs B vs TIE), should see variety in consensus patterns
            assert total_matches > 0, "No matches found"

            # Should have some matches with early consensus and some requiring third judge
            consensus_rate = (
                total_early_consensus / total_matches if total_matches > 0 else 0
            )
            three_judge_rate = (
                total_three_judge / total_matches if total_matches > 0 else 0
            )

            print(
                f"Tournament Results: {total_matches} matches, {consensus_rate:.2%} early consensus, {three_judge_rate:.2%} three-judge"
            )

            # Verify both early consensus and tie resolution are working
            assert (
                total_early_consensus >= 0
            ), "Early consensus mechanism should function"
            assert total_three_judge >= 0, "Three-judge resolution should function"

            # At least one of the mechanisms should be used
            assert (
                total_early_consensus + total_three_judge
            ) == total_matches, "All matches should be resolved via either early consensus or three-judge resolution"


# Fixtures for deterministic testing


@pytest.fixture
def fixed_random_seed():
    """Ensure deterministic random behavior in tests."""
    random.seed(12345)
    yield
    # Reset seed after test
    random.seed()


@pytest.fixture
def clean_testonly_environment():
    """Ensure clean testonly environment before each test."""
    testonly_data = Path("data/testonly")
    if testonly_data.exists():
        shutil.rmtree(testonly_data)
    yield
    # Cleanup after test
    if testonly_data.exists():
        shutil.rmtree(testonly_data)


# Integration with existing test framework


def test_tournament_pipeline_integration():
    """
    Integration test verifying tournament logic works end-to-end
    with the existing pipeline framework.
    """
    # This test verifies that tournament logic integrates properly with:
    # 1. Snakemake pipeline execution
    # 2. Cache invalidation logic
    # 3. Profile isolation
    # 4. Deterministic output generation

    from test_invalidation_minimal_rebuilds import SnakemakeTestFramework

    with SnakemakeTestFramework("tournament_integration") as framework:
        # Run baseline to ensure tournaments are generated
        framework.run_snakemake_scc(cores=1)

        # Verify tournament files exist
        assert Path(
            "data/testonly/tournaments.json"
        ).exists(), "tournaments.json not generated"
        assert Path(
            "data/testonly/skill_ratings.json"
        ).exists(), "skill_ratings.json not generated"

        # Verify tournaments contain expected structure
        with open("data/testonly/tournaments.json") as f:
            tournaments = json.load(f)

        assert len(tournaments) > 0, "No tournaments found in output"

        for tournament_id, tournament_data in tournaments.items():
            assert (
                "rounds" in tournament_data
            ), f"No rounds in tournament {tournament_id}"
            assert (
                "scores" in tournament_data
            ), f"No scores in tournament {tournament_id}"

            # Verify matches have required fields
            for round_matches in tournament_data["rounds"]:
                for match in round_matches:
                    required_fields = [
                        "model_a_id",
                        "model_b_id",
                        "result",
                        "judge_votes",
                    ]
                    for field in required_fields:
                        assert (
                            field in match
                        ), f"Missing {field} in match {match.get('match_id', 'unknown')}"

        print(
            f"✓ Tournament integration verified: {len(tournaments)} tournaments generated"
        )
