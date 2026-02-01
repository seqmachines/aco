"""Prompt templates and extraction logic for experiment understanding."""

from datetime import datetime

from aco.engine.gemini import GeminiClient, get_gemini_client
from aco.engine.models import (
    AssayPlatform,
    AssayStructure,
    ExperimentType,
    ExperimentUnderstanding,
    QualityConcern,
    RecommendedCheck,
    SampleInfo,
)
from aco.manifest.models import Manifest


SYSTEM_INSTRUCTION = """You are an expert bioinformatics scientist specializing in sequencing quality control. Your role is to analyze experiment manifests and provide structured understanding of sequencing experiments.

You excel at:
- Identifying experiment types from file patterns and user descriptions
- Recognizing sequencing platforms and assay kits from filenames and metadata
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

3. **Sample Structure**: Identify the samples, their relationships, and any experimental conditions

4. **Key Parameters**: Extract important parameters like expected cell counts, read configurations, reference genomes needed

5. **Quality Concerns**: Flag any potential issues you notice in the data or setup

6. **Recommended Checks**: Suggest specific QC checks that should be performed

7. **Summary**: Provide a clear, concise summary of what this experiment is about

Be specific and reference actual files and metadata from the manifest in your analysis."""


def build_understanding_prompt(manifest: Manifest) -> str:
    """Build the prompt for experiment understanding from a manifest."""
    manifest_content = manifest.to_llm_context()
    return UNDERSTANDING_PROMPT_TEMPLATE.format(manifest_content=manifest_content)


def generate_understanding(
    manifest: Manifest,
    client: GeminiClient | None = None,
) -> ExperimentUnderstanding:
    """
    Generate experiment understanding from a manifest using Gemini.
    
    Args:
        manifest: The manifest to analyze
        client: Optional Gemini client (uses singleton if not provided)
    
    Returns:
        ExperimentUnderstanding with inferred experiment details
    """
    if client is None:
        client = get_gemini_client()
    
    prompt = build_understanding_prompt(manifest)
    
    understanding = client.generate_structured(
        prompt=prompt,
        response_schema=ExperimentUnderstanding,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.3,  # Lower temperature for more consistent structured output
    )
    
    # Add metadata
    understanding.model_used = client.model_name
    understanding.generated_at = datetime.now()
    
    return understanding


async def generate_understanding_async(
    manifest: Manifest,
    client: GeminiClient | None = None,
) -> ExperimentUnderstanding:
    """Async version of generate_understanding."""
    if client is None:
        client = get_gemini_client()
    
    prompt = build_understanding_prompt(manifest)
    
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
