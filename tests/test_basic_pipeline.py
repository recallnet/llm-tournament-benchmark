"""
Basic Pipeline Test - Verify the pipeline works end-to-end

Before we can test invalidation behavior, we need to ensure
the basic pipeline works correctly in our test environment.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class BasicPipelineTest:
    """Test basic pipeline functionality."""

    def __init__(self):
        self.temp_dir = None
        self.original_cwd = None
        self.original_env = {}

    def __enter__(self):
        """Set up isolated test environment."""
        self.temp_dir = tempfile.mkdtemp(prefix="afbench_basic_test_")
        self.original_cwd = Path.cwd()

        # Copy project structure
        project_root = Path(__file__).parent.parent
        self._copy_project_structure(project_root, Path(self.temp_dir))

        # Change to temp directory
        os.chdir(self.temp_dir)

        # Set up mock environment
        self._setup_mock_environment()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up test environment."""
        self._restore_environment()

        if self.original_cwd:
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
            "testonly",
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

    def _setup_mock_environment(self):
        """Set up mock environment variables."""
        env_vars_to_mock = ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
        for var in env_vars_to_mock:
            if var in os.environ:
                self.original_env[var] = os.environ[var]
            os.environ[var] = "test-mock-key-for-testing"

    def _restore_environment(self):
        """Restore original environment variables."""
        env_vars_to_mock = ["OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
        for var in env_vars_to_mock:
            if var in self.original_env:
                os.environ[var] = self.original_env[var]
            elif var in os.environ:
                del os.environ[var]

    def run_snakemake_scc(self, cores: int = 1, timeout: int = 300):
        """Run Single-Command Contract."""
        # First unlock
        unlock_cmd = ["snakemake", "--unlock"]
        unlock_result = subprocess.run(
            unlock_cmd, capture_output=True, text=True, timeout=30
        )

        if unlock_result.returncode != 0:
            print(f"Unlock failed: {unlock_result.stderr}")
            return unlock_result

        # Run pipeline
        run_cmd = ["snakemake", "--profile", "profiles/testonly", "-j", str(cores)]
        run_result = subprocess.run(
            run_cmd, capture_output=True, text=True, timeout=timeout
        )

        return run_result

    def check_testonly_pools(self):
        """Check what's in the testonly pools."""
        print("=== Model Pool ===")
        model_pool = Path("model_pools/testonly.csv")
        if model_pool.exists():
            print(model_pool.read_text())
        else:
            print("Model pool not found!")

        print("\n=== Judge Pool ===")
        judge_pool = Path("judge_pools/testonly.csv")
        if judge_pool.exists():
            print(judge_pool.read_text())
        else:
            print("Judge pool not found!")

        print("\n=== Skills ===")
        skills_dir = Path("testonly/skills")
        if skills_dir.exists():
            for skill_file in skills_dir.rglob("*.json"):
                print(f"Skill: {skill_file}")
        else:
            print("Skills directory not found!")

    def check_pipeline_outputs(self):
        """Check what the pipeline produced."""
        data_dir = Path("data/testonly")
        if not data_dir.exists():
            print("No data directory found!")
            return

        print("\n=== Pipeline Outputs ===")
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                print(f"{file_path}: {file_path.stat().st_size} bytes")

        # Check loaded models
        loaded_models = data_dir / "loaded_models.json"
        if loaded_models.exists():
            import json

            with open(loaded_models) as f:
                models_data = json.load(f)
            print(
                f"\nLoaded models: {[m['id'] for m in models_data.get('models', [])]}"
            )

    def test_basic_pipeline(self):
        """Test that the basic pipeline works."""
        print("Starting basic pipeline test...")

        # Check what we're working with
        self.check_testonly_pools()

        # Run the pipeline
        result = self.run_snakemake_scc(cores=1, timeout=120)

        print(f"\nPipeline exit code: {result.returncode}")

        if result.returncode != 0:
            print(f"STDERR:\n{result.stderr}")
            print(f"STDOUT:\n{result.stdout}")
        else:
            print("Pipeline completed successfully!")

        # Check what was produced
        self.check_pipeline_outputs()

        return result.returncode == 0


def test_basic_pipeline():
    """Run the basic pipeline test."""
    with BasicPipelineTest() as test:
        success = test.test_basic_pipeline()
        if success:
            print("\n✅ Basic pipeline test PASSED")
        else:
            print("\n❌ Basic pipeline test FAILED")
        return success


if __name__ == "__main__":
    test_basic_pipeline()
