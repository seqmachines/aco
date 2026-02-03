"""Understanding routes for LLM-driven experiment analysis."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aco.engine import (
    ExperimentUnderstanding,
    UnderstandingStore,
    approve_understanding,
    generate_understanding_async,
)
from aco.manifest import ManifestStore


router = APIRouter(prefix="/understanding", tags=["understanding"])


class UnderstandingRequest(BaseModel):
    """Request to generate experiment understanding."""
    
    manifest_id: str
    regenerate: bool = False
    model: str | None = None
    api_key: str | None = None


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
            
        # Generate understanding
        understanding = await generate_understanding_async(manifest, client=client)
        
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
