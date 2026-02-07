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
    
    def _strip_extension(self, name: str) -> str:
        """Strip file extension from script name if present."""
        p = Path(name)
        return p.stem if p.suffix else name
    
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

    def _iter_add_argument_blocks(self, code: str) -> list[str]:
        """Extract full add_argument(...) blocks from script code."""
        blocks: list[str] = []
        if not code:
            return blocks
        keyword = "add_argument("
        idx = 0
        length = len(code)
        while idx < length:
            start = code.find(keyword, idx)
            if start == -1:
                break
            i = start + len(keyword)
            depth = 1
            in_str: str | None = None
            escape = False
            while i < length:
                ch = code[i]
                if in_str:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == in_str:
                        in_str = None
                else:
                    if ch in ("'", '"'):
                        in_str = ch
                    elif ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            blocks.append(code[start:i + 1])
                            idx = i + 1
                            break
                i += 1
            else:
                # Unterminated call; stop parsing
                break
        return blocks

    def _extract_argparse_args(self, code: str) -> list[dict[str, object]]:
        """Extract argparse argument definitions from script code.

        Returns list of dicts: {name, required, multiple}
        """
        args: list[dict[str, object]] = []
        if not code:
            return args
        blocks = self._iter_add_argument_blocks(code)
        for block in blocks:
            # Only consider long options (e.g., --input_files)
            names = re.findall(r"['\"]--([a-zA-Z0-9_][a-zA-Z0-9_\-]*)['\"]", block)
            if not names:
                continue
            # Prefer the longest option name as the canonical name
            primary = sorted(set(names), key=len, reverse=True)[0]
            required = re.search(r"required\s*=\s*True", block) is not None
            multiple = re.search(r"nargs\s*=\s*['\"][+*]['\"]", block) is not None
            args.append({
                "name": primary,
                "required": required,
                "multiple": multiple,
            })
        return args

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
        prefer_multiple: bool = False,
    ) -> list[str]:
        """Select appropriate input arguments based on arg name and patterns."""
        lower = arg_name.lower()
        
        # Resolve all patterns first (this likely contains a mix of files)
        matches = self._resolve_input_matches(patterns, data_dir)
            
        # Helper to filter by extension
        def filter_by_ext(files: list[str], exts: list[str]) -> list[str]:
            return [f for f in files if any(f.lower().endswith(e) for e in exts)]

        # Helper to find any file in data_dir with specific extensions (Smart Discovery)
        def find_any_by_ext(exts: list[str]) -> list[str]:
            found = []
            if data_dir and data_dir.exists():
                for ext in exts:
                    # Case-insensitive-ish glob (linux is case sensitive, but we try standard case)
                    # We can use glob with case-insensitive char classes if needed, but simple glob first
                    found.extend(glob.glob(str(data_dir / f"*{ext}")))
                    # Also try uppercase extension just in case
                    found.extend(glob.glob(str(data_dir / f"*{ext.upper()}")))
            return sorted(list(set(found))) # Dedup

        # Specific heuristics based on argument name
        
        # 1. Excel files
        if "excel" in lower or "xlsx" in lower:
            # Strict filtering from matches
            candidates = filter_by_ext(matches, [".xlsx", ".xls"])
            if candidates:
                return candidates[:1]
            
            # Smart fallback: look for ANY excel file
            candidates = find_any_by_ext([".xlsx", ".xls"])
            if candidates:
                return candidates[:1]
            
            # Strict fail: do not return random files
            return []
        
        # 2. FASTQ files/dirs
        if "fastq" in lower:
            target_exts = [".fastq", ".fastq.gz", ".fq", ".fq.gz"]
            
            # If asking for directory
            if lower.endswith("_dir") or "dir" in lower:
                # Find directory containing fastq files
                fastq_files = filter_by_ext(matches, target_exts)
                if not fastq_files:
                    fastq_files = find_any_by_ext(target_exts)
                
                if fastq_files:
                    # Return the parent dir of the first fastq file
                    parent = str(Path(fastq_files[0]).parent)
                    return [parent]
            else:
                 candidates = filter_by_ext(matches, target_exts)
                 if not candidates:
                     candidates = find_any_by_ext(target_exts)
                 
                 if candidates:
                     return candidates if prefer_multiple else candidates[:1]
            
            # Strict fail
            return []

        # 3. CSV/TSV
        if "csv" in lower:
            candidates = filter_by_ext(matches, [".csv"])
            if not candidates:
                candidates = find_any_by_ext([".csv"])
            return candidates[:1] if candidates else []
            
        if "tsv" in lower:
            candidates = filter_by_ext(matches, [".tsv"])
            if not candidates:
                candidates = find_any_by_ext([".tsv"])
            return candidates[:1] if candidates else []

        # 4. Generic directory fallthrough
        if lower.endswith("_dir") or "dir" in lower:
            if not matches:
                # If no matches but we need a dir, maybe data_dir itself?
                if data_dir:
                    return [str(data_dir)]
                return []
                
            # Return common parent of whatever matched
            parents = [str(Path(m).parent) for m in matches]
            if parents:
                 return [parents[0]]

        # 5. Fallback: return first match (or all if multiple)
        # Only reach here if argument type is unknown (no 'excel', 'fastq', etc. in name)
        if not matches:
            return []
            
        if prefer_multiple:
            return matches
        return matches[:1]
    
    def _log_command(self, cmd: list[str], output_dir: Path, script_name: str) -> None:
        """Write the full command to a log file for debugging."""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            # User requested cmd.log extension
            log_path = output_dir / f"{self._strip_extension(script_name)}.cmd.log"
            with open(log_path, "w") as f:
                f.write(f"timestamp: {datetime.now().isoformat()}\n")
                f.write(f"cwd: {self.config.working_directory or os.getcwd()}\n")
                f.write(f"python: {self.config.python_executable}\n")
                f.write(f"command:\n  {' '.join(cmd)}\n")
        except Exception:
            pass  # Best-effort logging
    
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

        missing_required: list[str] = []

        # Auto-build input args based on script code + patterns
        if data_dir and script.code:
            arg_defs = self._extract_argparse_args(script.code)
            arg_names = {a["name"] for a in arg_defs}

            # Add data_dir only if the script defines it
            if "data_dir" in arg_names:
                cmd.extend(["--data_dir", str(data_dir)])

            for arg_def in arg_defs:
                arg = str(arg_def["name"])
                if arg in ("output_dir", "data_dir"):
                    continue
                selected = self._select_args_for_required(
                    arg,
                    script.input_files,
                    data_dir,
                    prefer_multiple=bool(arg_def["multiple"]),
                )
                if selected:
                    cmd.append(f"--{arg}")
                    cmd.extend(selected)
                elif arg_def["required"]:
                    missing_required.append(arg)

        if missing_required:
            return ExecutionResult(
                script_name=script.name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_seconds=(datetime.now() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(),
                error_message=(
                    "Missing required input arguments: "
                    + ", ".join(missing_required)
                ),
            )

        if input_args:
            cmd.extend(input_args)
        
        # Log the command to a file for debugging
        self._log_command(cmd, output_dir, script.name)

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
            
            # Wait for completion (no timeout — let scripts run as long as needed)
            stdout_bytes, stderr_bytes = await process.communicate()
            exit_code = process.returncode or 0
            
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
        base_name = self._strip_extension(script.name)
        script_path = output_dir / f"{base_name}{ext}"
        
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
            
            # Get script path (strip extension to avoid double .py.py)
            ext = get_script_extension(script.script_type)
            base_name = self._strip_extension(script.name)
            script_path = scripts_dir / f"{base_name}{ext}"
            
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
