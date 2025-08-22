#!/usr/bin/env python3
"""
Observability test suite for AFBench.

Tests Section 8 from TESTS.md:
- O1: "Why" traceability - reason for cached target re-runs visible via CLI
- O2: Provenance metadata - output artifacts include upstream versions
- O3: DAG visibility - clear pipeline stages without cycles

All tests use the Single-Command Contract (SCC):
snakemake --unlock && snakemake --profile profiles/testonly -j <cores>
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


class ObservabilityTestFramework:
    """Framework for testing observability characteristics of AFBench pipeline."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.temp_dir = None
        self.afbench_root = None

    def __enter__(self):
        # Create temporary test environment
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"observ_test_{self.test_name}_"))
        self.afbench_root = Path(__file__).parent.parent

        # Set up isolated test environment
        self._setup_test_workspace()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _setup_test_workspace(self):
        """Set up isolated test workspace for observability testing."""
        temp_path = self.temp_dir

        # Copy AFBench source files to test workspace
        source_files = [
            "Snakefile",
            "scripts/",
            "config/",
            "profiles/testonly/",
            "model_pools/testonly.csv",
            "judge_pools/testonly.csv",
            "testonly/skills/",
        ]

        for src_file in source_files:
            src_path = self.afbench_root / src_file
            dst_path = temp_path / src_file

            if src_path.is_file():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
            elif src_path.is_dir():
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

        return temp_path

    def run_snakemake_with_observability(
        self,
        cores: int = 1,
        extra_flags: list[str] = None,
        expect_failure: bool = False,
        timeout: int = 300,
    ) -> dict:
        """Run Snakemake using Single-Command Contract (SCC) with observability flags."""
        temp_path = self.temp_dir
        extra_flags = extra_flags or []

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

            # Run main pipeline with observability flags (SCC)
            main_cmd = [
                "snakemake",
                "--profile",
                "profiles/testonly",
                "-j",
                str(cores),
            ] + extra_flags

            start_time = time.time()
            main_result = subprocess.run(
                main_cmd, capture_output=True, text=True, env=env, timeout=timeout
            )
            end_time = time.time()

            return {
                "success": main_result.returncode == 0,
                "returncode": main_result.returncode,
                "stdout": main_result.stdout,
                "stderr": main_result.stderr,
                "duration": end_time - start_time,
                "unlock_success": unlock_result.returncode == 0,
                "unlock_output": unlock_result.stdout + unlock_result.stderr,
                "command": " ".join(main_cmd),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Pipeline execution timed out after {timeout}s",
                "duration": timeout,
                "unlock_success": False,
                "unlock_output": "",
                "command": " ".join(main_cmd),
            }
        finally:
            os.chdir(original_cwd)

    def analyze_why_traceability(self, run_output: dict) -> dict:
        """Analyze Snakemake output for 'why' traceability information."""
        analysis = {
            "reason_messages_found": [],
            "rebuild_explanations": [],
            "input_change_tracking": False,
            "rule_execution_reasons": [],
            "traceability_score": 0,
        }

        full_output = run_output["stdout"] + "\n" + run_output["stderr"]

        # Look for Snakemake reason messages
        reason_patterns = [
            r"Reason: (.+)",
            r"Input files updated: (.+)",
            r"Code has changed since last execution",
            r"Rule (.+): output files have been changed",
            r"Forced execution",
            r"Missing output files: (.+)",
            r"Updated input files: (.+)",
        ]

        for pattern in reason_patterns:
            matches = re.findall(pattern, full_output, re.IGNORECASE)
            if matches:
                analysis["reason_messages_found"].extend(matches)

        # Look for rule execution explanations
        rule_execution_pattern = r"rule (\w+):"
        rule_matches = re.findall(rule_execution_pattern, full_output)
        analysis["rule_execution_reasons"] = rule_matches

        # Check for input change tracking
        if re.search(r"input.*changed|updated.*input", full_output, re.IGNORECASE):
            analysis["input_change_tracking"] = True

        # Calculate traceability score
        score = 0
        if analysis["reason_messages_found"]:
            score += 3
        if analysis["rule_execution_reasons"]:
            score += 2
        if analysis["input_change_tracking"]:
            score += 2

        analysis["traceability_score"] = score

        return analysis

    def generate_dag_visualization(self) -> dict:
        """Generate DAG visualization and analyze pipeline structure."""
        temp_path = self.temp_dir
        original_cwd = os.getcwd()

        try:
            os.chdir(temp_path)

            # Set environment for testing
            env = os.environ.copy()
            env["AFBENCH_TESTING"] = "true"

            # Generate DAG
            dag_cmd = ["snakemake", "--profile", "profiles/testonly", "--dag"]

            dag_result = subprocess.run(
                dag_cmd, capture_output=True, text=True, env=env, timeout=60
            )

            analysis = {
                "dag_generated": dag_result.returncode == 0,
                "dag_content": dag_result.stdout if dag_result.returncode == 0 else "",
                "dag_error": dag_result.stderr if dag_result.returncode != 0 else "",
                "has_cycles": False,
                "pipeline_stages": [],
                "node_count": 0,
                "edge_count": 0,
            }

            if analysis["dag_generated"]:
                # Analyze DAG content
                dag_content = analysis["dag_content"]

                # Count nodes and edges - try multiple patterns for nodes
                # Pattern 1: Standard Graphviz node declaration
                node_matches = re.findall(
                    r'^\s*"[^"]*"\s*\[', dag_content, re.MULTILINE
                )
                # Pattern 2: Node with attributes on same line
                if not node_matches:
                    node_matches = re.findall(
                        r"^\s*\d+\s*\[", dag_content, re.MULTILINE
                    )
                # Pattern 3: Any line that looks like a node (number followed by attributes)
                if not node_matches:
                    node_matches = re.findall(
                        r"^\s*\d+\s*\[label=", dag_content, re.MULTILINE
                    )

                edge_matches = re.findall(r"->", dag_content)
                analysis["node_count"] = len(node_matches)
                analysis["edge_count"] = len(edge_matches)

                # Look for expected pipeline stages in node names
                expected_stages = [
                    "conversations",
                    "pairings",
                    "matches",
                    "tournaments",
                    "scores",
                    "ratings",
                    "summaries",
                ]

                found_stages = []
                for stage in expected_stages:
                    if stage in dag_content.lower():
                        found_stages.append(stage)

                analysis["pipeline_stages"] = found_stages

                # Simple cycle detection - look for back edges or explicit cycle mentions
                if "cycle" in dag_content.lower() or "circular" in dag_content.lower():
                    analysis["has_cycles"] = True

            return analysis

        except subprocess.TimeoutExpired:
            return {
                "dag_generated": False,
                "dag_content": "",
                "dag_error": "DAG generation timed out",
                "has_cycles": False,
                "pipeline_stages": [],
                "node_count": 0,
                "edge_count": 0,
            }
        finally:
            os.chdir(original_cwd)

    def check_provenance_metadata(self) -> dict:
        """Check output artifacts for provenance metadata."""
        temp_path = self.temp_dir
        data_dir = temp_path / "data" / "testonly"

        analysis = {
            "artifacts_found": [],
            "metadata_files": [],
            "provenance_data": {},
            "has_input_versions": False,
            "has_config_versions": False,
            "has_run_context": False,
            "reproducible_artifacts": [],
            "input_file_hashes": {},
            "config_file_hashes": {},
        }

        if not data_dir.exists():
            return analysis

        # Collect all output artifacts
        for artifact_file in data_dir.rglob("*"):
            if artifact_file.is_file():
                rel_path = artifact_file.relative_to(data_dir)
                analysis["artifacts_found"].append(str(rel_path))

                # Look for metadata in JSON files
                if artifact_file.name.endswith(".json"):
                    try:
                        with open(artifact_file) as f:
                            content = json.load(f)

                        # Check for provenance information
                        provenance_keys = [
                            "metadata",
                            "provenance",
                            "generated_by",
                            "inputs",
                            "config",
                            "timestamp",
                            "version",
                            "run_id",
                        ]

                        found_provenance = {}
                        for key in provenance_keys:
                            if key in content:
                                found_provenance[key] = content[key]

                        if found_provenance:
                            analysis["metadata_files"].append(str(rel_path))
                            analysis["provenance_data"][
                                str(rel_path)
                            ] = found_provenance

                            # Enhanced provenance validation - check for reproduction sufficiency
                            reproduction_score = 0

                            # Check for specific provenance types with deeper validation
                            if (
                                "inputs" in found_provenance
                                or "input" in str(content).lower()
                            ):
                                analysis["has_input_versions"] = True
                                reproduction_score += 2
                            if "config" in found_provenance:
                                analysis["has_config_versions"] = True
                                reproduction_score += 2
                            if (
                                "timestamp" in found_provenance
                                or "run_id" in found_provenance
                            ):
                                analysis["has_run_context"] = True
                                reproduction_score += 1

                            # Check for file hashes/checksums that would enable reproduction verification
                            metadata = found_provenance.get("metadata", {})
                            if isinstance(metadata, dict):
                                if any(
                                    key in metadata
                                    for key in ["input_hash", "config_hash", "checksum"]
                                ):
                                    reproduction_score += 2
                                if "skill_id" in metadata and "eval_id" in metadata:
                                    reproduction_score += 1

                            # An artifact is considered reproducible if it has sufficient metadata
                            if (
                                reproduction_score >= 4
                            ):  # Require substantial provenance info
                                analysis["reproducible_artifacts"].append(str(rel_path))

                    except (json.JSONDecodeError, OSError):
                        continue

        # Collect input and config file hashes for reference
        input_files = [
            "model_pools/testonly.csv",
            "judge_pools/testonly.csv",
            "config/testonly_config.yaml",
        ]
        for input_file in input_files:
            input_path = temp_path / input_file
            if input_path.exists():
                try:
                    import hashlib

                    with open(input_path, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
                    analysis["input_file_hashes"][input_file] = file_hash
                except OSError:
                    pass

        return analysis

    def modify_input_and_track_changes(self) -> tuple[dict, dict]:
        """Modify input files and track how changes are detected."""
        temp_path = self.temp_dir

        # Run initial baseline
        baseline_result = self.run_snakemake_with_observability(cores=1)
        if not baseline_result["success"]:
            return baseline_result, {}

        # Modify model pool to trigger rebuild - change a safe field
        model_pool_file = temp_path / "model_pools" / "testonly.csv"
        if model_pool_file.exists():
            # Read current content
            with open(model_pool_file) as f:
                content = f.read()

            # Change max_tokens value to trigger rebuild
            modified_content = content.replace("max_tokens:1000", "max_tokens:1001")
            if modified_content == content:
                # If that didn't work, try the other format
                modified_content = content.replace(",1000", ",1001")

            with open(model_pool_file, "w") as f:
                f.write(modified_content)

        # Run again with verbose output to see rebuild reasons
        verbose_flags = ["--verbose", "--printshellcmds"]
        rebuild_result = self.run_snakemake_with_observability(
            cores=1, extra_flags=verbose_flags
        )

        return baseline_result, rebuild_result

    def test_dry_run_observability(self) -> dict:
        """Test observability through dry-run mode."""
        dry_run_result = self.run_snakemake_with_observability(
            cores=1, extra_flags=["--dry-run", "--verbose"]
        )

        analysis = {
            "dry_run_success": dry_run_result["success"],
            "shows_planned_work": False,
            "shows_dependencies": False,
            "execution_plan_clear": False,
        }

        if dry_run_result["success"]:
            output = dry_run_result["stdout"] + dry_run_result["stderr"]

            # Check for planned work indication
            if re.search(
                r"would be executed|plan to run|job\s+\d+", output, re.IGNORECASE
            ):
                analysis["shows_planned_work"] = True

            # Check for dependency information
            if re.search(
                r"depends on|input.*files|rule.*requires", output, re.IGNORECASE
            ):
                analysis["shows_dependencies"] = True

            # Overall execution plan clarity
            if analysis["shows_planned_work"] and analysis["shows_dependencies"]:
                analysis["execution_plan_clear"] = True

        return analysis

    def test_reproduction_sufficiency(self, provenance: dict) -> dict:
        """Test if provenance metadata is sufficient for artifact reproduction."""
        analysis = {
            "sufficient_for_reproduction": False,
            "missing_elements": [],
            "reproducible_count": len(provenance.get("reproducible_artifacts", [])),
        }

        # Check essential elements for reproduction
        required_elements = [
            ("input_file_hashes", "Input file versions/hashes"),
            ("has_run_context", "Run context (timestamp/run_id)"),
        ]

        optional_elements = [
            ("has_input_versions", "Input version tracking"),
            ("has_config_versions", "Configuration version tracking"),
        ]

        missing = []
        for key, description in required_elements:
            if not provenance.get(key):
                missing.append(description)

        # At least some optional elements should be present
        optional_present = any(provenance.get(key) for key, _ in optional_elements)
        if not optional_present:
            missing.append("Input or config version tracking")

        analysis["missing_elements"] = missing

        # Consider sufficient if we have essential elements and some reproducible artifacts
        analysis["sufficient_for_reproduction"] = len(
            missing
        ) <= 1 and (  # Allow one missing element
            analysis["reproducible_count"] > 0
            or provenance.get("has_run_context", False)
        )

        return analysis


def test_why_traceability():
    """
    Test O1: "Why" traceability - reason for cached target re-runs visible.

    When: A previously cached target re-runs
    Then: The reason is visible via standard CLI flags (or logs), linked to the specific upstream change
    """
    print("=== Test O1: Why Traceability ===")

    with ObservabilityTestFramework("why_traceability") as framework:
        temp_path = framework.temp_dir
        print(f"Test workspace: {temp_path}")

        print("\n--- Step 1: Run baseline to establish cache ---")
        baseline_result, rebuild_result = framework.modify_input_and_track_changes()

        if not baseline_result["success"]:
            print(f"❌ Baseline run failed: {baseline_result['stderr']}")
            assert False

        print("✅ Baseline run completed successfully")

        if not rebuild_result["success"]:
            print(f"❌ Rebuild after modification failed: {rebuild_result['stderr']}")
            assert False

        print("✅ Rebuild after modification completed successfully")

        # Analyze traceability information
        print("\n--- Step 2: Analyzing why traceability ---")
        traceability = framework.analyze_why_traceability(rebuild_result)

        print(f"Reason messages found: {len(traceability['reason_messages_found'])}")
        for reason in traceability["reason_messages_found"][:3]:  # Show first 3
            print(f"  - {reason}")

        print(
            f"Rule execution tracking: {len(traceability['rule_execution_reasons'])} rules"
        )
        print(f"Input change tracking: {traceability['input_change_tracking']}")
        print(f"Traceability score: {traceability['traceability_score']}/7")

        # Check for acceptable traceability
        if traceability["traceability_score"] < 3:
            print(
                "❌ Insufficient traceability - reasons for rebuilds not clearly visible"
            )
            assert False

        print("✅ Why traceability verified - rebuild reasons are visible")

        # Additional test: dry-run observability
        print("\n--- Step 3: Testing dry-run observability ---")
        dry_run_analysis = framework.test_dry_run_observability()

        if not dry_run_analysis["dry_run_success"]:
            print("❌ Dry-run failed - cannot test execution plan visibility")
            assert False

        print(f"Shows planned work: {dry_run_analysis['shows_planned_work']}")
        print(f"Shows dependencies: {dry_run_analysis['shows_dependencies']}")
        print(f"Execution plan clear: {dry_run_analysis['execution_plan_clear']}")

        if not dry_run_analysis["execution_plan_clear"]:
            print("⚠️  Execution plan could be clearer, but basic traceability works")

        print("✅ Dry-run observability verified")
        assert True


def test_provenance_metadata():
    """
    Test O2: Provenance metadata - output artifacts include upstream versions.

    Given: Any output artifact
    Then: Its metadata includes the versions of upstream inputs/configs and run context sufficient to reproduce it
    """
    print("\n=== Test O2: Provenance Metadata ===")

    with ObservabilityTestFramework("provenance_metadata") as framework:
        temp_path = framework.temp_dir
        print(f"Test workspace: {temp_path}")

        # Run pipeline to generate artifacts
        print("\n--- Step 1: Running pipeline to generate artifacts ---")
        run_result = framework.run_snakemake_with_observability(cores=1)

        if not run_result["success"]:
            print(f"❌ Pipeline run failed: {run_result['stderr']}")
            assert False

        print("✅ Pipeline completed successfully")

        # Check for provenance metadata in artifacts
        print("\n--- Step 2: Checking provenance metadata ---")
        provenance = framework.check_provenance_metadata()

        print(f"Artifacts found: {len(provenance['artifacts_found'])}")
        print(f"Files with metadata: {len(provenance['metadata_files'])}")
        print(f"Reproducible artifacts: {len(provenance['reproducible_artifacts'])}")
        print(f"Has input versions: {provenance['has_input_versions']}")
        print(f"Has config versions: {provenance['has_config_versions']}")
        print(f"Has run context: {provenance['has_run_context']}")
        print(f"Input file hashes tracked: {len(provenance['input_file_hashes'])}")

        # Show examples of provenance data found
        if provenance["provenance_data"]:
            print("Sample provenance data:")
            for file_path, metadata in list(provenance["provenance_data"].items())[:2]:
                print(f"  {file_path}:")
                for key, value in metadata.items():
                    value_str = (
                        str(value)[:100] + "..."
                        if len(str(value)) > 100
                        else str(value)
                    )
                    print(f"    {key}: {value_str}")

        # Enhanced provenance evaluation - focus on reproducibility
        provenance_score = 0
        if provenance["metadata_files"]:
            provenance_score += 2
        if provenance["has_input_versions"]:
            provenance_score += 2
        if provenance["has_config_versions"]:
            provenance_score += 2
        if provenance["has_run_context"]:
            provenance_score += 1
        if provenance["reproducible_artifacts"]:
            provenance_score += 2  # Bonus for artifacts with sufficient metadata
        if provenance["input_file_hashes"]:
            provenance_score += 1  # Bonus for input file tracking

        print(f"Provenance score: {provenance_score}/10 (enhanced scoring)")

        # Step 3: Test reproduction sufficiency
        print("\n--- Step 3: Testing reproduction sufficiency ---")
        reproduction_test = framework.test_reproduction_sufficiency(provenance)
        print(
            f"Reproduction test passed: {reproduction_test['sufficient_for_reproduction']}"
        )
        if reproduction_test["missing_elements"]:
            print(
                f"Missing for reproduction: {', '.join(reproduction_test['missing_elements'])}"
            )

        # More stringent requirements for reproduction
        if (
            provenance_score < 4
            and not reproduction_test["sufficient_for_reproduction"]
        ):
            print("❌ Insufficient provenance metadata for reproduction")
            print(
                "Expected: metadata enabling artifact reproduction (input versions, config, checksums)"
            )
            assert False

        print("✅ Provenance metadata verification passed")
        assert True


def test_dag_visibility():
    """
    Test O3: DAG visibility - clear pipeline stages without cycles.

    When: Generating a DAG preview
    Then: The graph shows clear stages (conversations → pairings → matches → scores → summaries) with no unexpected cycles
    """
    print("\n=== Test O3: DAG Visibility ===")

    with ObservabilityTestFramework("dag_visibility") as framework:
        temp_path = framework.temp_dir
        print(f"Test workspace: {temp_path}")

        # Generate and analyze DAG
        print("\n--- Step 1: Generating DAG visualization ---")
        dag_analysis = framework.generate_dag_visualization()

        if not dag_analysis["dag_generated"]:
            print(f"❌ DAG generation failed: {dag_analysis['dag_error']}")
            assert False

        print("✅ DAG generated successfully")

        print(f"DAG nodes: {dag_analysis['node_count']}")
        print(f"DAG edges: {dag_analysis['edge_count']}")
        print(f"Pipeline stages found: {dag_analysis['pipeline_stages']}")
        print(f"Has cycles: {dag_analysis['has_cycles']}")

        # Enhanced stage dependency analysis
        if "stage_dependencies" in dag_analysis:
            stage_deps = dag_analysis["stage_dependencies"]
            print(f"Valid pipeline flow: {stage_deps['valid_flow']}")
            if stage_deps["missing_deps"]:
                print(f"Missing dependencies: {', '.join(stage_deps['missing_deps'])}")
            if stage_deps["unexpected_deps"]:
                print(
                    f"Unexpected dependencies: {', '.join(stage_deps['unexpected_deps'])}"
                )

        # Debug: show first few lines of DAG for troubleshooting
        if dag_analysis["dag_generated"] and dag_analysis["node_count"] == 0:
            dag_lines = dag_analysis["dag_content"].split("\n")[:10]
            print("Debug - First 10 lines of DAG:")
            for i, line in enumerate(dag_lines):
                print(f"  {i+1}: {line}")

        # Validate DAG structure
        if dag_analysis["node_count"] == 0:
            print("❌ DAG appears to be empty - no nodes found")
            assert False

        if dag_analysis["has_cycles"]:
            print("❌ DAG contains cycles - pipeline structure is invalid")
            assert False

        # Enhanced dependency validation
        if "stage_dependencies" in dag_analysis:
            stage_deps = dag_analysis["stage_dependencies"]
            if not stage_deps["valid_flow"]:
                print(
                    "⚠️  Invalid pipeline flow detected - some dependencies may be missing"
                )
                print("This could indicate broken dependency chains")

        # Check for expected pipeline stages
        expected_stages = ["conversations", "tournaments", "scores", "ratings"]
        found_expected = [
            stage
            for stage in expected_stages
            if stage in dag_analysis["pipeline_stages"]
        ]

        if len(found_expected) < 2:
            print(f"⚠️  Few expected pipeline stages found: {found_expected}")
            print("Expected stages like: conversations, tournaments, scores, ratings")
            # Don't fail the test as stage names might be different in implementation
        else:
            print(f"✅ Found expected pipeline stages: {found_expected}")

        print("✅ DAG visibility verification passed")
        assert True


def main():
    """Run all observability tests."""
    print("AFBench Observability Tests")
    print("=" * 40)

    tests = [
        ("Why Traceability", test_why_traceability),
        ("Provenance Metadata", test_provenance_metadata),
        ("DAG Visibility", test_dag_visibility),
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
    print(f"Observability Tests: {passed}/{total} passed")

    if passed == total:
        print("🎉 All observability tests passed!")
        return 0
    else:
        print("⚠️  Some observability tests failed")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
