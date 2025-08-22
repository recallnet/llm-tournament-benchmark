#!/usr/bin/env python3
"""
Execute conversations between models and evals using OpenRouter API.
Handles both single-step and multi-step eval chains with proper caching.
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env.local")


class ConversationExecutor:
    """Executes conversations between models and evals with caching."""

    def __init__(self, cache_dir: Path, intermediary_cache_dir: Path):
        # SAFETY: Cache directories must always be provided by caller to prevent path confusion
        self.api_key = os.getenv("OPENROUTER_API_KEY")

        # Allow mock execution for testing environments
        is_testing = (
            os.getenv("AFBENCH_TESTING") == "true"
            or "test" in str(cache_dir).lower()
            or "pytest" in sys.modules
        )

        if not self.api_key and not is_testing:
            raise ValueError("OPENROUTER_API_KEY not found in environment")
        elif is_testing and not self.api_key:
            print("⚠️  Running in testing mode without OPENROUTER_API_KEY")
            self.api_key = "mock-api-key-for-testing"

        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.intermediary_cache_dir = intermediary_cache_dir
        self.intermediary_cache_dir.mkdir(parents=True, exist_ok=True)

        # Rate limiting
        self.last_request_time = 0
        self.min_interval = 0.1  # 100ms between requests

    def _rate_limit(self):
        """Apply rate limiting between API calls."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _generate_cache_key(self, model_id: str, eval_data: dict[str, Any]) -> str:
        """Generate a unique cache key for model-eval combination."""
        # Always use eval data content hash for reliable cache invalidation
        # This ensures changes in eval configuration properly invalidate cache
        eval_data_for_hash = {k: v for k, v in eval_data.items() if k != "_metadata"}
        eval_content = json.dumps(eval_data_for_hash, sort_keys=True)
        cache_content = f"{model_id}:{eval_content}"

        return hashlib.sha256(cache_content.encode()).hexdigest()[:16]

    def _get_cache_path(
        self, skill_id: str, eval_id: str, model_id: str, cache_key: str
    ) -> Path:
        """Get the cache file path for a conversation."""
        safe_model_id = model_id.replace("/", "_").replace(":", "_")
        filename = f"{eval_id}_{safe_model_id}_{cache_key}.json"
        return self.cache_dir / skill_id / filename

    def _load_from_cache(self, cache_path: Path) -> dict[str, Any] | None:
        """Load conversation from cache if it exists."""
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                # Corrupted cache, remove it
                cache_path.unlink(missing_ok=True)
        return None

    def _save_to_cache(self, cache_path: Path, conversation_data: dict[str, Any]):
        """Save conversation to cache."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(conversation_data, f, indent=2)

    def _make_api_request(
        self, model_id: str, messages: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Make a request to OpenRouter API."""
        self._rate_limit()

        # Check for fault injection during testing
        fault_injection = self._check_fault_injection(model_id)
        if fault_injection.get("should_fail"):
            raise requests.exceptions.HTTPError(fault_injection["error_message"])

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://recall.network/",
            "X-Title": "Recall Network"
        }

        payload = {"model": model_id, "messages": messages}

        # In testing mode, return mock response
        if self.api_key == "mock-api-key-for-testing":
            return {
                "choices": [
                    {
                        "message": {
                            "content": f"Mock response from {model_id}: "
                            + messages[-1]["content"]
                        }
                    }
                ]
            }

        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def _check_fault_injection(self, model_id: str) -> dict:
        """Check if fault injection is configured for this model."""
        # Look for fault injection config file
        fault_config_paths = [
            Path.cwd() / ".fault_injection.json",
            Path("/tmp/.fault_injection.json"),
        ]

        for config_path in fault_config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)

                    # print(f"🔍 Fault injection check for {model_id}: config={config}")  # Debug output

                    # Check if this model should fail
                    if config.get("target") == "conversations" and (
                        config.get("model_id") == model_id
                        or config.get("model_id") == "all"
                    ):

                        failure_count = config.get("failure_count", 0)
                        if failure_count > 0:
                            # Track retry attempts for validation
                            retry_attempts = config.get("retry_attempts", 0) + 1
                            config["retry_attempts"] = retry_attempts

                            # Decrement failure count
                            config["failure_count"] = failure_count - 1
                            with open(config_path, "w") as f:
                                json.dump(config, f)

                            print(
                                f"💥 Triggering fault injection for {model_id} (attempt {retry_attempts}, remaining failures: {failure_count - 1})"
                            )
                            return {
                                "should_fail": True,
                                "error_message": f"Injected failure for model {model_id} (attempt {retry_attempts}, remaining: {failure_count - 1})",
                            }
                except (json.JSONDecodeError, OSError) as e:
                    print(f"⚠️  Error reading fault injection config: {e}")

        return {"should_fail": False}

    def _resolve_file_references(self, text: str) -> str:
        """Resolve ${file:...} references in text."""
        import re

        def replace_file_ref(match):
            file_path = match.group(1)
            try:
                with open(file_path) as f:
                    return f.read()
            except (OSError, FileNotFoundError) as e:
                return f"[FILE_ERROR: {e}]"

        return re.sub(r"\$\{file:([^}]+)\}", replace_file_ref, text)

    def _prepare_step_inputs(
        self, step: dict[str, Any], conversation_history: list[dict[str, str]]
    ) -> str:
        """Prepare inputs for a step, resolving dependencies and file references."""
        prompt = step["prompt"]

        # Resolve file references in prompt
        prompt = self._resolve_file_references(prompt)

        # Handle custom inputs
        if "inputs" in step:
            for key, value in step["inputs"].items():
                # Resolve file references in input values
                resolved_value = self._resolve_file_references(str(value))
                placeholder = "{{" + key + "}}"
                prompt = prompt.replace(placeholder, resolved_value)

        return prompt

    def _get_intermediary_cache_path(
        self,
        skill_id: str,
        eval_id: str,
        intermediary_id: str,
        judge_model_id: str,
        cache_key: str,
    ) -> Path:
        """Get cache path for intermediary execution."""
        safe_judge_id = judge_model_id.replace("/", "_").replace(":", "_")
        filename = f"{eval_id}_{intermediary_id}_{safe_judge_id}_{cache_key}.json"
        return self.intermediary_cache_dir / skill_id / filename

    def _substitute_intermediary_variables(
        self, intermediary: dict[str, Any], conversation_result: dict[str, Any]
    ) -> str:
        """Substitute variables in intermediary prompt from conversation results."""
        prompt = intermediary["prompt"]

        # Resolve file references first
        prompt = self._resolve_file_references(prompt)

        # Handle variable substitution from conversation steps
        for var_spec in intermediary.get("from", []):
            step_id = var_spec["step"]
            part = var_spec["part"]  # "final" or "history"
            var_name = var_spec["as"]

            # Find the content from the conversation
            messages = conversation_result["messages"]

            if part == "final":
                # Get the last assistant response for this step
                # For now, assume single step - in multi-step we'd need step tracking
                if messages and len(messages) >= 2:
                    content = messages[-1]["content"]  # Last assistant message
                else:
                    content = "[NO_CONTENT_FOUND]"
            elif part == "history":
                # Get the full conversation up to this step
                content = "\n".join(
                    [f"{msg['role']}: {msg['content']}" for msg in messages]
                )
            else:
                content = f"[UNKNOWN_PART: {part}]"

            # Replace the variable placeholder
            placeholder = "{{" + var_name + "}}"
            prompt = prompt.replace(placeholder, content)

        return prompt

    def execute_intermediary(
        self,
        intermediary: dict[str, Any],
        conversation_result: dict[str, Any],
        judge_model: dict[str, Any],
        skill_id: str,
        eval_id: str,
    ) -> dict[str, Any]:
        """Execute an intermediary step using the judge model."""
        intermediary_id = intermediary["id"]
        judge_model_id = judge_model["id"]

        # Generate cache key based on intermediary content + conversation result + judge model
        cache_content = {
            "intermediary": intermediary,
            "conversation_cache_key": conversation_result["metadata"]["cache_key"],
            "judge_model": judge_model_id,
        }
        cache_key = hashlib.sha256(
            json.dumps(cache_content, sort_keys=True).encode()
        ).hexdigest()[:16]
        cache_path = self._get_intermediary_cache_path(
            skill_id, eval_id, intermediary_id, judge_model_id, cache_key
        )

        # Check cache first
        cached_result = self._load_from_cache(cache_path)
        if cached_result:
            print(f"    📋 Using cached intermediary: {intermediary_id}")
            return cached_result

        print(f"    🔄 Executing intermediary: {intermediary_id} with {judge_model_id}")

        try:
            # Prepare the prompt with variable substitution
            prompt = self._substitute_intermediary_variables(
                intermediary, conversation_result
            )

            # Create message for judge model
            messages = [{"role": "user", "content": prompt}]

            # Execute with judge model
            response = self._make_api_request(judge_model_id, messages)

            if "choices" not in response or not response["choices"]:
                raise Exception(f"Invalid API response: {response}")

            assistant_message = response["choices"][0]["message"]["content"]
            messages.append({"role": "assistant", "content": assistant_message})

            # Create intermediary result
            intermediary_result = {
                "metadata": {
                    "skill_id": skill_id,
                    "eval_id": eval_id,
                    "intermediary_id": intermediary_id,
                    "judge_model_id": judge_model_id,
                    "conversation_cache_key": conversation_result["metadata"][
                        "cache_key"
                    ],
                    "timestamp": datetime.utcnow().isoformat(),
                    "cache_key": cache_key,
                },
                "messages": messages,
                "execution_info": {
                    "status": "completed",
                    "prompt_length": len(prompt),
                    "response_length": len(assistant_message),
                },
            }

            # Cache the result
            self._save_to_cache(cache_path, intermediary_result)
            print(
                f"    ✅ Intermediary {intermediary_id} completed ({len(assistant_message)} chars)"
            )

            return intermediary_result

        except Exception as e:
            error_result = {
                "metadata": {
                    "skill_id": skill_id,
                    "eval_id": eval_id,
                    "intermediary_id": intermediary_id,
                    "judge_model_id": judge_model_id,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "execution_info": {"status": "failed", "error": str(e)},
            }
            print(f"    ❌ Intermediary {intermediary_id} failed: {e}")
            return error_result

    def execute_conversation(
        self, model: dict[str, Any], skill_id: str, eval_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a complete conversation for a model-eval pair."""
        model_id = model["id"]
        eval_id = eval_data["id"]
        eval_name = eval_data["name"]

        # Check cache first
        cache_key = self._generate_cache_key(model_id, eval_data)
        cache_path = self._get_cache_path(skill_id, eval_id, model_id, cache_key)

        cached_result = self._load_from_cache(cache_path)
        if cached_result:
            print(f"📋 Using cached conversation: {skill_id}/{eval_id} x {model_id}")
            return cached_result

        print(f"🚀 Executing conversation: {skill_id}/{eval_id} x {model_id}")

        # Initialize conversation
        messages = []
        chain = eval_data["chain"]

        try:
            # Execute each step in the chain
            for i, step in enumerate(chain):
                step_id = step["id"]
                print(f"  Step {i+1}/{len(chain)}: {step_id}")

                # Prepare the prompt for this step
                prompt = self._prepare_step_inputs(step, messages)

                # Add user message
                messages.append({"role": "user", "content": prompt})

                # Get model response
                response = self._make_api_request(model_id, messages)

                # Extract assistant message
                if "choices" not in response or not response["choices"]:
                    raise Exception(f"Invalid API response: {response}")

                assistant_message = response["choices"][0]["message"]["content"]

                # Add assistant response to conversation
                messages.append({"role": "assistant", "content": assistant_message})

                print(
                    f"    ✅ Step {step_id} completed ({len(assistant_message)} chars)"
                )

            # Create conversation result
            conversation_result = {
                "metadata": {
                    "skill_id": skill_id,
                    "eval_id": eval_id,
                    "eval_name": eval_name,
                    "model_id": model_id,
                    "model_slug": model.get("slug", ""),
                    "model_author": model.get("author", ""),
                    "timestamp": datetime.utcnow().isoformat(),
                    "cache_key": cache_key,
                    "step_count": len(chain),
                    "message_count": len(messages),
                },
                "messages": messages,
                "execution_info": {
                    "total_steps": len(chain),
                    "completed_steps": len(chain),
                    "status": "completed",
                },
            }

            # Cache the result
            self._save_to_cache(cache_path, conversation_result)
            print("  💾 Cached conversation result")

            return conversation_result

        except Exception as e:
            error_result = {
                "metadata": {
                    "skill_id": skill_id,
                    "eval_id": eval_id,
                    "eval_name": eval_name,
                    "model_id": model_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "cache_key": cache_key,
                    "error": str(e),
                },
                "messages": messages,
                "execution_info": {
                    "total_steps": len(chain),
                    "completed_steps": len(
                        [m for m in messages if m["role"] == "assistant"]
                    ),
                    "status": "failed",
                    "error": str(e),
                },
            }

            print(f"  ❌ Conversation failed: {e}")
            return error_result


def cleanup_stale_cache(
    models: list, judges: list, cache_dir: Path, intermediary_cache_dir: Path
):
    """Remove cached conversations for models that no longer exist in the pools."""
    current_model_ids = {model["id"] for model in models}
    current_judge_ids = {judge["id"] for judge in judges}
    cleaned_count = 0

    print("🧹 Cleaning stale cache entries...")
    print(f"   Current models: {sorted(current_model_ids)}")
    print(f"   Current judges: {sorted(current_judge_ids)}")

    # Clean conversation cache
    if cache_dir.exists():
        for skill_dir in cache_dir.iterdir():
            if skill_dir.is_dir():
                for cache_file in skill_dir.glob("*.json"):
                    try:
                        # Read the actual metadata from the JSON file
                        with open(cache_file) as f:
                            cache_data = json.load(f)
                        model_id = cache_data.get("metadata", {}).get("model_id")
                        if model_id and model_id not in current_model_ids:
                            print(
                                f"   🗑️  Removing stale conversation cache: {cache_file.name} (model: {model_id})"
                            )
                            cache_file.unlink()
                            cleaned_count += 1
                    except (json.JSONDecodeError, OSError):
                        # If we can't read the file, it's corrupted - remove it
                        print(
                            f"   🗑️  Removing corrupted conversation cache: {cache_file.name}"
                        )
                        cache_file.unlink()
                        cleaned_count += 1

    # Clean intermediary cache
    if intermediary_cache_dir.exists():
        for skill_dir in intermediary_cache_dir.iterdir():
            if skill_dir.is_dir():
                for cache_file in skill_dir.glob("*.json"):
                    # Extract judge model ID from filename: eval_intermediary_judgemodel_hash.json
                    parts = cache_file.stem.split("_")
                    if len(parts) >= 4:
                        # Reconstruct judge model ID (handle slashes that became underscores)
                        judge_parts = parts[
                            2:-1
                        ]  # Skip eval name, intermediary name, and hash
                        potential_judge_id = "/".join(judge_parts)

                        # Also check with underscores (fallback)
                        potential_judge_id_underscore = "_".join(judge_parts)

                        if (
                            potential_judge_id not in current_judge_ids
                            and potential_judge_id_underscore not in current_judge_ids
                        ):
                            print(
                                f"   🗑️  Removing stale intermediary cache: {cache_file.name}"
                            )
                            cache_file.unlink()
                            cleaned_count += 1

    if cleaned_count > 0:
        print(f"   ✅ Cleaned {cleaned_count} stale cache files")
    else:
        print("   ✅ No stale cache files found")


def execute_all_conversations(
    models_file: Path, skills_file: Path, judges_file: Path, output_file: Path
):
    """Execute conversations for all model-eval pairs."""

    # Define cache directories from output file path structure
    data_dir = output_file.parent
    cache_dir = data_dir / "conversations"
    intermediary_cache_dir = data_dir / "intermediaries"

    # Load models, skills, and judges
    with open(models_file) as f:
        models_data = json.load(f)

    with open(skills_file) as f:
        skills_data = json.load(f)

    with open(judges_file) as f:
        judges_data = json.load(f)

    models = models_data["models"]
    evals = skills_data["evals"]
    judges = judges_data["judges"]

    print(
        f"🎯 Executing conversations for {len(models)} models x {len(evals)} evals = {len(models) * len(evals)} total"
    )
    print(
        f"🧑‍⚖️ Using {len(judges)} judge models for intermediaries (primary: {judges[0]['id'] if judges else 'none'})"
    )

    executor = ConversationExecutor(cache_dir, intermediary_cache_dir)

    # Clean up stale cache entries
    cleanup_stale_cache(
        models, judges, executor.cache_dir, executor.intermediary_cache_dir
    )

    results = []
    intermediary_results = []

    total_combinations = len(models) * len(evals)
    completed = 0

    for eval_data in evals:
        skill_id = eval_data["_metadata"]["skill"]
        eval_id = eval_data["id"]
        has_intermediaries = (
            "intermediaries" in eval_data and eval_data["intermediaries"]
        )

        for model in models:
            completed += 1
            print(
                f"\n[{completed}/{total_combinations}] Processing {skill_id}/{eval_id} x {model['id']}"
            )

            try:
                # Execute main conversation
                conversation_result = executor.execute_conversation(
                    model, skill_id, eval_data
                )
                results.append(conversation_result)

                # Execute intermediaries if they exist
                if has_intermediaries and judges:
                    primary_judge = judges[
                        0
                    ]  # Use first judge model for intermediaries
                    print(
                        f"  🔄 Processing {len(eval_data['intermediaries'])} intermediaries with {primary_judge['id']}"
                    )

                    for intermediary in eval_data["intermediaries"]:
                        try:
                            intermediary_result = executor.execute_intermediary(
                                intermediary,
                                conversation_result,
                                primary_judge,
                                skill_id,
                                eval_id,
                            )
                            intermediary_results.append(intermediary_result)
                        except Exception as e:
                            print(
                                f"    ❌ Failed to execute intermediary {intermediary['id']}: {e}"
                            )
                            intermediary_results.append(
                                {
                                    "metadata": {
                                        "skill_id": skill_id,
                                        "eval_id": eval_id,
                                        "intermediary_id": intermediary["id"],
                                        "judge_model_id": primary_judge["id"],
                                        "error": str(e),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    },
                                    "execution_info": {
                                        "status": "failed",
                                        "error": str(e),
                                    },
                                }
                            )

            except Exception as e:
                print(f"❌ Failed to execute conversation: {e}")
                # Still add failed result for tracking
                results.append(
                    {
                        "metadata": {
                            "skill_id": skill_id,
                            "eval_id": eval_data["id"],
                            "model_id": model["id"],
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        "execution_info": {"status": "failed", "error": str(e)},
                    }
                )

    # Save all results
    final_output = {
        "execution_info": {
            "total_conversations": total_combinations,
            "successful_conversations": len(
                [
                    r
                    for r in results
                    if r.get("execution_info", {}).get("status") == "completed"
                ]
            ),
            "failed_conversations": len(
                [
                    r
                    for r in results
                    if r.get("execution_info", {}).get("status") == "failed"
                ]
            ),
            "total_intermediaries": len(intermediary_results),
            "successful_intermediaries": len(
                [
                    r
                    for r in intermediary_results
                    if r.get("execution_info", {}).get("status") == "completed"
                ]
            ),
            "failed_intermediaries": len(
                [
                    r
                    for r in intermediary_results
                    if r.get("execution_info", {}).get("status") == "failed"
                ]
            ),
            "timestamp": datetime.utcnow().isoformat(),
            "models_count": len(models),
            "evals_count": len(evals),
            "judges_count": len(judges),
        },
        "conversations": results,
        "intermediaries": intermediary_results,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(final_output, f, indent=2)

    print("\n🎉 Conversation execution completed!")
    print(
        f"📊 Conversations: {final_output['execution_info']['successful_conversations']} successful, {final_output['execution_info']['failed_conversations']} failed"
    )
    print(
        f"🔄 Intermediaries: {final_output['execution_info']['successful_intermediaries']} successful, {final_output['execution_info']['failed_intermediaries']} failed"
    )
    print(f"💾 Output saved to: {output_file}")


def main():
    """Main function for Snakemake integration."""
    if "snakemake" in globals():
        # Called by Snakemake
        models_file = Path(snakemake.input.models)
        skills_file = Path(snakemake.input.skills)
        judges_file = Path(snakemake.input.judges)
        output_file = Path(snakemake.output[0])
    else:
        # Called directly - MUST provide data_dir via environment variable
        data_dir_env = os.getenv("AFBENCH_DATA_DIR")
        if not data_dir_env:
            raise ValueError(
                "🚨 SAFETY: execute_conversations.py requires explicit data directory.\n"
                "Set AFBENCH_DATA_DIR environment variable or run via Snakemake."
            )

        data_dir = Path(data_dir_env)
        models_file = data_dir / "loaded_models.json"
        skills_file = data_dir / "loaded_skills.json"
        judges_file = data_dir / "loaded_judges.json"
        output_file = data_dir / "conversations.json"

    execute_all_conversations(models_file, skills_file, judges_file, output_file)


if __name__ == "__main__":
    main()
