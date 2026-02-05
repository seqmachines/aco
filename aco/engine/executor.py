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
import glob
import re

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

    def _extract_required_args(self, code: str) -> list[str]:
        """Extract required argparse arguments from script code."""
        if not code:
            return []
        pattern = re.compile(
            r"add_argument\(\s*['\"]--(?P<name>[a-zA-Z0-9_]+)['\"][^)]*required=True",
            re.DOTALL,
        )
        return list({match.group("name") for match in pattern.finditer(code)})

    def _resolve_input_matches(self, patterns: list[str], data_dir: Path) -> list[str]:
        """Resolve glob patterns relative to data_dir into file paths."""
        matches: list[str] = []
        for pattern in patterns:
            search_path = str(data_dir / pattern)
            matches.extend(glob.glob(search_path, recursive=True))
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                deduped.append(m)
        return deduped

    def _select_args_for_required(
        self,
        arg_name: str,
        patterns: list[str],
        data_dir: Path,
    ) -> list[str]:
        """Select appropriate input arguments based on arg name and patterns."""
        if not patterns:
            return []

        lower = arg_name.lower()
        matches = self._resolve_input_matches(patterns, data_dir)
        if not matches:
            return []

        # If argument expects a directory, use the common parent
        if lower.endswith("_dir") or "dir" in lower:
            parents = [str(Path(m).parent) for m in matches]
            common_dir = os.path.commonpath(parents) if parents else None
            return [common_dir] if common_dir else []

        # If argument expects a single file, pick the first match
        if any(key in lower for key in ["whitelist", "reference", "ref", "csv", "tsv", "file", "path"]):
            return [matches[0]]

        # Otherwise pass all matches (works for nargs="+")
        return matches
    
    async def execute_script(
        self,
        script: GeneratedScript,
        script_path: Path,
        output_dir: Path,
        data_dir: Path | None = None,
        input_args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute a script and capture results.
        
        Args:
            script: The script specification
            script_path: Path to the script file
            output_dir: Directory for outputs
            data_dir: Directory containing input data files
            input_args: Additional command-line arguments
        
        Returns:
            ExecutionResult with output and status
        """
        started_at = datetime.now()
        
        # Build command
        interpreter = self._get_interpreter(script.script_type)
        cmd = interpreter + [str(script_path)]
        
        # Add output directory (use underscore to match argparse convention)
        cmd.extend(["--output_dir", str(output_dir)])

        # Add data directory only if the script accepts it
        if data_dir and script.code and "--data_dir" in script.code:
            cmd.extend(["--data_dir", str(data_dir)])

        # Auto-build required input args based on script code + patterns
        if data_dir and script.code:
            required_args = self._extract_required_args(script.code)
            for arg in required_args:
                if arg in ("output_dir", "data_dir"):
                    continue
                selected = self._select_args_for_required(arg, script.input_files, data_dir)
                if selected:
                    cmd.append(f"--{arg}")
                    cmd.extend(selected)

        # Add any additional arguments (explicit overrides)
        if input_args:
            cmd.extend(input_args)
        
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
            
            # Find output files (exclude internal result JSON files)
            output_files = []
            if output_dir.exists():
                for f in output_dir.iterdir():
                    if f.is_file():
                        # Skip internal result/metadata JSON files
                        if f.name.endswith("_result.json"):
                            continue
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
        data_dir: Path | None = None,
    ) -> list[ExecutionResult]:
        """Execute a list of scripts in order.
        
        Args:
            scripts: Scripts to execute
            scripts_dir: Directory containing script files
            output_dir: Base output directory
            data_dir: Directory containing input data files
        
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
                data_dir=data_dir,
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
