"""Manifest routes for CRUD operations on manifests."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aco.manifest import Manifest, ManifestStore, update_manifest


router = APIRouter(prefix="/manifest", tags=["manifest"])


class ManifestUpdateRequest(BaseModel):
    """Request body for updating a manifest."""
    
    experiment_description: str | None = None
    goals: str | None = None
    known_issues: str | None = None
    additional_notes: str | None = None
    rescan: bool = False


class ManifestResponse(BaseModel):
    """Response containing a manifest."""
    
    manifest: Manifest


class ManifestListResponse(BaseModel):
    """Response containing list of manifest IDs."""
    
    manifest_ids: list[str]
    count: int


# Store instance (will be set from main app)
_store: ManifestStore | None = None


def set_store(store: ManifestStore) -> None:
    """Set the manifest store for this router."""
    global _store
    _store = store


def get_store() -> ManifestStore:
    """Get the manifest store."""
    if _store is None:
        raise HTTPException(status_code=500, detail="Manifest store not initialized")
    return _store


@router.get("", response_model=ManifestListResponse)
async def list_manifests() -> ManifestListResponse:
    """List all manifest IDs."""
    store = get_store()
    manifest_ids = store.list_all()
    
    return ManifestListResponse(
        manifest_ids=manifest_ids,
        count=len(manifest_ids),
    )


@router.get("/latest", response_model=ManifestResponse)
async def get_latest_manifest() -> ManifestResponse:
    """Get the most recently modified manifest."""
    store = get_store()
    manifest = store.get_latest()
    
    if manifest is None:
        raise HTTPException(status_code=404, detail="No manifests found")
    
    return ManifestResponse(manifest=manifest)


@router.get("/{manifest_id}", response_model=ManifestResponse)
async def get_manifest(manifest_id: str) -> ManifestResponse:
    """Get a specific manifest by ID."""
    store = get_store()
    manifest = store.load(manifest_id)
    
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Manifest not found: {manifest_id}")
    
    return ManifestResponse(manifest=manifest)


@router.put("/{manifest_id}", response_model=ManifestResponse)
async def update_manifest_endpoint(
    manifest_id: str,
    request: ManifestUpdateRequest,
) -> ManifestResponse:
    """Update an existing manifest."""
    store = get_store()
    manifest = store.load(manifest_id)
    
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Manifest not found: {manifest_id}")
    
    try:
        updated = update_manifest(
            manifest=manifest,
            experiment_description=request.experiment_description,
            goals=request.goals,
            known_issues=request.known_issues,
            additional_notes=request.additional_notes,
            rescan=request.rescan,
        )
        
        store.save(updated)
        
        return ManifestResponse(manifest=updated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update manifest: {e}")


@router.delete("/{manifest_id}")
async def delete_manifest(manifest_id: str) -> dict:
    """Delete a manifest."""
    store = get_store()
    
    if not store.delete(manifest_id):
        raise HTTPException(status_code=404, detail=f"Manifest not found: {manifest_id}")
    
    return {"message": f"Manifest {manifest_id} deleted"}


@router.get("/{manifest_id}/llm-context")
async def get_manifest_llm_context(manifest_id: str) -> dict:
    """Get the LLM-friendly text representation of a manifest."""
    store = get_store()
    manifest = store.load(manifest_id)
    
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Manifest not found: {manifest_id}")
    
    return {
        "manifest_id": manifest_id,
        "llm_context": manifest.to_llm_context(),
    }
