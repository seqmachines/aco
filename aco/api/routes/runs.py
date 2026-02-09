"""Run management API routes.

Provides endpoints for listing, loading, and comparing analysis runs.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aco.engine.runs import get_run_manager, RunManager
from aco.engine import UnderstandingStore
from aco.manifest import ManifestStore


router = APIRouter(prefix="/runs", tags=["runs"])


class RunInfo(BaseModel):
    """Information about a single run."""
    
    manifest_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    stages_completed: list[str] = Field(default_factory=list)
    has_understanding: bool = False
    has_scripts: bool = False  # maps to "execute" stage
    has_notebook: bool = False
    has_report: bool = False
    has_strategy: bool = False
    experiment_name: str | None = None
    assay_type: str | None = None


class ListRunsResponse(BaseModel):
    """Response listing all runs."""
    
    runs: list[RunInfo]
    total: int


class RunComparisonItem(BaseModel):
    """A single item in a run comparison."""
    
    manifest_id: str
    metric_name: str
    value: Any
    

class RunComparisonResponse(BaseModel):
    """Response with run comparison data."""
    
    runs: list[str]
    metrics: list[dict]


# Store instances
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


def get_storage_dir() -> Path:
    return Path(os.getenv("ACO_STORAGE_DIR", os.path.expanduser("~/.aco")))


def get_runs_root_dir() -> Path:
    """Get the directory where aco_runs should be located."""
    return Path(os.getenv("ACO_WORKING_DIR", os.getcwd()))


@router.get("/list", response_model=ListRunsResponse)
async def list_runs():
    """List all analysis runs."""
    """List all analysis runs."""
    runs_root_dir = get_runs_root_dir()
    runs_dir = get_runs_root_dir() / "aco_runs"
    
    runs = []
    
    if runs_dir.exists():
        for run_path in runs_dir.iterdir():
            if run_path.is_dir():
                manifest_id = run_path.name
                run_manager = get_run_manager(runs_root_dir, manifest_id)
                
                # Check which stages exist (try new three-phase layout first, then legacy)
                stages = []
                stage_dirs = [
                    ("01_understand/scan", "scan"),
                    ("01_understand/understanding", "understanding"),
                    ("02_analyze/hypothesis", "hypothesis"),
                    ("02_analyze/strategy", "strategy"),
                    ("02_analyze/results", "execute"),
                    ("03_summarize/plots", "plots"),
                    ("03_summarize/notebook", "notebook"),
                    ("03_summarize/report", "report"),
                ]
                # Legacy fallbacks
                legacy_dirs = [
                    ("01_scan", "scan"),
                    ("02_manifest", "scan"),
                    ("03_understanding", "understanding"),
                    ("04_scripts", "execute"),
                    ("05_notebook", "notebook"),
                    ("06_report", "report"),
                ]
                
                for stage_dir, stage_name in stage_dirs:
                    if run_manager.stage_path(stage_dir).exists():
                        stages.append(stage_name)
                # Add legacy stages not yet found
                for stage_dir, stage_name in legacy_dirs:
                    if stage_name not in stages and run_manager.stage_path(stage_dir).exists():
                        stages.append(stage_name)
                
                # Get understanding info if available
                understanding_store = get_understanding_store()
                understanding = understanding_store.load(manifest_id)
                
                run_info = RunInfo(
                    manifest_id=manifest_id,
                    stages_completed=stages,
                    has_understanding="understanding" in stages,
                    has_scripts="execute" in stages,
                    has_notebook="notebook" in stages,
                    has_report="report" in stages,
                    has_strategy="strategy" in stages,
                    experiment_name=None,
                    assay_type=understanding.assay_name if understanding else None,
                )
                
                # Get timestamps from run directory
                stat = run_path.stat()
                run_info.created_at = datetime.fromtimestamp(stat.st_ctime)
                run_info.updated_at = datetime.fromtimestamp(stat.st_mtime)
                
                runs.append(run_info)
    
    # Also check manifest store for runs without aco_runs folder
    manifest_store = get_manifest_store()
    for manifest_id in manifest_store.list_all():
        if not any(r.manifest_id == manifest_id for r in runs):
            manifest = manifest_store.load(manifest_id)
            understanding_store = get_understanding_store()
            understanding = understanding_store.load(manifest_id)
            
            run_info = RunInfo(
                manifest_id=manifest_id,
                stages_completed=["manifest"] + (["understanding"] if understanding else []),
                has_understanding=understanding is not None,
                experiment_name=None, # Don't use summary as name, it's too verbose
                assay_type=understanding.assay_name if understanding else None,
            )
            runs.append(run_info)
    
    # Sort by updated_at descending
    runs.sort(key=lambda r: r.updated_at or datetime.min, reverse=True)
    
    return ListRunsResponse(runs=runs, total=len(runs))


@router.get("/{manifest_id}", response_model=RunInfo)
async def get_run(manifest_id: str):
    """Get information about a specific run."""
    runs_root_dir = get_runs_root_dir()
    run_manager = get_run_manager(runs_root_dir, manifest_id)
    
    # Check which stages exist (try new three-phase layout first, then legacy)
    stages = []
    stage_dirs = [
        ("01_understand/scan", "scan"),
        ("01_understand/understanding", "understanding"),
        ("02_analyze/hypothesis", "hypothesis"),
        ("02_analyze/strategy", "strategy"),
        ("02_analyze/results", "execute"),
        ("03_summarize/plots", "plots"),
        ("03_summarize/notebook", "notebook"),
        ("03_summarize/report", "report"),
    ]
    legacy_dirs = [
        ("01_scan", "scan"),
        ("02_manifest", "scan"),
        ("03_understanding", "understanding"),
        ("04_scripts", "execute"),
        ("05_notebook", "notebook"),
        ("06_report", "report"),
    ]
    
    for stage_dir, stage_name in stage_dirs:
        if run_manager.stage_path(stage_dir).exists():
            stages.append(stage_name)
    for stage_dir, stage_name in legacy_dirs:
        if stage_name not in stages and run_manager.stage_path(stage_dir).exists():
            stages.append(stage_name)
    
    # Get understanding info
    understanding_store = get_understanding_store()
    understanding = understanding_store.load(manifest_id)
    
    run_info = RunInfo(
        manifest_id=manifest_id,
        stages_completed=stages,
        has_understanding="understanding" in stages or understanding is not None,
        has_scripts="execute" in stages,
        has_notebook="notebook" in stages,
        has_report="report" in stages,
        has_strategy="strategy" in stages,
        experiment_name=None,
        assay_type=understanding.assay_name if understanding else None,
    )
    
    run_path = runs_root_dir / "aco_runs" / manifest_id
    if run_path.exists():
        stat = run_path.stat()
        run_info.created_at = datetime.fromtimestamp(stat.st_ctime)
        run_info.updated_at = datetime.fromtimestamp(stat.st_mtime)
    
    return run_info


@router.delete("/{manifest_id}")
async def delete_run(manifest_id: str):
    """Delete a run and all its data."""
    import shutil
    
    """Delete a run and all its data."""
    import shutil
    
    runs_root_dir = get_runs_root_dir()
    run_path = runs_root_dir / "aco_runs" / manifest_id
    
    deleted = []
    
    if run_path.exists():
        shutil.rmtree(run_path)
        deleted.append("run_data")
    
    # Also delete from stores
    manifest_store = get_manifest_store()
    understanding_store = get_understanding_store()
    
    if manifest_store.load(manifest_id):
        manifest_store.delete(manifest_id)
        deleted.append("manifest")
    
    if understanding_store.load(manifest_id):
        understanding_store.delete(manifest_id)
        deleted.append("understanding")
    
    if not deleted:
        raise HTTPException(404, "Run not found")
    
    return {"message": f"Deleted: {', '.join(deleted)}"}


@router.post("/compare", response_model=RunComparisonResponse)
async def compare_runs(manifest_ids: list[str]):
    """Compare multiple runs."""
    if len(manifest_ids) < 2:
        raise HTTPException(400, "Need at least 2 runs to compare")
    if len(manifest_ids) > 5:
        raise HTTPException(400, "Can compare at most 5 runs")
    
    understanding_store = get_understanding_store()
    
    metrics = []
    
    # Gather understanding metrics
    for manifest_id in manifest_ids:
        understanding = understanding_store.load(manifest_id)
        if understanding:
            metrics.append({
                "manifest_id": manifest_id,
                "assay_type": understanding.assay_name,
                "species": understanding.key_parameters.get("Species") or understanding.key_parameters.get("Organism") or "Unknown",
                "sample_count": understanding.sample_count,
                "read_count": understanding.read_structure.total_reads if understanding.read_structure else "Unknown",
            })
    
    return RunComparisonResponse(
        runs=manifest_ids,
        metrics=metrics,
    )
