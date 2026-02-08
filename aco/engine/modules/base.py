"""Abstract base class for deterministic QC modules."""

from __future__ import annotations

import abc
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModuleResult(BaseModel):
    """Standardized result from a QC module run."""

    module_name: str
    success: bool
    gate_passed: bool | None = Field(
        default=None, description="True if the QC gate passed, None if no gate"
    )
    summary: str = Field(default="", description="Human-readable summary")
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Key-value metrics produced"
    )
    output_files: list[str] = Field(
        default_factory=list, description="Paths to output files"
    )
    errors: list[str] = Field(default_factory=list, description="Error messages")
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0


class QCModule(abc.ABC):
    """Abstract base class for a deterministic QC module.

    Subclasses must implement:
    - `name` (class attribute): unique module name used in the registry.
    - `description` (class attribute): short description of the module.
    - `run()`: main execution logic.

    Optionally override:
    - `validate_inputs()`: check that required inputs are available.
    - `required_tools()`: return a list of external tools that must be on PATH.
    """

    name: str = ""
    description: str = ""
    version: str = "0.1.0"

    # Declared I/O schema (informational)
    input_patterns: list[str] = []   # e.g. ["*.fastq.gz", "*.bam"]
    output_names: list[str] = []     # e.g. ["barcode_report.json"]

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate inputs before running.

        Args:
            inputs: Dict with at least "data_dir" and optionally
                    module-specific keys.

        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []
        data_dir = inputs.get("data_dir")
        if not data_dir or not Path(data_dir).is_dir():
            errors.append(f"data_dir is not a valid directory: {data_dir}")
        return errors

    @abc.abstractmethod
    def run(
        self,
        inputs: dict[str, Any],
        output_dir: Path,
    ) -> ModuleResult:
        """Execute the module.

        Args:
            inputs: Dict with "data_dir" and module-specific keys.
            output_dir: Directory to write outputs to.

        Returns:
            ModuleResult with metrics, output files, etc.
        """
        ...

    def required_tools(self) -> list[str]:
        """Return a list of external CLI tools this module needs."""
        return []

    def save_result(self, result: ModuleResult, output_dir: Path) -> Path:
        """Save the module result as JSON."""
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self.name}_result.json"
        path.write_text(result.model_dump_json(indent=2))
        return path

    def get_run_command(self, inputs: dict[str, Any], output_dir: Path) -> str:
        """Return a CLI command string to run this module standalone.

        Subclasses can override this to provide a copy-paste command.
        """
        return f"python -m aco.engine.modules.{self.name} --data_dir {inputs.get('data_dir', '.')} --output_dir {output_dir}"
