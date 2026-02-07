"""Chat engine for LLM-powered conversation across all workflow steps.

This module provides step-specific chat handlers that maintain context
and conversation history for each workflow step. Messages are persisted
as JSON files per manifest per step.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from aco.engine.gemini import GeminiClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """A single chat message between user and assistant."""

    role: str = Field(..., description="user or assistant")
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ScriptPlanIntentDecision(BaseModel):
    """Decision model for whether scripts chat should mutate the plan."""

    should_update_plan: bool = Field(
        ..., description="Whether the user is requesting a plan change."
    )
    confidence: float = Field(
        ..., description="Confidence from 0.0 to 1.0 for the decision."
    )
    reasoning: str = Field(
        ..., description="Short rationale grounded in the user message."
    )
    requested_changes: list[str] = Field(
        default_factory=list,
        description="Concrete requested modifications parsed from the message.",
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class ChatStore:
    """File-based persistence for chat messages per manifest per step."""

    def __init__(self) -> None:
        pass  # stateless, derives paths from working dir

    def _get_chat_path(self, manifest_id: str, step: str) -> Path:
        """Return the path to the chat JSON file for a given manifest and step."""
        working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
        return Path(working_dir) / "aco_runs" / manifest_id / "chat" / f"{step}.json"

    def save_messages(
        self, manifest_id: str, step: str, messages: list[ChatMessage]
    ) -> None:
        """Persist a list of chat messages to disk."""
        path = self._get_chat_path(manifest_id, step)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [msg.model_dump(mode="json") for msg in messages]
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def load_messages(self, manifest_id: str, step: str) -> list[ChatMessage]:
        """Load chat messages from disk. Returns empty list if none exist."""
        path = self._get_chat_path(manifest_id, step)
        if not path.exists():
            return []
        try:
            with open(path) as f:
                data = json.load(f)
            return [ChatMessage.model_validate(item) for item in data]
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Failed to load chat history from %s: %s", path, exc)
            return []

    def clear_messages(self, manifest_id: str, step: str) -> None:
        """Delete the chat history file for a manifest/step."""
        path = self._get_chat_path(manifest_id, step)
        if path.exists():
            path.unlink()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_conversation_context(chat_history: list[ChatMessage]) -> str:
    """Format the last 10 messages into a conversation string."""
    recent = chat_history[-10:]
    lines: list[str] = []
    for msg in recent:
        prefix = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{prefix}: {msg.content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_INTAKE = (
    "You are a bioinformatics assistant helping a user describe their "
    "sequencing experiment. Provide thorough, detailed answers. Suggest "
    "improvements to the experiment description, goals, or known issues "
    "when relevant. Use examples and explain your reasoning."
)

_SYSTEM_SCANNING = (
    "You are a bioinformatics assistant explaining file scan results. "
    "Provide thorough, detailed answers. Help the user understand what "
    "was found, whether the file structure looks correct, and what the "
    "file types and sizes indicate about the experiment."
)

_SYSTEM_MANIFEST = (
    "You are a bioinformatics assistant helping review an experiment "
    "manifest. Provide thorough, detailed answers. Explain the data "
    "structure, suggest corrections if something looks off, and help "
    "the user understand how the manifest connects to their experiment."
)

_SYSTEM_UNDERSTANDING = (
    "You are a bioinformatics assistant helping review and refine an "
    "experiment understanding. Provide thorough, detailed answers.\n\n"
    "IMPORTANT: If the user asks you to change, modify, update, fix, "
    "or correct something in the understanding, start your response with "
    "the exact marker '[MODIFY]' on its own line, followed by a detailed "
    "explanation of what you are changing and why. Do NOT use this marker "
    "when the user is just asking a question.\n\n"
    "Examples of modification requests: 'change the experiment type to X', "
    "'the read structure is wrong, it should be Y', 'update the summary', "
    "'add a quality concern about Z', 'remove sample X'.\n\n"
    "Examples of questions (no marker): 'what is the experiment type?', "
    "'explain the read structure', 'why was this assay detected?'."
)

_SYSTEM_SCRIPTS = (
    "You are a bioinformatics assistant answering questions about a script "
    "execution plan. You can explain the plan, discuss bioinformatics concepts, "
    "and help the user understand what each script does.\n\n"
    "CRITICAL CONSTRAINT: You CANNOT modify, update, or change the script plan. "
    "Plan modifications are handled by a separate system. NEVER say you have "
    "updated, changed, modified, added, or removed anything in the plan. "
    "If the user asks you to change the plan, tell them you are processing "
    "their request and the plan will be updated shortly."
)

_SYSTEM_NOTEBOOK = (
    "You are a bioinformatics assistant helping with a QC notebook. "
    "Provide thorough, detailed answers. Explain results, interpret "
    "plots and metrics, and suggest next steps with reasoning."
)

_SYSTEM_REPORT = (
    "You are a bioinformatics assistant helping review a QC report. "
    "Provide thorough, detailed answers. Summarize findings, explain "
    "their implications, and flag issues with context."
)


_SCRIPTS_INTENT_PROMPT = """Classify whether this user message requests changing the script plan.

# Current Script Plan (JSON)
{plan_json}

# Experiment Context
Type: {experiment_type}
Summary: {understanding_summary}

# Recent Conversation
{conversation}

# User Message
{message}

# Decision Rule
- should_update_plan=true when the user explicitly or implicitly asks to add/remove/rename/change scripts, dependencies, inputs, outputs, categories, or execution order.
- should_update_plan=false for pure questions, clarification requests, or explanations.
- When uncertain, still set should_update_plan=true if the message leans toward requesting a change.
  Use confidence to express certainty (0.5+ is sufficient for update).
- Only set should_update_plan=false when the message is clearly a question with no intent to modify.

Return structured output only.
"""


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def _detect_modify_intent(response_text: str) -> tuple[bool, str]:
    """Check if the LLM response indicates a modification intent.

    Returns:
        Tuple of (is_modify, cleaned_response_text).
        If is_modify is True, the [MODIFY] marker is stripped from the response.
    """
    stripped = response_text.strip()
    if stripped.startswith("[MODIFY]"):
        cleaned = stripped[len("[MODIFY]"):].lstrip("\n").lstrip()
        return True, cleaned
    return False, stripped


def _serialize_plan_for_prompt(plan) -> str:
    """Serialize plan details (without code) for intent classification."""
    if plan is None:
        return "[]"
    data = []
    for s in plan.scripts:
        data.append(
            {
                "name": s.name,
                "category": s.category.value if hasattr(s.category, "value") else s.category,
                "script_type": s.script_type.value if hasattr(s.script_type, "value") else s.script_type,
                "description": s.description,
                "dependencies": s.dependencies,
                "input_files": s.input_files,
                "output_files": s.output_files,
            }
        )
    return json.dumps(data, indent=2)


async def _classify_scripts_plan_intent(
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    plan=None,
    understanding=None,
) -> ScriptPlanIntentDecision:
    """Classify whether a scripts-step chat message should mutate the plan."""
    plan_json = _serialize_plan_for_prompt(plan)
    conversation = _build_conversation_context(chat_history)
    experiment_type = (
        understanding.experiment_type.value
        if understanding is not None and hasattr(understanding.experiment_type, "value")
        else "unknown"
    )
    understanding_summary = (
        understanding.summary[:600] if understanding is not None else "No understanding available."
    )

    prompt = _SCRIPTS_INTENT_PROMPT.format(
        plan_json=plan_json,
        experiment_type=experiment_type,
        understanding_summary=understanding_summary,
        conversation=conversation or "(no prior conversation)",
        message=message,
    )

    decision = await client.generate_structured_async(
        prompt=prompt,
        response_schema=ScriptPlanIntentDecision,
        system_instruction=(
            "You are a strict classifier for script-plan update intent in a "
            "bioinformatics assistant."
        ),
        temperature=0.1,
    )
    return decision


# ---------------------------------------------------------------------------
# Artifact refinement helpers
# ---------------------------------------------------------------------------

_REFINE_UNDERSTANDING_PROMPT = """You are refining an experiment understanding based on user feedback.

# Current Understanding (JSON)

{understanding_json}

# User Feedback

{feedback}

# Instructions

Apply the user's requested changes to the understanding. Modify ONLY the fields
the user mentioned. Keep everything else exactly the same.

Return the COMPLETE updated understanding (not just the changes).
"""


async def _refine_understanding(
    understanding,
    feedback: str,
    client: GeminiClient,
):
    """Refine an ExperimentUnderstanding based on user chat feedback.

    Uses structured output to produce a valid ExperimentUnderstanding.
    """
    from aco.engine.models import ExperimentUnderstanding

    understanding_json = json.dumps(
        understanding.model_dump(mode="json"), indent=2
    )

    prompt = _REFINE_UNDERSTANDING_PROMPT.format(
        understanding_json=understanding_json,
        feedback=feedback,
    )

    updated = await client.generate_structured_async(
        prompt=prompt,
        response_schema=ExperimentUnderstanding,
        system_instruction=(
            "You are an expert bioinformatics scientist. Apply the requested "
            "changes precisely. Do not change fields the user did not mention."
        ),
        temperature=0.3,
        max_output_tokens=8192,
    )

    # Preserve metadata fields
    updated.model_used = understanding.model_used
    updated.generated_at = understanding.generated_at
    updated.is_approved = understanding.is_approved
    updated.approved_at = understanding.approved_at
    updated.user_edits = understanding.user_edits

    return updated


# ---------------------------------------------------------------------------
# Step handlers
# ---------------------------------------------------------------------------

async def handle_intake_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    manifest=None,
    **kwargs,
) -> tuple[str, bool, dict | None, dict | None]:
    """Handle chat in the intake step.

    Context: user intake data (experiment_description, goals, known_issues).
    Always returns artifact_updated=False because intake is form-based.
    """
    context_parts: list[str] = ["## Current Intake Information"]
    if manifest is not None:
        intake = manifest.user_intake
        context_parts.append(f"Description: {intake.experiment_description}")
        if intake.goals:
            context_parts.append(f"Goals: {intake.goals}")
        if intake.known_issues:
            context_parts.append(f"Known issues: {intake.known_issues}")
    else:
        context_parts.append("No intake information available yet.")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    response = await client.generate_async(
        prompt=prompt,
        system_instruction=_SYSTEM_INTAKE,
        temperature=0.7,
        max_output_tokens=4096,
    )
    return response.strip(), False, None, None


async def handle_scanning_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    manifest=None,
    **kwargs,
) -> tuple[str, bool, dict | None, dict | None]:
    """Handle chat in the scanning step.

    Context: scan result summary (file counts, types).
    Read-only -- explains findings. artifact_updated=False.
    """
    context_parts: list[str] = ["## Scan Results"]
    if manifest is not None and manifest.scan_result is not None:
        sr = manifest.scan_result
        context_parts.append(f"Scanned path: {sr.scan_path}")
        context_parts.append(f"Total files: {sr.total_files} ({sr.total_size_human})")
        context_parts.append(f"FASTQ: {sr.fastq_count}, BAM: {sr.bam_count}, "
                             f"CellRanger outputs: {sr.cellranger_count}, "
                             f"Other: {sr.other_count}")
        if sr.directories:
            context_parts.append("Special directories: "
                                 + ", ".join(d.name for d in sr.directories))
    else:
        context_parts.append("No scan results available yet.")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    response = await client.generate_async(
        prompt=prompt,
        system_instruction=_SYSTEM_SCANNING,
        temperature=0.7,
        max_output_tokens=4096,
    )
    return response.strip(), False, None, None


async def handle_manifest_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    manifest=None,
    **kwargs,
) -> tuple[str, bool, dict | None, dict | None]:
    """Handle chat in the manifest step.

    Context: manifest summary.
    artifact_updated=False -- user edits manifest directly in the UI.
    """
    context_parts: list[str] = ["## Manifest Summary"]
    if manifest is not None:
        context_parts.append(f"ID: {manifest.id}")
        context_parts.append(f"Status: {manifest.status}")
        context_parts.append(f"Description: {manifest.user_intake.experiment_description[:300]}")
        if manifest.scan_result:
            context_parts.append(f"Files: {manifest.scan_result.total_files} "
                                 f"({manifest.scan_result.total_size_human})")
    else:
        context_parts.append("No manifest available yet.")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    response = await client.generate_async(
        prompt=prompt,
        system_instruction=_SYSTEM_MANIFEST,
        temperature=0.7,
        max_output_tokens=4096,
    )
    return response.strip(), False, None, None


async def handle_understanding_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    understanding=None,
    **kwargs,
) -> tuple[str, bool, dict | None, dict | None]:
    """Handle chat in the understanding step.

    Context: full understanding JSON for detailed answers.
    Detects [MODIFY] marker and refines understanding via structured output.
    """
    context_parts: list[str] = ["## Experiment Understanding"]
    if understanding is not None:
        # Provide full understanding as JSON for comprehensive answers
        understanding_dict = understanding.model_dump(mode="json")
        understanding_json = json.dumps(understanding_dict, indent=2)
        if len(understanding_json) > 8000:
            # Fall back to key fields if too large
            context_parts.append(f"Type: {understanding.experiment_type.value}")
            context_parts.append(f"Assay: {understanding.assay_name}")
            context_parts.append(f"Platform: {understanding.assay_platform.value}")
            context_parts.append(f"Samples: {understanding.sample_count}")
            context_parts.append(f"Summary: {understanding.summary}")
            if understanding.read_structure:
                rs = understanding.read_structure
                context_parts.append(
                    f"Read Structure: {rs.assay_name}, "
                    f"R1={rs.read1_length}bp, R2={rs.read2_length}bp"
                )
                for seg in rs.segments:
                    context_parts.append(
                        f"  Segment: {seg.name} ({seg.segment_type}), "
                        f"pos {seg.start_position}-{seg.end_position}"
                    )
            if understanding.quality_concerns:
                for c in understanding.quality_concerns:
                    context_parts.append(
                        f"Quality Concern: {c.title} ({c.severity}): {c.description}"
                    )
            if understanding.recommended_checks:
                for c in understanding.recommended_checks:
                    context_parts.append(
                        f"Recommended Check: {c.name} ({c.priority}): {c.description}"
                    )
        else:
            context_parts.append(understanding_json)
    else:
        context_parts.append("No understanding generated yet.")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    # Step 1: Freeform response
    response = await client.generate_async(
        prompt=prompt,
        system_instruction=_SYSTEM_UNDERSTANDING,
        temperature=0.7,
        max_output_tokens=4096,
    )

    is_modify, cleaned_response = _detect_modify_intent(response)

    if not is_modify or understanding is None:
        return cleaned_response, False, None, None

    # Step 2: Structured modification
    try:
        updated_understanding = await _refine_understanding(
            understanding=understanding,
            feedback=message,
            client=client,
        )
        updated_data = updated_understanding.model_dump(mode="json")
        return cleaned_response, True, updated_data, None
    except Exception as exc:
        logger.error("Failed to refine understanding: %s", exc, exc_info=True)
        return (
            cleaned_response + "\n\n(Note: I tried to apply the modification but "
            "encountered an error. Please try again or use the regenerate button.)",
            False,
            None,
            None,
        )


async def handle_scripts_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    plan=None,
    understanding=None,
    **kwargs,
) -> tuple[str, bool, dict | None, dict | None]:
    """Handle chat in the scripts step.

    Classifies intent from user message, then updates the plan when needed.
    """
    context_parts: list[str] = ["## Script Plan"]
    if plan is not None:
        plan_summary = []
        for s in plan.scripts:
            plan_summary.append({
                "name": s.name,
                "category": s.category.value if hasattr(s.category, "value") else s.category,
                "script_type": s.script_type.value if hasattr(s.script_type, "value") else s.script_type,
                "description": s.description,
                "dependencies": s.dependencies,
                "input_files": s.input_files,
                "output_files": s.output_files,
                "estimated_runtime": s.estimated_runtime,
            })
        context_parts.append(json.dumps(plan_summary, indent=2))
        if plan.execution_order:
            context_parts.append(f"Execution order: {', '.join(plan.execution_order)}")
    else:
        context_parts.append("No script plan generated yet.")

    if understanding is not None:
        context_parts.append(f"\n## Experiment Context")
        context_parts.append(f"Type: {understanding.experiment_type.value}")
        context_parts.append(f"Summary: {understanding.summary[:500]}")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    # If plan context is missing, keep this path conversational.
    if plan is None or understanding is None:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction=_SYSTEM_SCRIPTS,
            temperature=0.7,
            max_output_tokens=4096,
        )
        return response.strip(), False, None, None

    # Step 1: Structured intent decision from user message.
    decision: ScriptPlanIntentDecision | None = None
    should_update = False
    try:
        decision = await _classify_scripts_plan_intent(
            message=message,
            chat_history=chat_history,
            client=client,
            plan=plan,
            understanding=understanding,
        )
        logger.info(
            "Script intent classifier: should_update=%s, confidence=%.2f, reasoning=%s",
            decision.should_update_plan,
            decision.confidence,
            decision.reasoning,
        )
        if decision.should_update_plan and decision.confidence >= 0.5:
            should_update = True
    except Exception as exc:
        logger.warning("Script intent classification failed: %s", exc)
        # Fallback keyword detection if classifier fails.
        lowered = message.lower()
        fallback_keywords = (
            "update plan",
            "change plan",
            "modify plan",
            "add script",
            "remove script",
            "replace script",
            "rename script",
            "regenerate plan",
            "add a step",
            "remove a step",
            "include",
            "exclude",
            "skip",
            "use instead",
            "swap",
            "reorder",
        )
        should_update = any(k in lowered for k in fallback_keywords)

    logger.info("Script chat final update decision: should_update=%s", should_update)

    if not should_update:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction=_SYSTEM_SCRIPTS,
            temperature=0.7,
            max_output_tokens=4096,
        )
        return response.strip(), False, None, None

    # Step 2: Regenerate/refine plan and return deterministic change summary.
    try:
        from aco.engine.scripts import (
            format_plan_change_summary,
            plans_equivalent,
            refine_script_plan,
            summarize_plan_changes,
        )

        updated_plan, _ = await refine_script_plan(
            plan=plan,
            feedback=message,
            understanding=understanding,
            client=client,
        )
        if plans_equivalent(plan, updated_plan):
            return (
                "I reviewed your update request, but no effective plan changes were "
                "produced. Please specify exactly what to add, remove, or modify.",
                False,
                None,
                None,
            )

        updated_plan.manifest_id = manifest_id
        updated_data = updated_plan.model_dump(mode="json")
        change_summary = summarize_plan_changes(plan, updated_plan)
        summary_text = format_plan_change_summary(change_summary)

        interpreted = decision.requested_changes if decision else []
        interpreted_text = ""
        if interpreted:
            interpreted_text = "\n".join(f"- {c}" for c in interpreted)
            interpreted_text = f"Interpreted requested changes:\n{interpreted_text}\n\n"

        response_text = (
            "Updated the script plan using your latest chat feedback.\n\n"
            f"{interpreted_text}{summary_text}"
        )
        return response_text, True, updated_data, change_summary
    except Exception as exc:
        logger.error("Failed to refine script plan: %s", exc, exc_info=True)
        return (
            "I understood this as a plan update request, but I encountered an "
            "error while regenerating the plan. Please try again.",
            False,
            None,
            None,
        )


async def handle_notebook_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    **kwargs,
) -> tuple[str, bool, dict | None, dict | None]:
    """Handle chat in the notebook step.

    Conversational response about the notebook. artifact_updated=False.
    """
    context_parts: list[str] = ["## Notebook"]
    notebook_info = kwargs.get("notebook_info")
    if notebook_info:
        context_parts.append(str(notebook_info)[:500])
    else:
        context_parts.append("No notebook information available yet.")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    response = await client.generate_async(
        prompt=prompt,
        system_instruction=_SYSTEM_NOTEBOOK,
        temperature=0.7,
        max_output_tokens=4096,
    )
    return response.strip(), False, None, None


async def handle_report_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    **kwargs,
) -> tuple[str, bool, dict | None, dict | None]:
    """Handle chat in the report step.

    Conversational response about the report. artifact_updated=False.
    """
    context_parts: list[str] = ["## Report"]
    report_info = kwargs.get("report_info")
    if report_info:
        context_parts.append(str(report_info)[:500])
    else:
        context_parts.append("No report information available yet.")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    response = await client.generate_async(
        prompt=prompt,
        system_instruction=_SYSTEM_REPORT,
        temperature=0.7,
        max_output_tokens=4096,
    )
    return response.strip(), False, None, None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

STEP_HANDLERS = {
    "intake": handle_intake_chat,
    "scanning": handle_scanning_chat,
    "manifest": handle_manifest_chat,
    "understanding": handle_understanding_chat,
    "scripts": handle_scripts_chat,
    "notebook": handle_notebook_chat,
    "report": handle_report_chat,
}

# Shared store instance
_chat_store = ChatStore()


def get_chat_store() -> ChatStore:
    """Return the module-level ChatStore instance."""
    return _chat_store


async def handle_chat_message(
    manifest_id: str,
    step: str,
    message: str,
    client: GeminiClient,
    **context,
) -> tuple[str, bool, dict | None, dict | None]:
    """Dispatch a user chat message to the appropriate step handler.

    This is the main entry point for the chat engine.  It:
    1. Loads existing chat history for the manifest/step.
    2. Appends the new user message.
    3. Passes the last 10 messages to the step handler.
    4. Appends the assistant response.
    5. Persists the updated history.

    Args:
        manifest_id: The manifest this conversation belongs to.
        step: Workflow step name (intake, scanning, manifest, ...).
        message: The user's message text.
        client: A GeminiClient instance for LLM calls.
        **context: Step-specific keyword arguments (manifest, understanding,
            plan, notebook_info, report_info, etc.).

    Returns:
        A tuple of (response_text, artifact_updated, updated_data, change_summary).
    """
    handler = STEP_HANDLERS.get(step)
    if handler is None:
        return (
            "I can help with that step, but I don't have a specific handler for it yet.",
            False,
            None,
            None,
        )

    store = get_chat_store()

    # Load history and append the incoming user message
    history = store.load_messages(manifest_id, step)
    user_msg = ChatMessage(role="user", content=message)
    history.append(user_msg)

    # Use last 10 messages as context for the handler
    recent_history = history[-10:]

    try:
        response_text, artifact_updated, updated_data, change_summary = await handler(
            manifest_id=manifest_id,
            message=message,
            chat_history=recent_history,
            client=client,
            **context,
        )
    except Exception as exc:
        logger.error("Chat handler error for step '%s': %s", step, exc, exc_info=True)
        response_text = (
            "I encountered an error processing your message. Please try again."
        )
        artifact_updated = False
        updated_data = None
        change_summary = None

    # Append assistant response and persist
    assistant_msg = ChatMessage(role="assistant", content=response_text)
    history.append(assistant_msg)
    store.save_messages(manifest_id, step, history)

    return response_text, artifact_updated, updated_data, change_summary
