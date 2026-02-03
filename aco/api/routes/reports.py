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


@router.post("/generate", response_model=GenerateReportResponse)
async def generate_report_endpoint(request: GenerateReportRequest):
    """Generate a QC report based on all analysis results."""
    understanding_store = get_understanding_store()
    
    # Get understanding
    understanding = understanding_store.get(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not generated yet")
    
    # Parse format
    try:
        report_format = ReportFormat(request.format.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid format: {request.format}. Use 'html' or 'pdf'")
    
    # Get cached data
    script_results = _script_results.get(request.manifest_id, [])
    notebook = _notebooks.get(request.manifest_id)
    
    # Get output directory
    storage_dir = os.getenv("ACO_STORAGE_DIR", os.path.expanduser("~/.aco"))
    run_manager = get_run_manager(Path(storage_dir), request.manifest_id)
    output_dir = run_manager.stage_path("06_report")
    
    # Create Gemini client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or "gemini-2.5-flash"
    
    try:
        client = GeminiClient(api_key=api_key, model_name=model)
        report = await generate_report(
            understanding=understanding,
            script_results=script_results,
            notebook=notebook,
            client=client,
        )
        
        # Save report
        saved_path = save_report(report, output_dir, report_format)
        
        # Cache report
        _generated_reports[request.manifest_id] = report
        
        return GenerateReportResponse(
            manifest_id=request.manifest_id,
            report=report,
            saved_path=str(saved_path),
            message=f"Generated report with {len(report.insights)} insights and {len(report.hypotheses)} hypotheses",
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate report: {str(e)}")


@router.get("/{manifest_id}", response_model=GetReportResponse)
async def get_report_endpoint(manifest_id: str):
    """Get the generated report for a manifest."""
    report = _generated_reports.get(manifest_id)
    
    if not report:
        return GetReportResponse(
            manifest_id=manifest_id,
            report=None,
            html_content=None,
        )
    
    html_content = report_to_html(report)
    
    return GetReportResponse(
        manifest_id=manifest_id,
        report=report,
        html_content=html_content,
    )


@router.get("/{manifest_id}/html", response_class=HTMLResponse)
async def get_report_html_endpoint(manifest_id: str):
    """Get the report as raw HTML (for iframe display)."""
    report = _generated_reports.get(manifest_id)
    
    if not report:
        # Try to load from disk
        storage_dir = os.getenv("ACO_STORAGE_DIR", os.path.expanduser("~/.aco"))
        run_manager = get_run_manager(Path(storage_dir), manifest_id)
        report_path = run_manager.stage_path("06_report") / "qc_report.html"
        
        if report_path.exists():
            return HTMLResponse(content=report_path.read_text())
        
        return HTMLResponse(
            content="<html><body><p>No report generated yet.</p></body></html>",
            status_code=404,
        )
    
    html_content = report_to_html(report)
    return HTMLResponse(content=html_content)


@router.delete("/{manifest_id}")
async def delete_report_endpoint(manifest_id: str):
    """Delete the cached report for a manifest."""
    if manifest_id in _generated_reports:
        del _generated_reports[manifest_id]
        return {"message": "Report cache cleared"}
    return {"message": "No cached report found"}
