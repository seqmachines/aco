"""Script generation and execution routes."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aco.engine.gemini import GeminiClient
from aco.engine.scripts import (
    GeneratedScript,
    ScriptCategory,
    ScriptPlan,
    ScriptType,
    generate_script_code,
    generate_script_plan,
)
from aco.engine.executor import (
    ExecutionConfig,
    ExecutionResult,
    ScriptExecutor,
    check_dependencies,
)
from aco.engine.runs import get_run_manager
from aco.engine import UnderstandingStore
from aco.manifest import ManifestStore


router = APIRouter(prefix="/scripts", tags=["scripts"])


class GeneratePlanRequest(BaseModel):
    """Request to generate a script plan."""
    
    manifest_id: str
    model: str | None = None
    api_key: str | None = None


class GeneratePlanResponse(BaseModel):
    """Response with generated script plan."""
    
    manifest_id: str
    plan: ScriptPlan
    message: str


class GenerateCodeRequest(BaseModel):
    """Request to generate code for a specific script."""
    
    manifest_id: str
    script_index: int
    model: str | None = None
    api_key: str | None = None


class GenerateCodeResponse(BaseModel):
    """Response with generated script code."""
    
    manifest_id: str
    script_name: str
    code: str
    saved_path: str


class ExecuteScriptRequest(BaseModel):
    """Request to execute a script."""
    
    manifest_id: str
    script_name: str
    timeout_seconds: int = 300


class ExecuteScriptResponse(BaseModel):
    """Response with execution result."""
    
    manifest_id: str
    result: ExecutionResult


class ExecuteAllRequest(BaseModel):
    """Request to execute all scripts in order."""
    
    manifest_id: str
    timeout_seconds: int = 300


class ExecuteAllResponse(BaseModel):
    """Response with all execution results."""
    
    manifest_id: str
    results: list[ExecutionResult]
    all_succeeded: bool


class DependencyCheckResponse(BaseModel):
    """Response with dependency check results."""
    
    manifest_id: str
    dependencies: dict[str, bool]
    all_available: bool


# Store instances
_manifest_store: ManifestStore | None = None
_understanding_store: UnderstandingStore | None = None
_script_plans: dict[str, ScriptPlan] = {}  # In-memory cache


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


@router.post("/plan", response_model=GeneratePlanResponse)
async def generate_plan_endpoint(request: GeneratePlanRequest):
    """Generate a script plan based on experiment understanding."""
    manifest_store = get_manifest_store()
    understanding_store = get_understanding_store()
    
    # Get manifest
    manifest = manifest_store.get(request.manifest_id)
    if not manifest:
        raise HTTPException(404, f"Manifest {request.manifest_id} not found")
    
    # Get understanding
    understanding = understanding_store.get(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not generated yet")
    
    # Get file list from manifest
    file_list = []
    if manifest.scan_result:
        file_list = [f.path for f in manifest.scan_result.files]
    
    # Create Gemini client with optional overrides
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or "gemini-2.5-flash"
    
    try:
        client = GeminiClient(api_key=api_key, model_name=model)
        plan = await generate_script_plan(understanding, file_list, client)
        plan.manifest_id = request.manifest_id
        
        # Cache the plan
        _script_plans[request.manifest_id] = plan
        
        return GeneratePlanResponse(
            manifest_id=request.manifest_id,
            plan=plan,
            message=f"Generated plan with {len(plan.scripts)} scripts",
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate plan: {str(e)}")


@router.get("/plan/{manifest_id}", response_model=GeneratePlanResponse)
async def get_plan_endpoint(manifest_id: str):
    """Get the current script plan for a manifest."""
    if manifest_id not in _script_plans:
        raise HTTPException(404, "No script plan found. Generate one first.")
    
    plan = _script_plans[manifest_id]
    return GeneratePlanResponse(
        manifest_id=manifest_id,
        plan=plan,
        message="Retrieved existing plan",
    )


@router.post("/generate-code", response_model=GenerateCodeResponse)
async def generate_code_endpoint(request: GenerateCodeRequest):
    """Generate code for a specific script in the plan."""
    if request.manifest_id not in _script_plans:
        raise HTTPException(404, "No script plan found. Generate one first.")
    
    plan = _script_plans[request.manifest_id]
    
    if request.script_index < 0 or request.script_index >= len(plan.scripts):
        raise HTTPException(400, f"Invalid script index: {request.script_index}")
    
    script = plan.scripts[request.script_index]
    
    # Get understanding for context
    understanding_store = get_understanding_store()
    understanding = understanding_store.get(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not found")
    
    # Get output directory from run manager
    storage_dir = os.getenv("ACO_STORAGE_DIR", os.path.expanduser("~/.aco"))
    run_manager = get_run_manager(Path(storage_dir), request.manifest_id)
    output_dir = run_manager.stage_path(f"02_{script.category.value}")
    
    # Create Gemini client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or "gemini-2.5-flash"
    
    try:
        client = GeminiClient(api_key=api_key, model_name=model)
        code = await generate_script_code(script, understanding, str(output_dir), client)
        
        # Update script with generated code
        script.code = code
        
        # Save to disk
        executor = ScriptExecutor()
        scripts_dir = run_manager.stage_path(script.category.value)
        script_path = executor.save_script(script, scripts_dir)
        
        return GenerateCodeResponse(
            manifest_id=request.manifest_id,
            script_name=script.name,
            code=code,
            saved_path=str(script_path),
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate code: {str(e)}")


@router.post("/execute", response_model=ExecuteScriptResponse)
async def execute_script_endpoint(request: ExecuteScriptRequest):
    """Execute a specific script."""
    if request.manifest_id not in _script_plans:
        raise HTTPException(404, "No script plan found. Generate one first.")
    
    plan = _script_plans[request.manifest_id]
    
    # Find the script
    script = next((s for s in plan.scripts if s.name == request.script_name), None)
    if not script:
        raise HTTPException(404, f"Script {request.script_name} not found in plan")
    
    if not script.code:
        raise HTTPException(400, "Script code not generated yet")
    
    # Get paths
    storage_dir = os.getenv("ACO_STORAGE_DIR", os.path.expanduser("~/.aco"))
    run_manager = get_run_manager(Path(storage_dir), request.manifest_id)
    scripts_dir = run_manager.stage_path(script.category.value)
    output_dir = run_manager.stage_path(f"04_qc_results")
    
    # Execute
    config = ExecutionConfig(timeout_seconds=request.timeout_seconds)
    executor = ScriptExecutor(config)
    
    from aco.engine.scripts import get_script_extension
    ext = get_script_extension(script.script_type)
    script_path = scripts_dir / f"{script.name}{ext}"
    
    if not script_path.exists():
        raise HTTPException(400, "Script file not found. Generate code first.")
    
    result = await executor.execute_script(script, script_path, output_dir)
    
    # Save result
    run_manager.save_artifact(
        "04_qc_results",
        f"{script.name}_result.json",
        result,
    )
    
    return ExecuteScriptResponse(
        manifest_id=request.manifest_id,
        result=result,
    )


@router.post("/execute-all", response_model=ExecuteAllResponse)
async def execute_all_endpoint(request: ExecuteAllRequest):
    """Execute all scripts in the plan."""
    if request.manifest_id not in _script_plans:
        raise HTTPException(404, "No script plan found. Generate one first.")
    
    plan = _script_plans[request.manifest_id]
    
    # Filter scripts that have code
    scripts_to_run = [s for s in plan.scripts if s.code]
    if not scripts_to_run:
        raise HTTPException(400, "No scripts have generated code yet")
    
    # Get paths
    storage_dir = os.getenv("ACO_STORAGE_DIR", os.path.expanduser("~/.aco"))
    run_manager = get_run_manager(Path(storage_dir), request.manifest_id)
    
    # Execute each script
    config = ExecutionConfig(timeout_seconds=request.timeout_seconds)
    executor = ScriptExecutor(config)
    
    results = []
    for script in scripts_to_run:
        scripts_dir = run_manager.stage_path(script.category.value)
        output_dir = run_manager.stage_path("04_qc_results")
        
        from aco.engine.scripts import get_script_extension
        ext = get_script_extension(script.script_type)
        script_path = scripts_dir / f"{script.name}{ext}"
        
        if script_path.exists():
            result = await executor.execute_script(script, script_path, output_dir)
            results.append(result)
            
            # Save result
            run_manager.save_artifact(
                "04_qc_results",
                f"{script.name}_result.json",
                result,
            )
    
    all_succeeded = all(r.success for r in results)
    
    return ExecuteAllResponse(
        manifest_id=request.manifest_id,
        results=results,
        all_succeeded=all_succeeded,
    )


@router.get("/check-dependencies/{manifest_id}", response_model=DependencyCheckResponse)
async def check_dependencies_endpoint(manifest_id: str):
    """Check if all required dependencies are available."""
    if manifest_id not in _script_plans:
        raise HTTPException(404, "No script plan found. Generate one first.")
    
    plan = _script_plans[manifest_id]
    
    # Collect all dependencies
    all_deps = set()
    for script in plan.scripts:
        all_deps.update(script.dependencies)
    
    # Check availability
    deps_status = check_dependencies(list(all_deps))
    
    return DependencyCheckResponse(
        manifest_id=manifest_id,
        dependencies=deps_status,
        all_available=all(deps_status.values()),
    )
