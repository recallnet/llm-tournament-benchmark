#!/usr/bin/env python3
"""
Proper type definitions for AFBench - this would have caught the runtime bugs.

The bugs we hit were caused by loose typing with dict[str, Any] everywhere.
With proper types, MyPy would have caught:
- Missing 'status' key access
- Wrong method signature calls
- Invalid dictionary structure assumptions
"""

from typing import Literal, TypedDict


class ModelConfig(TypedDict):
    """Type-safe model configuration."""

    id: str
    author: str
    slug: str | None
    context_window: int
    endpoint: str


class JudgeConfig(TypedDict):
    """Type-safe judge configuration."""

    id: str
    author: str
    context_window: int | None


class EvalMetadata(TypedDict):
    """Type-safe eval metadata."""

    skill: str


class IntermediaryConfig(TypedDict):
    """Type-safe intermediary configuration."""

    id: str
    prompt: str


class EvalConfig(TypedDict):
    """Type-safe evaluation configuration."""

    id: str
    name: str | None
    _metadata: EvalMetadata
    chain: list[str]
    intermediaries: list[IntermediaryConfig] | None


class ConversationMessage(TypedDict):
    """Type-safe conversation message."""

    role: Literal["user", "assistant", "system"]
    content: str


class ConversationMetadata(TypedDict):
    """Type-safe conversation metadata."""

    skill_id: str
    eval_id: str
    eval_name: str | None
    model_id: str
    model_slug: str | None
    model_author: str
    timestamp: str
    cache_key: str
    step_count: int
    message_count: int


class ConversationExecutionInfo(TypedDict):
    """Type-safe execution info."""

    total_steps: int
    completed_steps: int
    status: Literal[
        "completed", "failed", "partial"
    ]  # THIS would have caught the KeyError!


class ConversationResult(TypedDict):
    """Type-safe conversation result."""

    metadata: ConversationMetadata
    messages: list[ConversationMessage]
    execution_info: ConversationExecutionInfo


class PipelineExecutionInfo(TypedDict):
    """Type-safe pipeline execution info - this is what was missing the 'status' field."""

    total_conversations: int
    successful_conversations: int
    failed_conversations: int
    total_intermediaries: int
    successful_intermediaries: int
    failed_intermediaries: int
    timestamp: str
    models_count: int
    evals_count: int
    judges_count: int
    # Notice: NO 'status' field here - this was the source of KeyError: 'status'


class PipelineResult(TypedDict):
    """Type-safe pipeline result."""

    execution_info: PipelineExecutionInfo  # This dict structure was the issue!
    conversations: list[ConversationResult]
    intermediaries: list[ConversationResult]


class IntermediaryResult(TypedDict):
    """Type-safe intermediary result."""

    metadata: ConversationMetadata
    messages: list[ConversationMessage]
    execution_info: ConversationExecutionInfo


# With proper typing, the ConversationExecutor methods would be:


class TypedConversationExecutor:
    """Properly typed version that would have prevented the bugs."""

    def execute_intermediary(
        self,
        intermediary: IntermediaryConfig,  # Clear structure
        conversation_result: ConversationResult,  # Clear structure
        judge_model: JudgeConfig,  # Clear structure
        skill_id: str,
        eval_id: str,
    ) -> IntermediaryResult:
        """
        With proper typing, the call site would have failed to compile:

        executor.execute_intermediary(
            target_model,      # ❌ ModelConfig != IntermediaryConfig
            judges[0],         # ❌ JudgeConfig != ConversationResult
            skill_id,          # ❌ str != JudgeConfig
            eval_data,         # ❌ EvalConfig != str
            intermediary_data, # ❌ IntermediaryConfig != str
            conversation_result # ❌ Too many arguments!
        )
        """
        pass

    def execute_conversations_for_model_cache_only(
        self, models_file: str, skills_file: str, judges_file: str, target_model_id: str
    ) -> bool:
        """
        With proper typing, this would have failed to compile:

        result: PipelineResult = execute_conversations_for_model(...)
        return result["execution_info"]["status"] == "completed"
        #      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        #      ❌ MyPy Error: "status" key does not exist in PipelineExecutionInfo
        """
        pass


# Example of how proper typing would catch the exact bugs we hit:


def demonstrate_typing_would_catch_bugs():
    """Show how proper typing would have prevented the runtime failures."""

    # Bug 1: KeyError: 'status'

    # This would be a MyPy error with proper typing:
    # status = pipeline_result["execution_info"]["status"]  # ❌ Key 'status' not in PipelineExecutionInfo

    # Bug 2: Wrong method signature

    TypedConversationExecutor()

    # This would be a MyPy error with proper typing:
    # executor.execute_intermediary(judge, intermediary, conversation, "skill", "eval")
    # ❌ Arguments have wrong types and wrong order

    print("With proper typing, both bugs would be caught at development time!")


if __name__ == "__main__":
    demonstrate_typing_would_catch_bugs()
