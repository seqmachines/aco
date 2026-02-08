"""Analyze phase API routes.

Provides endpoints for hypothesis management, reference selection,
and analysis strategy generation.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aco.engine.models import (
    AnalysisStrategy,
    HypothesisSet,
    PlotSelection,
    UserHypothesis,
)
from aco.engine import UnderstandingStore
from aco.manifest import ManifestStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["analyze"])

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


def _get_working_dir() -> Path:
    return Path(os.getenv("ACO_WORKING_DIR", os.getcwd()))


def _artifact_path(manifest_id: str, phase_dir: str, filename: str) -> Path:
    """Build the path to a run artifact file."""
    return _get_working_dir() / "aco_runs" / manifest_id / phase_dir / filename


# ---------------------------------------------------------------------------
# Hypothesis endpoints
# ---------------------------------------------------------------------------


class SaveHypothesisRequest(BaseModel):
    manifest_id: str
    what_is_wrong: str = ""
    what_to_prove: str = ""
    hypotheses: list[UserHypothesis] = Field(default_factory=list)


class SaveHypothesisResponse(BaseModel):
    manifest_id: str
    hypothesis_set: HypothesisSet
    message: str


@router.post("/hypothesis", response_model=SaveHypothesisResponse)
async def save_hypothesis(request: SaveHypothesisRequest):
    """Save or update the user's hypotheses for a run."""
    hypothesis_set = HypothesisSet(
        manifest_id=request.manifest_id,
        what_is_wrong=request.what_is_wrong,
        what_to_prove=request.what_to_prove,
        hypotheses=request.hypotheses,
        updated_at=datetime.now(),
    )
    path = _artifact_path(
        request.manifest_id, "02_analyze/hypothesis", "hypotheses.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(hypothesis_set.model_dump_json(indent=2))

    return SaveHypothesisResponse(
        manifest_id=request.manifest_id,
        hypothesis_set=hypothesis_set,
        message="Hypotheses saved",
    )


@router.get("/hypothesis/{manifest_id}", response_model=SaveHypothesisResponse)
async def get_hypothesis(manifest_id: str):
    """Load the saved hypotheses for a run."""
    path = _artifact_path(manifest_id, "02_analyze/hypothesis", "hypotheses.json")
    if not path.exists():
        raise HTTPException(404, "No hypotheses saved yet")
    data = json.loads(path.read_text())
    hypothesis_set = HypothesisSet.model_validate(data)
    return SaveHypothesisResponse(
        manifest_id=manifest_id,
        hypothesis_set=hypothesis_set,
        message="Loaded from disk",
    )


# ---------------------------------------------------------------------------
# Reference selection endpoints
# ---------------------------------------------------------------------------


class SelectedReference(BaseModel):
    path: str
    name: str
    ref_type: str = Field(description="script | prior_run | protocol")
    description: str = ""


class SaveReferencesRequest(BaseModel):
    manifest_id: str
    references: list[SelectedReference] = Field(default_factory=list)


class SaveReferencesResponse(BaseModel):
    manifest_id: str
    references: list[SelectedReference]
    message: str


@router.post("/references", response_model=SaveReferencesResponse)
async def save_references(request: SaveReferencesRequest):
    """Save the user's selected references for a run."""
    path = _artifact_path(
        request.manifest_id, "02_analyze/references", "selected.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "manifest_id": request.manifest_id,
        "references": [r.model_dump() for r in request.references],
        "saved_at": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(data, indent=2))
    return SaveReferencesResponse(
        manifest_id=request.manifest_id,
        references=request.references,
        message=f"Saved {len(request.references)} reference(s)",
    )


@router.get("/references/{manifest_id}", response_model=SaveReferencesResponse)
async def get_references(manifest_id: str):
    """Load the saved references for a run."""
    path = _artifact_path(manifest_id, "02_analyze/references", "selected.json")
    if not path.exists():
        raise HTTPException(404, "No references saved yet")
    data = json.loads(path.read_text())
    refs = [SelectedReference.model_validate(r) for r in data.get("references", [])]
    return SaveReferencesResponse(
        manifest_id=manifest_id,
        references=refs,
        message="Loaded from disk",
    )


# ---------------------------------------------------------------------------
# Strategy endpoints (placeholder -- full LLM generation in Increment 4)
# ---------------------------------------------------------------------------


class GenerateStrategyRequest(BaseModel):
    manifest_id: str
    model: str | None = None
    api_key: str | None = None
    user_approach: str | None = None


class StrategyResponse(BaseModel):
    manifest_id: str
    strategy: AnalysisStrategy | None = None
    message: str


@router.post("/strategy", response_model=StrategyResponse)
async def generate_strategy_endpoint(request: GenerateStrategyRequest):
    """Generate an analysis strategy using LLM."""
    from aco.engine.gemini import GeminiClient
    from aco.engine.strategy import generate_strategy as _generate_strategy

    # Load understanding
    if _understanding_store is None:
        raise HTTPException(500, "Understanding store not initialized")
    understanding = _understanding_store.load(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not generated yet")

    # Load hypotheses (optional)
    hyp_path = _artifact_path(
        request.manifest_id, "02_analyze/hypothesis", "hypotheses.json"
    )
    hypothesis_set = None
    if hyp_path.exists():
        from aco.engine.models import HypothesisSet as HypothesisSetModel
        hypothesis_set = HypothesisSetModel.model_validate(
            json.loads(hyp_path.read_text())
        )

    # Load selected references (optional)
    ref_path = _artifact_path(
        request.manifest_id, "02_analyze/references", "selected.json"
    )
    reference_paths: list[str] = []
    if ref_path.exists():
        ref_data = json.loads(ref_path.read_text())
        reference_paths = [r["path"] for r in ref_data.get("references", [])]

    # Create client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model_name = request.model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    try:
        client = GeminiClient(api_key=api_key, model_name=model_name)
        strategy = await _generate_strategy(
            understanding=understanding,
            hypothesis_set=hypothesis_set,
            reference_paths=reference_paths,
            client=client,
            user_approach=request.user_approach,
        )
        strategy.manifest_id = request.manifest_id

        # Save to disk
        save_path = _artifact_path(
            request.manifest_id, "02_analyze/strategy", "strategy.json"
        )
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(strategy.model_dump_json(indent=2))

        return StrategyResponse(
            manifest_id=request.manifest_id,
            strategy=strategy,
            message=f"Strategy generated with {len(strategy.gate_checklist)} gate(s) and {len(strategy.execution_plan)} step(s)",
        )
    except Exception as e:
        logger.error("Failed to generate strategy: %s", e, exc_info=True)
        raise HTTPException(500, f"Failed to generate strategy: {str(e)}")


@router.get("/strategy/{manifest_id}", response_model=StrategyResponse)
async def get_strategy(manifest_id: str):
    """Load the saved strategy for a run."""
    path = _artifact_path(manifest_id, "02_analyze/strategy", "strategy.json")
    if not path.exists():
        raise HTTPException(404, "No strategy generated yet")
    data = json.loads(path.read_text())
    strategy = AnalysisStrategy.model_validate(data)
    return StrategyResponse(
        manifest_id=manifest_id,
        strategy=strategy,
        message="Loaded from disk",
    )


class UpdateStrategyRequest(BaseModel):
    """Request to update a strategy."""
    
    strategy: AnalysisStrategy


@router.put("/strategy/{manifest_id}", response_model=StrategyResponse)
async def update_strategy_endpoint(manifest_id: str, request: UpdateStrategyRequest):
    """Update the analysis strategy."""
    strategy = request.strategy
    strategy.manifest_id = manifest_id
    
    # Save to disk
    save_path = _artifact_path(
        manifest_id, "02_analyze/strategy", "strategy.json"
    )
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(strategy.model_dump_json(indent=2))
    
    return StrategyResponse(
        manifest_id=manifest_id,
        strategy=strategy,
        message="Strategy updated",
    )


# ---------------------------------------------------------------------------
# Plot selection endpoints (Phase 3 but grouped here for convenience)
# ---------------------------------------------------------------------------


class SavePlotSelectionRequest(BaseModel):
    manifest_id: str
    selected_plots: list[str] = Field(default_factory=list)
    custom_plot_requests: str = ""
    selected_tests: list[str] = Field(default_factory=list)


class PlotSelectionResponse(BaseModel):
    manifest_id: str
    selection: PlotSelection
    message: str


@router.post("/plots", response_model=PlotSelectionResponse)
async def save_plot_selection(request: SavePlotSelectionRequest):
    """Save the user's plot and test selections."""
    selection = PlotSelection(
        manifest_id=request.manifest_id,
        selected_plots=request.selected_plots,
        custom_plot_requests=request.custom_plot_requests,
        selected_tests=request.selected_tests,
    )
    path = _artifact_path(
        request.manifest_id, "03_summarize/plots", "plot_selection.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(selection.model_dump_json(indent=2))
    return PlotSelectionResponse(
        manifest_id=request.manifest_id,
        selection=selection,
        message="Plot selection saved",
    )


@router.get("/plots/{manifest_id}", response_model=PlotSelectionResponse)
async def get_plot_selection(manifest_id: str):
    """Load the saved plot selection for a run."""
    path = _artifact_path(manifest_id, "03_summarize/plots", "plot_selection.json")
    if not path.exists():
        raise HTTPException(404, "No plot selection saved yet")
    data = json.loads(path.read_text())
    selection = PlotSelection.model_validate(data)
    return PlotSelectionResponse(
        manifest_id=manifest_id,
        selection=selection,
        message="Loaded from disk",
    )


# ---------------------------------------------------------------------------
# QC module info endpoint
# ---------------------------------------------------------------------------


class ModuleInfoResponse(BaseModel):
    modules: list[dict]
    count: int


@router.get("/modules", response_model=ModuleInfoResponse)
async def list_modules():
    """List all registered deterministic QC modules."""
    from aco.engine.modules import registry

    info = registry.info()
    return ModuleInfoResponse(modules=info, count=len(info))
