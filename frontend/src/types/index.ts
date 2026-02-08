/**
 * TypeScript types matching the backend Pydantic models
 */

// File types enum
export type FileType =
  | "fastq"
  | "bam"
  | "sam"
  | "cram"
  | "cellranger_outs"
  | "metrics_csv"
  | "web_summary"
  | "vcf"
  | "bed"
  | "gtf"
  | "unknown";

// File metadata
export interface FileMetadata {
  path: string;
  filename: string;
  file_type: FileType;
  size_bytes: number;
  size_human: string;
  modified_at: string;
  is_compressed: boolean;
  compression_type: string | null;
  parent_dir: string;
  sample_name: string | null;
  read_number: number | null;
  lane: string | null;
}

// Directory metadata
export interface DirectoryMetadata {
  path: string;
  name: string;
  dir_type: string;
  total_size_bytes: number;
  total_size_human: string;
  file_count: number;
  key_files: string[];
}

// Scan result
export interface ScanResult {
  scan_path: string;
  scanned_at: string;
  files: FileMetadata[];
  directories: DirectoryMetadata[];
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  fastq_count: number;
  bam_count: number;
  cellranger_count: number;
  other_count: number;
}

// Document reference
export interface DocumentReference {
  filename: string;
  path: string | null;
  content_type: string | null;
  size_bytes: number | null;
  description: string | null;
  extracted_text: string | null;
}

// User intake
export interface UserIntake {
  experiment_description: string;
  goals: string | null;
  known_issues: string | null;
  documents: DocumentReference[];
  target_directory: string;
  additional_notes: string | null;
  created_at: string;
}

// Manifest
export interface Manifest {
  id: string;
  version: string;
  created_at: string;
  updated_at: string;
  user_intake: UserIntake;
  scan_result: ScanResult | null;
  status: string;
  metadata: Record<string, unknown>;
}

// Experiment types
export type ExperimentType =
  | "bulk_rna_seq"
  | "single_cell_rna_seq"
  | "single_cell_atac_seq"
  | "single_cell_multiome"
  | "whole_genome_seq"
  | "whole_exome_seq"
  | "targeted_seq"
  | "amplicon_seq"
  | "chip_seq"
  | "atac_seq"
  | "methylation_seq"
  | "spatial_transcriptomics"
  | "long_read_seq"
  | "metagenomics"
  | "other";

// Assay platforms
export type AssayPlatform =
  | "illumina_novaseq"
  | "illumina_nextseq"
  | "illumina_miseq"
  | "illumina_hiseq"
  | "pacbio_sequel"
  | "pacbio_revio"
  | "ont_minion"
  | "ont_promethion"
  | "10x_chromium"
  | "10x_visium"
  | "parse_biosciences"
  | "scale_bio"
  | "unknown";

// Quality concern
export interface QualityConcern {
  title: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  affected_files: string[];
  suggested_action: string | null;
}

// Recommended check
export interface RecommendedCheck {
  name: string;
  description: string;
  priority: "required" | "recommended" | "optional";
  tool: string | null;
  command_template: string | null;
  expected_output: string | null;
}

// Sample info
export interface SampleInfo {
  sample_id: string;
  sample_name: string | null;
  condition: string | null;
  replicate: number | null;
  files: string[];
  expected_cells: number | null;
  notes: string | null;
}

// Assay structure
export interface AssayStructure {
  library_type: string;
  read_configuration: string | null;
  expected_read_length: number | null;
  index_type: string | null;
  umi_present: boolean;
  umi_length: number | null;
  cell_barcode_length: number | null;
  reference_genome: string | null;
  annotation_version: string | null;
}

// Read segment (barcode, UMI, insert, etc.)
export interface ReadSegment {
  name: string;
  segment_type: string;
  start_position: number;
  end_position: number;
  length: number;
  read_number: number;
  description: string | null;
  whitelist_file: string | null;
}

// Library types for multimodal experiments
export type LibraryType =
  | "gex"
  | "cite_seq"
  | "adt"
  | "hto"
  | "atac"
  | "vdj_t"
  | "vdj_b"
  | "crispr"
  | "custom";

// Read structure definition
export interface ReadStructure {
  assay_name: string;
  library_type: LibraryType;
  total_reads: number;
  read1_length: number | null;
  read2_length: number | null;
  index1_length: number | null;
  index2_length: number | null;
  segments: ReadSegment[];
  has_umi: boolean;
  has_cell_barcode: boolean;
  has_sample_barcode: boolean;
  confidence: number;
  detection_notes: string | null;
}

// Detected script
export interface DetectedScript {
  filename: string;
  name: string;
  purpose: string | null;
  description: string | null;
}

// Experiment understanding
export interface ExperimentUnderstanding {
  experiment_type: ExperimentType;
  experiment_type_confidence: number;
  experiment_type_reasoning: string | null;
  assay_name: string;
  assay_platform: AssayPlatform;
  assay_structure: AssayStructure | null;
  read_structure: ReadStructure | null;
  additional_read_structures: ReadStructure[];
  detected_scripts: DetectedScript[];
  sample_count: number;
  samples: SampleInfo[];
  expected_cells_total: number | null;
  key_parameters: Record<string, string>;
  quality_concerns: QualityConcern[];
  recommended_checks: RecommendedCheck[];
  suggested_pipeline: string | null;
  pipeline_parameters: Record<string, string>;
  summary: string;
  generated_at: string;
  model_used: string | null;
  is_approved: boolean;
  approved_at: string | null;
  user_edits: Record<string, string>;
}

// API Response types
export interface IntakeResponse {
  manifest_id: string;
  message: string;
  manifest: Manifest;
}

export interface ScanResponse {
  message: string;
  result: ScanResult;
}

export interface ManifestResponse {
  manifest: Manifest;
}

export interface ManifestListResponse {
  manifest_ids: string[];
  count: number;
}

export interface UnderstandingResponse {
  manifest_id: string;
  understanding: ExperimentUnderstanding;
}

export interface ApprovalResponse {
  manifest_id: string;
  understanding: ExperimentUnderstanding;
  message: string;
}

// ---------------------------------------------------------------------------
// Workflow phases & steps
// ---------------------------------------------------------------------------

/** Top-level workflow phases */
export type Phase = "understand" | "analyze" | "summarize";

/** Sub-steps within each phase */
export type UnderstandStep = "describe" | "scan" | "understanding";
export type AnalyzeStep = "hypothesis" | "strategy" | "execute";
export type SummarizeStep = "plots" | "notebook" | "report" | "optimize";

/** Flat union of every possible step (used as the primary navigation key) */
export type AppStep = UnderstandStep | AnalyzeStep | SummarizeStep;

/** Describes a single sub-step in the sidebar / progress bar */
export interface StepDefinition {
  id: AppStep;
  label: string;
  shortLabel: string;
}

/** Describes a top-level phase containing ordered sub-steps */
export interface PhaseDefinition {
  id: Phase;
  label: string;
  shortLabel: string;
  steps: StepDefinition[];
}

/** Canonical phase & step ordering used by the sidebar and progress bar */
export const PHASES: PhaseDefinition[] = [
  {
    id: "understand",
    label: "Understand",
    shortLabel: "Understand",
    steps: [
      { id: "describe", label: "Describe Your Experiment", shortLabel: "Describe" },
      { id: "scan", label: "Scan & Index Files", shortLabel: "Scan" },
      { id: "understanding", label: "Experiment Understanding", shortLabel: "Understanding" },
    ],
  },
  {
    id: "analyze",
    label: "Analyze",
    shortLabel: "Analyze",
    steps: [
      { id: "hypothesis", label: "Reference", shortLabel: "Reference" },
      { id: "strategy", label: "Analysis Strategy", shortLabel: "Strategy" },
      { id: "execute", label: "Execute Plan", shortLabel: "Execute" },
    ],
  },
  {
    id: "summarize",
    label: "Summarize",
    shortLabel: "Summarize",
    steps: [
      { id: "plots", label: "Choose Plots & Tests", shortLabel: "Plots" },
      { id: "notebook", label: "Analysis Notebook", shortLabel: "Notebook" },
      { id: "report", label: "Export Report", shortLabel: "Report" },
      { id: "optimize", label: "Optimize & Chat", shortLabel: "Optimize" },
    ],
  },
];

/** Flat ordered list of all steps (derived from PHASES) */
export const ALL_STEPS: AppStep[] = PHASES.flatMap((p) => p.steps.map((s) => s.id));

/** Look up which phase a step belongs to */
export function phaseForStep(step: AppStep): Phase {
  for (const phase of PHASES) {
    if (phase.steps.some((s) => s.id === step)) return phase.id;
  }
  return "understand";
}

/** Get the flat index of a step across all phases */
export function stepIndex(step: AppStep): number {
  return ALL_STEPS.indexOf(step);
}

/** Get the StepDefinition for a given step id */
export function stepDef(step: AppStep): StepDefinition | undefined {
  for (const phase of PHASES) {
    const found = phase.steps.find((s) => s.id === step);
    if (found) return found;
  }
  return undefined;
}

// App state types
export interface AppState {
  currentStep: AppStep;
  manifest: Manifest | null;
  understanding: ExperimentUnderstanding | null;
  isLoading: boolean;
  error: string | null;
}

// Intake form data (for auto-save)
export interface IntakeFormData {
  experiment_description: string;
  target_directory: string;
  goals?: string;
  known_issues?: string;
  additional_notes?: string;
  uploaded_files?: UploadedFile[];
}

export interface UploadedFile {
  name: string;
  size: number;
  type: string;
  dataUrl?: string; // For images
  content?: string; // For text files
}

// Config response
export interface ConfigResponse {
  working_dir: string;
  storage_dir: string;
  has_api_key: boolean;
  api_key_masked: string | null;
  api_key: string | null;
}

// Script plan types (for displaying draft plan on understanding page)
export interface PlannedScript {
  name: string;
  category: string;
  script_type: string;
  description: string;
  code: string;
  dependencies: string[];
  input_files: string[];
  output_files: string[];
  estimated_runtime: string | null;
  requires_approval: boolean;
}

export interface ScriptPlan {
  manifest_id: string;
  scripts: PlannedScript[];
  execution_order: string[];
  total_estimated_runtime: string | null;
  usage_instructions: string | null;
  generated_at: string;
  is_approved: boolean;
}

// Chat message for plan feedback
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface ScriptPlanModifiedItem {
  name: string;
  changed_fields: string[];
}

export interface ScriptPlanChangeSummary {
  added_scripts: string[];
  removed_scripts: string[];
  modified_scripts: ScriptPlanModifiedItem[];
  execution_order_changed: boolean;
  old_execution_order: string[];
  new_execution_order: string[];
  total_estimated_runtime_changed?: boolean;
  old_total_estimated_runtime?: string | null;
  new_total_estimated_runtime?: string | null;
}

// Chat API response
export interface ChatResponse {
  response: string;
  artifact_updated: boolean;
  updated_data?: Record<string, unknown>;
  change_summary?: ScriptPlanChangeSummary;
}

// Chat history response
export interface ChatHistoryResponse {
  manifest_id: string;
  step: string;
  messages: ChatMessage[];
}

// Pipeline phases
export type PipelinePhase =
  | "idle"
  | "generating_code"
  | "creating_env"
  | "installing_deps"
  | "executing"
  | "complete"
  | "failed";

// Pipeline step result
export interface PipelineStepResult {
  step: string;
  success: boolean;
  message: string;
}

// Pipeline response
export interface ExecutePipelineResponse {
  manifest_id: string;
  steps: PipelineStepResult[];
  execution_results: ExecutionResult[];
  all_succeeded: boolean;
  message: string;
}

// ---------------------------------------------------------------------------
// Phase 2: Analyze types
// ---------------------------------------------------------------------------

export interface UserHypothesis {
  text: string;
  priority: "high" | "medium" | "low";
  rationale: string | null;
}

export interface HypothesisSet {
  manifest_id: string;
  what_is_wrong: string;
  what_to_prove: string;
  hypotheses: UserHypothesis[];
  created_at: string;
  updated_at: string;
}

export interface SelectedReference {
  path: string;
  name: string;
  ref_type: "script" | "prior_run" | "protocol";
  description: string;
}

export interface HypothesisTest {
  hypothesis: string;
  test_method: string;
  expected_outcome: string;
  required_data: string[];
}

export interface GateCheckItem {
  gate_name: string;
  description: string;
  pass_criteria: string;
  fail_criteria: string;
  module_name: string | null;
  priority: string;
}

export interface ExecutionStepDef {
  name: string;
  description: string;
  tool_or_module: string;
  depends_on: string[];
  is_deterministic: boolean;
  estimated_runtime: string | null;
}

export interface ScriptInsight {
  script_path: string;
  intent: string;
  parameters: Record<string, string>;
  adaptation_notes: string[];
}

export interface AnalysisStrategy {
  manifest_id: string;
  hypotheses_to_test: HypothesisTest[];
  gate_checklist: GateCheckItem[];
  required_modules: string[];
  required_tools: string[];
  execution_plan: ExecutionStepDef[];
  script_insights: ScriptInsight[];
  summary: string;
  user_approach: string | null;
  generated_at: string;
  model_used: string | null;
  is_approved: boolean;
}

export interface PlotSelection {
  manifest_id: string;
  selected_plots: string[];
  custom_plot_requests: string;
  selected_tests: string[];
  created_at: string;
}

// Existing script info (from /scripts/existing endpoint)
export interface ExistingScriptInfo {
  path: string;
  name: string;
  size_bytes: number;
  preview: string;
  source: "data_dir" | "previous_run";
}

// Execution result
export interface ExecutionResult {
  script_name: string;
  success: boolean;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_seconds: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  output_files: string[];
}
