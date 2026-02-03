"""Script execution engine with sandboxing.

This module provides safe execution of generated scripts with:
- Subprocess isolation
- Timeout handling
- Output capture
- Error reporting
"""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from aco.engine.scripts import (
    GeneratedScript,
    ScriptType,
    get_script_extension,
    ExecutionResult,
    ExecutionConfig
)

logger = logging.getLogger(__name__)


class ScriptExecutor:
    """Executes generated scripts safely."""
    
    def __init__(self, config: ExecutionConfig | None = None):
        """Initialize the executor.
        
        Args:
            config: Execution configuration
        """
        self.config = config or ExecutionConfig()
    
    def _get_interpreter(self, script_type: ScriptType) -> list[str]:
        """Get the interpreter command for a script type."""
        if script_type == ScriptType.PYTHON:
            return [self.config.python_executable]
        elif script_type == ScriptType.BASH:
            return ["/bin/bash"]
        elif script_type == ScriptType.R:
            return ["Rscript"]
        else:
            raise ValueError(f"Unknown script type: {script_type}")
    
    def _build_environment(self) -> dict[str, str]:
        """Build the execution environment."""
        env = os.environ.copy()
        env.update(self.config.environment)
        # Ensure Python can find packages
        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = ""
        return env
    
    async def execute_script(
        self,
        script: GeneratedScript,
        script_path: Path,
        output_dir: Path,
        input_args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute a script and capture results.
        
        Args:
            script: The script specification
            script_path: Path to the script file
            output_dir: Directory for outputs
            input_args: Additional command-line arguments
        
        Returns:
            ExecutionResult with output and status
        """
        started_at = datetime.now()
        
        # Build command
        interpreter = self._get_interpreter(script.script_type)
        cmd = interpreter + [str(script_path)]
        
        # Add standard arguments
        if input_args:
            cmd.extend(input_args)
        
        # Add output directory
        cmd.extend(["--output-dir", str(output_dir)])
        
        logger.info(f"Executing: {' '.join(cmd)}")
        
        try:
            # Run the script
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE if self.config.capture_output else None,
                stderr=asyncio.subprocess.PIPE if self.config.capture_output else None,
                cwd=self.config.working_directory,
                env=self._build_environment(),
            )
            
            # Wait with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout_seconds,
                )
                exit_code = process.returncode or 0
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ExecutionResult(
                    script_name=script.name,
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    duration_seconds=(datetime.now() - started_at).total_seconds(),
                    started_at=started_at,
                    completed_at=datetime.now(),
                    error_message=f"Script timed out after {self.config.timeout_seconds}s",
                )
            
            completed_at = datetime.now()
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            
            # Find output files
            output_files = []
            if output_dir.exists():
                for f in output_dir.iterdir():
                    if f.is_file():
                        output_files.append(str(f))
            
            return ExecutionResult(
                script_name=script.name,
                success=(exit_code == 0),
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=(completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
                output_files=output_files,
            )
            
        except Exception as e:
            logger.exception(f"Script execution failed: {e}")
            return ExecutionResult(
                script_name=script.name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(),
                error_message=str(e),
            )
    
    def save_script(
        self,
        script: GeneratedScript,
        output_dir: Path,
    ) -> Path:
        """Save a script to disk.
        
        Args:
            script: The script to save
            output_dir: Directory to save to
        
        Returns:
            Path to the saved script
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        ext = get_script_extension(script.script_type)
        script_path = output_dir / f"{script.name}{ext}"
        
        script_path.write_text(script.code)
        
        # Make executable if bash
        if script.script_type == ScriptType.BASH:
            script_path.chmod(script_path.stat().st_mode | 0o111)
        
        return script_path
    
    async def execute_plan(
        self,
        scripts: list[GeneratedScript],
        scripts_dir: Path,
        output_dir: Path,
    ) -> list[ExecutionResult]:
        """Execute a list of scripts in order.
        
        Args:
            scripts: Scripts to execute
            scripts_dir: Directory containing script files
            output_dir: Base output directory
        
        Returns:
            List of execution results
        """
        results = []
        
        for script in scripts:
            # Create output subdirectory for this script
            script_output_dir = output_dir / script.category.value
            script_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Get script path
            ext = get_script_extension(script.script_type)
            script_path = scripts_dir / f"{script.name}{ext}"
            
            if not script_path.exists():
                results.append(ExecutionResult(
                    script_name=script.name,
                    success=False,
                    exit_code=-1,
                    duration_seconds=0,
                    error_message=f"Script file not found: {script_path}",
                ))
                continue
            
            # Execute
            result = await self.execute_script(
                script=script,
                script_path=script_path,
                output_dir=script_output_dir,
            )
            results.append(result)
            
            # Stop on failure if it's a critical script
            if not result.success and script.requires_approval:
                logger.warning(f"Script {script.name} failed, stopping execution")
                break
        
        return results


def check_dependencies(dependencies: list[str]) -> dict[str, bool]:
    """Check if required dependencies are available.
    
    Args:
        dependencies: List of package names to check
    
    Returns:
        Dict mapping package name to availability
    """
    results = {}
    
    for dep in dependencies:
        try:
            # Try importing the package
            __import__(dep.replace("-", "_"))
            results[dep] = True
        except ImportError:
            results[dep] = False
    
    return results
