"""Report generation and management routes."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from aco.engine.gemini import GeminiClient
from aco.engine.report import (
    GeneratedReport,
    ReportFormat,
    generate_report,
    report_to_html,
    save_report,
)
from aco.engine.scripts import ExecutionResult
from aco.engine.notebook import GeneratedNotebook
from aco.engine.runs import get_run_manager
from aco.engine import UnderstandingStore
from aco.manifest import ManifestStore


router = APIRouter(prefix="/reports", tags=["reports"])


class GenerateReportRequest(BaseModel):
    """Request to generate a report."""
    
    manifest_id: str
    format: str = Field(default="html", description="html or pdf")
    model: str | None = None
    api_key: str | None = None


class GenerateReportResponse(BaseModel):
    """Response with generated report."""
    
    manifest_id: str
    report: GeneratedReport
    saved_path: str
    message: str


class GetReportResponse(BaseModel):
    """Response with report data."""
    
    manifest_id: str
    report: GeneratedReport | None
    html_content: str | None = None


# Store instances
_manifest_store: ManifestStore | None = None
_understanding_store: UnderstandingStore | None = None
_generated_reports: dict[str, GeneratedReport] = {}  # In-memory cache
_script_results: dict[str, list[ExecutionResult]] = {}  # Cache script results
_notebooks: dict[str, GeneratedNotebook] = {}  # Cache notebooks


def set_stores(manifest_store: ManifestStore, understanding_store: UnderstandingStore):
    """Set the store instances for this router."""
    global _manifest_store, _understanding_store
    _manifest_store = manifest_store
    _understanding_store = understanding_store


def cache_script_results(manifest_id: str, results: list[ExecutionResult]):
    """Cache script results for report generation."""
    _script_results[manifest_id] = results


def cache_notebook(manifest_id: str, notebook: GeneratedNotebook):
    """Cache notebook for report generation."""
    _notebooks[manifest_id] = notebook


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
        detail="Summarize phase is temporarily disabled. Report generation is unavailable.",
    )


@router.post("/generate", response_model=GenerateReportResponse)
async def generate_report_endpoint(request: GenerateReportRequest):
    """Temporarily disabled while summarize phase is turned off."""
    _summarize_disabled()


@router.get("/{manifest_id}", response_model=GetReportResponse)
async def get_report_endpoint(manifest_id: str):
    """Temporarily disabled while summarize phase is turned off."""
    _summarize_disabled()


@router.get("/{manifest_id}/html", response_class=HTMLResponse)
async def get_report_html_endpoint(manifest_id: str):
    """Temporarily disabled while summarize phase is turned off."""
    _summarize_disabled()


@router.delete("/{manifest_id}")
async def delete_report_endpoint(manifest_id: str):
    """Temporarily disabled while summarize phase is turned off."""
    _summarize_disabled()
