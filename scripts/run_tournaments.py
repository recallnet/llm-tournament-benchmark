#!/usr/bin/env python3
"""
Swiss-system tournament implementation for model evaluation.
Handles pairwise model competitions with judge consensus and proper cache invalidation.
"""

import hashlib
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env.local")


class TournamentMatch:
    """Represents a single match between two models on an eval."""

    def __init__(self, model_a_id: str, model_b_id: str, eval_id: str, skill_id: str):
        self.model_a_id = model_a_id
        self.model_b_id = model_b_id
        self.eval_id = eval_id
        self.skill_id = skill_id
        self.match_id = self._generate_match_id()
        self.timestamp: str | None = None
        self.judge_votes: dict[str, str] = {}  # judge_id -> "A" | "B" | "TIE"
        self.judge_conversations: dict[str, list[dict[str, str]]] = (
            {}
        )  # judge_id -> full messages array
        self.judge_explanations: dict[str, str] = {}  # judge_id -> reasoning text
        self.result: str | None = None  # "A" | "B" | "TIE"
        self.conversation_a_key: str | None = None
        self.conversation_b_key: str | None = None

    def _generate_match_id(self) -> str:
        """Generate unique match ID from model pair and eval."""
        # Ensure consistent ordering for deterministic match IDs
        models = sorted([self.model_a_id, self.model_b_id])
        content = f"{models[0]}:{models[1]}:{self.eval_id}:{self.skill_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def add_judge_result(
        self,
        judge_id: str,
        vote: str,
        conversation: list[dict[str, str]],
        explanation: str,
    ) -> None:
        """Add a judge's complete result for this match."""
        if vote not in ["A", "B", "TIE"]:
            raise ValueError(f"Invalid vote: {vote}. Must be 'A', 'B', or 'TIE'")
        self.judge_votes[judge_id] = vote
        self.judge_conversations[judge_id] = conversation
        self.judge_explanations[judge_id] = explanation

    def check_early_consensus(self) -> bool:
        """Check if first 2 judges agree for early consensus optimization."""
        if len(self.judge_votes) != 2:
            return False

        votes = list(self.judge_votes.values())
        return votes[0] == votes[1]

    def calculate_result(self) -> str:
        """Calculate match result from judge consensus."""
        if not self.judge_votes:
            raise ValueError("No judge votes available")

        vote_counts = {"A": 0, "B": 0, "TIE": 0}
        for vote in self.judge_votes.values():
            vote_counts[vote] += 1

        # Find majority winner
        max_votes = max(vote_counts.values())
        winners = [vote for vote, count in vote_counts.items() if count == max_votes]

        if len(winners) == 1:
            self.result = winners[0]
        else:
            # Handle ties in judging - default to TIE
            self.result = "TIE"

        return self.result

    def to_dict(self) -> dict[str, Any]:
        """Convert match to dictionary for serialization."""
        return {
            "match_id": self.match_id,
            "model_a_id": self.model_a_id,
            "model_b_id": self.model_b_id,
            "eval_id": self.eval_id,
            "skill_id": self.skill_id,
            "timestamp": self.timestamp,
            "judge_votes": self.judge_votes,
            "judge_conversations": self.judge_conversations,
            "judge_explanations": self.judge_explanations,
            "result": self.result,
            "conversation_a_key": self.conversation_a_key,
            "conversation_b_key": self.conversation_b_key,
        }


class SwissTournament:
    """Swiss-system tournament implementation."""

    def __init__(self, skill_id: str, eval_id: str, models: list[dict[str, Any]]):
        self.skill_id = skill_id
        self.eval_id = eval_id
        self.models = models
        self.model_ids = [model["id"] for model in models]
        self.tournament_id = self._generate_tournament_id()

        # Tournament state
        self.rounds: list[list[TournamentMatch]] = []
        self.scores: dict[str, float] = {model_id: 0.0 for model_id in self.model_ids}
        self.head_to_head: dict[tuple[str, str], str] = (
            {}
        )  # (model_a, model_b) -> winner
        self.completed = False
        self.winner: str | None = None

    def _generate_tournament_id(self) -> str:
        """Generate unique tournament ID."""
        model_ids_sorted = sorted(self.model_ids)
        content = f"{self.skill_id}:{self.eval_id}:{':'.join(model_ids_sorted)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _calculate_rounds_needed(self) -> int:
        """Calculate optimal number of Swiss rounds."""
        n = len(self.models)
        if n <= 2:
            return 1
        # Standard Swiss: log2(n) rounded up, but at least n-1 if small field
        return min(n - 1, max(3, math.ceil(math.log2(n))))

    def _get_pairings_for_round(self, round_num: int) -> list[tuple[str, str]]:
        """Generate Swiss pairings for given round."""
        if round_num == 0:
            # First round: random pairings
            shuffled = self.model_ids.copy()
            random.shuffle(shuffled)
            return [
                (shuffled[i], shuffled[i + 1]) for i in range(0, len(shuffled) - 1, 2)
            ]

        # Subsequent rounds: pair by score, avoid rematches
        sorted_by_score = sorted(
            self.model_ids, key=lambda x: (self.scores[x], x), reverse=True
        )

        # Build set of all previous pairings for efficient lookup
        previous_pairings = set()
        for round_matches in self.rounds:
            for match in round_matches:
                pair_key = tuple(sorted([match.model_a_id, match.model_b_id]))
                previous_pairings.add(pair_key)

        pairings = []
        used = set()

        i = 0
        while i < len(sorted_by_score) - 1:
            if sorted_by_score[i] in used:
                i += 1
                continue

            # Find best pairing for current model
            paired = False
            for j in range(i + 1, len(sorted_by_score)):
                if sorted_by_score[j] in used:
                    continue

                model_a, model_b = sorted_by_score[i], sorted_by_score[j]
                pair_key = tuple(sorted([model_a, model_b]))

                # Check if this pairing already occurred
                if pair_key not in previous_pairings:
                    pairings.append((model_a, model_b))
                    used.add(model_a)
                    used.add(model_b)
                    paired = True
                    break

            # If no valid pairing found, we must allow a rematch (Swiss constraint)
            if not paired:
                # Pair with closest available opponent even if it's a rematch
                for j in range(i + 1, len(sorted_by_score)):
                    if sorted_by_score[j] not in used:
                        model_a, model_b = sorted_by_score[i], sorted_by_score[j]
                        pairings.append((model_a, model_b))
                        used.add(model_a)
                        used.add(model_b)
                        print(
                            f"      ⚠️  Forced rematch: {model_a} vs {model_b} (no other pairings available)"
                        )
                        break

            i += 1

        # Handle odd number of models (bye)
        if len(used) < len(sorted_by_score):
            unused = [m for m in sorted_by_score if m not in used]
            # Award bye (1 point) to lowest-scoring unused model
            bye_model = min(unused, key=lambda x: self.scores[x])
            self.scores[bye_model] += 1.0
            print(f"      👋 Bye awarded to: {bye_model}")

        return pairings

    def update_scores(self, match: TournamentMatch) -> None:
        """Update tournament scores based on match result."""
        if match.result == "A":
            self.scores[match.model_a_id] += 1.0
        elif match.result == "B":
            self.scores[match.model_b_id] += 1.0
        elif match.result == "TIE":
            self.scores[match.model_a_id] += 0.5
            self.scores[match.model_b_id] += 0.5

        # Record head-to-head
        pair_key = tuple(sorted([match.model_a_id, match.model_b_id]))
        self.head_to_head[pair_key] = match.result

    def is_tournament_complete(self) -> bool:
        """Check if tournament can be concluded."""
        if len(self.rounds) < self._calculate_rounds_needed():
            return False

        # Check if there's a clear winner
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)

        if len(sorted_scores) >= 2:
            first_score = sorted_scores[0][1]
            second_score = sorted_scores[1][1]

            # Clear winner if significant score gap
            if first_score > second_score:
                self.winner = sorted_scores[0][0]
                return True

        # Continue if tied at the top
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert tournament to dictionary for serialization."""
        return {
            "tournament_id": self.tournament_id,
            "skill_id": self.skill_id,
            "eval_id": self.eval_id,
            "model_ids": self.model_ids,
            "rounds": [
                [match.to_dict() for match in round_matches]
                for round_matches in self.rounds
            ],
            "scores": self.scores,
            "head_to_head": {f"{k[0]}:{k[1]}": v for k, v in self.head_to_head.items()},
            "completed": self.completed,
            "winner": self.winner,
            "timestamp": datetime.utcnow().isoformat(),
        }


class JudgeExecutor:
    """Handles judge execution for tournament matches."""

    def __init__(self, cache_dir: Path):
        # SAFETY: Cache directory must always be provided by caller to prevent path confusion
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

        # Rate limiting
        self.last_request_time = 0
        self.min_interval = 0.1  # 100ms between requests

    def cleanup_invalid_match_cache(
        self,
        current_models: list[dict[str, Any]],
        current_judges: list[dict[str, Any]],
        current_evals: list[dict[str, Any]],
    ) -> None:
        """Remove ALL cached judge decisions that are no longer valid due to model/judge/eval changes."""
        # CRITICAL SAFETY: Prevent production data destruction during testing
        try:
            from scripts.safety_guards import (
                check_production_data_access,
                ensure_test_mode_for_cache_operations,
            )
        except ImportError:
            from safety_guards import (
                check_production_data_access,
                ensure_test_mode_for_cache_operations,
            )
        ensure_test_mode_for_cache_operations()
        check_production_data_access(self.cache_dir, "cache cleanup")
        current_model_ids = {model["id"] for model in current_models}
        current_judge_ids = {judge["id"] for judge in current_judges}
        current_eval_ids = {eval_data["id"] for eval_data in current_evals}
        current_skill_ids = {
            eval_data["_metadata"]["skill"] for eval_data in current_evals
        }

        cleaned_count = 0

        print("🧹 Cleaning invalid tournament match cache entries...")
        print(f"   Valid models: {sorted(current_model_ids)}")
        print(f"   Valid judges: {sorted(current_judge_ids)}")
        print(f"   Valid evals: {sorted(current_eval_ids)}")

        if self.cache_dir.exists():
            for skill_dir in self.cache_dir.iterdir():
                if skill_dir.is_dir():
                    skill_name = skill_dir.name

                    # Remove entire skill directory if skill no longer exists
                    if skill_name not in current_skill_ids:
                        print(f"   🗑️  Removing entire skill directory: {skill_name}")
                        import shutil

                        shutil.rmtree(skill_dir)
                        cleaned_count += 1
                        continue

                    # Check individual match cache files in valid skills
                    for cache_file in skill_dir.glob("*.json"):
                        should_remove = False
                        remove_reason = ""

                        try:
                            # Load the cache file to check its validity
                            with open(cache_file) as f:
                                cached_data = json.load(f)

                            metadata = cached_data.get("metadata", {})

                            # Check if all referenced entities still exist
                            model_a = metadata.get("model_a_id")
                            model_b = metadata.get("model_b_id")
                            judge_id = metadata.get("judge_id")
                            eval_id = metadata.get("eval_id")
                            skill_id = metadata.get("skill_id")

                            # Validate all required components exist
                            if model_a and model_a not in current_model_ids:
                                should_remove = True
                                remove_reason = f"model_a '{model_a}' no longer exists"
                            elif model_b and model_b not in current_model_ids:
                                should_remove = True
                                remove_reason = f"model_b '{model_b}' no longer exists"
                            elif judge_id and judge_id not in current_judge_ids:
                                should_remove = True
                                remove_reason = f"judge '{judge_id}' no longer exists"
                            elif eval_id and eval_id not in current_eval_ids:
                                should_remove = True
                                remove_reason = f"eval '{eval_id}' no longer exists"
                            elif skill_id and skill_id not in current_skill_ids:
                                should_remove = True
                                remove_reason = f"skill '{skill_id}' no longer exists"

                        except (OSError, json.JSONDecodeError, KeyError):
                            # Corrupted or invalid cache file
                            should_remove = True
                            remove_reason = "corrupted cache file"

                        if should_remove:
                            print(
                                f"   🗑️  Removing invalid match cache: {cache_file.name} ({remove_reason})"
                            )
                            cache_file.unlink()
                            cleaned_count += 1

        if cleaned_count > 0:
            print(
                f"   ✅ Cleaned {cleaned_count} invalid match cache files/directories"
            )
        else:
            print("   ✅ No invalid match cache files found")

    def _generate_judge_cache_key_with_prompt(
        self,
        match: TournamentMatch,
        judge_id: str,
        final_prompt: str,
        eval_config: dict[str, Any],
    ) -> str:
        """Generate cache key for judge decision including the actual final prompt."""
        # Include match details + judge + FINAL prompt for cache key
        cache_content = {
            "match_id": match.match_id,
            "judge_id": judge_id,
            "final_prompt": final_prompt,  # This includes all substitutions and modifications
            "model_a": match.model_a_id,
            "model_b": match.model_b_id,
            "eval_judge_system": eval_config.get("judge", {}).get("system", ""),
        }
        return hashlib.sha256(
            json.dumps(cache_content, sort_keys=True).encode()
        ).hexdigest()[:16]

    def _get_judge_cache_path(
        self, match: TournamentMatch, judge_id: str, cache_key: str
    ) -> Path:
        """Get cache file path for judge decision."""
        safe_judge_id = judge_id.replace("/", "_").replace(":", "_")
        filename = f"{match.match_id}_{safe_judge_id}_{cache_key}.json"
        return self.cache_dir / match.skill_id / filename

    def _load_judge_cache(self, cache_path: Path) -> dict[str, Any] | None:
        """Load judge decision from cache."""
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                cache_path.unlink(missing_ok=True)
        return None

    def _save_judge_cache(self, cache_path: Path, judge_result: dict[str, Any]) -> None:
        """Save judge decision to cache."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(judge_result, f, indent=2)

    def _rate_limit(self) -> None:
        """Apply rate limiting between API calls."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _make_api_request(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        endpoint: str = "openrouter",
    ) -> dict[str, Any]:
        """Make a request to API or return mock response for testing."""
        # Handle mock endpoints for testing
        if endpoint == "mock":
            return self._generate_mock_response(model_id, messages)

        self._rate_limit()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://recall.network/",
            "X-Title": "Recall Network"
        }
        payload = {"model": model_id, "messages": messages}

        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def _generate_mock_response(
        self, model_id: str, messages: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Generate deterministic mock response for testing."""
        # Extract judge behavior from model_id (e.g., "test/judge-agree_A" -> "agree_A")
        judge_behavior = "agree_A"  # Default
        if "agree_A" in model_id:
            judge_behavior = "agree_A"
        elif "agree_B" in model_id:
            judge_behavior = "agree_B"
        elif "agree_TIE" in model_id:
            judge_behavior = "agree_TIE"
        elif "disagree_A" in model_id:
            judge_behavior = "disagree_A"
        elif "disagree_B" in model_id:
            judge_behavior = "disagree_B"

        # Generate response based on behavior
        if judge_behavior == "agree_A":
            content = "After careful analysis, I believe Option A provides a better response. MY VOTE IS FOR: A"
        elif judge_behavior == "agree_B":
            content = "After careful analysis, I believe Option B provides a better response. MY VOTE IS FOR: B"
        elif judge_behavior == "agree_TIE":
            content = "Both responses have equal merit and quality. MY VOTE IS FOR: TIE"
        elif judge_behavior == "disagree_A":
            content = "I disagree with the previous assessment. Option A is clearly better. MY VOTE IS FOR: A"
        elif judge_behavior == "disagree_B":
            content = "I disagree with the previous assessment. Option B is clearly better. MY VOTE IS FOR: B"
        else:
            content = "Both responses are comparable in quality. MY VOTE IS FOR: TIE"

        return {
            "choices": [{"message": {"content": content, "role": "assistant"}}],
            "_mock": True,
            "_behavior": judge_behavior,
        }

    def _build_view_content(
        self,
        view_spec: list[dict[str, str]],
        conversations_cache_dir: str,
        intermediaries_data: dict[str, Any],
        model_id: str,
        skill_id: str,
        eval_id: str,
    ) -> str:
        """Build the content shown to judge based on view specification using direct cache access."""
        content_parts = []

        for view_item in view_spec:
            kind = view_item["kind"]  # "step" or "intermediary"
            item_id = view_item["id"]  # step_id or intermediary_id
            part = view_item["part"]  # "final" or "history"

            if kind == "step":
                # Find conversation directly from cache
                conversation = find_conversation_in_cache(
                    conversations_cache_dir, skill_id, eval_id, model_id
                )

                if not conversation:
                    content_parts.append(f"[STEP_NOT_FOUND: {item_id}]")
                    continue

                if part == "final":
                    # Get the final assistant response for this step
                    messages = conversation.get("messages", [])
                    # For now, assume single step - in multi-step we'd need step tracking
                    if messages and len(messages) >= 2:
                        content_parts.append(messages[-1]["content"])
                    else:
                        content_parts.append("[NO_FINAL_RESPONSE]")

                elif part == "history":
                    # Get the full conversation history for this step
                    messages = conversation.get("messages", [])
                    history_text = "\n".join(
                        [f"{msg['role']}: {msg['content']}" for msg in messages]
                    )
                    content_parts.append(history_text)

            elif kind == "intermediary":
                # Find intermediary result for this model/eval/intermediary
                intermediary = None
                for inter in intermediaries_data.get("intermediaries", []):
                    if (
                        inter["metadata"]["judge_model_id"]  # Has judge model
                        and inter["metadata"]["skill_id"] == skill_id
                        and inter["metadata"]["eval_id"] == eval_id
                        and inter["metadata"]["intermediary_id"] == item_id
                    ):
                        # Check if this intermediary was generated from the right model's conversation
                        # We'd need to match conversation cache keys for this
                        intermediary = inter
                        break

                if not intermediary:
                    content_parts.append(f"[INTERMEDIARY_NOT_FOUND: {item_id}]")
                    continue

                if part == "final":
                    # Get the final assistant response from intermediary
                    messages = intermediary.get("messages", [])
                    if messages and len(messages) >= 2:
                        content_parts.append(messages[-1]["content"])
                    else:
                        content_parts.append("[NO_INTERMEDIARY_RESPONSE]")

                elif part == "history":
                    # Get the full intermediary conversation
                    messages = intermediary.get("messages", [])
                    history_text = "\n".join(
                        [f"{msg['role']}: {msg['content']}" for msg in messages]
                    )
                    content_parts.append(history_text)

        return "\n\n".join(content_parts)

    def execute_judge_decision(
        self,
        match: TournamentMatch,
        judge: dict[str, Any],
        eval_config: dict[str, Any],
        conversations_cache_dir: str,
        intermediaries_data: dict[str, Any],
    ) -> tuple[str, list[dict[str, str]], str]:
        """Execute judge decision for a match and return vote, conversation, explanation."""

        judge_id = judge["id"]
        judge_config = eval_config["judge"]

        # Build view content for model A and B FIRST using direct cache access
        view_a_content = self._build_view_content(
            judge_config["view"]["A"],
            conversations_cache_dir,
            intermediaries_data,
            match.model_a_id,
            match.skill_id,
            match.eval_id,
        )
        view_b_content = self._build_view_content(
            judge_config["view"]["B"],
            conversations_cache_dir,
            intermediaries_data,
            match.model_b_id,
            match.skill_id,
            match.eval_id,
        )

        # Build the FINAL prompt that will actually be executed
        judge_prompt = judge_config["prompt"]
        judge_prompt = judge_prompt.replace("{{A}}", view_a_content)
        judge_prompt = judge_prompt.replace("{{B}}", view_b_content)
        judge_prompt += "\n\nPlease end your response with exactly one of these formats:\n- MY VOTE IS FOR: A\n- MY VOTE IS FOR: B\n- MY VOTE IS FOR: TIE"

        # Generate cache key based on the FINAL prompt (not the template)
        cache_key = self._generate_judge_cache_key_with_prompt(
            match, judge_id, judge_prompt, eval_config
        )
        cache_path = self._get_judge_cache_path(match, judge_id, cache_key)

        cached_result = self._load_judge_cache(cache_path)
        if cached_result:
            print(f"    📋 Using cached judge decision: {judge_id}")
            return (
                cached_result["vote"],
                cached_result["conversation"],
                cached_result["explanation"],
            )

        # Create messages for judge
        messages = []
        if "system" in judge_config:
            messages.append({"role": "system", "content": judge_config["system"]})
        messages.append({"role": "user", "content": judge_prompt})

        print(f"    🧑‍⚖️ Judging with {judge_id}...")

        try:
            # Execute judge decision
            judge_endpoint = judge.get("endpoint", "openrouter")
            response = self._make_api_request(judge_id, messages, judge_endpoint)

            if "choices" not in response or not response["choices"]:
                raise Exception(f"Invalid API response: {response}")

            judge_response = response["choices"][0]["message"]["content"]
            messages.append({"role": "assistant", "content": judge_response})

            # Parse vote from judge response
            vote = self._parse_judge_vote(judge_response)

            # Cache the result
            judge_result = {
                "vote": vote,
                "conversation": messages,
                "explanation": judge_response,
                "metadata": {
                    "match_id": match.match_id,
                    "judge_id": judge_id,
                    "model_a_id": match.model_a_id,
                    "model_b_id": match.model_b_id,
                    "eval_id": match.eval_id,
                    "skill_id": match.skill_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "cache_key": cache_key,
                },
            }
            self._save_judge_cache(cache_path, judge_result)

            print(f"    ✅ Judge {judge_id} voted: {vote}")
            return vote, messages, judge_response

        except Exception as e:
            print(f"    ❌ Judge {judge_id} failed: {e}")
            error_msg = f"[JUDGE_ERROR: {e}]"
            messages.append({"role": "assistant", "content": error_msg})

            # Cache the error result too
            error_result = {
                "vote": "TIE",
                "conversation": messages,
                "explanation": error_msg,
                "metadata": {
                    "match_id": match.match_id,
                    "judge_id": judge_id,
                    "model_a_id": match.model_a_id,
                    "model_b_id": match.model_b_id,
                    "eval_id": match.eval_id,
                    "skill_id": match.skill_id,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                    "cache_key": cache_key,
                },
            }
            self._save_judge_cache(cache_path, error_result)

            return "TIE", messages, error_msg  # Default to TIE on error

    def _parse_judge_vote(self, judge_response: str) -> str:
        """Parse judge vote from response text."""
        # First, look for the explicit format we requested
        response_upper = judge_response.upper()
        if "MY VOTE IS FOR: A" in response_upper:
            return "A"
        elif "MY VOTE IS FOR: B" in response_upper:
            return "B"
        elif "MY VOTE IS FOR: TIE" in response_upper:
            return "TIE"

        # Fallback to original parsing logic in case format wasn't followed
        response_lower = judge_response.lower()

        # Look for explicit choice statements
        if (
            "choose a" in response_lower
            or "option a" in response_lower
            or judge_response.strip().upper().startswith("A")
        ):
            return "A"
        elif (
            "choose b" in response_lower
            or "option b" in response_lower
            or judge_response.strip().upper().startswith("B")
        ):
            return "B"
        elif (
            "tie" in response_lower
            or "equal" in response_lower
            or "draw" in response_lower
        ):
            return "TIE"

        # Fallback: look for A or B near the start of response
        words = judge_response.strip().split()
        if len(words) > 0:
            first_word = words[0].upper()
            if first_word in ["A", "B"]:
                return first_word

        # Default to TIE if unclear
        return "TIE"


def find_conversation_in_cache(
    cache_dir: str, skill_id: str, eval_id: str, model_id: str
) -> dict | None:
    """
    Find a conversation directly from cache files instead of mega conversations.json.

    Args:
        cache_dir: Path to conversations cache directory
        skill_id: Skill identifier
        eval_id: Evaluation identifier
        model_id: Model identifier

    Returns:
        Conversation dict or None if not found
    """

    # Sanitize model ID for filename pattern
    safe_model_id = model_id.replace("/", "_").replace(":", "_")

    # Look for cache files matching this model/eval combination
    matching_files = list(
        Path(cache_dir).glob(f"{skill_id}/{eval_id}_{safe_model_id}_*.json")
    )

    if not matching_files:
        return None

    # Use the most recent file if multiple exist
    cache_file = max(matching_files, key=lambda p: p.stat().st_mtime)

    try:
        with open(cache_file) as f:
            conversation = json.load(f)
        return conversation
    except (json.JSONDecodeError, OSError):
        return None


def build_judge_prompt_from_cache(
    cache_dir: str, skill_id: str, eval_id: str, model_a_id: str, model_b_id: str
) -> str:
    """
    Build judge prompt by reading conversations directly from cache.

    Args:
        cache_dir: Path to conversations cache directory
        skill_id: Skill identifier
        eval_id: Evaluation identifier
        model_a_id: First model identifier
        model_b_id: Second model identifier

    Returns:
        Formatted judge prompt string
    """
    # Find conversations for both models
    conv_a = find_conversation_in_cache(cache_dir, skill_id, eval_id, model_a_id)
    conv_b = find_conversation_in_cache(cache_dir, skill_id, eval_id, model_b_id)

    if not conv_a or not conv_b:
        return f"[ERROR: Missing conversations - A:{conv_a is not None}, B:{conv_b is not None}]"

    # Extract final responses
    messages_a = conv_a.get("messages", [])
    messages_b = conv_b.get("messages", [])

    response_a = "[NO_RESPONSE]"
    response_b = "[NO_RESPONSE]"

    if messages_a and len(messages_a) >= 2:
        response_a = messages_a[-1]["content"]

    if messages_b and len(messages_b) >= 2:
        response_b = messages_b[-1]["content"]

    # Build judge prompt (simplified version for now)
    prompt = f"""Compare these two responses:

Model A Response:
{response_a}

Model B Response:
{response_b}

Which response is better? Choose A, B, or TIE."""

    return prompt


def main_with_cache_dir(
    conversations_cache_dir: str,
    models_file: str,
    judges_file: str,
    skills_file: str,
    output_file: str,
):
    """
    Main function that reads directly from conversation cache directory.

    Args:
        conversations_cache_dir: Path to conversations cache directory
        models_file: Path to loaded models JSON
        judges_file: Path to loaded judges JSON
        skills_file: Path to loaded skills JSON
        output_file: Path to output tournaments JSON

    Returns:
        dict: Success/failure status
    """
    print("🏆 Swiss Tournament System Starting (Direct Cache Mode)!")

    # Load input data (excluding conversations mega file)
    with open(models_file) as f:
        models_data = json.load(f)

    with open(judges_file) as f:
        judges_data = json.load(f)

    with open(skills_file) as f:
        skills_data = json.load(f)

    models = models_data["models"]
    judges = judges_data["judges"]
    skills_data["skills"]
    evals = skills_data["evals"]

    print(f"📊 Loaded {len(models)} models, {len(judges)} judges, {len(evals)} evals")
    print(f"📁 Using conversation cache: {conversations_cache_dir}")

    # Define judge cache directory from conversation cache directory structure
    conversations_path = Path(conversations_cache_dir)
    data_dir = (
        conversations_path.parent
    )  # Go up one level from conversations to data/profile
    cache_dir = data_dir / "judge_cache"
    print(f"📁 Using judge cache: {cache_dir}")

    if len(models) < 2:
        print("⚠️  Need at least 2 models for tournaments - skipping")
        tournament_results = {
            "tournaments": [],
            "execution_info": {
                "status": "insufficient_models",
                "models_count": len(models),
                "message": "Need at least 2 models for tournaments",
            },
        }
    else:
        print(f"🚀 Running tournaments for {len(evals)} evals...")

        judge_executor = JudgeExecutor(cache_dir)

        # Clean up invalid match cache entries first
        judge_executor.cleanup_invalid_match_cache(models, judges, evals)

        all_tournaments = []

        # Create empty intermediaries structure - we'll use cache directly for conversations
        intermediaries_data = {"intermediaries": []}

        for eval_data in evals:
            skill_id = eval_data["_metadata"]["skill"]
            eval_id = eval_data["id"]

            print(f"\n🏟️  Tournament: {skill_id}/{eval_id}")

            # Create tournament
            tournament = SwissTournament(skill_id, eval_id, models)
            rounds_needed = tournament._calculate_rounds_needed()

            print(f"   📋 {len(models)} models, {rounds_needed} rounds planned")

            # Run tournament rounds
            for round_num in range(rounds_needed):
                print(f"\n   🔄 Round {round_num + 1}/{rounds_needed}")

                # Get pairings for this round
                pairings = tournament._get_pairings_for_round(round_num)

                if not pairings:
                    print("   ⚠️  No pairings possible (odd numbers with byes)")
                    break

                round_matches = []

                for model_a_id, model_b_id in pairings:
                    print(f"      🥊 {model_a_id} vs {model_b_id}")

                    # Create match
                    match = TournamentMatch(model_a_id, model_b_id, eval_id, skill_id)
                    match.timestamp = datetime.utcnow().isoformat()

                    # Execute judges for this match
                    for i, judge in enumerate(judges):
                        try:
                            vote, conversation, explanation = (
                                judge_executor.execute_judge_decision(
                                    match,
                                    judge,
                                    eval_data,
                                    conversations_cache_dir,
                                    intermediaries_data,
                                )
                            )
                            match.add_judge_result(
                                judge["id"], vote, conversation, explanation
                            )

                            # Check for early consensus after 2nd judge
                            if i == 1 and match.check_early_consensus():
                                print(f"         🎯 Early consensus reached: {vote}")
                                break

                        except Exception as e:
                            print(f"         ❌ Judge {judge['id']} failed: {e}")
                            # Add error vote
                            error_conversation = [
                                {"role": "user", "content": "[JUDGE_EXECUTION_ERROR]"},
                                {"role": "assistant", "content": f"Error: {e}"},
                            ]
                            match.add_judge_result(
                                judge["id"], "TIE", error_conversation, f"Error: {e}"
                            )

                    # Calculate match result
                    match.calculate_result()
                    print(f"         🏆 Winner: {match.result}")

                    # Update tournament scores
                    tournament.update_scores(match)
                    round_matches.append(match)

                tournament.rounds.append(round_matches)

                # Check if tournament is complete
                if tournament.is_tournament_complete():
                    print(f"   🎉 Tournament complete! Winner: {tournament.winner}")
                    break

            if not tournament.completed and tournament.winner:
                tournament.completed = True

            all_tournaments.append(tournament.to_dict())

        tournament_results = {
            "tournaments": all_tournaments,
            "execution_info": {
                "status": "completed",
                "tournaments_count": len(all_tournaments),
                "total_models": len(models),
                "total_judges": len(judges),
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    # Write output
    with open(output_file, "w") as f:
        json.dump(tournament_results, f, indent=2)

    return {"success": True}


def _execute_judges_for_match(
    match,
    judges,
    judge_executor,
    eval_data,
    conversations_cache_dir
):
    """
    Execute judges for a match with parallel optimization for first two judges.
    
    This function maintains complete backward compatibility with existing cache
    and results while optimizing performance by running the first two judges
    in parallel when possible.
    """
    if len(judges) < 2:
        # Fallback to sequential for edge case
        for i, judge in enumerate(judges):
            try:
                vote, conversation, explanation = (
                    judge_executor.execute_judge_decision(
                        match,
                        judge,
                        eval_data,
                        conversations_cache_dir,
                        {},  # Empty intermediaries for now
                    )
                )
                match.add_judge_result(
                    judge["id"], vote, conversation, explanation
                )
            except Exception as e:
                print(f"         ❌ Judge {judge['id']} failed: {e}")
                error_conversation = [
                    {
                        "role": "user",
                        "content": "[JUDGE_EXECUTION_ERROR]",
                    },
                    {"role": "assistant", "content": f"Error: {e}"},
                ]
                match.add_judge_result(
                    judge["id"],
                    "TIE",
                    error_conversation,
                    f"Error: {e}",
                )
        return

    # Parallel execution for first two judges
    first_two_judges = judges[:2]
    
    def execute_single_judge(judge):
        """Execute a single judge and return results with judge info."""
        try:
            vote, conversation, explanation = (
                judge_executor.execute_judge_decision(
                    match,
                    judge,
                    eval_data,
                    conversations_cache_dir,
                    {},  # Empty intermediaries for now
                )
            )
            return {
                "judge_id": judge["id"],
                "vote": vote,
                "conversation": conversation,
                "explanation": explanation,
                "success": True,
            }
        except Exception as e:
            print(f"         ❌ Judge {judge['id']} failed: {e}")
            error_conversation = [
                {
                    "role": "user",
                    "content": "[JUDGE_EXECUTION_ERROR]",
                },
                {"role": "assistant", "content": f"Error: {e}"},
            ]
            return {
                "judge_id": judge["id"],
                "vote": "TIE",
                "conversation": error_conversation,
                "explanation": f"Error: {e}",
                "success": False,
            }

    # Execute first two judges in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both judges for parallel execution
        future_to_judge = {
            executor.submit(execute_single_judge, judge): judge
            for judge in first_two_judges
        }
        
        # Collect results in order (important for deterministic behavior)
        judge_results = {}
        for future in as_completed(future_to_judge):
            result = future.result()
            judge_results[result["judge_id"]] = result
    
    # Add results to match in original judge order (preserves determinism)
    for judge in first_two_judges:
        result = judge_results[judge["id"]]
        match.add_judge_result(
            result["judge_id"],
            result["vote"],
            result["conversation"],
            result["explanation"]
        )
    
    # Check for early consensus after first two judges
    if match.check_early_consensus():
        # Get the consensus vote for logging (both judges agree)
        consensus_vote = list(match.judge_votes.values())[0]
        print(f"         🎯 Early consensus reached: {consensus_vote}")
        return  # Skip third judge
    
    # Execute third judge sequentially if needed
    if len(judges) > 2:
        third_judge = judges[2]
        try:
            vote, conversation, explanation = (
                judge_executor.execute_judge_decision(
                    match,
                    third_judge,
                    eval_data,
                    conversations_cache_dir,
                    {},  # Empty intermediaries for now
                )
            )
            match.add_judge_result(
                third_judge["id"], vote, conversation, explanation
            )
        except Exception as e:
            print(f"         ❌ Judge {third_judge['id']} failed: {e}")
            error_conversation = [
                {
                    "role": "user",
                    "content": "[JUDGE_EXECUTION_ERROR]",
                },
                {"role": "assistant", "content": f"Error: {e}"},
            ]
            match.add_judge_result(
                third_judge["id"],
                "TIE",
                error_conversation,
                f"Error: {e}",
            )


def main_with_cache_dir_data_driven(
    conversations_cache_dir: str,
    models_file: str,
    judges_file: str,
    skills_file: str,
    output_file: str,
):
    """
    Data-driven tournament generation that fixes the restart loop bug.

    This version processes tournaments for ALL skills that have conversation files,
    not just the skills in loaded_skills.json. This fixes the issue where:
    1. Pipeline generates conversations for all skills
    2. Config gets changed to limit skills
    3. Tournament system only processes limited skills
    4. Pipeline gets stuck in restart loop

    Args:
        conversations_cache_dir: Path to conversations cache directory
        models_file: Path to loaded models JSON
        judges_file: Path to loaded judges JSON
        skills_file: Path to loaded skills JSON (used for eval definitions)
        output_file: Path to output tournaments JSON

    Returns:
        dict: Success/failure status
    """
    print("🏆 Swiss Tournament System Starting (Data-Driven Mode)!")

    # Import restart detector
    from tournament_restart_detector import TournamentRestartDetector

    # Load input data
    with open(models_file) as f:
        models_data = json.load(f)
    with open(judges_file) as f:
        judges_data = json.load(f)
    with open(skills_file) as f:
        skills_data = json.load(f)

    models = models_data["models"]
    judges = judges_data["judges"]

    # CRITICAL FIX: Get skills from conversation directories, not config
    conversations_dir = Path(conversations_cache_dir)
    detector = TournamentRestartDetector(conversations_dir, Path(output_file))
    skills_with_conversations = detector.get_skills_with_conversations()

    # Define judge cache directory
    data_dir = (
        conversations_dir.parent
    )  # Go up one level from conversations to data/profile
    cache_dir = data_dir / "judge_cache"

    print(f"📊 Loaded {len(models)} models, {len(judges)} judges")
    print(f"📁 Using conversation cache: {conversations_cache_dir}")
    print(f"📁 Using judge cache: {cache_dir}")
    print(f"🔍 Found conversations for skills: {sorted(skills_with_conversations)}")

    # Filter evals to only include those for skills with conversations
    available_evals = []
    dict(skills_data["skills"].items())

    for eval_data in skills_data["evals"]:
        skill_id = eval_data["_metadata"]["skill"]
        if skill_id in skills_with_conversations:
            available_evals.append(eval_data)

    print(
        f"🚀 Running tournaments for {len(available_evals)} evals across {len(skills_with_conversations)} skills..."
    )

    if len(models) < 2:
        print("⚠️  Need at least 2 models for tournaments - skipping")
        tournament_results = {
            "tournaments": [],
            "execution_info": {
                "status": "insufficient_models",
                "models_count": len(models),
                "message": "Need at least 2 models for tournaments",
            },
        }
    else:
        judge_executor = JudgeExecutor(cache_dir)

        # Clean up invalid match cache entries first
        judge_executor.cleanup_invalid_match_cache(models, judges, available_evals)

        all_tournaments = []

        # Process tournaments for all skills with conversations
        for skill_id in sorted(skills_with_conversations):
            skill_evals = [
                e for e in available_evals if e["_metadata"]["skill"] == skill_id
            ]

            if not skill_evals:
                continue

            print(f"\n🏟️  Processing skill: {skill_id} ({len(skill_evals)} evals)")

            for eval_data in skill_evals:
                eval_id = eval_data["id"]
                skill_id_from_eval = eval_data["_metadata"]["skill"]

                print(f"\n🏟️  Tournament: {skill_id_from_eval}/{eval_id}")

                # Create tournament
                tournament = SwissTournament(skill_id_from_eval, eval_id, models)
                rounds_needed = tournament._calculate_rounds_needed()
                print(f"   📋 {len(models)} models, {rounds_needed} rounds planned")

                # Run tournament rounds
                for round_num in range(rounds_needed):
                    print(f"\n   🔄 Round {round_num + 1}/{rounds_needed}")

                    # Generate pairings for this round
                    pairings = tournament._get_pairings_for_round(round_num)
                    round_matches = []

                    for model_a_id, model_b_id in pairings:
                        print(f"      🥊 {model_a_id} vs {model_b_id}")

                        # Create match
                        match = TournamentMatch(
                            model_a_id, model_b_id, eval_id, skill_id_from_eval
                        )
                        match.timestamp = datetime.utcnow().isoformat()

                        # Execute judges for this match with parallel optimization
                        _execute_judges_for_match(
                            match, judges, judge_executor, eval_data, conversations_cache_dir
                        )

                        # Calculate match result
                        match.calculate_result()
                        print(f"         🏆 Winner: {match.result}")

                        round_matches.append(match)
                        tournament.update_scores(match)

                    # Add completed round to tournament
                    tournament.rounds.append(round_matches)

                print(f"   🎉 Tournament {skill_id_from_eval}/{eval_id} complete!")

                # Mark tournament as completed if we have a winner
                if not tournament.completed and tournament.winner:
                    tournament.completed = True
                all_tournaments.append(tournament.to_dict())

        tournament_results = {
            "tournaments": all_tournaments,
            "execution_info": {
                "status": "completed",
                "tournaments_count": len(all_tournaments),
                "skills_processed": len(skills_with_conversations),
                "evals_processed": len(available_evals),
                "models_count": len(models),
                "judges_count": len(judges),
                "data_driven": True,
                "restart_detection_used": True,
            },
        }

    # Save results
    with open(output_file, "w") as f:
        json.dump(tournament_results, f, indent=2)

    print(f"\n💾 Tournament results saved to: {output_file}")
    return {"success": True}


def main():
    """Main function for Snakemake integration."""
    if "snakemake" in globals():
        # Check if using new cache dir mode or old conversations.json mode
        if hasattr(snakemake.input, "conversations_cache_dir"):
            # New mode: Direct cache directory access
            return main_with_cache_dir(
                str(snakemake.input.conversations_cache_dir),
                str(snakemake.input.models),
                str(snakemake.input.judges),
                str(snakemake.input.skills),
                str(snakemake.output[0]),
            )
        else:
            # Old mode: conversations.json file (legacy)
            conversations_file = Path(snakemake.input.conversations)
            models_file = Path(snakemake.input.models)
            judges_file = Path(snakemake.input.judges)
            skills_file = Path(snakemake.input.skills)
            output_file = Path(snakemake.output[0])
    else:
        # Called directly - MUST provide data_dir via environment variable
        data_dir_env = os.getenv("AFBENCH_DATA_DIR")
        if not data_dir_env:
            raise ValueError(
                "🚨 SAFETY: run_tournaments.py requires explicit data directory.\n"
                "Set AFBENCH_DATA_DIR environment variable or run via Snakemake."
            )

        data_dir = Path(data_dir_env)
        conversations_file = data_dir / "conversations.json"
        models_file = data_dir / "loaded_models.json"
        judges_file = data_dir / "loaded_judges.json"
        skills_file = data_dir / "loaded_skills.json"
        output_file = data_dir / "tournaments.json"

    # Define cache_dir for both Snakemake and direct execution modes
    if "snakemake" in globals():
        # Extract data_dir from Snakemake output path
        output_path = Path(snakemake.output[0])
        data_dir_snakemake = output_path.parent
        cache_dir = data_dir_snakemake / "judge_cache"
    else:
        # Use data_dir from environment variable
        cache_dir = data_dir / "judge_cache"

    print("🏆 Swiss Tournament System Starting!")

    # Load all input data
    with open(conversations_file) as f:
        json.load(f)

    with open(models_file) as f:
        models_data = json.load(f)

    with open(judges_file) as f:
        judges_data = json.load(f)

    with open(skills_file) as f:
        skills_data = json.load(f)

    models = models_data["models"]
    judges = judges_data["judges"]
    evals = skills_data["evals"]

    print(f"📊 Loaded: {len(models)} models, {len(judges)} judges, {len(evals)} evals")

    if len(models) < 2:
        print("⚠️  Need at least 2 models for tournaments - skipping")
        result = {
            "tournaments": [],
            "execution_info": {
                "status": "insufficient_models",
                "models_count": len(models),
                "message": "Need at least 2 models for tournaments",
            },
        }
    else:
        print(f"🚀 Running tournaments for {len(evals)} evals...")

        judge_executor = JudgeExecutor(cache_dir)

        # Clean up invalid match cache entries first
        judge_executor.cleanup_invalid_match_cache(models, judges, evals)

        all_tournaments = []

        for eval_data in evals:
            skill_id = eval_data["_metadata"]["skill"]
            eval_id = eval_data["id"]

            print(f"\n🏟️  Tournament: {skill_id}/{eval_id}")

            # Create tournament
            tournament = SwissTournament(skill_id, eval_id, models)
            rounds_needed = tournament._calculate_rounds_needed()

            print(f"   📋 {len(models)} models, {rounds_needed} rounds planned")

            # Run tournament rounds
            for round_num in range(rounds_needed):
                print(f"\n   🔄 Round {round_num + 1}/{rounds_needed}")

                # Get pairings for this round
                pairings = tournament._get_pairings_for_round(round_num)

                if not pairings:
                    print("   ⚠️  No pairings possible (odd numbers with byes)")
                    break

                round_matches = []

                for model_a_id, model_b_id in pairings:
                    print(f"      🥊 {model_a_id} vs {model_b_id}")

                    # Create match
                    match = TournamentMatch(model_a_id, model_b_id, eval_id, skill_id)
                    match.timestamp = datetime.utcnow().isoformat()

                    # Execute judges for this match
                    for i, judge in enumerate(judges):
                        try:
                            vote, conversation, explanation = (
                                judge_executor.execute_judge_decision(
                                    match,
                                    judge,
                                    eval_data,
                                    conversations_cache_dir,
                                    intermediaries_data,
                                )
                            )
                            match.add_judge_result(
                                judge["id"], vote, conversation, explanation
                            )

                            # Check for early consensus after 2nd judge
                            if i == 1 and match.check_early_consensus():
                                print(f"         🎯 Early consensus reached: {vote}")
                                break

                        except Exception as e:
                            print(f"         ❌ Judge {judge['id']} failed: {e}")
                            # Add error vote
                            error_conversation = [
                                {"role": "user", "content": "[JUDGE_EXECUTION_ERROR]"},
                                {"role": "assistant", "content": f"Error: {e}"},
                            ]
                            match.add_judge_result(
                                judge["id"], "TIE", error_conversation, f"Error: {e}"
                            )

                    # Calculate match result
                    match.calculate_result()
                    print(f"         🏆 Winner: {match.result}")

                    # Update tournament scores
                    tournament.update_scores(match)
                    round_matches.append(match)

                tournament.rounds.append(round_matches)

                # Check if tournament is complete
                if tournament.is_tournament_complete():
                    print(f"   🎉 Tournament complete! Winner: {tournament.winner}")
                    break

            if not tournament.completed and tournament.winner:
                tournament.completed = True

            all_tournaments.append(tournament.to_dict())

        result = {
            "tournaments": all_tournaments,
            "execution_info": {
                "status": "completed",
                "tournaments_count": len(all_tournaments),
                "total_models": len(models),
                "total_judges": len(judges),
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    # Save results
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n💾 Tournament results saved to: {output_file}")


if __name__ == "__main__":
    main()
