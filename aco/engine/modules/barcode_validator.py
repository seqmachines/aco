"""Barcode validation QC module (stub).

Validates cell barcodes and UMIs against a whitelist, checks distribution,
and flags anomalies.

TODO: Implement actual barcode validation logic.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from aco.engine.modules.base import QCModule, ModuleResult

# Import the singleton registry so we can register this module
from aco.engine.modules import registry


@registry.register
class BarcodeValidator(QCModule):
    name = "barcode_validator"
    description = "Validate cell barcodes and UMIs against whitelist"
    version = "0.1.0"
    input_patterns = ["*.fastq.gz", "*.fastq"]
    output_names = ["barcode_report.json", "barcode_distribution.csv"]

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        errors = super().validate_inputs(inputs)
        # Could also check for whitelist file, etc.
        return errors

    def run(self, inputs: dict[str, Any], output_dir: Path) -> ModuleResult:
        """Run barcode validation.

        This is a stub. Replace with actual implementation.
        """
        started = datetime.now()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Stub: report that the module ran but has no real logic yet
        result = ModuleResult(
            module_name=self.name,
            success=True,
            gate_passed=None,
            summary="Barcode validator stub executed. Implement real logic in barcode_validator.py.",
            metrics={},
            output_files=[],
            started_at=started,
            completed_at=datetime.now(),
            duration_seconds=(datetime.now() - started).total_seconds(),
        )
        self.save_result(result, output_dir)
        return result

    def required_tools(self) -> list[str]:
        return []

    def get_run_command(self, inputs: dict[str, Any], output_dir: Path) -> str:
        data_dir = inputs.get("data_dir", ".")
        return f"python -m aco.engine.modules.barcode_validator --data_dir {data_dir} --output_dir {output_dir}"
