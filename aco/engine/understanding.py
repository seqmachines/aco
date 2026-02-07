"""Prompt templates and extraction logic for experiment understanding."""

import logging
from datetime import datetime

from aco.engine.gemini import GeminiClient, get_gemini_client

logger = logging.getLogger(__name__)
from aco.engine.models import (
    AssayPlatform,
    AssayStructure,
    ExperimentType,
    ExperimentUnderstanding,
    QualityConcern,
    ReadSegment,
    ReadStructure,
    RecommendedCheck,
    SampleInfo,
)
from aco.manifest.models import Manifest


SYSTEM_INSTRUCTION = """You are an expert bioinformatics scientist specializing in sequencing quality control. Your role is to analyze experiment manifests and provide structured understanding of sequencing experiments.

You excel at:
- Identifying experiment types from file patterns and user descriptions
- Recognizing sequencing platforms and assay kits from filenames and metadata
- Identifying previous scripts for data processing and their purpose if any
- Inferring sample structure and experimental design
- Identifying potential quality concerns
- Recommending appropriate QC checks

Always be precise and evidence-based in your analysis. If information is ambiguous or missing, clearly indicate your uncertainty and reasoning."""


UNDERSTANDING_PROMPT_TEMPLATE = """Analyze the following sequencing experiment manifest and provide a comprehensive understanding of the experiment.

# Manifest Content

{manifest_content}

# Analysis Instructions

Based on the manifest above, provide:

1. **Experiment Type**: Identify the type of sequencing experiment (e.g., single-cell RNA-seq, bulk RNA-seq, whole genome sequencing, etc.)

2. **Assay Details**: Identify the platform and assay kit used (e.g., 10x Genomics Chromium, Illumina TruSeq, etc.)

3. **Read Structure** (CRITICAL for sequencing runs):
   - Identify the barcode and UMI structure for each read
   - For each segment, specify: name, type (barcode/umi/insert/linker/polyT/index), start position, end position, length
   - Common structures:
     - 10x Chromium 3' v3: R1=28bp (16bp cell barcode + 12bp UMI), R2=91bp (insert)
     - 10x Chromium 5': R1=26bp (16bp CB + 10bp UMI), R2=insert
     - Parse Biosciences: Multiple rounds of barcoding
   - Include confidence level and detection reasoning

4. **Sample Structure**: Identify the samples, their relationships, and any experimental conditions

5. **Key Parameters**: Extract important parameters like expected cell counts, read configurations, reference genomes needed

6. **Detected Scripts**: Look for any existing scripts (.py, .R, .sh, .nf, .wdl, Snakefile, etc.) in the directory that indicate previous processing. For each script, identify its purpose.

7. **Quality Concerns**: Flag any potential issues you notice in the data or setup

8. **Recommended Checks**: Suggest specific QC checks that should be performed

9. **Analysis Script Strategy**: Based on your understanding, think about what analysis scripts would be most valuable:
   - What types of QC scripts should be generated (barcode validation, sequencing health, quality metrics)?
   - What specific analyses would address the user's goals and known issues?
   - What dependencies/tools would be needed?
   - Include this reasoning in your summary.

10. **Summary**: Provide a clear, concise summary of what this experiment is about, including your recommended analysis strategy and what scripts should be generated to investigate the quality concerns and goals

Be specific and reference actual files and metadata from the manifest in your analysis."""


REFERENCE_FILES_ADDENDUM = """

# Attached Reference Files

The following files have been uploaded for your review via the Gemini Files API.
Analyze their contents to better understand previous processing, experimental
protocols, or relevant context. Use details from these files (e.g. barcode
whitelists, argument parsers, processing logic) to produce a more accurate
understanding of the experiment.

Uploaded files: {file_names}
"""


def build_understanding_prompt(
    manifest: Manifest,
    reference_file_paths: list[str] | None = None,
) -> str:
    """Build the prompt for experiment understanding from a manifest.

    Args:
        manifest: The experiment manifest.
        reference_file_paths: Optional list of file paths that will be
            uploaded alongside the prompt. When provided, an extra
            instruction block is appended so the model knows to inspect
            them.

    Returns:
        The formatted prompt string.
    """
    manifest_content = manifest.to_llm_context()
    prompt = UNDERSTANDING_PROMPT_TEMPLATE.format(manifest_content=manifest_content)

    if reference_file_paths:
        from pathlib import Path

        names = ", ".join(Path(p).name for p in reference_file_paths)
        prompt += REFERENCE_FILES_ADDENDUM.format(file_names=names)

    return prompt


def generate_understanding(
    manifest: Manifest,
    client: GeminiClient | None = None,
    reference_file_paths: list[str] | None = None,
) -> ExperimentUnderstanding:
    """
    Generate experiment understanding from a manifest using Gemini.
    
    Args:
        manifest: The manifest to analyze
        client: Optional Gemini client (uses singleton if not provided)
        reference_file_paths: Optional list of local file paths to upload
            via the Gemini Files API for richer context.
    
    Returns:
        ExperimentUnderstanding with inferred experiment details
    """
    if client is None:
        client = get_gemini_client()
    
    prompt = build_understanding_prompt(manifest, reference_file_paths)

    # Filter to files that actually exist
    valid_paths = _filter_existing_paths(reference_file_paths)

    if valid_paths:
        logger.info(
            "Generating understanding with %d reference file(s)", len(valid_paths)
        )
        understanding = client.generate_structured_with_files(
            prompt=prompt,
            file_paths=valid_paths,
            response_schema=ExperimentUnderstanding,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.3,
        )
    else:
        understanding = client.generate_structured(
            prompt=prompt,
            response_schema=ExperimentUnderstanding,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.3,
        )
    
    # Add metadata
    understanding.model_used = client.model_name
    understanding.generated_at = datetime.now()
    
    return understanding


async def generate_understanding_async(
    manifest: Manifest,
    client: GeminiClient | None = None,
    reference_file_paths: list[str] | None = None,
) -> ExperimentUnderstanding:
    """Async version of generate_understanding.

    Args:
        manifest: The manifest to analyze.
        client: Optional Gemini client.
        reference_file_paths: Optional file paths to upload for context.
    """
    if client is None:
        client = get_gemini_client()
    
    prompt = build_understanding_prompt(manifest, reference_file_paths)

    valid_paths = _filter_existing_paths(reference_file_paths)

    if valid_paths:
        logger.info(
            "Generating understanding (async) with %d reference file(s)",
            len(valid_paths),
        )
        understanding = await client.generate_structured_with_files_async(
            prompt=prompt,
            file_paths=valid_paths,
            response_schema=ExperimentUnderstanding,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.3,
        )
    else:
        understanding = await client.generate_structured_async(
            prompt=prompt,
            response_schema=ExperimentUnderstanding,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.3,
        )
    
    # Add metadata
    understanding.model_used = client.model_name
    understanding.generated_at = datetime.now()
    
    return understanding


def _filter_existing_paths(paths: list[str] | None) -> list[str]:
    """Return only paths that exist on disk."""
    if not paths:
        return []
    from pathlib import Path

    valid = [p for p in paths if Path(p).exists()]
    skipped = len(paths) - len(valid)
    if skipped:
        logger.warning("Skipped %d non-existent reference file(s)", skipped)
    return valid


def approve_understanding(
    understanding: ExperimentUnderstanding,
    edits: dict[str, str] | None = None,
) -> ExperimentUnderstanding:
    """
    Approve an experiment understanding, optionally applying edits.
    
    Args:
        understanding: The understanding to approve
        edits: Optional dictionary of field edits to apply
    
    Returns:
        Approved ExperimentUnderstanding
    """
    if edits:
        # Apply edits to the understanding
        for field, value in edits.items():
            if hasattr(understanding, field):
                # Track the edit
                understanding.user_edits[field] = value
                
                # Apply simple string edits
                if isinstance(getattr(understanding, field), str):
                    setattr(understanding, field, value)
                elif field == "experiment_type" and value in ExperimentType.__members__:
                    setattr(understanding, field, ExperimentType(value))
                elif field == "assay_platform" and value in AssayPlatform.__members__:
                    setattr(understanding, field, AssayPlatform(value))
    
    understanding.is_approved = True
    understanding.approved_at = datetime.now()
    
    return understanding


class UnderstandingStore:
    """Simple file-based understanding storage."""
    
    def __init__(self, storage_dir: str):
        """Initialize the understanding store."""
        from pathlib import Path
        import json
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, manifest_id: str):
        """Get the file path for an understanding."""
        from pathlib import Path
        return self.storage_dir / f"understanding_{manifest_id}.json"
    
    def save(self, manifest_id: str, understanding: ExperimentUnderstanding) -> None:
        """Save an understanding to disk."""
        import json
        
        path = self._get_path(manifest_id)
        with open(path, "w") as f:
            json.dump(understanding.model_dump(mode="json"), f, indent=2, default=str)
    
    def load(self, manifest_id: str) -> ExperimentUnderstanding | None:
        """Load an understanding from disk."""
        import json
        
        path = self._get_path(manifest_id)
        if not path.exists():
            return None
        
        with open(path) as f:
            data = json.load(f)
        
        return ExperimentUnderstanding.model_validate(data)
    
    def delete(self, manifest_id: str) -> bool:
        """Delete an understanding from disk."""
        path = self._get_path(manifest_id)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def exists(self, manifest_id: str) -> bool:
        """Check if an understanding exists."""
        return self._get_path(manifest_id).exists()
