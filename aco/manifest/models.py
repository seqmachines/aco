"""Pydantic models for manifest data structures."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class FileType(str, Enum):
    """Types of sequencing files that can be detected."""

    FASTQ = "fastq"
    BAM = "bam"
    SAM = "sam"
    CRAM = "cram"
    CELLRANGER_OUTS = "cellranger_outs"
    METRICS_CSV = "metrics_csv"
    WEB_SUMMARY = "web_summary"
    VCF = "vcf"
    BED = "bed"
    GTF = "gtf"
    UNKNOWN = "unknown"


class FileMetadata(BaseModel):
    """Metadata for a discovered sequencing file."""

    path: str = Field(..., description="Absolute path to the file")
    filename: str = Field(..., description="Name of the file")
    file_type: FileType = Field(..., description="Detected file type")
    size_bytes: int = Field(..., description="File size in bytes")
    size_human: str = Field(..., description="Human-readable file size")
    modified_at: datetime = Field(..., description="Last modification timestamp")
    is_compressed: bool = Field(default=False, description="Whether file is compressed")
    compression_type: str | None = Field(default=None, description="Compression type if any")
    parent_dir: str = Field(..., description="Parent directory name")
    
    # Optional parsed metadata from filename patterns
    sample_name: str | None = Field(default=None, description="Inferred sample name")
    read_number: int | None = Field(default=None, description="Read number (R1, R2)")
    lane: str | None = Field(default=None, description="Sequencing lane if detectable")


class DirectoryMetadata(BaseModel):
    """Metadata for a discovered directory (e.g., CellRanger outs)."""

    path: str = Field(..., description="Absolute path to the directory")
    name: str = Field(..., description="Directory name")
    dir_type: str = Field(..., description="Type of directory structure")
    total_size_bytes: int = Field(..., description="Total size of directory contents")
    total_size_human: str = Field(..., description="Human-readable total size")
    file_count: int = Field(..., description="Number of files in directory")
    key_files: list[str] = Field(default_factory=list, description="Important files found")


class ScanResult(BaseModel):
    """Result of scanning a directory for sequencing files."""

    scan_path: str = Field(..., description="Root path that was scanned")
    scanned_at: datetime = Field(default_factory=datetime.now, description="Scan timestamp")
    files: list[FileMetadata] = Field(default_factory=list, description="Discovered files")
    directories: list[DirectoryMetadata] = Field(
        default_factory=list, description="Discovered special directories"
    )
    total_files: int = Field(default=0, description="Total number of files found")
    total_size_bytes: int = Field(default=0, description="Total size of all files")
    total_size_human: str = Field(default="0 B", description="Human-readable total size")
    
    # Categorized counts
    fastq_count: int = Field(default=0, description="Number of FASTQ files")
    bam_count: int = Field(default=0, description="Number of BAM files")
    cellranger_count: int = Field(default=0, description="Number of CellRanger outputs")
    other_count: int = Field(default=0, description="Number of other files")


class DocumentReference(BaseModel):
    """Reference to an uploaded or linked document."""

    filename: str = Field(..., description="Original filename")
    path: str | None = Field(default=None, description="Path if local file")
    content_type: str | None = Field(default=None, description="MIME type")
    size_bytes: int | None = Field(default=None, description="File size")
    description: str | None = Field(default=None, description="User description of document")
    extracted_text: str | None = Field(default=None, description="Extracted text content")


class UserIntake(BaseModel):
    """User-provided experiment information."""

    experiment_description: str = Field(
        ..., description="Description of the experiment and its goals"
    )
    goals: str | None = Field(default=None, description="Specific goals and objectives")
    known_issues: str | None = Field(
        default=None, description="Known potential issues or concerns"
    )
    documents: list[DocumentReference] = Field(
        default_factory=list, description="Uploaded documentation references"
    )
    target_directory: str = Field(..., description="Directory to scan for sequencing files")
    additional_notes: str | None = Field(default=None, description="Any additional notes")
    
    created_at: datetime = Field(default_factory=datetime.now, description="Intake timestamp")


class Manifest(BaseModel):
    """Consolidated manifest combining user input and file metadata."""

    id: str = Field(..., description="Unique manifest identifier")
    version: str = Field(default="1.0", description="Manifest schema version")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    
    # User-provided information
    user_intake: UserIntake = Field(..., description="User intake information")
    
    # Scan results
    scan_result: ScanResult | None = Field(default=None, description="File scan results")
    
    # Status tracking
    status: str = Field(default="draft", description="Manifest status")
    
    # Additional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    def to_llm_context(self) -> str:
        """Convert manifest to a text representation for LLM processing."""
        parts = []
        
        # User description
        parts.append("## Experiment Description")
        parts.append(self.user_intake.experiment_description)
        
        if self.user_intake.goals:
            parts.append("\n## Goals")
            parts.append(self.user_intake.goals)
        
        if self.user_intake.known_issues:
            parts.append("\n## Known Issues/Concerns")
            parts.append(self.user_intake.known_issues)
        
        if self.user_intake.documents:
            parts.append("\n## Referenced Documentation")
            for doc in self.user_intake.documents:
                parts.append(f"- {doc.filename}")
                if doc.description:
                    parts.append(f"  Description: {doc.description}")
                if doc.extracted_text:
                    parts.append(f"  Content: {doc.extracted_text[:500]}...")
        
        if self.scan_result:
            parts.append("\n## Discovered Files")
            parts.append(f"Scanned: {self.scan_result.scan_path}")
            parts.append(f"Total files: {self.scan_result.total_files}")
            parts.append(f"Total size: {self.scan_result.total_size_human}")
            
            if self.scan_result.fastq_count:
                parts.append(f"\n### FASTQ Files ({self.scan_result.fastq_count})")
                for f in self.scan_result.files:
                    if f.file_type == FileType.FASTQ:
                        parts.append(f"- {f.filename} ({f.size_human})")
                        if f.sample_name:
                            parts.append(f"  Sample: {f.sample_name}")
            
            if self.scan_result.bam_count:
                parts.append(f"\n### BAM Files ({self.scan_result.bam_count})")
                for f in self.scan_result.files:
                    if f.file_type == FileType.BAM:
                        parts.append(f"- {f.filename} ({f.size_human})")
            
            if self.scan_result.directories:
                parts.append("\n### Special Directories")
                for d in self.scan_result.directories:
                    parts.append(f"- {d.name} ({d.dir_type})")
                    parts.append(f"  Files: {d.file_count}, Size: {d.total_size_human}")
        
        if self.user_intake.additional_notes:
            parts.append("\n## Additional Notes")
            parts.append(self.user_intake.additional_notes)
        
        return "\n".join(parts)
