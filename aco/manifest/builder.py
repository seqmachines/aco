"""Manifest builder to combine user input with file metadata."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from aco.manifest.models import (
    DocumentReference,
    Manifest,
    ScanResult,
    UserIntake,
)
from aco.manifest.scanner import scan_directory, scan_directory_async


def generate_manifest_id() -> str:
    """Generate a unique manifest ID."""
    return f"manifest_{uuid.uuid4().hex[:12]}"


def build_manifest(
    experiment_description: str,
    target_directory: str,
    goals: str | None = None,
    known_issues: str | None = None,
    documents: list[DocumentReference] | None = None,
    additional_notes: str | None = None,
    scan_files: bool = True,
    max_scan_depth: int = 10,
) -> Manifest:
    """
    Build a manifest from user input and optional file scan.
    
    Args:
        experiment_description: User's description of the experiment
        target_directory: Directory containing sequencing files
        goals: Specific goals and objectives
        known_issues: Known potential issues
        documents: Referenced documentation
        additional_notes: Additional notes
        scan_files: Whether to scan for files
        max_scan_depth: Maximum directory depth for scanning
    
    Returns:
        Complete Manifest object
    """
    # Create user intake
    user_intake = UserIntake(
        experiment_description=experiment_description,
        goals=goals,
        known_issues=known_issues,
        documents=documents or [],
        target_directory=target_directory,
        additional_notes=additional_notes,
    )
    
    # Scan for files if requested
    scan_result = None
    if scan_files and target_directory:
        target_path = Path(target_directory)
        if target_path.exists() and target_path.is_dir():
            scan_result = scan_directory(target_path, max_depth=max_scan_depth)
    
    # Build manifest
    manifest = Manifest(
        id=generate_manifest_id(),
        user_intake=user_intake,
        scan_result=scan_result,
        status="draft",
    )
    
    return manifest


async def build_manifest_async(
    experiment_description: str,
    target_directory: str,
    goals: str | None = None,
    known_issues: str | None = None,
    documents: list[DocumentReference] | None = None,
    additional_notes: str | None = None,
    scan_files: bool = True,
    max_scan_depth: int = 10,
) -> Manifest:
    """Async version of build_manifest."""
    # Create user intake
    user_intake = UserIntake(
        experiment_description=experiment_description,
        goals=goals,
        known_issues=known_issues,
        documents=documents or [],
        target_directory=target_directory,
        additional_notes=additional_notes,
    )
    
    # Scan for files if requested
    scan_result = None
    if scan_files and target_directory:
        target_path = Path(target_directory)
        if target_path.exists() and target_path.is_dir():
            scan_result = await scan_directory_async(target_path, max_depth=max_scan_depth)
    
    # Build manifest
    manifest = Manifest(
        id=generate_manifest_id(),
        user_intake=user_intake,
        scan_result=scan_result,
        status="draft",
    )
    
    return manifest


def update_manifest(
    manifest: Manifest,
    experiment_description: str | None = None,
    goals: str | None = None,
    known_issues: str | None = None,
    additional_notes: str | None = None,
    rescan: bool = False,
) -> Manifest:
    """
    Update an existing manifest with new information.
    
    Args:
        manifest: Existing manifest to update
        experiment_description: New description (if provided)
        goals: New goals (if provided)
        known_issues: New known issues (if provided)
        additional_notes: New additional notes (if provided)
        rescan: Whether to rescan the directory
    
    Returns:
        Updated Manifest object
    """
    # Update user intake fields if provided
    if experiment_description is not None:
        manifest.user_intake.experiment_description = experiment_description
    if goals is not None:
        manifest.user_intake.goals = goals
    if known_issues is not None:
        manifest.user_intake.known_issues = known_issues
    if additional_notes is not None:
        manifest.user_intake.additional_notes = additional_notes
    
    # Rescan if requested
    if rescan and manifest.user_intake.target_directory:
        target_path = Path(manifest.user_intake.target_directory)
        if target_path.exists() and target_path.is_dir():
            manifest.scan_result = scan_directory(target_path)
    
    manifest.updated_at = datetime.now()
    
    return manifest


class ManifestStore:
    """Simple file-based manifest storage."""
    
    def __init__(self, storage_dir: str | Path):
        """Initialize the manifest store."""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, manifest_id: str) -> Path:
        """Get the file path for a manifest."""
        return self.storage_dir / f"{manifest_id}.json"
    
    def save(self, manifest: Manifest) -> None:
        """Save a manifest to disk."""
        path = self._get_path(manifest.id)
        with open(path, "w") as f:
            json.dump(manifest.model_dump(mode="json"), f, indent=2, default=str)
    
    def load(self, manifest_id: str) -> Manifest | None:
        """Load a manifest from disk."""
        path = self._get_path(manifest_id)
        if not path.exists():
            return None
        
        with open(path) as f:
            data = json.load(f)
        
        return Manifest.model_validate(data)
    
    def delete(self, manifest_id: str) -> bool:
        """Delete a manifest from disk."""
        path = self._get_path(manifest_id)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def list_all(self) -> list[str]:
        """List all manifest IDs."""
        return [
            p.stem for p in self.storage_dir.glob("manifest_*.json")
        ]
    
    def get_latest(self) -> Manifest | None:
        """Get the most recently modified manifest."""
        manifests = list(self.storage_dir.glob("manifest_*.json"))
        if not manifests:
            return None
        
        latest = max(manifests, key=lambda p: p.stat().st_mtime)
        return self.load(latest.stem)
