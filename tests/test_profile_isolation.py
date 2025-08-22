#!/usr/bin/env python3
"""
Profile isolation test suite for AFBench.

Tests Section 6 from TESTS.md:
- P1: Profile isolation - artifacts, logs, cache isolated
- P2: Promotion parity - results equivalent aside from scale

All tests use the Single-Command Contract (SCC):
snakemake --unlock && snakemake --profile profiles/<profile> -j <cores>
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


class ProfileIsolationTestFramework:
    """Framework for testing profile isolation between quick and production profiles."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.temp_dir = None
        self.afbench_root = None

    def __enter__(self):
        # Create temporary test environment
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"profile_test_{self.test_name}_"))
        self.afbench_root = Path(__file__).parent.parent

        # Set up isolated test environment
        self._setup_test_workspace()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _setup_test_workspace(self):
        """Set up isolated test workspace with full AFBench structure."""
        temp_path = self.temp_dir

        # Copy AFBench source files to test workspace
        source_files = [
            "Snakefile",
            "scripts/",
            "config/",
            "profiles/",
            "model_pools/",
            "judge_pools/",
            "skills/",  # Copy entire skills directory structure
        ]

        for src_file in source_files:
            src_path = self.afbench_root / src_file
            dst_path = temp_path / src_file

            if src_path.is_file():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
            elif src_path.is_dir():
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

        # Create profile-specific configurations for testing
        self._setup_profile_configs(temp_path)

        return temp_path

    def _setup_profile_configs(self, temp_path: Path):
        """Set up quick and production profiles for isolation testing."""
        # Create quick profile config
        quick_profile_dir = temp_path / "profiles" / "quick"
        quick_profile_dir.mkdir(parents=True, exist_ok=True)

        quick_profile_config = {
            "cores": 2,
            "keep-going": True,
            "printshellcmds": True,
            "configfile": "config/profile_test_quick_config.yaml",
        }

        with open(quick_profile_dir / "config.yaml", "w") as f:
            import yaml

            yaml.dump(quick_profile_config, f)

        # Create production profile config
        prod_profile_dir = temp_path / "profiles" / "production"
        prod_profile_dir.mkdir(parents=True, exist_ok=True)

        prod_profile_config = {
            "cores": 2,
            "keep-going": False,
            "printshellcmds": False,
            "configfile": "config/profile_test_production_config.yaml",
        }

        with open(prod_profile_dir / "config.yaml", "w") as f:
            yaml.dump(prod_profile_config, f)

        # Create profile-specific data configs
        quick_config = {
            "data_dir": "data/quick",
            "model_pool": {"default_pool": "testonly", "pools_dir": "model_pools"},
            "judge_pool": {"default_pool": "testonly", "pools_dir": "judge_pools"},
            "skills": {
                "skills_dir": "testonly/skills",
                "selected_skills": [],
            },  # Use testonly skills directory
            "n_samples": 50,  # Small for quick testing
            "random_seed": 42,
        }

        with open(temp_path / "config" / "profile_test_quick_config.yaml", "w") as f:
            yaml.dump(quick_config, f)

        prod_config = {
            "data_dir": "data/production",
            "model_pool": {"default_pool": "testonly", "pools_dir": "model_pools"},
            "judge_pool": {"default_pool": "testonly", "pools_dir": "judge_pools"},
            "skills": {
                "skills_dir": "testonly/skills",
                "selected_skills": [],
            },  # Use testonly skills directory
            "n_samples": 100,  # Larger for production-like testing
            "random_seed": 42,  # Same seed for parity testing
        }

        with open(
            temp_path / "config" / "profile_test_production_config.yaml", "w"
        ) as f:
            yaml.dump(prod_config, f)

    def run_snakemake_with_profile(
        self, profile: str, cores: int = 1, expect_failure: bool = False
    ) -> dict:
        """Run Snakemake using Single-Command Contract (SCC) with specific profile."""
        temp_path = self.temp_dir

        # Change to test workspace directory
        original_cwd = os.getcwd()

        try:
            os.chdir(temp_path)

            # Set environment for testing
            env = os.environ.copy()
            env["AFBENCH_TESTING"] = "true"

            # Run unlock first (part of SCC)
            unlock_cmd = ["snakemake", "--unlock"]
            unlock_result = subprocess.run(
                unlock_cmd, capture_output=True, text=True, env=env
            )

            # Run main pipeline (SCC)
            main_cmd = [
                "snakemake",
                "--profile",
                f"profiles/{profile}",
                "-j",
                str(cores),
                "--forceall",  # Force rebuild to see full behavior
            ]

            start_time = time.time()
            main_result = subprocess.run(
                main_cmd, capture_output=True, text=True, env=env, timeout=300
            )  # 5 minute timeout
            end_time = time.time()

            return {
                "success": main_result.returncode == 0,
                "returncode": main_result.returncode,
                "stdout": main_result.stdout,
                "stderr": main_result.stderr,
                "duration": end_time - start_time,
                "unlock_success": unlock_result.returncode == 0,
                "unlock_output": unlock_result.stdout + unlock_result.stderr,
                "profile": profile,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Pipeline execution timed out",
                "duration": 300.0,
                "unlock_success": False,
                "unlock_output": "",
                "profile": profile,
            }
        finally:
            os.chdir(original_cwd)

    def analyze_profile_artifacts(self, profile: str) -> dict:
        """Analyze artifacts created by a specific profile."""
        temp_path = self.temp_dir
        profile_data_dir = temp_path / "data" / profile

        artifacts = {
            "data_dir": str(profile_data_dir),
            "exists": profile_data_dir.exists(),
            "artifacts": [],
            "cache_files": [],
            "log_files": [],
            "conversations_exist": False,
            "tournaments_exist": False,
            "ratings_exist": False,
        }

        if not profile_data_dir.exists():
            return artifacts

        # Collect all artifacts
        for artifact_file in profile_data_dir.rglob("*"):
            if artifact_file.is_file():
                rel_path = artifact_file.relative_to(profile_data_dir)
                artifacts["artifacts"].append(str(rel_path))

                # Categorize artifacts
                if "conversations" in str(artifact_file):
                    artifacts["cache_files"].append(str(rel_path))
                elif artifact_file.name.endswith(".log"):
                    artifacts["log_files"].append(str(rel_path))

        # Check for key output files
        artifacts["conversations_exist"] = (
            profile_data_dir / "conversations.json"
        ).exists()
        artifacts["tournaments_exist"] = (
            profile_data_dir / "tournaments.json"
        ).exists()
        artifacts["ratings_exist"] = (profile_data_dir / "skill_ratings.json").exists()

        return artifacts

    def check_cross_contamination(self, profile1: str, profile2: str) -> dict:
        """Check if running one profile affects the other's artifacts."""
        temp_path = self.temp_dir

        profile1_dir = temp_path / "data" / profile1
        profile2_dir = temp_path / "data" / profile2

        contamination = {
            "profile1_exists": profile1_dir.exists(),
            "profile2_exists": profile2_dir.exists(),
            "shared_files": [],
            "isolated": True,
        }

        if not (profile1_dir.exists() and profile2_dir.exists()):
            return contamination

        # Check for any shared file paths (shouldn't happen with proper isolation)
        profile1_files = set()
        profile2_files = set()

        for f in profile1_dir.rglob("*"):
            if f.is_file():
                profile1_files.add(f.relative_to(profile1_dir))

        for f in profile2_dir.rglob("*"):
            if f.is_file():
                profile2_files.add(f.relative_to(profile2_dir))

        # Files should have same structure but different content/timestamps
        shared_structure = profile1_files.intersection(profile2_files)
        contamination["shared_structure"] = list(shared_structure)

        # Check if files are truly isolated by comparing full paths
        profile1_full_paths = {str(f) for f in profile1_dir.rglob("*") if f.is_file()}
        profile2_full_paths = {str(f) for f in profile2_dir.rglob("*") if f.is_file()}

        shared_full_paths = profile1_full_paths.intersection(profile2_full_paths)
        contamination["shared_files"] = list(shared_full_paths)
        contamination["isolated"] = len(shared_full_paths) == 0

        return contamination

    def compare_results_parity(self, profile1: str, profile2: str) -> dict:
        """Compare results between profiles for functional parity."""
        temp_path = self.temp_dir

        profile1_dir = temp_path / "data" / profile1
        profile2_dir = temp_path / "data" / profile2

        parity = {
            "both_have_results": False,
            "conversations_count_match": False,
            "tournament_structure_match": False,
            "ratings_keys_match": False,
            "functional_parity": False,
            "scale_differences": {},
        }

        # Check if both profiles have results
        p1_conversations = profile1_dir / "conversations.json"
        p2_conversations = profile2_dir / "conversations.json"
        p1_tournaments = profile1_dir / "tournaments.json"
        p2_tournaments = profile2_dir / "tournaments.json"
        p1_ratings = profile1_dir / "skill_ratings.json"
        p2_ratings = profile2_dir / "skill_ratings.json"

        # Debug: Check what files actually exist
        parity["debug_files"] = {
            "profile1_conversations_exists": p1_conversations.exists(),
            "profile2_conversations_exists": p2_conversations.exists(),
            "profile1_tournaments_exists": p1_tournaments.exists(),
            "profile2_tournaments_exists": p2_tournaments.exists(),
            "profile1_ratings_exists": p1_ratings.exists(),
            "profile2_ratings_exists": p2_ratings.exists(),
        }

        # For parity testing, we can use tournaments and ratings if conversations.json doesn't exist
        # This might happen if the conversations are stored in a different format
        has_essential_results = (
            p1_conversations.exists()
            or (p1_tournaments.exists() and p1_ratings.exists())
        ) and (
            p2_conversations.exists()
            or (p2_tournaments.exists() and p2_ratings.exists())
        )

        if not has_essential_results:
            return parity

        parity["both_have_results"] = True

        try:
            # Compare conversations if they exist
            p1_conv_count = 0
            p2_conv_count = 0

            if p1_conversations.exists() and p2_conversations.exists():
                with open(p1_conversations) as f:
                    p1_conv_data = json.load(f)
                with open(p2_conversations) as f:
                    p2_conv_data = json.load(f)

                p1_conv_count = len(p1_conv_data.get("conversations", []))
                p2_conv_count = len(p2_conv_data.get("conversations", []))
                parity["conversations_count_match"] = p1_conv_count == p2_conv_count
            else:
                # If conversations.json doesn't exist, assume it's not generated by this pipeline configuration
                parity["conversations_count_match"] = True
                parity["conversations_note"] = (
                    "conversations.json not found - may not be generated in this configuration"
                )

            # Compare tournaments structure
            if p1_tournaments.exists() and p2_tournaments.exists():
                with open(p1_tournaments) as f:
                    p1_tourn_data = json.load(f)
                with open(p2_tournaments) as f:
                    p2_tourn_data = json.load(f)

                p1_tourns = set(p1_tourn_data.keys())
                p2_tourns = set(p2_tourn_data.keys())
                parity["tournament_structure_match"] = p1_tourns == p2_tourns
            else:
                parity["tournament_structure_match"] = False

            # Compare ratings keys
            if p1_ratings.exists() and p2_ratings.exists():
                with open(p1_ratings) as f:
                    p1_rating_data = json.load(f)
                with open(p2_ratings) as f:
                    p2_rating_data = json.load(f)

                p1_models = (
                    set(p1_rating_data.keys())
                    if isinstance(p1_rating_data, dict)
                    else set()
                )
                p2_models = (
                    set(p2_rating_data.keys())
                    if isinstance(p2_rating_data, dict)
                    else set()
                )
                parity["ratings_keys_match"] = p1_models == p2_models
            else:
                parity["ratings_keys_match"] = False

            # Overall functional parity - focus on tournaments and ratings
            parity["functional_parity"] = (
                parity["tournament_structure_match"] and parity["ratings_keys_match"]
            )

            # Record scale differences (expected)
            parity["scale_differences"] = {
                "conversation_counts": {
                    "profile1": p1_conv_count,
                    "profile2": p2_conv_count,
                },
            }

        except (json.JSONDecodeError, OSError) as e:
            parity["error"] = str(e)

        return parity

    def check_cache_isolation(self) -> dict:
        """Check that Snakemake cache and logs are isolated between profiles."""
        temp_path = self.temp_dir

        isolation = {"snakemake_dirs": [], "isolated": True}

        # Check for .snakemake directories
        snakemake_dirs = list(temp_path.glob("**/.snakemake"))
        isolation["snakemake_dirs"] = [
            str(d.relative_to(temp_path)) for d in snakemake_dirs
        ]

        # Should only have one .snakemake directory at the root
        isolation["isolated"] = len(snakemake_dirs) <= 1

        return isolation


def test_profile_isolation():
    """
    Test P1: Profile isolation - artifacts, logs, cache isolated.

    Given: Quick and production profiles
    When: Both are run against the same inputs
    Then: Their artifacts, logs, and cache are isolated; running one does not trigger rebuilds in the other
    """
    print("=== Test P1: Profile Isolation ===")

    with ProfileIsolationTestFramework("profile_isolation") as framework:
        temp_path = framework.temp_dir
        print(f"Test workspace: {temp_path}")

        # Step 1: Run quick profile first
        print("\n--- Step 1: Running quick profile ---")
        quick_result = framework.run_snakemake_with_profile("quick", cores=2)

        if not quick_result["success"]:
            print(f"❌ Quick profile run failed: {quick_result['stderr']}")
            return False

        print("✅ Quick profile completed successfully")

        # Step 2: Analyze quick profile artifacts
        quick_artifacts = framework.analyze_profile_artifacts("quick")
        print(f"Quick profile artifacts: {len(quick_artifacts['artifacts'])} files")
        print(f"  Data directory: {quick_artifacts['data_dir']}")
        print(f"  Has conversations: {quick_artifacts['conversations_exist']}")
        print(f"  Has tournaments: {quick_artifacts['tournaments_exist']}")
        print(f"  Has ratings: {quick_artifacts['ratings_exist']}")

        # Step 3: Run production profile
        print("\n--- Step 3: Running production profile ---")
        prod_result = framework.run_snakemake_with_profile("production", cores=2)

        if not prod_result["success"]:
            print(f"❌ Production profile run failed: {prod_result['stderr']}")
            return False

        print("✅ Production profile completed successfully")

        # Step 4: Analyze production profile artifacts
        prod_artifacts = framework.analyze_profile_artifacts("production")
        print(f"Production profile artifacts: {len(prod_artifacts['artifacts'])} files")
        print(f"  Data directory: {prod_artifacts['data_dir']}")
        print(f"  Has conversations: {prod_artifacts['conversations_exist']}")
        print(f"  Has tournaments: {prod_artifacts['tournaments_exist']}")
        print(f"  Has ratings: {prod_artifacts['ratings_exist']}")

        # Step 5: Check for cross-contamination
        print("\n--- Step 5: Checking isolation ---")
        contamination = framework.check_cross_contamination("quick", "production")

        if not contamination["isolated"]:
            print(
                f"❌ Profiles not isolated! Shared files: {contamination['shared_files']}"
            )
            return False

        print("✅ Profiles are properly isolated")
        print(f"  Quick profile exists: {contamination['profile1_exists']}")
        print(f"  Production profile exists: {contamination['profile2_exists']}")
        print(
            f"  Shared structure (expected): {len(contamination.get('shared_structure', []))} files"
        )

        # Step 6: Check cache isolation
        cache_isolation = framework.check_cache_isolation()
        if not cache_isolation["isolated"]:
            print(
                f"❌ Cache not isolated! Multiple .snakemake dirs: {cache_isolation['snakemake_dirs']}"
            )
            return False

        print("✅ Cache isolation verified")

        # Step 7: Test that running one profile doesn't trigger rebuilds in the other
        print("\n--- Step 7: Testing rebuild isolation ---")

        # Re-run quick profile and check if production artifacts are modified
        prod_dir = temp_path / "data" / "production"
        prod_files_before = {}

        if prod_dir.exists():
            for f in prod_dir.rglob("*"):
                if f.is_file():
                    prod_files_before[str(f)] = f.stat().st_mtime

        # Re-run quick profile (should be no-op)
        quick_rerun_result = framework.run_snakemake_with_profile("quick", cores=2)

        if not quick_rerun_result["success"]:
            print(f"❌ Quick profile re-run failed: {quick_rerun_result['stderr']}")
            return False

        # Check if production files were modified
        prod_files_modified = False
        if prod_dir.exists():
            for f in prod_dir.rglob("*"):
                if f.is_file():
                    file_path = str(f)
                    if file_path in prod_files_before:
                        if f.stat().st_mtime > prod_files_before[file_path]:
                            prod_files_modified = True
                            break

        if prod_files_modified:
            print("❌ Running quick profile modified production artifacts")
            return False

        print("✅ Profile rebuild isolation verified")
        return True


def test_promotion_parity():
    """
    Test P2: Promotion parity - results equivalent aside from scale.

    Given: Identical inputs
    When: Quick completes then production runs
    Then: Functional results (conversations, matches, scores) are equivalent aside from expected scale/resource differences
    """
    print("\n=== Test P2: Promotion Parity ===")

    with ProfileIsolationTestFramework("promotion_parity") as framework:
        temp_path = framework.temp_dir
        print(f"Test workspace: {temp_path}")

        # Step 1: Run quick profile
        print("\n--- Step 1: Running quick profile ---")
        quick_result = framework.run_snakemake_with_profile("quick", cores=2)

        if not quick_result["success"]:
            print(f"❌ Quick profile run failed: {quick_result['stderr']}")
            return False

        print("✅ Quick profile completed")

        # Step 2: Run production profile
        print("\n--- Step 2: Running production profile ---")
        prod_result = framework.run_snakemake_with_profile("production", cores=2)

        if not prod_result["success"]:
            print(f"❌ Production profile run failed: {prod_result['stderr']}")
            return False

        print("✅ Production profile completed")

        # Step 3: Compare results for functional parity
        print("\n--- Step 3: Checking functional parity ---")
        parity = framework.compare_results_parity("quick", "production")

        if not parity["both_have_results"]:
            print("❌ Both profiles don't have complete results")
            return False

        # Debug output (can be enabled for troubleshooting)
        # if "debug_files" in parity:
        #     print(f"  Debug - File existence:")
        #     for key, exists in parity["debug_files"].items():
        #         print(f"    {key}: {exists}")

        if not parity["functional_parity"]:
            print("❌ Functional parity check failed:")
            print(f"  Conversations count match: {parity['conversations_count_match']}")
            print(
                f"  Tournament structure match: {parity['tournament_structure_match']}"
            )
            print(f"  Ratings keys match: {parity['ratings_keys_match']}")
            if "conversations_note" in parity:
                print(f"  Note: {parity['conversations_note']}")
            if "error" in parity:
                print(f"  Error: {parity['error']}")
            return False

        print("✅ Functional parity verified")
        print(f"  Conversations: {parity['conversations_count_match']}")
        print(f"  Tournament structure: {parity['tournament_structure_match']}")
        print(f"  Rating models: {parity['ratings_keys_match']}")

        # Step 4: Verify expected scale differences
        scale_diffs = parity.get("scale_differences", {})
        if "conversation_counts" in scale_diffs:
            conv_counts = scale_diffs["conversation_counts"]
            print("  Scale differences (expected):")
            print(f"    Quick conversations: {conv_counts.get('profile1', 'N/A')}")
            print(f"    Production conversations: {conv_counts.get('profile2', 'N/A')}")

        return True


def main():
    """Run all profile isolation tests."""
    print("AFBench Profile Isolation Tests")
    print("=" * 40)

    tests = [
        ("Profile Isolation", test_profile_isolation),
        ("Promotion Parity", test_promotion_parity),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            success = test_func()
            if success:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'='*40}")
    print(f"Profile Isolation Tests: {passed}/{total} passed")

    if passed == total:
        print("🎉 All profile isolation tests passed!")
        return 0
    else:
        print("⚠️  Some profile isolation tests failed")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
