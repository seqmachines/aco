"""Chat API routes for LLM-powered conversation across all workflow steps."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from aco.engine.chat import (
    ChatMessage,
    ChatStore,
    get_chat_store,
    handle_chat_message,
)
from aco.engine.gemini import GeminiClient
from aco.engine import UnderstandingStore
from aco.manifest import ManifestStore


router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""

    manifest_id: str
    step: str = Field(..., description="Workflow step: describe, scan, understanding, hypothesis, strategy, execute, optimize")
    message: str
    model: str | None = None
    api_key: str | None = None


class ChatMessageResponse(BaseModel):
    """Response from a chat message."""

    response: str
    artifact_updated: bool = False
    updated_data: dict | None = None
    change_summary: dict | None = None


class ChatHistoryResponse(BaseModel):
    """Response containing chat history."""

    manifest_id: str
    step: str
    messages: list[dict]


# ---------------------------------------------------------------------------
# Store instances (set during app startup via set_stores)
# ---------------------------------------------------------------------------

_manifest_store: ManifestStore | None = None
_understanding_store: UnderstandingStore | None = None


def set_stores(manifest_store: ManifestStore, understanding_store: UnderstandingStore):
    """Set the store instances for this router."""
    global _manifest_store, _understanding_store
    _manifest_store = manifest_store
    _understanding_store = understanding_store


def get_manifest_store() -> ManifestStore:
    if _manifest_store is None:
        raise HTTPException(500, "Manifest store not initialized")
    return _manifest_store


def get_understanding_store() -> UnderstandingStore:
    if _understanding_store is None:
        raise HTTPException(500, "Understanding store not initialized")
    return _understanding_store


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

VALID_STEPS = {
    # New three-phase step names
    "describe", "scan", "understanding",
    "hypothesis", "references", "strategy", "execute",
    "optimize",
    # Legacy names (backward compat)
    "intake", "scanning", "manifest", "scripts",
}


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(request: ChatMessageRequest):
    """Send a chat message and get an LLM response for the current step."""
    if request.step not in VALID_STEPS:
        raise HTTPException(400, f"Invalid step: {request.step}. Must be one of: {', '.join(sorted(VALID_STEPS))}")

    # Create Gemini client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    try:
        client = GeminiClient(api_key=api_key, model_name=model)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Build step-specific context
    context: dict = {}

    manifest_store = get_manifest_store()
    understanding_store = get_understanding_store()

    # Load manifest for context (used by most steps)
    manifest = manifest_store.load(request.manifest_id)
    if manifest:
        context["manifest"] = manifest

    # Load understanding for relevant steps
    if request.step in ("understanding", "strategy", "execute", "optimize", "scripts", "hypothesis", "references"):
        understanding = understanding_store.load(request.manifest_id)
        if understanding:
            context["understanding"] = understanding

    # Load script plan for execute / scripts step
    if request.step in ("execute", "scripts"):
        try:
            from aco.api.routes.scripts import _script_plans, load_plan_from_disk
            # Prefer disk to avoid stale per-worker in-memory cache.
            plan = load_plan_from_disk(request.manifest_id) or _script_plans.get(request.manifest_id)
            if plan:
                context["plan"] = plan
        except ImportError:
            pass

    try:
        response_text, artifact_updated, updated_data, change_summary = await handle_chat_message(
            manifest_id=request.manifest_id,
            step=request.step,
            message=request.message,
            client=client,
            **context,
        )
    except Exception as e:
        raise HTTPException(500, f"Chat error: {str(e)}")

    # Persist updated artifacts
    persistence_error: str | None = None
    if artifact_updated and updated_data:
        if request.step == "understanding":
            try:
                from aco.engine.models import ExperimentUnderstanding
                updated_understanding = ExperimentUnderstanding.model_validate(updated_data)
                understanding_store.save(request.manifest_id, updated_understanding)
            except Exception as e:
                logger.error("Failed to persist understanding update: %s", e)
                persistence_error = "Failed to persist understanding update"

        elif request.step in ("execute", "scripts"):
            try:
                from aco.engine.scripts import ScriptPlan
                from aco.api.routes.scripts import (
                    _script_plans,
                    save_plan_to_disk,
                    save_requirements_txt,
                )
                updated_plan = ScriptPlan.model_validate(updated_data)
                updated_plan.manifest_id = request.manifest_id
                _script_plans[request.manifest_id] = updated_plan
                save_plan_to_disk(request.manifest_id, updated_plan)
                save_requirements_txt(request.manifest_id, updated_plan)
            except Exception as e:
                logger.error("Failed to persist script plan update: %s", e)
                persistence_error = "Failed to persist script plan update"

    if persistence_error:
        artifact_updated = False
        updated_data = None
        change_summary = None
        response_text = (
            response_text + "\n\n(Note: I could not save the update. "
            "Please try again.)"
        )

    return ChatMessageResponse(
        response=response_text,
        artifact_updated=artifact_updated,
        updated_data=updated_data,
        change_summary=change_summary,
    )


@router.get("/history/{manifest_id}/{step}", response_model=ChatHistoryResponse)
async def get_history(manifest_id: str, step: str):
    """Get chat history for a manifest and step."""
    if step not in VALID_STEPS:
        raise HTTPException(400, f"Invalid step: {step}")

    store = get_chat_store()
    messages = store.load_messages(manifest_id, step)

    return ChatHistoryResponse(
        manifest_id=manifest_id,
        step=step,
        messages=[msg.model_dump(mode="json") for msg in messages],
    )


@router.delete("/history/{manifest_id}/{step}")
async def clear_history(manifest_id: str, step: str):
    """Clear chat history for a manifest and step."""
    if step not in VALID_STEPS:
        raise HTTPException(400, f"Invalid step: {step}")

    store = get_chat_store()
    store.clear_messages(manifest_id, step)

    return {"message": f"Chat history cleared for {manifest_id}/{step}"}
