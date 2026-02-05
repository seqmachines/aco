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

// Read structure definition
export interface ReadStructure {
  assay_name: string;
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

// App state types
export type AppStep = "intake" | "scanning" | "manifest" | "understanding" | "scripts" | "notebook" | "report" | "approved";

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
  generated_at: string;
  is_approved: boolean;
}

// Chat message for plan feedback
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

// Chat API response
export interface ChatResponse {
  response: string;
  artifact_updated: boolean;
  updated_data?: Record<string, unknown>;
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
