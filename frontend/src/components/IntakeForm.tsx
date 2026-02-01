import { useState } from "react"
import { Beaker, FolderSearch, AlertTriangle, FileText, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

interface IntakeFormProps {
  onSubmit: (data: {
    experiment_description: string
    target_directory: string
    goals?: string
    known_issues?: string
    additional_notes?: string
  }) => void
  isLoading: boolean
}

export function IntakeForm({ onSubmit, isLoading }: IntakeFormProps) {
  const [experimentDescription, setExperimentDescription] = useState("")
  const [targetDirectory, setTargetDirectory] = useState("")
  const [goals, setGoals] = useState("")
  const [knownIssues, setKnownIssues] = useState("")
  const [additionalNotes, setAdditionalNotes] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!experimentDescription.trim() || !targetDirectory.trim()) {
      return
    }

    onSubmit({
      experiment_description: experimentDescription,
      target_directory: targetDirectory,
      goals: goals || undefined,
      known_issues: knownIssues || undefined,
      additional_notes: additionalNotes || undefined,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card className="border-primary/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Beaker className="h-5 w-5 text-primary" />
            Experiment Description
          </CardTitle>
          <CardDescription>
            Describe your sequencing experiment in detail. Include the type of assay,
            organism, and what you're trying to measure.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            placeholder="e.g., Single-cell RNA sequencing of mouse brain tissue using 10x Genomics Chromium v3. We're studying neuronal subtypes in the hippocampus region..."
            value={experimentDescription}
            onChange={(e) => setExperimentDescription(e.target.value)}
            className="min-h-[150px]"
            required
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderSearch className="h-5 w-5 text-secondary" />
            Data Location
          </CardTitle>
          <CardDescription>
            Provide the path to the directory containing your sequencing files.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="target-directory">Target Directory</Label>
            <Input
              id="target-directory"
              placeholder="/path/to/sequencing/data"
              value={targetDirectory}
              onChange={(e) => setTargetDirectory(e.target.value)}
              required
            />
            <p className="text-xs text-muted-foreground">
              The scanner will recursively search for FASTQ, BAM, and CellRanger outputs.
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="h-4 w-4 text-accent" />
              Goals & Objectives
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="What specific questions are you trying to answer? What are the key deliverables?"
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
              className="min-h-[100px]"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-4 w-4 text-warning" />
              Known Issues
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="Any known problems with the data? Low quality samples? Technical issues during sequencing?"
              value={knownIssues}
              onChange={(e) => setKnownIssues(e.target.value)}
              className="min-h-[100px]"
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Additional Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            placeholder="Any other relevant information..."
            value={additionalNotes}
            onChange={(e) => setAdditionalNotes(e.target.value)}
            className="min-h-[80px]"
          />
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          type="submit"
          size="lg"
          disabled={isLoading || !experimentDescription.trim() || !targetDirectory.trim()}
          className="min-w-[200px]"
        >
          {isLoading ? (
            <>
              <span className="animate-pulse">Processing...</span>
            </>
          ) : (
            <>
              <Send className="mr-2 h-4 w-4" />
              Start Analysis
            </>
          )}
        </Button>
      </div>
    </form>
  )
}
