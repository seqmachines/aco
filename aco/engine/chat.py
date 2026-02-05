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
# System prompts (kept concise for token efficiency)
# ---------------------------------------------------------------------------

_SYSTEM_INTAKE = (
    "You are a bioinformatics assistant helping a user describe their "
    "sequencing experiment. Be concise and helpful. Suggest improvements "
    "to the experiment description, goals, or known issues when relevant."
)

_SYSTEM_SCANNING = (
    "You are a bioinformatics assistant explaining file scan results. "
    "Be concise. Help the user understand what was found and whether "
    "the file structure looks correct."
)

_SYSTEM_MANIFEST = (
    "You are a bioinformatics assistant helping review an experiment "
    "manifest. Be concise and helpful. Explain the data and suggest "
    "corrections if something looks off."
)

_SYSTEM_UNDERSTANDING = (
    "You are a bioinformatics assistant helping review an experiment "
    "understanding. Be concise and helpful. When the user asks to modify "
    "something, explain what you would change."
)

_SYSTEM_SCRIPTS = (
    "You are a bioinformatics assistant helping refine a script execution "
    "plan. You can suggest adding, removing, or modifying scripts. Be concise."
)

_SYSTEM_NOTEBOOK = (
    "You are a bioinformatics assistant helping with a QC notebook. "
    "Be concise. Explain results and suggest next steps."
)

_SYSTEM_REPORT = (
    "You are a bioinformatics assistant helping review a QC report. "
    "Be concise. Summarise findings and flag issues."
)


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
) -> tuple[str, bool, dict | None]:
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
        max_output_tokens=2048,
    )
    return response.strip(), False, None


async def handle_scanning_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    manifest=None,
    **kwargs,
) -> tuple[str, bool, dict | None]:
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
        max_output_tokens=2048,
    )
    return response.strip(), False, None


async def handle_manifest_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    manifest=None,
    **kwargs,
) -> tuple[str, bool, dict | None]:
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
        max_output_tokens=2048,
    )
    return response.strip(), False, None


async def handle_understanding_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    understanding=None,
    **kwargs,
) -> tuple[str, bool, dict | None]:
    """Handle chat in the understanding step.

    Context: understanding summary, quality concerns, recommended checks.
    artifact_updated=False for now (refinement via regenerate).
    """
    context_parts: list[str] = ["## Experiment Understanding"]
    if understanding is not None:
        context_parts.append(f"Type: {understanding.experiment_type.value}")
        context_parts.append(f"Assay: {understanding.assay_name}")
        context_parts.append(f"Samples: {understanding.sample_count}")
        context_parts.append(f"Summary: {understanding.summary[:500]}")
        if understanding.quality_concerns:
            concerns = "; ".join(
                f"{c.title} ({c.severity})" for c in understanding.quality_concerns
            )
            context_parts.append(f"Quality concerns: {concerns}")
        if understanding.recommended_checks:
            checks = "; ".join(
                f"{c.name} ({c.priority})" for c in understanding.recommended_checks
            )
            context_parts.append(f"Recommended checks: {checks}")
    else:
        context_parts.append("No understanding generated yet.")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    response = await client.generate_async(
        prompt=prompt,
        system_instruction=_SYSTEM_UNDERSTANDING,
        temperature=0.7,
        max_output_tokens=2048,
    )
    return response.strip(), False, None


async def handle_scripts_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    plan=None,
    understanding=None,
    **kwargs,
) -> tuple[str, bool, dict | None]:
    """Handle chat in the scripts step.

    Context: current script plan + understanding summary.
    For now this provides conversational responses about the plan.
    Actual plan refinement is done via the /scripts/plan/refine endpoint.
    artifact_updated=False (conversational only).
    """
    context_parts: list[str] = ["## Script Plan"]
    if plan is not None:
        context_parts.append(f"Scripts ({len(plan.scripts)}):")
        for s in plan.scripts:
            context_parts.append(f"  - {s.name}: {s.description[:120]}")
        if plan.execution_order:
            context_parts.append(f"Execution order: {', '.join(plan.execution_order)}")
    else:
        context_parts.append("No script plan generated yet.")

    if understanding is not None:
        context_parts.append(f"\n## Experiment Context")
        context_parts.append(f"Type: {understanding.experiment_type.value}")
        context_parts.append(f"Summary: {understanding.summary[:300]}")

    conversation = _build_conversation_context(chat_history)
    prompt = (
        f"{chr(10).join(context_parts)}\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"User: {message}"
    )

    response = await client.generate_async(
        prompt=prompt,
        system_instruction=_SYSTEM_SCRIPTS,
        temperature=0.7,
        max_output_tokens=2048,
    )
    return response.strip(), False, None


async def handle_notebook_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    **kwargs,
) -> tuple[str, bool, dict | None]:
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
        max_output_tokens=2048,
    )
    return response.strip(), False, None


async def handle_report_chat(
    manifest_id: str,
    message: str,
    chat_history: list[ChatMessage],
    client: GeminiClient,
    **kwargs,
) -> tuple[str, bool, dict | None]:
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
        max_output_tokens=2048,
    )
    return response.strip(), False, None


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
) -> tuple[str, bool, dict | None]:
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
        A tuple of (response_text, artifact_updated, updated_data).
    """
    handler = STEP_HANDLERS.get(step)
    if handler is None:
        return (
            "I can help with that step, but I don't have a specific handler for it yet.",
            False,
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
        response_text, artifact_updated, updated_data = await handler(
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

    # Append assistant response and persist
    assistant_msg = ChatMessage(role="assistant", content=response_text)
    history.append(assistant_msg)
    store.save_messages(manifest_id, step, history)

    return response_text, artifact_updated, updated_data
