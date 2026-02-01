"""File scanner for discovering sequencing files and outputs."""

import os
import re
from datetime import datetime
from pathlib import Path

from aco.manifest.models import (
    DirectoryMetadata,
    FileMetadata,
    FileType,
    ScanResult,
)


# File extension mappings
FASTQ_EXTENSIONS = {".fastq", ".fq", ".fastq.gz", ".fq.gz"}
BAM_EXTENSIONS = {".bam"}
SAM_EXTENSIONS = {".sam"}
CRAM_EXTENSIONS = {".cram"}
VCF_EXTENSIONS = {".vcf", ".vcf.gz", ".bcf"}
BED_EXTENSIONS = {".bed", ".bed.gz"}
GTF_EXTENSIONS = {".gtf", ".gtf.gz", ".gff", ".gff.gz", ".gff3", ".gff3.gz"}

# Compression extensions
COMPRESSION_EXTENSIONS = {".gz": "gzip", ".bz2": "bzip2", ".xz": "xz", ".zst": "zstd"}

# CellRanger directory markers
CELLRANGER_MARKERS = {
    "metrics_summary.csv",
    "web_summary.html",
    "filtered_feature_bc_matrix",
    "raw_feature_bc_matrix",
    "possorted_genome_bam.bam",
}

# Illumina filename patterns
ILLUMINA_PATTERN = re.compile(
    r"^(?P<sample>[^_]+)_(?P<barcode>S\d+)_(?P<lane>L\d+)_(?P<read>R[12])_(?P<segment>\d+)\.fastq(\.gz)?$"
)

# Simple sample name pattern
SAMPLE_PATTERN = re.compile(r"^(?P<sample>[^_\.]+)")


def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def detect_file_type(path: Path) -> FileType:
    """Detect the type of a sequencing file based on extension."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    
    # Handle double extensions like .fastq.gz
    if name.endswith(".fastq.gz") or name.endswith(".fq.gz"):
        return FileType.FASTQ
    if name.endswith(".vcf.gz"):
        return FileType.VCF
    if name.endswith(".bed.gz"):
        return FileType.BED
    if name.endswith(".gtf.gz") or name.endswith(".gff.gz") or name.endswith(".gff3.gz"):
        return FileType.GTF
    
    # Single extensions
    if suffix in FASTQ_EXTENSIONS:
        return FileType.FASTQ
    if suffix in BAM_EXTENSIONS:
        return FileType.BAM
    if suffix in SAM_EXTENSIONS:
        return FileType.SAM
    if suffix in CRAM_EXTENSIONS:
        return FileType.CRAM
    if suffix in VCF_EXTENSIONS:
        return FileType.VCF
    if suffix in BED_EXTENSIONS:
        return FileType.BED
    if suffix in GTF_EXTENSIONS:
        return FileType.GTF
    
    # Special files
    if name == "metrics_summary.csv":
        return FileType.METRICS_CSV
    if name == "web_summary.html":
        return FileType.WEB_SUMMARY
    
    return FileType.UNKNOWN


def detect_compression(path: Path) -> tuple[bool, str | None]:
    """Detect if a file is compressed and what type."""
    name = path.name.lower()
    
    for ext, comp_type in COMPRESSION_EXTENSIONS.items():
        if name.endswith(ext):
            return True, comp_type
    
    return False, None


def parse_fastq_filename(filename: str) -> dict:
    """Parse Illumina-style FASTQ filename for metadata."""
    result = {"sample_name": None, "read_number": None, "lane": None}
    
    # Try Illumina pattern first
    match = ILLUMINA_PATTERN.match(filename)
    if match:
        result["sample_name"] = match.group("sample")
        read = match.group("read")
        result["read_number"] = int(read[1]) if read else None
        result["lane"] = match.group("lane")
        return result
    
    # Fall back to simple sample extraction
    match = SAMPLE_PATTERN.match(filename)
    if match:
        result["sample_name"] = match.group("sample")
    
    # Try to find read number
    if "_R1" in filename or "_r1" in filename or ".R1" in filename:
        result["read_number"] = 1
    elif "_R2" in filename or "_r2" in filename or ".R2" in filename:
        result["read_number"] = 2
    
    return result


def scan_file(path: Path) -> FileMetadata | None:
    """Scan a single file and extract metadata."""
    try:
        stat = path.stat()
        file_type = detect_file_type(path)
        
        # Skip unknown files unless they're in special locations
        if file_type == FileType.UNKNOWN:
            return None
        
        is_compressed, compression_type = detect_compression(path)
        
        # Parse filename for additional metadata
        parsed = {}
        if file_type == FileType.FASTQ:
            parsed = parse_fastq_filename(path.name)
        
        return FileMetadata(
            path=str(path.absolute()),
            filename=path.name,
            file_type=file_type,
            size_bytes=stat.st_size,
            size_human=human_readable_size(stat.st_size),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            is_compressed=is_compressed,
            compression_type=compression_type,
            parent_dir=path.parent.name,
            sample_name=parsed.get("sample_name"),
            read_number=parsed.get("read_number"),
            lane=parsed.get("lane"),
        )
    except (OSError, PermissionError):
        return None


def detect_cellranger_directory(path: Path) -> DirectoryMetadata | None:
    """Check if a directory is a CellRanger output and extract metadata."""
    if not path.is_dir():
        return None
    
    # Look for CellRanger markers
    found_markers = set()
    for item in path.iterdir():
        if item.name in CELLRANGER_MARKERS:
            found_markers.add(item.name)
        elif item.is_dir() and item.name in {"filtered_feature_bc_matrix", "raw_feature_bc_matrix"}:
            found_markers.add(item.name)
    
    # Need at least 2 markers to consider it CellRanger output
    if len(found_markers) < 2:
        return None
    
    # Calculate total size and file count
    total_size = 0
    file_count = 0
    key_files = []
    
    for root, dirs, files in os.walk(path):
        for f in files:
            file_path = Path(root) / f
            try:
                total_size += file_path.stat().st_size
                file_count += 1
                if f in CELLRANGER_MARKERS:
                    key_files.append(f)
            except (OSError, PermissionError):
                continue
    
    return DirectoryMetadata(
        path=str(path.absolute()),
        name=path.name,
        dir_type="cellranger_outs",
        total_size_bytes=total_size,
        total_size_human=human_readable_size(total_size),
        file_count=file_count,
        key_files=key_files,
    )


def scan_directory(
    root_path: str | Path,
    max_depth: int = 10,
    include_hidden: bool = False,
) -> ScanResult:
    """
    Scan a directory recursively for sequencing files.
    
    Args:
        root_path: Path to scan
        max_depth: Maximum directory depth to traverse
        include_hidden: Whether to include hidden files/directories
    
    Returns:
        ScanResult with discovered files and directories
    """
    root = Path(root_path).resolve()
    
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root}")
    
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")
    
    files: list[FileMetadata] = []
    directories: list[DirectoryMetadata] = []
    visited_dirs: set[str] = set()
    
    def should_skip(path: Path) -> bool:
        """Check if path should be skipped."""
        if not include_hidden and path.name.startswith("."):
            return True
        return False
    
    def scan_recursive(current: Path, depth: int = 0):
        """Recursively scan directory."""
        if depth > max_depth:
            return
        
        if str(current.absolute()) in visited_dirs:
            return
        visited_dirs.add(str(current.absolute()))
        
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            return
        
        # Check if this is a CellRanger directory
        if current.name == "outs" or any(
            (current / marker).exists() for marker in ["metrics_summary.csv", "web_summary.html"]
        ):
            cellranger_dir = detect_cellranger_directory(current)
            if cellranger_dir:
                directories.append(cellranger_dir)
                # Don't recurse into CellRanger directories, but still scan for key files
                for entry in entries:
                    if entry.is_file() and not should_skip(entry):
                        file_meta = scan_file(entry)
                        if file_meta:
                            files.append(file_meta)
                return
        
        for entry in entries:
            if should_skip(entry):
                continue
            
            if entry.is_file():
                file_meta = scan_file(entry)
                if file_meta:
                    files.append(file_meta)
            elif entry.is_dir():
                scan_recursive(entry, depth + 1)
    
    scan_recursive(root)
    
    # Calculate totals
    total_size = sum(f.size_bytes for f in files)
    for d in directories:
        total_size += d.total_size_bytes
    
    fastq_count = sum(1 for f in files if f.file_type == FileType.FASTQ)
    bam_count = sum(1 for f in files if f.file_type in {FileType.BAM, FileType.SAM, FileType.CRAM})
    
    return ScanResult(
        scan_path=str(root),
        scanned_at=datetime.now(),
        files=files,
        directories=directories,
        total_files=len(files),
        total_size_bytes=total_size,
        total_size_human=human_readable_size(total_size),
        fastq_count=fastq_count,
        bam_count=bam_count,
        cellranger_count=len(directories),
        other_count=len(files) - fastq_count - bam_count,
    )


async def scan_directory_async(
    root_path: str | Path,
    max_depth: int = 10,
    include_hidden: bool = False,
) -> ScanResult:
    """Async wrapper for scan_directory."""
    import asyncio
    
    return await asyncio.to_thread(
        scan_directory, root_path, max_depth, include_hidden
    )
