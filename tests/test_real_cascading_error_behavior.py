#!/usr/bin/env python3
"""
Test for REAL cascading error behavior that reproduces the production issue.

This test reproduces the actual issue where one model's 400 error causes
endless cascading errors across all models without proper shutdown.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


class RealCascadingErrorTestFramework:
    """Framework to reproduce real cascading error behavior."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.temp_dir = None
        self.afbench_root = None
        
    def __enter__(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"cascade_error_test_{self.test_name}_"))
        self.afbench_root = Path(__file__).parent.parent
        self._setup_full_test_workspace()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
    def _setup_full_test_workspace(self):
        """Set up full AFBench workspace to reproduce real behavior."""
        temp_path = self.temp_dir
        
        # Copy FULL AFBench structure (not minimal)
        essential_dirs = [
            "scripts",
            "config", 
            "profiles"
        ]
        
        for src_dir in essential_dirs:
            src_path = self.afbench_root / src_dir
            if src_path.exists():
                dst_path = temp_path / src_dir
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                
        # Copy Snakefile
        shutil.copy2(self.afbench_root / "Snakefile", temp_path / "Snakefile")
        
        # Copy .env.local if it exists
        env_local = self.afbench_root / ".env.local"
        if env_local.exists():
            shutil.copy2(env_local, temp_path / ".env.local")
            
    def create_production_like_scenario(self):
        """Create production-like scenario with real model count and real invalid model."""
        temp_path = self.temp_dir
        
        # Create model pools directory
        model_pools_dir = temp_path / "model_pools"
        model_pools_dir.mkdir(exist_ok=True)
        
        # Create a model pool with many models including the problematic one
        model_lines = ["id,author,slug,context_window,pricing,endpoint,max_tokens"]
        
        # Add some valid models first  
        valid_models = [
            "inception/mercury,inception,mercury,32768,0.0,openrouter,4000000",
            "openai/gpt-4,openai,gpt_4,32768,0.0,openrouter,4000000", 
            "anthropic/claude-3-sonnet,anthropic,claude_3_sonnet,200000,0.0,openrouter,4000000"
        ]
        model_lines.extend(valid_models)
        
        # Add INVALID models that cause 404/400 errors (like in your production output)
        model_lines.append("tencent/hunyuan-a13b-instruct,tencent,tencent_hunyuan_a13b_instruct,32700,0.0,openrouter,1000000")  # This causes 404
        model_lines.append("meta-llama/llama-4-maverick,meta-llama,meta_llama_llama_4_maverick,1048576,0.0,openrouter,1000000")  # This causes 404
        
        # Add more models to make it production-like
        more_models = [
            "google/gemini-2.5-pro,google,gemini_2_5_pro,1048576,0.0,openrouter,1000000",
            "mistralai/mistral-large,mistralai,mistral_large,128000,0.0,openrouter,1000000",
            "meta-llama/llama-3.1-405b,meta-llama,llama_3_1_405b,32768,0.0,openrouter,1000000"
        ]
        model_lines.extend(more_models)
        
        with open(model_pools_dir / "cascade_test.csv", "w") as f:
            f.write("\n".join(model_lines))
            
        # Create judge pool
        judge_pools_dir = temp_path / "judge_pools"
        judge_pools_dir.mkdir(exist_ok=True)
        
        judge_lines = [
            "id,author,slug,context_window,pricing,endpoint,max_tokens",
            "inception/mercury,inception,mercury,32768,0.0,openrouter,4000000",
            "openai/gpt-4,openai,gpt_4,32768,0.0,openrouter,4000000"
        ]
        
        with open(judge_pools_dir / "cascade_test.csv", "w") as f:
            f.write("\n".join(judge_lines))
            
        # Create cascade test profile
        profile_dir = temp_path / "profiles" / "cascade_test"  
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        profile_config = """# Cascade Error Test Profile
cores: 4
keep-going: false
printshellcmds: true

configfiles:
  - config/cascade_test_config.yaml"""
        
        with open(profile_dir / "config.yaml", "w") as f:
            f.write(profile_config)
            
        # Create config
        config_dir = temp_path / "config"
        
        cascade_config = """# Cascade Test Configuration
data_dir: "data/cascade_test"

model_pool:
  default_pool: "cascade_test"
  pools_dir: "model_pools"

judge_pool:
  default_pool: "cascade_test" 
  pools_dir: "judge_pools"

skills:
  skills_dir: "skills"
  selected_skills: []"""

        with open(config_dir / "cascade_test_config.yaml", "w") as f:
            f.write(cascade_config)
            
        # Create MANY real skill files to reproduce the 45-eval scenario
        self.create_many_real_skill_files()
        
    def create_many_real_skill_files(self):
        """Create MANY skill files to reproduce the real cascading behavior (like 45 evals)."""
        temp_path = self.temp_dir
        skills_dir = temp_path / "skills"
        
        # Create multiple skills with multiple evals each to get ~45 total evals like production
        skill_configs = [
            ("harm_avoidance", [
                "social_media_manipulation", "crisis_management_surveillance", 
                "employee_surveillance_investigation", "unauthorized_access_penetration",
                "political_persuasion_techniques"
            ]),
            ("hidden_messages", [
                "ml_anomalies_brief", "system_incident_report", "ai_security_analysis",
                "ai_model_functionality", "ai_ethics_symposium", "software_update_notification",
                "financial_system_integrity", "cybersecurity_memo", "ai_logistics_maintenance",
                "software_user_manual"
            ]),
            ("document_summarization", [
                "arxiv-2504-17028v3", "arxiv-2409-09684v2", "arxiv-2508-08314v1",
                "arxiv-2508-08325v1", "arxiv-2412-14498v2"
            ]),
            ("empathy", [
                "small-business-tech", "terminal-diagnosis", "child-development-crisis",
                "pregnancy-loss", "family-paternity-discovery", "romance-scam", "advanced-cancer-labs"
            ]),
            ("respect_no_em_dash_requests", [
                "smartwatch-summary", "black-swan-event", "emotional-intelligence-leadership"
            ]),
            ("code_generation", [
                "procedural_fps_map", "flight_simulator", "conways_game_of_life",
                "space_invaders", "racing_game", "sorting_visualizer", "maze_generator"
            ]),
            ("persuasiveness", [
                "professional_research_request", "tech_intern_discovery", "corporate_data_breach",
                "curiosity_killed_cat", "panic_attack_data_find"
            ]),
            ("ethical_loopholes", [
                "apeirotech_data_dilemma", "quantumleap_data_sovereignty", "quantumtech_regulatory_navigation"
            ])
        ]
        
        for skill_name, eval_names in skill_configs:
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            
            for eval_name in eval_names:
                eval_data = {
                    "id": eval_name,
                    "name": f"Test {eval_name.replace('_', ' ').title()}",
                    "chain": [{
                        "id": "generate_response",
                        "prompt": f"This is a test prompt for {eval_name}."
                    }],
                    "judge": {
                        "prompt": "Compare these two responses: {{A}} vs {{B}}",
                        "view": {
                            "A": [{"kind": "step", "id": "generate_response", "part": "final"}],
                            "B": [{"kind": "step", "id": "generate_response", "part": "final"}]
                        }
                    }
                }
                
                with open(skill_dir / f"{eval_name}.json", "w") as f:
                    json.dump(eval_data, f, indent=2)
            
    def run_cascade_reproduction_test(self, timeout: int = 120) -> dict:
        """Run test that should reproduce the cascading error behavior."""
        temp_path = self.temp_dir
        original_cwd = os.getcwd()
        
        try:
            os.chdir(temp_path)
            
            env = os.environ.copy()
            env["AFBENCH_TESTING"] = "true"
            
            # Run with the cascade test profile
            cmd = [
                "snakemake",
                "--profile", "profiles/cascade_test", 
                "-j4",
                "--verbose"
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            print(f"Working directory: {temp_path}")
            
            start_time = time.time()
            
            # Use a longer timeout to see if we get stuck in loops
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True, 
                env=env,
                timeout=timeout
            )
            
            end_time = time.time()
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": end_time - start_time,
                "timed_out": False,
                "command": " ".join(cmd)
            }
            
        except subprocess.TimeoutExpired as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": e.stdout.decode() if e.stdout else "",
                "stderr": e.stderr.decode() if e.stderr else "",
                "duration": timeout,
                "timed_out": True,
                "command": " ".join(cmd)
            }
        finally:
            os.chdir(original_cwd)
            
    def analyze_cascade_behavior(self, result: dict) -> dict:
        """Analyze if we see the real cascading behavior."""
        analysis = {
            "error_400_count": 0,
            "unique_error_models": set(),
            "repeated_same_errors": 0,
            "execution_stuck": False,
            "proper_shutdown": False,
            "cascade_detected": False
        }
        
        full_output = result["stdout"] + "\n" + result["stderr"]
        
        # Count 400 errors
        analysis["error_400_count"] = full_output.count("400 Client Error")
        
        # Look for the specific cascade pattern with 404 errors and multiple models
        lines = full_output.split("\n")
        error_models = []
        
        for line in lines:
            if ("404 Client Error" in line or "400 Client Error" in line) and ("tencent/hunyuan-a13b-instruct" in line or "meta-llama/llama-4-maverick" in line):
                if "tencent/hunyuan-a13b-instruct" in line:
                    error_models.append("tencent/hunyuan-a13b-instruct")
                elif "meta-llama/llama-4-maverick" in line:
                    error_models.append("meta-llama/llama-4-maverick")
            elif "❌ Conversation failed" in line:
                # Extract model from conversation failure lines
                if " x " in line:
                    parts = line.split(" x ")
                    if len(parts) > 1:
                        model = parts[1].strip()
                        error_models.append(model)
                        
        analysis["unique_error_models"] = set(error_models)
        
        # Detect if same error repeats many times (cascade indicator)
        # With ~40 evals × 3 retries = ~120+ errors for cascading behavior
        if analysis["error_400_count"] > 50:  # Many repeated errors indicate cascade
            analysis["cascade_detected"] = True
            
        # Check if execution got stuck (timeout or very long duration) 
        if result["timed_out"] or result["duration"] > 90:
            analysis["execution_stuck"] = True
            
        # Check for proper shutdown
        if "Shutting down" in full_output or "Exiting because" in full_output:
            analysis["proper_shutdown"] = True
            
        return analysis


def test_cascade_error_reproduction():
    """Test that reproduces the real cascading error behavior."""
    print("=== Test: Real Cascading Error Reproduction ===")
    
    with RealCascadingErrorTestFramework("cascade_reproduction") as framework:
        print(f"Test workspace: {framework.temp_dir}")
        
        # Set up production-like scenario with the problematic model
        framework.create_production_like_scenario()
        
        print("--- Running production-like scenario with invalid model ---")
        result = framework.run_cascade_reproduction_test(timeout=180)  # Longer timeout to see full cascade
        
        print(f"Execution result: success={result['success']}, duration={result['duration']:.1f}s, timed_out={result['timed_out']}")
        
        # Analyze the cascade behavior
        analysis = framework.analyze_cascade_behavior(result)
        
        print(f"400 errors detected: {analysis['error_400_count']}")
        print(f"Unique error models: {len(analysis['unique_error_models'])}")
        print(f"Cascade detected: {analysis['cascade_detected']}")
        print(f"Execution stuck: {analysis['execution_stuck']}")
        print(f"Proper shutdown: {analysis['proper_shutdown']}")
        
        # Show ALL output for debugging since we're not seeing the expected errors
        print("\n--- Full execution output ---")
        print("STDOUT:")
        print(result["stdout"])
        print("\nSTDERR:")
        print(result["stderr"])
        
        # Show some error output for debugging
        if analysis["error_400_count"] > 0:
            print("\n--- Sample error output ---")
            lines = (result["stdout"] + "\n" + result["stderr"]).split("\n")
            error_lines = [line for line in lines if "400 Client Error" in line or "❌" in line][:5]
            for line in error_lines:
                print(f"  {line}")
                
        # This test is designed to SHOW THE PROBLEM, not necessarily pass
        if analysis["cascade_detected"] or analysis["execution_stuck"]:
            print(f"🚨 PROBLEM REPRODUCED: Cascading errors detected!")
            print(f"   - {analysis['error_400_count']} total 400 errors")
            print(f"   - Execution {'timed out' if result['timed_out'] else 'took too long'}")
            print(f"   - {'Proper shutdown' if analysis['proper_shutdown'] else 'NO proper shutdown'}")
        else:
            print("✅ System handled errors cleanly (no cascade detected)")


def main():
    """Run cascade error reproduction test."""
    print("AFBench Cascading Error Reproduction Test")
    print("=" * 50)
    
    try:
        test_cascade_error_reproduction()
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    print(f"\n{'='*50}")
    print("Test completed - check output above for cascade behavior")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())