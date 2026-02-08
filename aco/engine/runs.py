"""ACO Runs folder structure manager.

Manages the aco_runs/<manifest_id>/ directory structure for organizing
all outputs from a QC analysis session.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RunConfig(BaseModel):
    """Configuration for an ACO run."""
    
    manifest_id: str = Field(..., description="Unique manifest identifier")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="initialized", description="Current run status")
    current_stage: str = Field(default="00_manifest", description="Current processing stage")
    notebook_type: str = Field(default="python", description="python or r")
    version: int = Field(default=2, description="Run config schema version (2 = three-phase)")


# Standard folder structure -- three-phase layout (v2)
STAGE_FOLDERS = [
    "01_understand/describe",
    "01_understand/scan",
    "01_understand/understanding",
    "02_analyze/hypothesis",
    "02_analyze/references",
    "02_analyze/strategy",
    "02_analyze/results",
    "03_summarize/plots",
    "03_summarize/notebook",
    "03_summarize/report",
]

# Legacy folder names kept for backward compat with v1 runs
LEGACY_STAGE_FOLDERS = [
    "00_manifest",
    "01_understanding",
    "02_parse_assay",
    "03_sequencing_health",
    "04_qc_results",
    "05_notebook",
    "06_report",
]


class RunManager:
    """Manages the aco_runs folder structure for a single run."""
    
    def __init__(self, base_dir: Path, manifest_id: str):
        """Initialize run manager.
        
        Args:
            base_dir: Base directory containing aco_runs/
            manifest_id: Unique identifier for this run
        """
        self.base_dir = Path(base_dir)
        self.manifest_id = manifest_id
        self.runs_dir = self.base_dir / "aco_runs"
        self.run_dir = self.runs_dir / manifest_id
        self.config_path = self.run_dir / "run_config.json"
        self._config: RunConfig | None = None
    
    @property
    def config(self) -> RunConfig:
        """Get or load the run configuration."""
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    def _load_config(self) -> RunConfig:
        """Load config from disk or create new."""
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text())
            return RunConfig.model_validate(data)
        return RunConfig(manifest_id=self.manifest_id)
    
    def _save_config(self) -> None:
        """Save config to disk."""
        self.config_path.write_text(
            self.config.model_dump_json(indent=2)
        )
    
    def initialize(self) -> None:
        """Create the full folder structure for this run."""
        # Create base runs directory
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create run directory
        self.run_dir.mkdir(exist_ok=True)
        
        # Create all stage folders
        for folder in STAGE_FOLDERS:
            stage_dir = self.run_dir / folder
            stage_dir.mkdir(exist_ok=True)
        
        # Create figures subfolder in notebook
        (self.run_dir / "03_summarize" / "notebook" / "figures").mkdir(parents=True, exist_ok=True)
        
        # Also create a scripts/ dir at the run level for generated code
        (self.run_dir / "scripts").mkdir(exist_ok=True)
        
        # Save initial config
        self._save_config()
    
    def stage_path(self, stage: str) -> Path:
        """Get the path for a specific stage folder.
        
        Args:
            stage: Stage name (e.g., "00_manifest", "01_understanding")
        
        Returns:
            Path to the stage folder
        """
        return self.run_dir / stage
    
    def save_artifact(
        self,
        stage: str,
        filename: str,
        data: Any,
        as_json: bool = True
    ) -> Path:
        """Save an artifact to a stage folder.
        
        Args:
            stage: Stage folder name
            filename: Output filename
            data: Data to save (dict/model for JSON, str for text)
            as_json: Whether to serialize as JSON
        
        Returns:
            Path to the saved file
        """
        stage_dir = self.stage_path(stage)
        stage_dir.mkdir(exist_ok=True)
        
        filepath = stage_dir / filename
        
        if as_json:
            if hasattr(data, "model_dump_json"):
                # Pydantic model
                filepath.write_text(data.model_dump_json(indent=2))
            else:
                # Dict or other JSON-serializable
                filepath.write_text(json.dumps(data, indent=2, default=str))
        else:
            filepath.write_text(str(data))
        
        # Update config
        self.config.updated_at = datetime.now()
        self._save_config()
        
        return filepath
    
    def load_artifact(self, stage: str, filename: str) -> dict | str | None:
        """Load an artifact from a stage folder.
        
        Args:
            stage: Stage folder name
            filename: Filename to load
        
        Returns:
            Parsed JSON dict or raw string, or None if not found
        """
        filepath = self.stage_path(stage) / filename
        
        if not filepath.exists():
            return None
        
        content = filepath.read_text()
        
        if filename.endswith(".json"):
            return json.loads(content)
        return content
    
    def update_stage(self, stage: str) -> None:
        """Update the current stage."""
        self.config.current_stage = stage
        self.config.updated_at = datetime.now()
        self._save_config()
    
    def update_status(self, status: str) -> None:
        """Update the run status."""
        self.config.status = status
        self.config.updated_at = datetime.now()
        self._save_config()
    
    def exists(self) -> bool:
        """Check if this run already exists."""
        return self.run_dir.exists()
    
    def cleanup(self) -> None:
        """Remove all files for this run."""
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)


def list_runs(base_dir: Path) -> list[dict]:
    """List all runs in the aco_runs directory.
    
    Args:
        base_dir: Base directory containing aco_runs/
    
    Returns:
        List of run info dicts with manifest_id, created_at, status, etc.
    """
    runs_dir = Path(base_dir) / "aco_runs"
    
    if not runs_dir.exists():
        return []
    
    runs = []
    for run_path in runs_dir.iterdir():
        if run_path.is_dir():
            config_path = run_path / "run_config.json"
            if config_path.exists():
                try:
                    config = RunConfig.model_validate(
                        json.loads(config_path.read_text())
                    )
                    runs.append({
                        "manifest_id": config.manifest_id,
                        "created_at": config.created_at.isoformat(),
                        "updated_at": config.updated_at.isoformat(),
                        "status": config.status,
                        "current_stage": config.current_stage,
                    })
                except Exception:
                    # Skip invalid runs
                    pass
    
    # Sort by updated_at descending
    runs.sort(key=lambda x: x["updated_at"], reverse=True)
    return runs


def get_run_manager(base_dir: Path, manifest_id: str) -> RunManager:
    """Get or create a run manager for a manifest.
    
    Args:
        base_dir: Base directory containing aco_runs/
        manifest_id: Manifest identifier
    
    Returns:
        RunManager instance
    """
    manager = RunManager(base_dir, manifest_id)
    if not manager.exists():
        manager.initialize()
    return manager
