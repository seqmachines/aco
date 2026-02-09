import { useState, useEffect, useRef, useCallback } from "react"
import {
  Beaker,
  FolderSearch,
  AlertTriangle,
  FileText,
  Send,
  Upload,
  X,
  Image as ImageIcon,
  File,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { IntakeFormData, UploadedFile } from "@/types"

interface IntakeFormProps {
  onSubmit: (data: IntakeFormData) => void
  isLoading: boolean
  defaultDirectory?: string
  savedData?: IntakeFormData | null
  onSave?: (data: IntakeFormData) => void
}

const ACCEPTED_FILE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
  "text/plain",
  "text/csv",
  "text/markdown",
  "application/pdf",
  "application/json",
].join(",")

export function IntakeForm({
  onSubmit,
  isLoading,
  defaultDirectory = "",
  savedData,
  onSave,
}: IntakeFormProps) {
  const [experimentDescription, setExperimentDescription] = useState("")
  const [targetDirectory, setTargetDirectory] = useState("")
  const [goals, setGoals] = useState("")
  const [knownIssues, setKnownIssues] = useState("")
  const [additionalNotes, setAdditionalNotes] = useState("")
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Load saved data on mount
  useEffect(() => {
    if (savedData) {
      setExperimentDescription(savedData.experiment_description || "")
      setTargetDirectory(savedData.target_directory || defaultDirectory)
      setGoals(savedData.goals || "")
      setKnownIssues(savedData.known_issues || "")
      setAdditionalNotes(savedData.additional_notes || "")
      setUploadedFiles(savedData.uploaded_files || [])
    } else if (defaultDirectory) {
      setTargetDirectory(defaultDirectory)
    }
  }, [savedData, defaultDirectory])

  // Auto-save with debouncing
  const triggerSave = useCallback(() => {
    if (!onSave) return

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
    }

    saveTimeoutRef.current = setTimeout(() => {
      onSave({
        experiment_description: experimentDescription,
        target_directory: targetDirectory,
        goals: goals || undefined,
        known_issues: knownIssues || undefined,
        additional_notes: additionalNotes || undefined,
        uploaded_files: uploadedFiles.length > 0 ? uploadedFiles : undefined,
      })
    }, 1000)
  }, [
    onSave,
    experimentDescription,
    targetDirectory,
    goals,
    knownIssues,
    additionalNotes,
    uploadedFiles,
  ])

  // Trigger save on field changes
  useEffect(() => {
    triggerSave()
  }, [
    experimentDescription,
    targetDirectory,
    goals,
    knownIssues,
    additionalNotes,
    uploadedFiles,
    triggerSave,
  ])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
    }
  }, [])

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
      uploaded_files: uploadedFiles.length > 0 ? uploadedFiles : undefined,
    })
  }

  // Process files (shared by file input, drag-drop, and paste)
  const processFiles = useCallback(async (files: FileList | File[]) => {
    const newFiles: UploadedFile[] = []

    for (const file of Array.from(files)) {
      const uploadedFile: UploadedFile = {
        name: file.name,
        size: file.size,
        type: file.type,
      }

      // Read file content
      if (file.type.startsWith("image/")) {
        // Convert image to data URL for preview
        const reader = new FileReader()
        const dataUrl = await new Promise<string>((resolve) => {
          reader.onload = () => resolve(reader.result as string)
          reader.readAsDataURL(file)
        })
        uploadedFile.dataUrl = dataUrl
      } else if (
        file.type.startsWith("text/") ||
        file.type === "application/json"
      ) {
        // Read text content
        const text = await file.text()
        uploadedFile.content = text
      }

      newFiles.push(uploadedFile)
    }

    setUploadedFiles((prev) => [...prev, ...newFiles])
  }, [])

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return

    await processFiles(files)

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  // Drag and drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // Only set dragging to false if we're leaving the drop zone entirely
    if (e.currentTarget === e.target) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      await processFiles(files)
    }
  }, [processFiles])

  // Handle paste in textarea (for images)
  const handlePaste = useCallback(async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData.items
    const imageFiles: File[] = []

    for (const item of Array.from(items)) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile()
        if (file) {
          // Generate a name for pasted images
          const extension = file.type.split("/")[1] || "png"
          const timestamp = new Date().toISOString().replace(/[:.]/g, "-")
          // Create a new file with a proper name
          Object.defineProperty(file, "name", {
            writable: true,
            value: `pasted-image-${timestamp}.${extension}`,
          })
          imageFiles.push(file)
        }
      }
    }

    if (imageFiles.length > 0) {
      e.preventDefault() // Prevent default paste behavior for images
      await processFiles(imageFiles)
    }
    // If no images, allow normal text paste
  }, [processFiles])

  const removeFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Experiment Description with File Upload */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Beaker className="h-5 w-5 text-primary" />
            Experiment Description
          </CardTitle>
          <CardDescription>
            Describe your sequencing experiment in detail. Include the type of assay,
            organism, and what you're trying to measure. You can paste images directly
            into the text box or upload supporting documents below.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            ref={textareaRef}
            placeholder="e.g., Single-cell RNA sequencing of mouse brain tissue using 10x Genomics Chromium v3. We're studying neuronal subtypes in the hippocampus region...

(You can paste images here with Ctrl+V / Cmd+V)"
            value={experimentDescription}
            onChange={(e) => setExperimentDescription(e.target.value)}
            onPaste={handlePaste}
            className="min-h-[150px]"
            required
          />

          {/* File Upload Area */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Label className="text-sm font-medium">Supporting Files</Label>
              <span className="text-xs text-muted-foreground">
                (protocols, images, sample sheets)
              </span>
            </div>

            {/* Upload Button with Drag and Drop */}
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-lg p-6 cursor-pointer transition-all duration-200
                ${isDragging 
                  ? "border-primary bg-primary/10 scale-[1.02]" 
                  : "border-border hover:border-primary/50 hover:bg-primary/5"
                }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_FILE_TYPES}
                multiple
                onChange={handleFileSelect}
                className="hidden"
              />
              <div className="flex flex-col items-center gap-2 text-center">
                <Upload className={`h-8 w-8 transition-colors ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">
                    Click to upload
                  </span>{" "}
                  or drag and drop
                </p>
                <p className="text-xs text-muted-foreground">
                  Images, PDFs, CSVs, or text files
                </p>
              </div>
            </div>

            {/* Uploaded Files List */}
            {uploadedFiles.length > 0 && (
              <div className="space-y-2">
                {uploadedFiles.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 group"
                  >
                    {file.dataUrl ? (
                      <img
                        src={file.dataUrl}
                        alt={file.name}
                        className="h-10 w-10 rounded object-cover"
                      />
                    ) : file.type.startsWith("image/") ? (
                      <div className="h-10 w-10 rounded bg-muted flex items-center justify-center">
                        <ImageIcon className="h-5 w-5 text-muted-foreground" />
                      </div>
                    ) : (
                      <div className="h-10 w-10 rounded bg-muted flex items-center justify-center">
                        <File className="h-5 w-5 text-muted-foreground" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(file.size)}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => removeFile(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Data Location */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderSearch className="h-5 w-5 text-secondary" />
            Data Location
          </CardTitle>
          <CardDescription>
            Path to the directory containing your sequencing raw data.
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
              The scanner will recursively search for FASTQ, BAM, and CellRanger
              outputs etc.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Goals and Known Issues */}
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

      {/* Additional Notes */}
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
          disabled={
            isLoading ||
            !experimentDescription.trim() ||
            !targetDirectory.trim()
          }
        >
          {isLoading ? (
            <span className="animate-pulse">Processing...</span>
          ) : (
            <>
              <Send className="mr-1.5 h-3.5 w-3.5" />
              Start Digesting
            </>
          )}
        </Button>
      </div>
    </form>
  )
}
