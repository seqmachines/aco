"""Pydantic models for experiment understanding and LLM outputs."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExperimentType(str, Enum):
    """Common sequencing experiment types."""

    BULK_RNA_SEQ = "bulk_rna_seq"
    SINGLE_CELL_RNA_SEQ = "single_cell_rna_seq"
    SINGLE_CELL_ATAC_SEQ = "single_cell_atac_seq"
    SINGLE_CELL_MULTIOME = "single_cell_multiome"
    WHOLE_GENOME_SEQ = "whole_genome_seq"
    WHOLE_EXOME_SEQ = "whole_exome_seq"
    TARGETED_SEQ = "targeted_seq"
    AMPLICON_SEQ = "amplicon_seq"
    CHIP_SEQ = "chip_seq"
    ATAC_SEQ = "atac_seq"
    METHYLATION_SEQ = "methylation_seq"
    SPATIAL_TRANSCRIPTOMICS = "spatial_transcriptomics"
    LONG_READ_SEQ = "long_read_seq"
    METAGENOMICS = "metagenomics"
    OTHER = "other"


class AssayPlatform(str, Enum):
    """Common sequencing platforms and assay kits."""

    ILLUMINA_NOVASEQ = "illumina_novaseq"
    ILLUMINA_NEXTSEQ = "illumina_nextseq"
    ILLUMINA_MISEQ = "illumina_miseq"
    ILLUMINA_HISEQ = "illumina_hiseq"
    PACBIO_SEQUEL = "pacbio_sequel"
    PACBIO_REVIO = "pacbio_revio"
    ONT_MINION = "ont_minion"
    ONT_PROMETHION = "ont_promethion"
    TEN_X_CHROMIUM = "10x_chromium"
    TEN_X_VISIUM = "10x_visium"
    PARSE_BIOSCIENCES = "parse_biosciences"
    SCALE_BIO = "scale_bio"
    UNKNOWN = "unknown"


class QualityConcern(BaseModel):
    """A specific quality concern identified by the LLM."""

    title: str = Field(..., description="Short title for the concern")
    description: str = Field(..., description="Detailed description of the concern")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected by this concern"
    )
    suggested_action: str | None = Field(
        default=None, description="Suggested action to address the concern"
    )


class RecommendedCheck(BaseModel):
    """A recommended QC check to perform."""

    name: str = Field(..., description="Name of the QC check")
    description: str = Field(..., description="What this check will verify")
    priority: str = Field(..., description="Priority: required, recommended, optional")
    tool: str | None = Field(default=None, description="Suggested tool to use")
    command_template: str | None = Field(
        default=None, description="Template command to run"
    )
    expected_output: str | None = Field(
        default=None, description="Description of expected output"
    )


class SampleInfo(BaseModel):
    """Information about a sample in the experiment."""

    sample_id: str = Field(..., description="Sample identifier")
    sample_name: str | None = Field(default=None, description="Human-readable sample name")
    condition: str | None = Field(default=None, description="Experimental condition")
    replicate: int | None = Field(default=None, description="Replicate number")
    files: list[str] = Field(default_factory=list, description="Associated files")
    expected_cells: int | None = Field(
        default=None, description="Expected cell count for single-cell"
    )
    notes: str | None = Field(default=None, description="Additional notes")


class AssayStructure(BaseModel):
    """Detailed structure of the assay/experiment."""

    library_type: str = Field(..., description="Type of library preparation")
    read_configuration: str | None = Field(
        default=None, description="Read configuration (e.g., PE150, SE100)"
    )
    expected_read_length: int | None = Field(
        default=None, description="Expected read length in bp"
    )
    index_type: str | None = Field(
        default=None, description="Index/barcode type used"
    )
    umi_present: bool = Field(default=False, description="Whether UMIs are present")
    umi_length: int | None = Field(default=None, description="UMI length if present")
    cell_barcode_length: int | None = Field(
        default=None, description="Cell barcode length for single-cell"
    )
    reference_genome: str | None = Field(
        default=None, description="Reference genome to use"
    )
    annotation_version: str | None = Field(
        default=None, description="Gene annotation version"
    )


class ReadSegment(BaseModel):
    """A segment within a sequencing read (barcode, UMI, insert, etc.)."""
    
    name: str = Field(..., description="Segment name (e.g., 'Cell Barcode', 'UMI', 'Insert')")
    segment_type: str = Field(..., description="Type: barcode, umi, insert, linker, index, polyT, other")
    start_position: int = Field(..., description="Start position (1-based)")
    end_position: int = Field(..., description="End position (1-based, inclusive)")
    length: int = Field(..., description="Segment length in bp")
    read_number: int = Field(default=1, description="Which read (1, 2, or index read I1/I2)")
    description: str | None = Field(default=None, description="Additional description")
    whitelist_file: str | None = Field(default=None, description="Barcode whitelist filename if applicable")


class LibraryType(str, Enum):
    """Library types within a multimodal experiment."""

    GEX = "gex"
    CITE_SEQ = "cite_seq"
    ADT = "adt"
    HTO = "hto"
    ATAC = "atac"
    VDJ_T = "vdj_t"
    VDJ_B = "vdj_b"
    CRISPR = "crispr"
    CUSTOM = "custom"


class ReadStructure(BaseModel):
    """Complete read structure definition for a sequencing assay."""
    
    assay_name: str = Field(..., description="Name of the assay (e.g., '10x Chromium 3' v3')")
    library_type: LibraryType = Field(
        default=LibraryType.GEX,
        description="Library type: gex, cite_seq, adt, hto, atac, vdj_t, vdj_b, crispr, custom",
    )
    total_reads: int = Field(default=2, description="Number of reads (typically 2 for PE)")
    read1_length: int | None = Field(default=None, description="Read 1 length")
    read2_length: int | None = Field(default=None, description="Read 2 length")
    index1_length: int | None = Field(default=None, description="Index 1 (I1) length")
    index2_length: int | None = Field(default=None, description="Index 2 (I2) length")
    
    # Detailed segment breakdown
    segments: list[ReadSegment] = Field(
        default_factory=list, description="All segments in order"
    )
    
    # Summary flags
    has_umi: bool = Field(default=False, description="Whether UMI is present")
    has_cell_barcode: bool = Field(default=False, description="Whether cell barcode is present")
    has_sample_barcode: bool = Field(default=False, description="Whether sample/hashtag barcode is present")
    
    # Confidence
    confidence: float = Field(default=0.0, description="Confidence in structure detection (0-1)")
    detection_notes: str | None = Field(default=None, description="Notes on how structure was detected")


class ExperimentUnderstanding(BaseModel):
    """Complete understanding of an experiment extracted by the LLM."""

    # Core identification
    experiment_type: ExperimentType = Field(
        ..., description="Inferred experiment type"
    )
    experiment_type_confidence: float = Field(
        default=0.0, description="Confidence in experiment type (0-1)"
    )
    experiment_type_reasoning: str | None = Field(
        default=None, description="Reasoning for experiment type classification"
    )
    
    # Assay details
    assay_name: str = Field(..., description="Name/description of the assay")
    assay_platform: AssayPlatform = Field(
        default=AssayPlatform.UNKNOWN, description="Detected platform/kit"
    )
    assay_structure: AssayStructure | None = Field(
        default=None, description="Detailed assay structure"
    )
    
    # Read structure (barcode/UMI layout) -- primary / GEX library
    read_structure: ReadStructure | None = Field(
        default=None, description="Primary read structure (typically GEX) with barcode/UMI segments"
    )
    # Additional read structures for multimodal experiments (CITE-seq/ADT, ATAC, VDJ, etc.)
    additional_read_structures: list[ReadStructure] = Field(
        default_factory=list,
        description="Read structures for additional library types (CITE-seq, ATAC, VDJ, etc.)",
    )
    
    # Detected existing scripts/pipelines
    detected_scripts: list[dict] = Field(
        default_factory=list,
        description="Previously existing scripts found in the directory with their purpose"
    )
    
    # Sample information
    sample_count: int = Field(default=0, description="Number of samples detected")
    samples: list[SampleInfo] = Field(
        default_factory=list, description="Detailed sample information"
    )
    
    # Single-cell specific
    expected_cells_total: int | None = Field(
        default=None, description="Total expected cells across all samples"
    )
    
    # Key parameters inferred
    key_parameters: dict[str, str] = Field(
        default_factory=dict, description="Key parameters inferred from context"
    )
    
    # Quality assessment
    quality_concerns: list[QualityConcern] = Field(
        default_factory=list, description="Identified quality concerns"
    )
    
    # Recommendations
    recommended_checks: list[RecommendedCheck] = Field(
        default_factory=list, description="Recommended QC checks to perform"
    )
    
    # Processing suggestions
    suggested_pipeline: str | None = Field(
        default=None, description="Suggested analysis pipeline"
    )
    pipeline_parameters: dict[str, str] = Field(
        default_factory=dict, description="Suggested pipeline parameters"
    )
    
    # Summary
    summary: str = Field(..., description="Human-readable summary of the experiment")
    
    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.now, description="When understanding was generated"
    )
    model_used: str | None = Field(
        default=None, description="LLM model used for generation"
    )
    
    # Approval tracking
    is_approved: bool = Field(default=False, description="Whether user has approved")
    approved_at: datetime | None = Field(default=None, description="Approval timestamp")
    user_edits: dict[str, str] = Field(
        default_factory=dict, description="Fields edited by user"
    )


class UnderstandingRequest(BaseModel):
    """Request to generate experiment understanding."""

    manifest_id: str = Field(..., description="ID of manifest to process")
    regenerate: bool = Field(
        default=False, description="Whether to regenerate even if exists"
    )
    focus_areas: list[str] = Field(
        default_factory=list, description="Specific areas to focus on"
    )


class UnderstandingApproval(BaseModel):
    """Approval or edit of experiment understanding."""

    understanding_id: str = Field(..., description="ID of understanding to approve")
    approved: bool = Field(..., description="Whether approved")
    edits: dict[str, str] = Field(
        default_factory=dict, description="Any edits to apply"
    )
    feedback: str | None = Field(
        default=None, description="User feedback for improvement"
    )


# ---------------------------------------------------------------------------
# Phase 2: Analyze -- Hypothesis & Goals
# ---------------------------------------------------------------------------


class HypothesisPriority(str, Enum):
    """Priority level for a hypothesis."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UserHypothesis(BaseModel):
    """A single user-declared hypothesis."""

    text: str = Field(..., description="Hypothesis statement")
    priority: HypothesisPriority = Field(
        default=HypothesisPriority.MEDIUM, description="Priority level"
    )
    rationale: str | None = Field(
        default=None, description="Why the user suspects this"
    )


class HypothesisSet(BaseModel):
    """Collection of user hypotheses and goals for a run."""

    manifest_id: str = Field(..., description="Manifest this belongs to")
    what_is_wrong: str = Field(
        default="", description="Free-text: what the user thinks is wrong"
    )
    what_to_prove: str = Field(
        default="", description="Free-text: what the user wants to prove"
    )
    hypotheses: list[UserHypothesis] = Field(
        default_factory=list, description="Structured hypothesis list"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Phase 2: Analyze -- Analysis Strategy
# ---------------------------------------------------------------------------


class HypothesisTest(BaseModel):
    """A single hypothesis mapped to a test method."""

    hypothesis: str = Field(..., description="Hypothesis text")
    test_method: str = Field(..., description="How to test it")
    expected_outcome: str = Field(
        default="", description="What a pass / fail looks like"
    )
    required_data: list[str] = Field(
        default_factory=list, description="Files or data needed"
    )


class GateCheckItem(BaseModel):
    """A single QC gate with pass/fail criteria."""

    gate_name: str = Field(..., description="Human-readable gate name")
    description: str = Field(default="", description="What this gate checks")
    pass_criteria: str = Field(default="", description="Pass condition")
    fail_criteria: str = Field(default="", description="Fail condition")
    module_name: str | None = Field(
        default=None, description="Deterministic module to use (if available)"
    )
    priority: str = Field(default="required", description="required | recommended | optional")


class ExecutionStep(BaseModel):
    """A single step in an ordered execution plan."""

    name: str = Field(..., description="Step name")
    description: str = Field(default="", description="What this step does")
    tool_or_module: str = Field(default="", description="Tool / module to run")
    depends_on: list[str] = Field(
        default_factory=list, description="Names of steps this depends on"
    )
    is_deterministic: bool = Field(
        default=False, description="True if a registered QC module handles this"
    )
    estimated_runtime: str | None = Field(default=None)


class ScriptInsight(BaseModel):
    """Insight extracted from a reference script (safe analysis)."""

    script_path: str = Field(..., description="Path to the analysed script")
    intent: str = Field(default="", description="What the script does")
    parameters: dict[str, str] = Field(
        default_factory=dict, description="Key parameters extracted"
    )
    adaptation_notes: list[str] = Field(
        default_factory=list,
        description="Diff-aware suggestions for adapting to new data",
    )


class AnalysisStrategy(BaseModel):
    """LLM-generated analysis strategy for a run."""

    manifest_id: str = Field(..., description="Manifest this belongs to")
    hypotheses_to_test: list[HypothesisTest] = Field(default_factory=list)
    gate_checklist: list[GateCheckItem] = Field(default_factory=list)
    required_modules: list[str] = Field(
        default_factory=list, description="Deterministic QC modules needed"
    )
    required_tools: list[str] = Field(
        default_factory=list, description="External tools needed (samtools, etc.)"
    )
    execution_plan: list[ExecutionStep] = Field(default_factory=list)
    script_insights: list[ScriptInsight] = Field(
        default_factory=list,
        description="Insights from reference scripts (safe analysis)",
    )
    summary: str = Field(default="", description="Human-readable strategy summary")
    user_approach: str | None = Field(
        default=None, description="User-specified analysis approach"
    )
    generated_at: datetime = Field(default_factory=datetime.now)
    model_used: str | None = None
    is_approved: bool = False


# ---------------------------------------------------------------------------
# Phase 3: Summarize -- Plot selection
# ---------------------------------------------------------------------------


class PlotSelection(BaseModel):
    """User's choice of plots and tests for notebook generation."""

    manifest_id: str = Field(..., description="Manifest this belongs to")
    selected_plots: list[str] = Field(
        default_factory=list, description="IDs of selected plot types"
    )
    custom_plot_requests: str = Field(
        default="", description="Free-text custom plot requests"
    )
    selected_tests: list[str] = Field(
        default_factory=list,
        description="Statistical tests to include (e.g. t_test, chi_square)",
    )
    created_at: datetime = Field(default_factory=datetime.now)
