import { useState } from "react"
import {
  FileJson,
  Pencil,
  Save,
  X,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Beaker,
  Target,
  AlertTriangle,
  FileText,
  ArrowRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { FileScanner } from "@/components/FileScanner"
import type { Manifest } from "@/types"

interface ManifestViewerProps {
  manifest: Manifest
  onUpdate: (data: {
    experiment_description?: string
    goals?: string
    known_issues?: string
    additional_notes?: string
    rescan?: boolean
  }) => Promise<void>
  onProceed: () => void
  isLoading: boolean
}

export function ManifestViewer({
  manifest,
  onUpdate,
  onProceed,
  isLoading,
}: ManifestViewerProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedDescription, setEditedDescription] = useState(
    manifest.user_intake.experiment_description
  )
  const [editedGoals, setEditedGoals] = useState(manifest.user_intake.goals || "")
  const [editedIssues, setEditedIssues] = useState(manifest.user_intake.known_issues || "")
  const [showJson, setShowJson] = useState(false)
  const [showFiles, setShowFiles] = useState(true)

  const handleSave = async () => {
    await onUpdate({
      experiment_description: editedDescription,
      goals: editedGoals || undefined,
      known_issues: editedIssues || undefined,
    })
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditedDescription(manifest.user_intake.experiment_description)
    setEditedGoals(manifest.user_intake.goals || "")
    setEditedIssues(manifest.user_intake.known_issues || "")
    setIsEditing(false)
  }

  const handleRescan = async () => {
    await onUpdate({ rescan: true })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <FileJson className="h-5 w-5 text-primary" />
            Run Data Review
          </h2>
          <p className="text-sm text-muted-foreground">
            Review and edit your experiment information before analysis
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">Run: {manifest.id}</Badge>
          <Badge variant={manifest.status === "draft" ? "warning" : "success"}>
            {manifest.status}
          </Badge>
        </div>
      </div>

      {/* User Intake Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Beaker className="h-4 w-4 text-primary" />
              Experiment Information
            </CardTitle>
            <CardDescription>
              Created: {new Date(manifest.created_at).toLocaleString()}
            </CardDescription>
          </div>
          {!isEditing && (
            <Button variant="ghost" size="sm" onClick={() => setIsEditing(true)}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Description */}
          <div>
            <label className="text-sm font-medium flex items-center gap-2 mb-2">
              <Beaker className="h-4 w-4 text-muted-foreground" />
              Description
            </label>
            {isEditing ? (
              <Textarea
                value={editedDescription}
                onChange={(e) => setEditedDescription(e.target.value)}
                className="min-h-[100px]"
              />
            ) : (
              <p className="text-sm text-foreground bg-muted/30 p-3 rounded-lg">
                {manifest.user_intake.experiment_description}
              </p>
            )}
          </div>

          {/* Goals */}
          <div>
            <label className="text-sm font-medium flex items-center gap-2 mb-2">
              <Target className="h-4 w-4 text-muted-foreground" />
              Goals
            </label>
            {isEditing ? (
              <Textarea
                value={editedGoals}
                onChange={(e) => setEditedGoals(e.target.value)}
                placeholder="No goals specified"
                className="min-h-[80px]"
              />
            ) : (
              <p className="text-sm text-foreground bg-muted/30 p-3 rounded-lg">
                {manifest.user_intake.goals || (
                  <span className="text-muted-foreground italic">Not specified</span>
                )}
              </p>
            )}
          </div>

          {/* Known Issues */}
          <div>
            <label className="text-sm font-medium flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              Known Issues
            </label>
            {isEditing ? (
              <Textarea
                value={editedIssues}
                onChange={(e) => setEditedIssues(e.target.value)}
                placeholder="No known issues"
                className="min-h-[80px]"
              />
            ) : (
              <p className="text-sm text-foreground bg-muted/30 p-3 rounded-lg">
                {manifest.user_intake.known_issues || (
                  <span className="text-muted-foreground italic">None reported</span>
                )}
              </p>
            )}
          </div>

          {/* Edit actions */}
          {isEditing && (
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={handleCancel}>
                <X className="h-4 w-4 mr-2" />
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={isLoading}>
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Files Section */}
      <Card>
        <CardHeader
          className="cursor-pointer"
          onClick={() => setShowFiles(!showFiles)}
        >
          <CardTitle className="text-base flex items-center justify-between">
            <span className="flex items-center gap-2">
              {showFiles ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              <FileText className="h-4 w-4 text-secondary" />
              Discovered Files
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                handleRescan()
              }}
              disabled={isLoading}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
              Rescan
            </Button>
          </CardTitle>
        </CardHeader>
        {showFiles && (
          <CardContent>
            <FileScanner scanResult={manifest.scan_result} isLoading={false} />
          </CardContent>
        )}
      </Card>

      {/* JSON Preview */}
      <Card>
        <CardHeader
          className="cursor-pointer"
          onClick={() => setShowJson(!showJson)}
        >
          <CardTitle className="text-base flex items-center gap-2">
            {showJson ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            <FileJson className="h-4 w-4 text-muted-foreground" />
            Raw JSON
          </CardTitle>
        </CardHeader>
        {showJson && (
          <CardContent>
            <pre className="text-xs bg-muted/30 p-4 rounded-lg overflow-auto max-h-[400px] font-mono">
              {JSON.stringify(manifest, null, 2)}
            </pre>
          </CardContent>
        )}
      </Card>

      {/* Actions */}
      <div className="flex justify-end">
        <Button size="lg" onClick={onProceed} disabled={isLoading || isEditing}>
          <span>Generate Understanding</span>
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
