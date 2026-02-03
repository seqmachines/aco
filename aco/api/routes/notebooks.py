"""Notebook generation and management routes."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aco.engine.gemini import GeminiClient
from aco.engine.notebook import (
    GeneratedNotebook,
    NotebookLanguage,
    generate_notebook,
    save_notebook,
    notebook_to_jupyter,
    notebook_to_rmarkdown,
)
from aco.engine.scripts import ExecutionResult
from aco.engine.runs import get_run_manager
from aco.engine import UnderstandingStore
from aco.manifest import ManifestStore


router = APIRouter(prefix="/notebooks", tags=["notebooks"])


class GenerateNotebookRequest(BaseModel):
    """Request to generate a notebook."""
    
    manifest_id: str
    language: str = Field(default="python", description="python or r")
    model: str | None = None
    api_key: str | None = None


class GenerateNotebookResponse(BaseModel):
    """Response with generated notebook."""
    
    manifest_id: str
    notebook: GeneratedNotebook
    saved_path: str
    message: str


class GetNotebookResponse(BaseModel):
    """Response with notebook content."""
    
    manifest_id: str
    notebook: GeneratedNotebook | None
    content: str | None = None
    format: str | None = None


class ListNotebooksResponse(BaseModel):
    """Response listing available notebooks."""
    
    manifest_id: str
    notebooks: list[dict]


# Store instances
_manifest_store: ManifestStore | None = None
_understanding_store: UnderstandingStore | None = None
_generated_notebooks: dict[str, GeneratedNotebook] = {}  # In-memory cache
_script_results: dict[str, list[ExecutionResult]] = {}  # Cache script results


def set_stores(manifest_store: ManifestStore, understanding_store: UnderstandingStore):
    """Set the store instances for this router."""
    global _manifest_store, _understanding_store
    _manifest_store = manifest_store
    _understanding_store = understanding_store


def cache_script_results(manifest_id: str, results: list[ExecutionResult]):
    """Cache script results for notebook generation."""
    _script_results[manifest_id] = results


def get_manifest_store() -> ManifestStore:
    if _manifest_store is None:
        raise HTTPException(500, "Manifest store not initialized")
    return _manifest_store


def get_understanding_store() -> UnderstandingStore:
    if _understanding_store is None:
        raise HTTPException(500, "Understanding store not initialized")
    return _understanding_store


@router.post("/generate", response_model=GenerateNotebookResponse)
async def generate_notebook_endpoint(request: GenerateNotebookRequest):
    """Generate a notebook based on experiment understanding and QC results."""
    understanding_store = get_understanding_store()
    
    # Get understanding
    understanding = understanding_store.get(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not generated yet")
    
    # Parse language
    try:
        language = NotebookLanguage(request.language.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid language: {request.language}. Use 'python' or 'r'")
    
    # Get script results if available
    script_results = _script_results.get(request.manifest_id, [])
    
    # Get output directory
    storage_dir = os.getenv("ACO_STORAGE_DIR", os.path.expanduser("~/.aco"))
    run_manager = get_run_manager(Path(storage_dir), request.manifest_id)
    output_dir = run_manager.stage_path("05_notebook")
    
    # Create Gemini client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or "gemini-2.5-flash"
    
    try:
        client = GeminiClient(api_key=api_key, model_name=model)
        notebook = await generate_notebook(
            understanding=understanding,
            script_results=script_results,
            language=language,
            output_dir=output_dir,
            client=client,
        )
        
        # Save notebook
        saved_path = save_notebook(notebook, output_dir)
        
        # Cache notebook
        _generated_notebooks[request.manifest_id] = notebook
        
        return GenerateNotebookResponse(
            manifest_id=request.manifest_id,
            notebook=notebook,
            saved_path=str(saved_path),
            message=f"Generated {language.value} notebook with {len(notebook.cells)} cells",
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate notebook: {str(e)}")


@router.get("/{manifest_id}", response_model=GetNotebookResponse)
async def get_notebook_endpoint(manifest_id: str, format: str | None = None):
    """Get the generated notebook for a manifest."""
    notebook = _generated_notebooks.get(manifest_id)
    
    if not notebook:
        return GetNotebookResponse(
            manifest_id=manifest_id,
            notebook=None,
            content=None,
            format=None,
        )
    
    # Convert to requested format
    content = None
    output_format = None
    if format == "jupyter" or (format is None and notebook.language == NotebookLanguage.PYTHON):
        import json
        content = json.dumps(notebook_to_jupyter(notebook), indent=2)
        output_format = "jupyter"
    elif format == "rmarkdown" or (format is None and notebook.language == NotebookLanguage.R):
        content = notebook_to_rmarkdown(notebook)
        output_format = "rmarkdown"
    
    return GetNotebookResponse(
        manifest_id=manifest_id,
        notebook=notebook,
        content=content,
        format=output_format,
    )


@router.get("/list/{manifest_id}", response_model=ListNotebooksResponse)
async def list_notebooks_endpoint(manifest_id: str):
    """List all notebooks for a manifest."""
    storage_dir = os.getenv("ACO_STORAGE_DIR", os.path.expanduser("~/.aco"))
    run_manager = get_run_manager(Path(storage_dir), manifest_id)
    notebook_dir = run_manager.stage_path("05_notebook")
    
    notebooks = []
    if notebook_dir.exists():
        for f in notebook_dir.iterdir():
            if f.suffix in [".ipynb", ".Rmd"]:
                notebooks.append({
                    "name": f.stem,
                    "path": str(f),
                    "format": "jupyter" if f.suffix == ".ipynb" else "rmarkdown",
                    "size_bytes": f.stat().st_size,
                })
    
    return ListNotebooksResponse(
        manifest_id=manifest_id,
        notebooks=notebooks,
    )


@router.delete("/{manifest_id}")
async def delete_notebook_endpoint(manifest_id: str):
    """Delete the cached notebook for a manifest."""
    if manifest_id in _generated_notebooks:
        del _generated_notebooks[manifest_id]
        return {"message": "Notebook cache cleared"}
    return {"message": "No cached notebook found"}
