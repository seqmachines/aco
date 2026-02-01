"""Intake routes for submitting experiment descriptions."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from aco.manifest import (
    DocumentReference,
    Manifest,
    ManifestStore,
    build_manifest_async,
)


router = APIRouter(prefix="/intake", tags=["intake"])


class IntakeRequest(BaseModel):
    """Request body for experiment intake."""
    
    experiment_description: str
    target_directory: str
    goals: str | None = None
    known_issues: str | None = None
    additional_notes: str | None = None


class IntakeResponse(BaseModel):
    """Response from intake submission."""
    
    manifest_id: str
    message: str
    manifest: Manifest


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


@router.post("", response_model=IntakeResponse)
async def submit_intake(request: IntakeRequest) -> IntakeResponse:
    """
    Submit experiment intake information.
    
    This creates a new manifest by:
    1. Recording the user's experiment description
    2. Scanning the target directory for sequencing files
    3. Combining everything into a consolidated manifest
    """
    store = get_store()
    
    try:
        manifest = await build_manifest_async(
            experiment_description=request.experiment_description,
            target_directory=request.target_directory,
            goals=request.goals,
            known_issues=request.known_issues,
            additional_notes=request.additional_notes,
            scan_files=True,
        )
        
        # Save the manifest
        store.save(manifest)
        
        return IntakeResponse(
            manifest_id=manifest.id,
            message="Intake submitted successfully",
            manifest=manifest,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process intake: {e}")


@router.post("/with-documents", response_model=IntakeResponse)
async def submit_intake_with_documents(
    experiment_description: str = Form(...),
    target_directory: str = Form(...),
    goals: str | None = Form(None),
    known_issues: str | None = Form(None),
    additional_notes: str | None = Form(None),
    documents: list[UploadFile] = File(default=[]),
) -> IntakeResponse:
    """
    Submit experiment intake with document uploads.
    
    Supports uploading protocol documents, assay specs, etc.
    """
    store = get_store()
    
    # Process uploaded documents
    doc_refs = []
    for doc in documents:
        content = await doc.read()
        
        # Try to extract text from the document
        extracted_text = None
        if doc.content_type and "text" in doc.content_type:
            try:
                extracted_text = content.decode("utf-8")
            except UnicodeDecodeError:
                pass
        
        doc_refs.append(DocumentReference(
            filename=doc.filename or "unknown",
            content_type=doc.content_type,
            size_bytes=len(content),
            extracted_text=extracted_text,
        ))
    
    try:
        manifest = await build_manifest_async(
            experiment_description=experiment_description,
            target_directory=target_directory,
            goals=goals,
            known_issues=known_issues,
            documents=doc_refs,
            additional_notes=additional_notes,
            scan_files=True,
        )
        
        store.save(manifest)
        
        return IntakeResponse(
            manifest_id=manifest.id,
            message="Intake with documents submitted successfully",
            manifest=manifest,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process intake: {e}")
