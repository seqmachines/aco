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


def _summarize_disabled() -> None:
    raise HTTPException(
        status_code=410,
        detail="Summarize phase is temporarily disabled. Notebook generation is unavailable.",
    )


@router.post("/generate", response_model=GenerateNotebookResponse)
async def generate_notebook_endpoint(request: GenerateNotebookRequest):
    """Temporarily disabled while summarize phase is turned off."""
    _summarize_disabled()


@router.get("/{manifest_id}", response_model=GetNotebookResponse)
async def get_notebook_endpoint(manifest_id: str, format: str | None = None):
    """Temporarily disabled while summarize phase is turned off."""
    _summarize_disabled()


@router.get("/list/{manifest_id}", response_model=ListNotebooksResponse)
async def list_notebooks_endpoint(manifest_id: str):
    """Temporarily disabled while summarize phase is turned off."""
    _summarize_disabled()


@router.delete("/{manifest_id}")
async def delete_notebook_endpoint(manifest_id: str):
    """Temporarily disabled while summarize phase is turned off."""
    _summarize_disabled()
