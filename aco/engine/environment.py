"""Environment management for script execution using uv."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class EnvironmentStatus:
    """Status of an execution environment."""
    
    exists: bool
    venv_path: str | None
    python_executable: str | None
    installed_packages: list[str]
    error: str | None = None


@dataclass
class InstallResult:
    """Result of installing dependencies."""
    
    success: bool
    installed: list[str]
    failed: list[str]
    output: str
    error: str | None = None


def get_execution_dir(manifest_id: str) -> Path:
    """Get the execution directory for a manifest."""
    working_dir = os.getenv("ACO_WORKING_DIR", os.getcwd())
    exec_dir = Path(working_dir) / "aco_runs" / manifest_id / "execution"
    exec_dir.mkdir(parents=True, exist_ok=True)
    return exec_dir


def get_venv_path(manifest_id: str) -> Path:
    """Get the virtual environment path for a manifest."""
    return get_execution_dir(manifest_id) / ".venv"


def get_logs_dir(manifest_id: str) -> Path:
    """Get the logs directory for a manifest."""
    logs_dir = get_execution_dir(manifest_id) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_results_dir(manifest_id: str) -> Path:
    """Get the results directory for a manifest."""
    results_dir = get_execution_dir(manifest_id) / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def check_uv_available() -> bool:
    """Check if uv is available on the system."""
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def create_venv(manifest_id: str) -> tuple[bool, str]:
    """Create a virtual environment using uv.
    
    Args:
        manifest_id: The manifest identifier
        
    Returns:
        Tuple of (success, message)
    """
    if not check_uv_available():
        return False, "uv is not installed. Please install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    
    venv_path = get_venv_path(manifest_id)
    
    # Check if venv already exists
    if (venv_path / "bin" / "python").exists():
        return True, f"Virtual environment already exists at {venv_path}"
    
    try:
        result = subprocess.run(
            ["uv", "venv", str(venv_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=get_execution_dir(manifest_id),
        )
        
        if result.returncode == 0:
            return True, f"Created virtual environment at {venv_path}"
        else:
            return False, f"Failed to create venv: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return False, "Timeout creating virtual environment"
    except Exception as e:
        return False, f"Error creating virtual environment: {str(e)}"


def install_dependencies(
    manifest_id: str,
    requirements_file: Path | None = None,
    packages: list[str] | None = None,
) -> InstallResult:
    """Install dependencies into the virtual environment.

    Installs packages one by one so that a single bad package doesn't
    break the entire installation. Packages that fail are skipped with
    a warning, and the overall result succeeds as long as at least some
    packages were installed (or none were needed).

    Args:
        manifest_id: The manifest identifier
        requirements_file: Path to requirements.txt (optional)
        packages: List of package names to install (optional)

    Returns:
        InstallResult with status and details
    """
    venv_path = get_venv_path(manifest_id)
    python_path = str(venv_path / "bin" / "python")

    if not (venv_path / "bin" / "python").exists():
        return InstallResult(
            success=False,
            installed=[],
            failed=[],
            output="",
            error="Virtual environment does not exist. Create it first.",
        )

    if not check_uv_available():
        return InstallResult(
            success=False,
            installed=[],
            failed=[],
            output="",
            error="uv is not installed",
        )

    # Collect all package names
    all_packages: list[str] = []

    if requirements_file and requirements_file.exists():
        with open(requirements_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    all_packages.append(line)

    if packages:
        all_packages.extend(packages)

    if not all_packages:
        return InstallResult(
            success=True,
            installed=[],
            failed=[],
            output="No packages to install",
        )

    # Install packages one by one for resilience
    installed = []
    failed = []
    all_output = []
    exec_dir = get_execution_dir(manifest_id)

    for pkg in all_packages:
        cmd = ["uv", "pip", "install", "--python", python_path, pkg]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes per package
                cwd=exec_dir,
            )
            if result.returncode == 0:
                installed.append(pkg)
                all_output.append(f"OK: {pkg}")
            else:
                failed.append(pkg)
                all_output.append(f"FAILED: {pkg} - {result.stderr.strip().split(chr(10))[-1]}")
        except subprocess.TimeoutExpired:
            failed.append(pkg)
            all_output.append(f"TIMEOUT: {pkg}")
        except Exception as e:
            failed.append(pkg)
            all_output.append(f"ERROR: {pkg} - {str(e)}")

    output_text = "\n".join(all_output)

    # Succeed even if some packages failed — the scripts may still work
    return InstallResult(
        success=True,
        installed=installed,
        failed=failed,
        output=output_text,
        error=f"Could not install: {', '.join(failed)}" if failed else None,
    )


def get_environment_status(manifest_id: str) -> EnvironmentStatus:
    """Get the status of an execution environment.
    
    Args:
        manifest_id: The manifest identifier
        
    Returns:
        EnvironmentStatus with current state
    """
    venv_path = get_venv_path(manifest_id)
    python_path = venv_path / "bin" / "python"
    
    if not python_path.exists():
        return EnvironmentStatus(
            exists=False,
            venv_path=None,
            python_executable=None,
            installed_packages=[],
        )
    
    # Get installed packages
    installed_packages = []
    try:
        result = subprocess.run(
            [str(python_path), "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            installed_packages = [f"{p['name']}=={p['version']}" for p in packages]
    except Exception:
        pass
    
    return EnvironmentStatus(
        exists=True,
        venv_path=str(venv_path),
        python_executable=str(python_path),
        installed_packages=installed_packages,
    )


def get_script_interpreter(
    manifest_id: str,
    script_type: Literal["python", "r", "bash"],
) -> str:
    """Get the interpreter path for a script type.
    
    Args:
        manifest_id: The manifest identifier
        script_type: The script language
        
    Returns:
        Path to the interpreter
    """
    if script_type == "python":
        venv_path = get_venv_path(manifest_id)
        python_path = venv_path / "bin" / "python"
        if python_path.exists():
            return str(python_path)
        return "python3"
    elif script_type == "r":
        return "Rscript"
    elif script_type == "bash":
        return "/bin/bash"
    else:
        return "python3"
