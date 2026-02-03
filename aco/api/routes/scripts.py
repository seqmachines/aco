"""Script generation and execution routes."""

import json
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
from aco.engine.environment import (
    create_venv,
    install_dependencies,
    get_environment_status,
    get_script_interpreter,
)
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


class CreateEnvRequest(BaseModel):
    """Request to create an execution environment."""
    
    manifest_id: str


class CreateEnvResponse(BaseModel):
    """Response with environment creation result."""
    
    manifest_id: str
    success: bool
    venv_path: str | None
    message: str


class InstallDepsRequest(BaseModel):
    """Request to install dependencies."""
    
    manifest_id: str
    additional_packages: list[str] = Field(default_factory=list)


class InstallDepsResponse(BaseModel):
    """Response with installation result."""
    
    manifest_id: str
    success: bool
    installed: list[str]
    output: str
    error: str | None = None


class EnvStatusResponse(BaseModel):
    """Response with environment status."""
    
    manifest_id: str
    exists: bool
    venv_path: str | None
    python_executable: str | None
    installed_packages: list[str]


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


def get_scripts_dir(manifest_id: str) -> Path:
    """Get the scripts directory for a manifest."""
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    scripts_dir = Path(working_dir) / "aco_runs" / manifest_id / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    return scripts_dir


def save_plan_to_disk(manifest_id: str, plan: ScriptPlan) -> Path:
    """Save script plan to disk."""
    scripts_dir = get_scripts_dir(manifest_id)
    plan_path = scripts_dir / "plan.json"
    with open(plan_path, "w") as f:
        f.write(plan.model_dump_json(indent=2))
    return plan_path


def load_plan_from_disk(manifest_id: str) -> ScriptPlan | None:
    """Load script plan from disk if it exists."""
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    plan_path = Path(working_dir) / "aco_runs" / manifest_id / "scripts" / "plan.json"
    if plan_path.exists():
        with open(plan_path) as f:
            data = json.load(f)
        return ScriptPlan.model_validate(data)
    return None


def save_script_to_disk(manifest_id: str, script: GeneratedScript) -> Path:
    """Save a generated script to disk."""
    scripts_dir = get_scripts_dir(manifest_id)
    # Determine extension based on script type
    ext = {
        ScriptType.PYTHON: ".py",
        ScriptType.R: ".R",
        ScriptType.BASH: ".sh",
    }.get(script.script_type, ".py")
    
    # Remove existing extension from script name if present
    script_name = script.name
    for existing_ext in [".py", ".R", ".sh", ".r"]:
        if script_name.endswith(existing_ext):
            script_name = script_name[:-len(existing_ext)]
            break
    
    script_path = scripts_dir / f"{script_name}{ext}"
    with open(script_path, "w") as f:
        f.write(script.code or "")
    return script_path


def save_requirements_txt(manifest_id: str, plan: ScriptPlan) -> Path:
    """Generate and save requirements.txt from all script dependencies."""
    scripts_dir = get_scripts_dir(manifest_id)
    all_deps = set()
    for script in plan.scripts:
        if script.script_type == ScriptType.PYTHON:
            for dep in script.dependencies:
                # Skip standard library modules
                if dep.lower() not in ["os", "sys", "json", "re", "logging", "pathlib", "collections", "gzip"]:
                    all_deps.add(dep.lower())
    
    req_path = scripts_dir / "requirements.txt"
    with open(req_path, "w") as f:
        for dep in sorted(all_deps):
            f.write(f"{dep}\n")
    return req_path


@router.post("/plan", response_model=GeneratePlanResponse)
async def generate_plan_endpoint(request: GeneratePlanRequest):
    """Generate a script plan based on experiment understanding."""
    manifest_store = get_manifest_store()
    understanding_store = get_understanding_store()
    
    # Get manifest
    manifest = manifest_store.load(request.manifest_id)
    if not manifest:
        raise HTTPException(404, f"Manifest {request.manifest_id} not found")
    
    # Get understanding
    understanding = understanding_store.load(request.manifest_id)
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
        
        # Cache the plan in memory
        _script_plans[request.manifest_id] = plan
        
        # Save plan to disk
        plan_path = save_plan_to_disk(request.manifest_id, plan)
        
        # Generate requirements.txt
        save_requirements_txt(request.manifest_id, plan)
        
        return GeneratePlanResponse(
            manifest_id=request.manifest_id,
            plan=plan,
            message=f"Generated plan with {len(plan.scripts)} scripts. Saved to {plan_path}",
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate plan: {str(e)}")


@router.get("/plan/{manifest_id}", response_model=GeneratePlanResponse)
async def get_plan_endpoint(manifest_id: str):
    """Get the current script plan for a manifest."""
    # Try memory cache first
    if manifest_id in _script_plans:
        plan = _script_plans[manifest_id]
        return GeneratePlanResponse(
            manifest_id=manifest_id,
            plan=plan,
            message="Retrieved from cache",
        )
    
    # Try loading from disk
    plan = load_plan_from_disk(manifest_id)
    if plan:
        # Cache it for future requests
        _script_plans[manifest_id] = plan
        return GeneratePlanResponse(
            manifest_id=manifest_id,
            plan=plan,
            message="Loaded from disk",
        )
    
    raise HTTPException(404, "No script plan found. Generate one first.")


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
    understanding = understanding_store.load(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not found")
    
    # Get output directory from run manager
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    run_manager = get_run_manager(Path(working_dir), request.manifest_id)
    output_dir = run_manager.stage_path(f"02_{script.category.value}")
    
    # Create Gemini client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or "gemini-2.5-flash"
    
    try:
        client = GeminiClient(api_key=api_key, model_name=model)
        code = await generate_script_code(script, understanding, str(output_dir), client)
        
        # Update script with generated code
        script.code = code
        
        # Save script to scripts folder
        script_path = save_script_to_disk(request.manifest_id, script)
        
        # Update plan on disk with new code
        save_plan_to_disk(request.manifest_id, plan)
        
        return GenerateCodeResponse(
            manifest_id=request.manifest_id,
            script_name=script.name,
            code=code,
            saved_path=str(script_path),
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate code: {str(e)}")


class GenerateAllCodeRequest(BaseModel):
    """Request to generate code for all scripts."""
    
    manifest_id: str
    model: str | None = None
    api_key: str | None = None


class GenerateAllCodeResponse(BaseModel):
    """Response with all generated code."""
    
    manifest_id: str
    generated: list[str]
    failed: list[str]
    scripts_dir: str


@router.post("/generate-all-code", response_model=GenerateAllCodeResponse)
async def generate_all_code_endpoint(request: GenerateAllCodeRequest):
    """Generate code for all scripts in the plan."""
    if request.manifest_id not in _script_plans:
        # Try loading from disk
        plan = load_plan_from_disk(request.manifest_id)
        if plan:
            _script_plans[request.manifest_id] = plan
        else:
            raise HTTPException(404, "No script plan found. Generate one first.")
    
    plan = _script_plans[request.manifest_id]
    
    # Get understanding for context
    understanding_store = get_understanding_store()
    understanding = understanding_store.load(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not found")
    
    # Get output directory
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    run_manager = get_run_manager(Path(working_dir), request.manifest_id)
    
    # Create Gemini client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or "gemini-2.5-flash"
    client = GeminiClient(api_key=api_key, model_name=model)
    
    generated = []
    failed = []
    
    for i, script in enumerate(plan.scripts):
        try:
            output_dir = run_manager.stage_path(f"02_{script.category.value}")
            code = await generate_script_code(script, understanding, str(output_dir), client)
            
            # Update script with generated code
            script.code = code
            
            # Save script to scripts folder
            save_script_to_disk(request.manifest_id, script)
            
            generated.append(script.name)
        except Exception as e:
            failed.append(f"{script.name}: {str(e)}")
    
    # Update plan on disk with all generated code
    save_plan_to_disk(request.manifest_id, plan)
    
    scripts_dir = get_scripts_dir(request.manifest_id)
    
    return GenerateAllCodeResponse(
        manifest_id=request.manifest_id,
        generated=generated,
        failed=failed,
        scripts_dir=str(scripts_dir),
    )


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
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    run_manager = get_run_manager(Path(working_dir), request.manifest_id)
    scripts_dir = get_scripts_dir(request.manifest_id)  # Use scripts/ folder
    output_dir = run_manager.stage_path(f"04_qc_results")
    
    # Execute
    config = ExecutionConfig(timeout_seconds=request.timeout_seconds)
    executor = ScriptExecutor(config)
    
    from aco.engine.scripts import get_script_extension
    ext = get_script_extension(script.script_type)
    
    # Handle script name (remove existing extension if present)
    script_name = script.name
    for existing_ext in [".py", ".R", ".sh", ".r"]:
        if script_name.endswith(existing_ext):
            script_name = script_name[:-len(existing_ext)]
            break
    
    script_path = scripts_dir / f"{script_name}{ext}"
    
    if not script_path.exists():
        raise HTTPException(400, f"Script file not found at {script_path}. Generate code first.")
    
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
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    run_manager = get_run_manager(Path(working_dir), request.manifest_id)
    scripts_dir = get_scripts_dir(request.manifest_id)  # Use scripts/ folder
    
    # Execute each script
    config = ExecutionConfig(timeout_seconds=request.timeout_seconds)
    executor = ScriptExecutor(config)
    
    results = []
    from aco.engine.scripts import get_script_extension
    
    for script in scripts_to_run:
        output_dir = run_manager.stage_path("04_qc_results")
        
        ext = get_script_extension(script.script_type)
        
        # Handle script name (remove existing extension if present)
        script_name = script.name
        for existing_ext in [".py", ".R", ".sh", ".r"]:
            if script_name.endswith(existing_ext):
                script_name = script_name[:-len(existing_ext)]
                break
        
        script_path = scripts_dir / f"{script_name}{ext}"
        
        if script_path.exists():
            result = await executor.execute_script(script, script_path, output_dir)
            results.append(result)
            
            # Save result
            run_manager.save_artifact(
                "04_qc_results",
                f"{script_name}_result.json",
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


@router.post("/create-env", response_model=CreateEnvResponse)
async def create_env_endpoint(request: CreateEnvRequest):
    """Create a virtual environment for script execution."""
    success, message = create_venv(request.manifest_id)
    
    status = get_environment_status(request.manifest_id)
    
    return CreateEnvResponse(
        manifest_id=request.manifest_id,
        success=success,
        venv_path=status.venv_path,
        message=message,
    )


@router.post("/install-deps", response_model=InstallDepsResponse)
async def install_deps_endpoint(request: InstallDepsRequest):
    """Install dependencies into the virtual environment."""
    # Get requirements.txt path
    scripts_dir = get_scripts_dir(request.manifest_id)
    requirements_path = scripts_dir / "requirements.txt"
    
    result = install_dependencies(
        request.manifest_id,
        requirements_file=requirements_path if requirements_path.exists() else None,
        packages=request.additional_packages if request.additional_packages else None,
    )
    
    return InstallDepsResponse(
        manifest_id=request.manifest_id,
        success=result.success,
        installed=result.installed,
        output=result.output,
        error=result.error,
    )


@router.get("/env-status/{manifest_id}", response_model=EnvStatusResponse)
async def env_status_endpoint(manifest_id: str):
    """Get the status of the execution environment."""
    status = get_environment_status(manifest_id)
    
    return EnvStatusResponse(
        manifest_id=manifest_id,
        exists=status.exists,
        venv_path=status.venv_path,
        python_executable=status.python_executable,
        installed_packages=status.installed_packages,
    )
