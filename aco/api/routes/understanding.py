"""Understanding routes for LLM-driven experiment analysis."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aco.engine import (
    ExperimentUnderstanding,
    UnderstandingStore,
    approve_understanding,
    generate_understanding_async,
)
from aco.manifest import ManifestStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/understanding", tags=["understanding"])

# Script extensions used when auto-discovering reference files
_SCRIPT_EXTENSIONS = {".py", ".R", ".r", ".sh", ".nf", ".wdl"}


class UnderstandingRequest(BaseModel):
    """Request to generate experiment understanding."""
    
    manifest_id: str
    regenerate: bool = False
    model: str | None = None
    api_key: str | None = None
    reference_file_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Optional list of local file paths to upload via the Gemini "
            "Files API so the model can read their contents for richer "
            "experiment understanding."
        ),
    )
    auto_include_detected_scripts: bool = Field(
        default=False,
        description=(
            "When True, automatically include script files (.py, .R, .sh, "
            "etc.) discovered during the file scan as reference files."
        ),
    )


class UnderstandingResponse(BaseModel):
    """Response containing experiment understanding."""
    
    manifest_id: str
    understanding: ExperimentUnderstanding


class ApprovalRequest(BaseModel):
    """Request to approve/edit understanding."""
    
    edits: dict[str, str] | None = None
    feedback: str | None = None


class ApprovalResponse(BaseModel):
    """Response from approval."""
    
    manifest_id: str
    understanding: ExperimentUnderstanding
    message: str


# Store instances (will be set from main app)
_manifest_store: ManifestStore | None = None
_understanding_store: UnderstandingStore | None = None


def set_stores(manifest_store: ManifestStore, understanding_store: UnderstandingStore) -> None:
    """Set the stores for this router."""
    global _manifest_store, _understanding_store
    _manifest_store = manifest_store
    _understanding_store = understanding_store


def get_manifest_store() -> ManifestStore:
    """Get the manifest store."""
    if _manifest_store is None:
        raise HTTPException(status_code=500, detail="Manifest store not initialized")
    return _manifest_store


def get_understanding_store() -> UnderstandingStore:
    """Get the understanding store."""
    if _understanding_store is None:
        raise HTTPException(status_code=500, detail="Understanding store not initialized")
    return _understanding_store


@router.post("", response_model=UnderstandingResponse)
async def generate_understanding_endpoint(
    request: UnderstandingRequest,
) -> UnderstandingResponse:
    """
    Generate experiment understanding from a manifest.
    
    Uses Gemini to analyze the manifest and extract structured
    information about the experiment.
    """
    manifest_store = get_manifest_store()
    understanding_store = get_understanding_store()
    
    # Check if understanding already exists
    if not request.regenerate:
        existing = understanding_store.load(request.manifest_id)
        if existing:
            return UnderstandingResponse(
                manifest_id=request.manifest_id,
                understanding=existing,
            )
    
    # Load the manifest
    manifest = manifest_store.load(request.manifest_id)
    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail=f"Manifest not found: {request.manifest_id}"
        )
    
    try:
        # Determine which client to use
        client = None
        api_key_to_use = request.api_key.strip() if request.api_key and request.api_key.strip() else None
        
        if api_key_to_use or request.model:
            from aco.engine import GeminiClient
            client = GeminiClient(
                api_key=api_key_to_use,
                model_name=request.model or "gemini-3-pro-preview"
            )

        # Collect reference file paths
        ref_paths = list(request.reference_file_paths)

        if request.auto_include_detected_scripts and manifest.scan_result:
            detected = _collect_detected_scripts(manifest)
            logger.info(
                "Auto-including %d detected script(s) as reference files",
                len(detected),
            )
            # Merge, avoiding duplicates
            existing = set(ref_paths)
            for p in detected:
                if p not in existing:
                    ref_paths.append(p)

        # Generate understanding
        understanding = await generate_understanding_async(
            manifest,
            client=client,
            reference_file_paths=ref_paths or None,
        )
        
        # Save it
        understanding_store.save(request.manifest_id, understanding)
        
        return UnderstandingResponse(
            manifest_id=request.manifest_id,
            understanding=understanding,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate understanding: {e}"
        )


@router.get("/{manifest_id}", response_model=UnderstandingResponse)
async def get_understanding(manifest_id: str) -> UnderstandingResponse:
    """Get the understanding for a manifest."""
    understanding_store = get_understanding_store()
    
    understanding = understanding_store.load(manifest_id)
    if understanding is None:
        raise HTTPException(
            status_code=404,
            detail=f"Understanding not found for manifest: {manifest_id}"
        )
    
    return UnderstandingResponse(
        manifest_id=manifest_id,
        understanding=understanding,
    )


@router.put("/{manifest_id}/approve", response_model=ApprovalResponse)
async def approve_understanding_endpoint(
    manifest_id: str,
    request: ApprovalRequest,
) -> ApprovalResponse:
    """
    Approve the experiment understanding, optionally with edits.
    
    This marks the understanding as reviewed and approved by the user.
    """
    understanding_store = get_understanding_store()
    
    understanding = understanding_store.load(manifest_id)
    if understanding is None:
        raise HTTPException(
            status_code=404,
            detail=f"Understanding not found for manifest: {manifest_id}"
        )
    
    # Apply approval (and any edits)
    approved = approve_understanding(understanding, request.edits)
    
    # Save the approved understanding
    understanding_store.save(manifest_id, approved)
    
    return ApprovalResponse(
        manifest_id=manifest_id,
        understanding=approved,
        message="Understanding approved successfully",
    )


@router.delete("/{manifest_id}")
async def delete_understanding(manifest_id: str) -> dict:
    """Delete an understanding."""
    understanding_store = get_understanding_store()
    
    if not understanding_store.delete(manifest_id):
        raise HTTPException(
            status_code=404,
            detail=f"Understanding not found for manifest: {manifest_id}"
        )
    
    return {"message": f"Understanding for {manifest_id} deleted"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_detected_scripts(manifest) -> list[str]:
    """Return paths of script files found in the manifest scan result.

    Only files whose extension is in ``_SCRIPT_EXTENSIONS`` and that
    actually exist on disk are returned.
    """
    if not manifest.scan_result:
        return []

    paths: list[str] = []
    for f in manifest.scan_result.files:
        p = Path(f.path)
        if p.suffix.lower() in _SCRIPT_EXTENSIONS and p.exists():
            paths.append(f.path)

    # Also check inside scanned directories for scripts
    if manifest.user_intake.target_directory:
        data_dir = Path(manifest.user_intake.target_directory)
        if data_dir.exists():
            for ext in _SCRIPT_EXTENSIONS:
                for script_file in data_dir.rglob(f"*{ext}"):
                    sp = str(script_file)
                    if sp not in paths:
                        # Skip __pycache__ and hidden dirs
                        if any(
                            part.startswith(".") or part == "__pycache__"
                            for part in script_file.parts
                        ):
                            continue
                        paths.append(sp)

    return paths
