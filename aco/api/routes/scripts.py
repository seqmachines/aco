"""Script generation and execution routes."""

import json
import os
import hashlib
import re
from datetime import datetime
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
    plans_equivalent,
    refine_script_plan,
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
    get_venv_path,
)
from aco.engine.chat import get_chat_store
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
    reference_script_path: str | None = Field(
        default=None,
        description=(
            "Optional path to an existing script to upload via the Gemini "
            "Files API as a reference / template for code generation."
        ),
    )


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


class ExecutePipelineRequest(BaseModel):
    """Request to run the full scripts pipeline."""

    manifest_id: str
    model: str | None = None
    api_key: str | None = None
    reference_script_paths: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional mapping of script name to reference script path "
            "used during code generation."
        ),
    )


class PipelineStepResult(BaseModel):
    """Result of a pipeline step."""

    step: str
    success: bool
    message: str


class ExecutePipelineResponse(BaseModel):
    """Response with pipeline results."""

    manifest_id: str
    steps: list[PipelineStepResult]
    execution_results: list[ExecutionResult]
    all_succeeded: bool
    message: str


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


def _get_search_dirs(manifest_id: str) -> list[str]:
    """Return directories to search for auto-detecting reference scripts.

    Includes the data directory (from the manifest) and the working
    directory so that ``detect_referenced_scripts`` can find scripts
    mentioned in a planned script's description.
    """
    dirs: list[str] = []

    # Data directory from manifest
    try:
        manifest_store = get_manifest_store()
        manifest = manifest_store.load(manifest_id)
        if manifest and manifest.user_intake.target_directory:
            dirs.append(manifest.user_intake.target_directory)
    except Exception:
        pass

    # Working directory
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    if working_dir not in dirs:
        dirs.append(working_dir)

    # Previous run scripts directories
    runs_dir = Path(working_dir) / "aco_runs"
    if runs_dir.exists():
        for run_dir in runs_dir.iterdir():
            scripts_sub = run_dir / "scripts"
            if scripts_sub.is_dir() and str(scripts_sub) not in dirs:
                dirs.append(str(scripts_sub))

    return dirs


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


def strip_script_extension(name: str) -> str:
    """Strip file extension from script name if present."""
    p = Path(name)
    return p.stem if p.suffix else name


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


def _normalize_package_name(name: str) -> str:
    """Normalize package name for comparison."""
    return re.sub(r"[-_]+", "-", name.strip().lower())


def _load_requirements(requirements_path: Path) -> list[str]:
    """Load requirements.txt lines (no comments/empties)."""
    if not requirements_path.exists():
        return []
    requirements: list[str] = []
    for line in requirements_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip inline comments and env markers
        line = line.split("#", 1)[0].strip()
        line = line.split(";", 1)[0].strip()
        if line:
            requirements.append(line)
    return requirements


def _extract_requirement_name(req: str) -> str:
    """Extract package name from a requirement spec."""
    # Split on common version separators
    parts = re.split(r"(==|>=|<=|~=|!=|>|<)", req, maxsplit=1)
    return parts[0].strip()


def _compute_plan_hash(plan: ScriptPlan) -> str:
    """Compute a stable hash for the script plan (excluding code)."""
    scripts_data = []
    for s in plan.scripts:
        scripts_data.append({
            "name": s.name,
            "category": s.category.value if hasattr(s.category, "value") else s.category,
            "script_type": s.script_type.value if hasattr(s.script_type, "value") else s.script_type,
            "description": s.description,
            "dependencies": s.dependencies,
            "input_files": s.input_files,
            "output_files": s.output_files,
            "estimated_runtime": s.estimated_runtime,
            "requires_approval": s.requires_approval,
        })
    payload = {
        "manifest_id": plan.manifest_id,
        "scripts": scripts_data,
        "execution_order": plan.execution_order,
        "total_estimated_runtime": plan.total_estimated_runtime,
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _plan_hash_path(manifest_id: str) -> Path:
    scripts_dir = get_scripts_dir(manifest_id)
    return scripts_dir / "plan.hash"


def _load_plan_hash(manifest_id: str) -> str | None:
    path = _plan_hash_path(manifest_id)
    if not path.exists():
        return None
    return path.read_text().strip() or None


def _save_plan_hash(manifest_id: str, plan_hash: str) -> None:
    path = _plan_hash_path(manifest_id)
    path.write_text(plan_hash)


def _get_latest_scripts_user_comment_ts(manifest_id: str) -> datetime | None:
    """Return the latest user chat timestamp for scripts step."""
    store = get_chat_store()
    messages = store.load_messages(manifest_id, "scripts")
    latest: datetime | None = None
    for msg in messages:
        if msg.role != "user":
            continue
        if latest is None or msg.timestamp > latest:
            latest = msg.timestamp
    return latest


def _get_scripts_user_comments_since(
    manifest_id: str,
    since: datetime | None,
) -> list[str]:
    """Return user script-step comments newer than ``since``."""
    store = get_chat_store()
    messages = store.load_messages(manifest_id, "scripts")
    comments: list[str] = []
    for msg in messages:
        if msg.role != "user":
            continue
        if since is not None and msg.timestamp <= since:
            continue
        text = msg.content.strip()
        if text:
            comments.append(text)
    return comments


def _script_file_candidates(script: GeneratedScript, scripts_dir: Path) -> list[Path]:
    from aco.engine.scripts import get_script_extension
    ext = get_script_extension(script.script_type)
    base = strip_script_extension(script.name)
    candidates = [scripts_dir / f"{base}{ext}", scripts_dir / script.name]
    # Deduplicate
    seen: set[str] = set()
    unique: list[Path] = []
    for c in candidates:
        if str(c) in seen:
            continue
        seen.add(str(c))
        unique.append(c)
    return unique


def _scripts_missing(plan: ScriptPlan, scripts_dir: Path) -> list[str]:
    missing: list[str] = []
    for s in plan.scripts:
        if not any(p.exists() for p in _script_file_candidates(s, scripts_dir)):
            missing.append(s.name)
    return missing


def _delete_script_files(scripts_dir: Path) -> None:
    """Delete script files from scripts directory."""
    for ext in (".py", ".sh", ".R", ".r"):
        for path in scripts_dir.glob(f"*{ext}"):
            try:
                path.unlink()
            except Exception:
                # Best-effort deletion; ignore failures
                pass


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
    # Prefer disk as source of truth to avoid stale per-worker memory cache.
    plan = load_plan_from_disk(manifest_id)
    if plan:
        _script_plans[manifest_id] = plan
        return GeneratePlanResponse(
            manifest_id=manifest_id,
            plan=plan,
            message="Loaded from disk",
        )

    # Fall back to memory cache if disk plan is missing.
    if manifest_id in _script_plans:
        plan = _script_plans[manifest_id]
        return GeneratePlanResponse(
            manifest_id=manifest_id,
            plan=plan,
            message="Retrieved from cache",
        )
    
    raise HTTPException(404, "No script plan found. Generate one first.")


class UpdatePlanRequest(BaseModel):
    """Request to save an edited script plan."""

    plan: dict


@router.put("/plan/{manifest_id}", response_model=GeneratePlanResponse)
async def update_plan_endpoint(manifest_id: str, request: UpdatePlanRequest):
    """Save a user-edited script plan (description changes, script deletions, etc.)."""
    try:
        updated_plan = ScriptPlan.model_validate(request.plan)
    except Exception as e:
        raise HTTPException(400, f"Invalid plan data: {e}")

    updated_plan.manifest_id = manifest_id
    _script_plans[manifest_id] = updated_plan
    save_plan_to_disk(manifest_id, updated_plan)
    save_requirements_txt(manifest_id, updated_plan)

    return GeneratePlanResponse(
        manifest_id=manifest_id,
        plan=updated_plan,
        message="Plan saved",
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
        code = await generate_script_code(
            script,
            understanding,
            str(output_dir),
            client,
            reference_script_path=request.reference_script_path,
            search_dirs=_get_search_dirs(request.manifest_id),
        )
        
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
    reference_script_paths: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional mapping of script name to reference script path. "
            "Each referenced file is uploaded via the Gemini Files API "
            "as context for generating that script's code."
        ),
    )


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
    
    ref_paths = request.reference_script_paths or {}
    search_dirs = _get_search_dirs(request.manifest_id)

    for i, script in enumerate(plan.scripts):
        try:
            output_dir = run_manager.stage_path(f"02_{script.category.value}")
            # Look up reference by script name (with or without extension)
            ref_path = ref_paths.get(script.name) or ref_paths.get(
                strip_script_extension(script.name)
            )
            code = await generate_script_code(
                script,
                understanding,
                str(output_dir),
                client,
                reference_script_path=ref_path,
                search_dirs=search_dirs,
            )
            
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
    scripts_dir = get_scripts_dir(request.manifest_id)
    output_dir = run_manager.stage_path("04_qc_results")
    
    # Get data directory from manifest
    manifest_store = get_manifest_store()
    manifest = manifest_store.load(request.manifest_id)
    data_dir = Path(manifest.user_intake.target_directory) if manifest else None
    
    # Execute using venv Python
    venv_python = str(get_venv_path(request.manifest_id) / "bin" / "python")
    config = ExecutionConfig(
        timeout_seconds=request.timeout_seconds,
        python_executable=venv_python,
    )
    executor = ScriptExecutor(config)
    
    from aco.engine.scripts import get_script_extension
    ext = get_script_extension(script.script_type)
    script_name = strip_script_extension(script.name)
    script_path = scripts_dir / f"{script_name}{ext}"
    
    if not script_path.exists():
        raise HTTPException(400, f"Script file not found at {script_path}. Generate code first.")
    
    result = await executor.execute_script(script, script_path, output_dir, data_dir=data_dir)
    
    # Save result
    run_manager.save_artifact(
        "04_qc_results",
        f"{script_name}_result.json",
        result,
    )
    
    return ExecuteScriptResponse(
        manifest_id=request.manifest_id,
        result=result,
    )


@router.post("/execute-all", response_model=ExecuteAllResponse)
async def execute_all_endpoint(request: ExecuteAllRequest):
    """Execute all scripts in the plan using the venv."""
    if request.manifest_id not in _script_plans:
        plan = load_plan_from_disk(request.manifest_id)
        if plan:
            _script_plans[request.manifest_id] = plan
        else:
            raise HTTPException(404, "No script plan found. Generate one first.")
    
    plan = _script_plans[request.manifest_id]
    scripts_dir = get_scripts_dir(request.manifest_id)
    
    from aco.engine.scripts import get_script_extension
    
    # Load code from disk for scripts missing it in memory
    for script in plan.scripts:
        if script.code and script.code.strip():
            continue
        ext = get_script_extension(script.script_type)
        script_name_base = strip_script_extension(script.name)
        for path in [scripts_dir / f"{script_name_base}{ext}", scripts_dir / script.name]:
            if path.exists():
                existing_code = path.read_text()
                if existing_code.strip():
                    script.code = existing_code
                    break
    
    # Filter scripts that have code
    scripts_to_run = [s for s in plan.scripts if s.code]
    if not scripts_to_run:
        raise HTTPException(400, "No scripts have generated code yet")
    
    # Get paths
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    run_manager = get_run_manager(Path(working_dir), request.manifest_id)
    
    # Get data directory from manifest
    manifest_store = get_manifest_store()
    manifest = manifest_store.load(request.manifest_id)
    data_dir = Path(manifest.user_intake.target_directory) if manifest else None
    
    # Execute using venv Python
    venv_python = str(get_venv_path(request.manifest_id) / "bin" / "python")
    config = ExecutionConfig(
        timeout_seconds=request.timeout_seconds,
        python_executable=venv_python,
    )
    executor = ScriptExecutor(config)
    
    results = []
    
    for script in scripts_to_run:
        output_dir = run_manager.stage_path("04_qc_results")
        ext = get_script_extension(script.script_type)
        script_name = strip_script_extension(script.name)
        script_path = scripts_dir / f"{script_name}{ext}"
        
        if script_path.exists():
            result = await executor.execute_script(script, script_path, output_dir, data_dir=data_dir)
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


@router.post("/pipeline", response_model=ExecutePipelineResponse)
async def execute_pipeline_endpoint(request: ExecutePipelineRequest):
    """Run the full scripts pipeline with plan reuse and env/deps checks."""
    steps: list[PipelineStepResult] = []
    execution_results: list[ExecutionResult] = []

    def add_step(step: str, success: bool, message: str) -> None:
        steps.append(PipelineStepResult(step=step, success=success, message=message))

    manifest_store = get_manifest_store()
    understanding_store = get_understanding_store()

    manifest = manifest_store.load(request.manifest_id)
    if not manifest:
        raise HTTPException(404, f"Manifest {request.manifest_id} not found")

    understanding = understanding_store.load(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not generated yet")

    # Load or generate plan
    plan = _script_plans.get(request.manifest_id) or load_plan_from_disk(request.manifest_id)
    plan_generated = False

    if not plan:
        # Generate plan if missing
        file_list = []
        if manifest.scan_result:
            file_list = [f.path for f in manifest.scan_result.files]

        api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        model = request.model or "gemini-2.5-flash"
        try:
            client = GeminiClient(api_key=api_key, model_name=model)
            plan = await generate_script_plan(understanding, file_list, client)
            plan.manifest_id = request.manifest_id
            plan_generated = True
            _script_plans[request.manifest_id] = plan
            save_plan_to_disk(request.manifest_id, plan)
            save_requirements_txt(request.manifest_id, plan)
        except Exception as e:
            raise HTTPException(500, f"Failed to generate plan: {str(e)}")
    else:
        _script_plans[request.manifest_id] = plan

    scripts_dir = get_scripts_dir(request.manifest_id)
    last_hash = _load_plan_hash(request.manifest_id)

    latest_comment_ts = _get_latest_scripts_user_comment_ts(request.manifest_id)
    has_new_comments = bool(
        latest_comment_ts and plan.generated_at and latest_comment_ts > plan.generated_at
    )
    comments_since = _get_scripts_user_comments_since(
        request.manifest_id, plan.generated_at
    )
    comment_refine_status = "none"
    comment_refine_message = ""

    # Apply newly added scripts-chat comments to plan before code-gen decisions.
    if comments_since:
        api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        model = request.model or "gemini-2.5-flash"
        try:
            client = GeminiClient(api_key=api_key, model_name=model)
            feedback = "\n\n".join(comments_since[-8:])
            refined_plan, _ = await refine_script_plan(
                plan=plan,
                feedback=feedback,
                understanding=understanding,
                client=client,
            )
            refined_plan.manifest_id = request.manifest_id
            if plans_equivalent(plan, refined_plan):
                comment_refine_status = "no_change"
                comment_refine_message = (
                    "Reviewed new chat comments; no effective plan changes."
                )
            else:
                plan = refined_plan
                _script_plans[request.manifest_id] = plan
                save_plan_to_disk(request.manifest_id, plan)
                save_requirements_txt(request.manifest_id, plan)
                comment_refine_status = "updated"
                comment_refine_message = (
                    f"Applied {len(comments_since)} new chat comment(s) to regenerate plan."
                )
        except Exception as e:
            comment_refine_status = "error"
            comment_refine_message = (
                "Could not apply new chat comments to the plan; "
                f"continuing with existing plan ({str(e)})."
            )

    plan_hash = _compute_plan_hash(plan)

    missing_scripts = _scripts_missing(plan, scripts_dir)
    plan_changed = (last_hash is None) or (plan_hash != last_hash)

    # Step 1: Generate code if needed
    if plan_changed:
        _delete_script_files(scripts_dir)
        missing_scripts = [s.name for s in plan.scripts]

    if missing_scripts:
        api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        model = request.model or "gemini-2.5-flash"
        client = GeminiClient(api_key=api_key, model_name=model)
        working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
        run_manager = get_run_manager(Path(working_dir), request.manifest_id)

        failed: list[str] = []
        pipeline_ref_paths = request.reference_script_paths or {}
        pipeline_search_dirs = _get_search_dirs(request.manifest_id)
        missing_set = {strip_script_extension(n) for n in missing_scripts}
        for script in plan.scripts:
            if strip_script_extension(script.name) not in missing_set:
                continue
            try:
                category_val = script.category.value if hasattr(script.category, "value") else str(script.category)
                output_dir = run_manager.stage_path(f"02_{category_val}")
                ref_path = pipeline_ref_paths.get(
                    script.name
                ) or pipeline_ref_paths.get(strip_script_extension(script.name))
                code = await generate_script_code(
                    script, understanding, str(output_dir), client,
                    reference_script_path=ref_path,
                    search_dirs=pipeline_search_dirs,
                )
                script.code = code
                save_script_to_disk(request.manifest_id, script)
            except Exception as e:
                failed.append(f"{script.name}: {str(e)}")

        if failed:
            add_step("generating_code", False, f"Code generation failed: {', '.join(failed)}")
            return ExecutePipelineResponse(
                manifest_id=request.manifest_id,
                steps=steps,
                execution_results=[],
                all_succeeded=False,
                message="Pipeline failed during code generation",
            )

        save_plan_to_disk(request.manifest_id, plan)
        save_requirements_txt(request.manifest_id, plan)
        _save_plan_hash(request.manifest_id, plan_hash)
        generated_msg = f"Generated {len(missing_scripts)} script(s)"
        if comment_refine_status == "updated":
            generated_msg = f"{comment_refine_message} {generated_msg}"
        add_step("generating_code", True, generated_msg)
    else:
        _save_plan_hash(request.manifest_id, plan_hash)
        if plan_generated:
            add_step("generating_code", True, "Generated plan; scripts already present")
        elif comment_refine_status == "no_change":
            add_step("generating_code", True, comment_refine_message)
        elif comment_refine_status == "error":
            add_step("generating_code", True, comment_refine_message)
        elif has_new_comments:
            add_step("generating_code", True, "Skipped (new comments but plan unchanged)")
        else:
            add_step("generating_code", True, "Skipped (scripts already present)")

    # Step 2: Create environment
    success, message = create_venv(request.manifest_id)
    add_step("creating_env", success, message)
    if not success:
        return ExecutePipelineResponse(
            manifest_id=request.manifest_id,
            steps=steps,
            execution_results=[],
            all_succeeded=False,
            message="Pipeline failed during environment creation",
        )

    # Step 3: Install dependencies (if missing)
    requirements_path = scripts_dir / "requirements.txt"
    if not requirements_path.exists():
        save_requirements_txt(request.manifest_id, plan)

    status = get_environment_status(request.manifest_id)
    installed_names = {
        _normalize_package_name(p.split("==")[0])
        for p in status.installed_packages
        if p
    }

    req_lines = _load_requirements(requirements_path)
    req_map: dict[str, str] = {}
    for req in req_lines:
        name = _extract_requirement_name(req)
        if not name:
            continue
        req_map[_normalize_package_name(name)] = req

    missing_specs = [spec for norm, spec in req_map.items() if norm not in installed_names]

    if missing_specs:
        install_result = install_dependencies(
            request.manifest_id,
            packages=missing_specs,
        )
        if install_result.failed:
            add_step("installing_deps", False, install_result.error or "Dependency installation failed")
            return ExecutePipelineResponse(
                manifest_id=request.manifest_id,
                steps=steps,
                execution_results=[],
                all_succeeded=False,
                message="Pipeline failed during dependency installation",
            )
        add_step("installing_deps", True, f"Installed {len(install_result.installed)} package(s)")
    else:
        add_step("installing_deps", True, "All dependencies already installed")

    # Step 4: Execute scripts
    from aco.engine.scripts import get_script_extension

    # Load code from disk for scripts missing code in memory
    for script in plan.scripts:
        if script.code and script.code.strip():
            continue
        ext = get_script_extension(script.script_type)
        script_name_base = strip_script_extension(script.name)
        for path in [scripts_dir / f"{script_name_base}{ext}", scripts_dir / script.name]:
            if path.exists():
                existing_code = path.read_text()
                if existing_code.strip():
                    script.code = existing_code
                    break

    scripts_with_code = [s for s in plan.scripts if s.code and s.code.strip()]
    if not scripts_with_code:
        add_step("executing", False, "No scripts have generated code")
        return ExecutePipelineResponse(
            manifest_id=request.manifest_id,
            steps=steps,
            execution_results=[],
            all_succeeded=False,
            message="Pipeline failed during execution",
        )

    # Order scripts by execution_order if present
    if plan.execution_order:
        name_to_script = {strip_script_extension(s.name): s for s in scripts_with_code}
        ordered: list[GeneratedScript] = []
        for name in plan.execution_order:
            base = strip_script_extension(name)
            script = name_to_script.pop(base, None)
            if script:
                ordered.append(script)
        for s in scripts_with_code:
            if s not in ordered:
                ordered.append(s)
        scripts_to_run = ordered
    else:
        scripts_to_run = scripts_with_code

    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    run_manager = get_run_manager(Path(working_dir), request.manifest_id)
    data_dir = Path(manifest.user_intake.target_directory) if manifest else None
    venv_python = str(get_venv_path(request.manifest_id) / "bin" / "python")
    config = ExecutionConfig(
        python_executable=venv_python,
    )
    executor = ScriptExecutor(config)

    output_dir = run_manager.stage_path("04_qc_results")
    execution_results = await executor.execute_plan(
        scripts=scripts_to_run,
        scripts_dir=scripts_dir,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    # Save results
    for result in execution_results:
        script_name = strip_script_extension(result.script_name)
        run_manager.save_artifact(
            "04_qc_results",
            f"{script_name}_result.json",
            result,
        )

    all_succeeded = all(r.success for r in execution_results)
    if all_succeeded:
        add_step("executing", True, "All scripts executed successfully")
    else:
        failed_names = [r.script_name for r in execution_results if not r.success]
        add_step("executing", False, f"Scripts failed: {', '.join(failed_names)}")

    return ExecutePipelineResponse(
        manifest_id=request.manifest_id,
        steps=steps,
        execution_results=execution_results,
        all_succeeded=all_succeeded,
        message="Pipeline complete" if all_succeeded else "Pipeline failed",
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


# ---------------------------------------------------------------------------
# Plan Refinement
# ---------------------------------------------------------------------------

class RefinePlanRequest(BaseModel):
    """Request to refine a script plan via chat feedback."""

    manifest_id: str
    feedback: str
    model: str | None = None
    api_key: str | None = None


class RefinePlanResponse(BaseModel):
    """Response with refined script plan."""

    manifest_id: str
    plan: ScriptPlan
    message: str


@router.post("/plan/refine", response_model=RefinePlanResponse)
async def refine_plan_endpoint(request: RefinePlanRequest):
    """Refine a script plan based on user feedback."""
    from aco.engine.scripts import refine_script_plan

    # Load existing plan
    plan = _script_plans.get(request.manifest_id) or load_plan_from_disk(request.manifest_id)
    if not plan:
        raise HTTPException(404, "No script plan found. Generate one first.")

    # Load understanding
    understanding_store = get_understanding_store()
    understanding = understanding_store.load(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not generated yet")

    # Create client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or "gemini-2.5-flash"

    try:
        client = GeminiClient(api_key=api_key, model_name=model)
        updated_plan, response_msg = await refine_script_plan(
            plan=plan,
            feedback=request.feedback,
            understanding=understanding,
            client=client,
        )
        updated_plan.manifest_id = request.manifest_id

        # Update caches
        _script_plans[request.manifest_id] = updated_plan
        save_plan_to_disk(request.manifest_id, updated_plan)
        save_requirements_txt(request.manifest_id, updated_plan)

        return RefinePlanResponse(
            manifest_id=request.manifest_id,
            plan=updated_plan,
            message=response_msg,
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to refine plan: {str(e)}")


# ---------------------------------------------------------------------------
# Pre-existing Scripts
# ---------------------------------------------------------------------------

class ExistingScriptInfo(BaseModel):
    """Info about an existing script found on disk."""

    path: str
    name: str
    size_bytes: int
    preview: str
    source: str = Field(description="Where the script was found: 'data_dir' or 'previous_run'")


class ExistingScriptsResponse(BaseModel):
    """Response listing existing scripts."""

    manifest_id: str
    scripts: list[ExistingScriptInfo]


@router.get("/existing/{manifest_id}", response_model=ExistingScriptsResponse)
async def list_existing_scripts(manifest_id: str):
    """List existing scripts from data directory and previous runs."""
    manifest_store = get_manifest_store()
    manifest = manifest_store.load(manifest_id)

    found_scripts: list[ExistingScriptInfo] = []
    seen_paths: set[str] = set()

    script_extensions = {".py", ".R", ".r", ".sh"}

    # 1. Scan data directory (from manifest target_directory)
    if manifest and manifest.user_intake.target_directory:
        data_dir = Path(manifest.user_intake.target_directory)
        if data_dir.exists():
            for ext in script_extensions:
                for script_file in data_dir.rglob(f"*{ext}"):
                    if str(script_file) in seen_paths:
                        continue
                    # Skip __pycache__ and hidden dirs
                    if any(part.startswith(".") or part == "__pycache__" for part in script_file.parts):
                        continue
                    seen_paths.add(str(script_file))
                    try:
                        content = script_file.read_text(errors="replace")
                        preview = "\n".join(content.splitlines()[:20])
                    except Exception:
                        preview = "(could not read)"
                    found_scripts.append(ExistingScriptInfo(
                        path=str(script_file),
                        name=script_file.name,
                        size_bytes=script_file.stat().st_size,
                        preview=preview,
                        source="data_dir",
                    ))

    # 2. Scan previous aco_runs for scripts
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    runs_dir = Path(working_dir) / "aco_runs"
    if runs_dir.exists():
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir() or run_dir.name == manifest_id:
                continue
            scripts_dir = run_dir / "scripts"
            if not scripts_dir.exists():
                continue
            for ext in script_extensions:
                for script_file in scripts_dir.glob(f"*{ext}"):
                    if str(script_file) in seen_paths:
                        continue
                    seen_paths.add(str(script_file))
                    try:
                        content = script_file.read_text(errors="replace")
                        preview = "\n".join(content.splitlines()[:20])
                    except Exception:
                        preview = "(could not read)"
                    found_scripts.append(ExistingScriptInfo(
                        path=str(script_file),
                        name=script_file.name,
                        size_bytes=script_file.stat().st_size,
                        preview=preview,
                        source="previous_run",
                    ))

    return ExistingScriptsResponse(
        manifest_id=manifest_id,
        scripts=found_scripts,
    )


class UpdateExistingScriptRequest(BaseModel):
    """Request to update an existing script."""

    manifest_id: str
    script_path: str
    instructions: str
    model: str | None = None
    api_key: str | None = None


class UpdateExistingScriptResponse(BaseModel):
    """Response with updated script code."""

    manifest_id: str
    original_path: str
    saved_path: str
    code: str


@router.post("/update-existing", response_model=UpdateExistingScriptResponse)
async def update_existing_script_endpoint(request: UpdateExistingScriptRequest):
    """Read an existing script and update it based on instructions."""
    from aco.engine.scripts import update_existing_script

    # Validate path exists
    if not Path(request.script_path).exists():
        raise HTTPException(404, f"Script not found: {request.script_path}")

    # Load understanding
    understanding_store = get_understanding_store()
    understanding = understanding_store.load(request.manifest_id)
    if not understanding:
        raise HTTPException(400, "Understanding not generated yet")

    # Create client
    api_key = request.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = request.model or "gemini-2.5-flash"

    try:
        client = GeminiClient(api_key=api_key, model_name=model)
        updated_code = await update_existing_script(
            script_path=request.script_path,
            understanding=understanding,
            instructions=request.instructions,
            client=client,
        )

        # Save updated script to the current run's scripts directory
        scripts_dir = get_scripts_dir(request.manifest_id)
        script_name = Path(request.script_path).name
        saved_path = scripts_dir / script_name
        with open(saved_path, "w") as f:
            f.write(updated_code)

        return UpdateExistingScriptResponse(
            manifest_id=request.manifest_id,
            original_path=request.script_path,
            saved_path=str(saved_path),
            code=updated_code,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to update script: {str(e)}")
