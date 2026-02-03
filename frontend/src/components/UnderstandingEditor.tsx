import { useState } from "react"
import {
  Brain,
  Check,
  RefreshCw,
  AlertTriangle,
  ClipboardCheck,
  Microscope,
  Users,
  Settings,
  Sparkles,
  Pencil,
  ChevronDown,
  ChevronRight,
  X,
  Code,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Spinner } from "@/components/ui/spinner"
import { ReadStructureVisualizer } from "@/components/ReadStructureVisualizer"
import type { ExperimentUnderstanding, QualityConcern, RecommendedCheck } from "@/types"

interface UnderstandingEditorProps {
  understanding: ExperimentUnderstanding | null
  isLoading: boolean
  onRegenerate: () => void
  onApprove: (edits?: Record<string, string>) => void
}

function getSeverityVariant(severity: string): "destructive" | "warning" | "secondary" | "default" {
  switch (severity) {
    case "critical":
    case "high":
      return "destructive"
    case "medium":
      return "warning"
    default:
      return "secondary"
  }
}

function getPriorityVariant(priority: string): "destructive" | "default" | "secondary" {
  switch (priority) {
    case "required":
      return "destructive"
    case "recommended":
      return "default"
    default:
      return "secondary"
  }
}

function QualityConcernCard({ concern }: { concern: QualityConcern }) {
  return (
    <div className="p-4 rounded-lg border border-border bg-muted/20">
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-sm">{concern.title}</h4>
        <Badge variant={getSeverityVariant(concern.severity)} className="text-xs">
          {concern.severity}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground mb-2">{concern.description}</p>
      {concern.suggested_action && (
        <p className="text-sm text-primary">
          <span className="font-medium">Suggestion:</span> {concern.suggested_action}
        </p>
      )}
      {concern.affected_files.length > 0 && (
        <div className="mt-2">
          <span className="text-xs text-muted-foreground">Affected files: </span>
          <span className="text-xs font-mono">{concern.affected_files.slice(0, 3).join(", ")}</span>
          {concern.affected_files.length > 3 && (
            <span className="text-xs text-muted-foreground">
              {" "}+{concern.affected_files.length - 3} more
            </span>
          )}
        </div>
      )}
    </div>
  )
}

function RecommendedCheckCard({ check }: { check: RecommendedCheck }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="p-4 rounded-lg border border-border bg-muted/20">
      <div
        className="flex items-start justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <h4 className="font-medium text-sm">{check.name}</h4>
        </div>
        <Badge variant={getPriorityVariant(check.priority)} className="text-xs">
          {check.priority}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground mt-2 ml-6">{check.description}</p>
      {expanded && (
        <div className="mt-3 ml-6 space-y-2">
          {check.tool && (
            <p className="text-sm">
              <span className="text-muted-foreground">Tool:</span>{" "}
              <code className="bg-muted px-1 py-0.5 rounded text-xs">{check.tool}</code>
            </p>
          )}
          {check.command_template && (
            <div>
              <span className="text-sm text-muted-foreground">Command:</span>
              <pre className="mt-1 p-2 bg-muted rounded text-xs font-mono overflow-x-auto">
                {check.command_template}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function UnderstandingEditor({
  understanding,
  isLoading,
  onRegenerate,
  onApprove,
}: UnderstandingEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedSummary, setEditedSummary] = useState("")
  const [editedAssayName, setEditedAssayName] = useState("")

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="relative">
            <Spinner size="lg" />
            <Brain className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-6 w-6 text-primary animate-pulse" />
          </div>
          <p className="mt-6 text-lg font-medium">Analyzing Experiment...</p>
          <p className="mt-2 text-muted-foreground text-center max-w-md">
            Gemini is processing your manifest to understand the experiment type,
            identify potential issues, and recommend QC checks.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (!understanding) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Brain className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="text-muted-foreground">No understanding generated yet</p>
        </CardContent>
      </Card>
    )
  }

  const handleStartEditing = () => {
    setEditedSummary(understanding.summary)
    setEditedAssayName(understanding.assay_name)
    setIsEditing(true)
  }

  const handleCancelEditing = () => {
    setIsEditing(false)
    setEditedSummary("")
    setEditedAssayName("")
  }

  const handleApprove = () => {
    if (isEditing) {
      const edits: Record<string, string> = {}
      if (editedSummary !== understanding.summary) {
        edits.summary = editedSummary
      }
      if (editedAssayName !== understanding.assay_name) {
        edits.assay_name = editedAssayName
      }
      onApprove(Object.keys(edits).length > 0 ? edits : undefined)
    } else {
      onApprove()
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            Experiment Understanding
          </h2>
          <p className="text-sm text-muted-foreground">
            Review the LLM's analysis of your experiment
          </p>
        </div>
        <div className="flex items-center gap-2">
          {understanding.is_approved && (
            <Badge variant="success" className="flex items-center gap-1">
              <Check className="h-3 w-3" />
              Approved
            </Badge>
          )}
          {understanding.model_used && (
            <Badge variant="outline">{understanding.model_used}</Badge>
          )}
        </div>
      </div>

      {/* Summary Card */}
      <Card className="border-primary/30">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Summary
          </CardTitle>
          <CardDescription>
            Confidence: {(understanding.experiment_type_confidence * 100).toFixed(0)}%
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isEditing ? (
            <Textarea
              value={editedSummary}
              onChange={(e) => setEditedSummary(e.target.value)}
              className="min-h-[100px]"
            />
          ) : (
            <p className="text-foreground leading-relaxed">{understanding.summary}</p>
          )}
        </CardContent>
      </Card>

      {/* Experiment Details Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Experiment Type */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Microscope className="h-4 w-4 text-secondary" />
              Experiment Type
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="default" className="text-sm">
              {understanding.experiment_type.replace(/_/g, " ")}
            </Badge>
            {understanding.experiment_type_reasoning && (
              <p className="text-xs text-muted-foreground mt-2">
                {understanding.experiment_type_reasoning}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Assay Details */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Settings className="h-4 w-4 text-accent" />
              Assay
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isEditing ? (
              <Input
                value={editedAssayName}
                onChange={(e) => setEditedAssayName(e.target.value)}
              />
            ) : (
              <p className="font-medium">{understanding.assay_name}</p>
            )}
            <Badge variant="outline" className="mt-2">
              {understanding.assay_platform.replace(/_/g, " ")}
            </Badge>
          </CardContent>
        </Card>

        {/* Samples */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" />
              Samples
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{understanding.sample_count}</p>
            {understanding.expected_cells_total && (
              <p className="text-sm text-muted-foreground">
                ~{understanding.expected_cells_total.toLocaleString()} expected cells
              </p>
            )}
          </CardContent>
        </Card>

        {/* Key Parameters */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Key Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {Object.entries(understanding.key_parameters).slice(0, 4).map(([key, value]) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{key}:</span>
                  <span className="font-medium">{value}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Read Structure Visualization */}
      {understanding.read_structure && (
        <ReadStructureVisualizer readStructure={understanding.read_structure} />
      )}

      {/* Detected Scripts */}
      {understanding.detected_scripts && understanding.detected_scripts.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Code className="h-4 w-4 text-accent" />
              Detected Scripts ({understanding.detected_scripts.length})
            </CardTitle>
            <CardDescription>
              Previously existing scripts found in the directory
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {understanding.detected_scripts.map((script, i) => (
                <div key={i} className="p-3 rounded-lg border border-border bg-muted/20">
                  <div className="flex items-center justify-between">
                    <code className="text-sm font-mono">{script.filename || script.name}</code>
                    {script.purpose && (
                      <Badge variant="outline" className="text-xs">
                        {script.purpose}
                      </Badge>
                    )}
                  </div>
                  {script.description && (
                    <p className="text-sm text-muted-foreground mt-1">{script.description}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quality Concerns */}
      {understanding.quality_concerns.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              Quality Concerns ({understanding.quality_concerns.length})
            </CardTitle>
            <CardDescription>
              Potential issues identified in your data
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {understanding.quality_concerns.map((concern, i) => (
                <QualityConcernCard key={i} concern={concern} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recommended Checks */}
      {understanding.recommended_checks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4 text-success" />
              Recommended QC Checks ({understanding.recommended_checks.length})
            </CardTitle>
            <CardDescription>
              Suggested quality control steps to perform
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {understanding.recommended_checks.map((check, i) => (
                <RecommendedCheckCard key={i} check={check} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Pipeline Suggestion */}
      {understanding.suggested_pipeline && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Suggested Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-medium mb-2">{understanding.suggested_pipeline}</p>
            {Object.keys(understanding.pipeline_parameters).length > 0 && (
              <div className="grid grid-cols-2 gap-2 mt-2">
                {Object.entries(understanding.pipeline_parameters).map(([key, value]) => (
                  <div key={key} className="text-sm">
                    <span className="text-muted-foreground">{key}:</span>{" "}
                    <code className="bg-muted px-1 py-0.5 rounded text-xs">{value}</code>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      <div className="flex justify-between items-center pt-4 border-t border-border">
        <Button variant="outline" onClick={onRegenerate} disabled={isLoading}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Regenerate
        </Button>

        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button variant="ghost" onClick={handleCancelEditing}>
                <X className="h-4 w-4 mr-2" />
                Cancel
              </Button>
              <Button onClick={handleApprove}>
                <Check className="h-4 w-4 mr-2" />
                Save & Approve
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={handleStartEditing}>
                <Pencil className="h-4 w-4 mr-2" />
                Edit
              </Button>
              <Button
                onClick={handleApprove}
                disabled={understanding.is_approved}
                className="glow-accent"
              >
                <Check className="h-4 w-4 mr-2" />
                {understanding.is_approved ? "Approved" : "Approve"}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
