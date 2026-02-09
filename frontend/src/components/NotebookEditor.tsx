import { useState } from "react"
import {
    Play,
    FileCode2,
    Download,
    CheckCircle,
    Loader2,
    BookOpen,
    Code,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface NotebookCell {
    cell_type: string
    source: string
    outputs: unknown[]
}

interface GeneratedNotebook {
    name: string
    language: string
    title: string
    description: string
    cells: NotebookCell[]
    dependencies: string[]
    generated_at: string
}

interface NotebookEditorProps {
    manifestId: string
    onComplete?: () => void
}

export function NotebookEditor({ manifestId, onComplete }: NotebookEditorProps) {
    const [notebook, setNotebook] = useState<GeneratedNotebook | null>(null)
    const [savedPath, setSavedPath] = useState<string | null>(null)
    const [isGenerating, setIsGenerating] = useState(false)
    const [selectedLanguage, setSelectedLanguage] = useState<"python" | "r">("python")
    const [error, setError] = useState<string | null>(null)

    const generateNotebook = async () => {
        setIsGenerating(true)
        setError(null)
        try {
            const response = await fetch("/notebooks/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    manifest_id: manifestId,
                    language: selectedLanguage,
                }),
            })
            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || "Failed to generate notebook")
            }
            const data = await response.json()
            setNotebook(data.notebook)
            setSavedPath(data.saved_path)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setIsGenerating(false)
        }
    }

    const downloadNotebook = async () => {
        if (!notebook) return

        try {
            const response = await fetch(`/notebooks/${manifestId}?format=${notebook.language === "python" ? "jupyter" : "rmarkdown"}`)
            if (!response.ok) throw new Error("Failed to fetch notebook")

            const data = await response.json()
            if (!data.content) throw new Error("No content")

            // Create download
            const blob = new Blob([data.content], { type: "application/json" })
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = `${notebook.name}.${notebook.language === "python" ? "ipynb" : "Rmd"}`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            URL.revokeObjectURL(url)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Download failed")
        }
    }

    if (!notebook) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                        <BookOpen className="h-5 w-5 text-primary" />
                        Notebook Generation
                    </CardTitle>
                    <CardDescription>
                        Generate an analysis notebook based on your QC results
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {error && (
                        <div className="p-3 bg-destructive/10 text-destructive rounded text-sm">
                            {error}
                        </div>
                    )}

                    {/* Language Selection */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Select Language</label>
                        <div className="flex gap-2">
                            <Button
                                variant={selectedLanguage === "python" ? "default" : "outline"}
                                size="sm"
                                onClick={() => setSelectedLanguage("python")}
                                className="flex items-center gap-2"
                            >
                                <Code className="h-4 w-4" />
                                Python (Jupyter)
                            </Button>
                            <Button
                                variant={selectedLanguage === "r" ? "default" : "outline"}
                                size="sm"
                                onClick={() => setSelectedLanguage("r")}
                                className="flex items-center gap-2"
                            >
                                <FileCode2 className="h-4 w-4" />
                                R (RMarkdown)
                            </Button>
                        </div>
                    </div>

                    <Button onClick={generateNotebook} disabled={isGenerating}>
                        {isGenerating ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <Play className="h-4 w-4 mr-2" />
                        )}
                        Generate Notebook
                    </Button>
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <BookOpen className="h-5 w-5 text-primary" />
                        {notebook.title}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                        {notebook.description}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Badge variant="outline" className="flex items-center gap-1">
                        {notebook.language === "python" ? (
                            <Code className="h-3 w-3" />
                        ) : (
                            <FileCode2 className="h-3 w-3" />
                        )}
                        {notebook.language === "python" ? "Jupyter" : "RMarkdown"}
                    </Badge>
                    <Badge variant="success" className="flex items-center gap-1">
                        <CheckCircle className="h-3 w-3" />
                        Generated
                    </Badge>
                </div>
            </div>

            {error && (
                <div className="p-3 bg-destructive/10 text-destructive rounded text-sm">
                    {error}
                </div>
            )}

            {/* Notebook Info */}
            <Card>
                <CardContent className="py-4 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <span className="text-xs text-muted-foreground">Cells</span>
                            <p className="text-sm font-medium">{notebook.cells.length}</p>
                        </div>
                        <div>
                            <span className="text-xs text-muted-foreground">Saved To</span>
                            <p className="text-sm font-mono truncate" title={savedPath || ""}>
                                {savedPath?.split("/").pop()}
                            </p>
                        </div>
                    </div>

                    {notebook.dependencies.length > 0 && (
                        <div>
                            <span className="text-xs text-muted-foreground">Dependencies</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                                {notebook.dependencies.map((dep) => (
                                    <Badge key={dep} variant="secondary" className="text-xs">
                                        {dep}
                                    </Badge>
                                ))}
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Cell Preview */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Notebook Preview</CardTitle>
                </CardHeader>
                <CardContent className="max-h-96 overflow-y-auto space-y-2">
                    {notebook.cells.slice(0, 10).map((cell, idx) => (
                        <div
                            key={idx}
                            className={cn(
                                "p-3 rounded border text-sm",
                                cell.cell_type === "markdown"
                                    ? "bg-muted/30"
                                    : "bg-slate-900 text-slate-100 font-mono text-xs"
                            )}
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <Badge
                                    variant="outline"
                                    className={cn(
                                        "text-[10px]",
                                        cell.cell_type === "code" && "bg-blue-500/10 text-blue-500"
                                    )}
                                >
                                    {cell.cell_type}
                                </Badge>
                            </div>
                            <pre className="whitespace-pre-wrap overflow-x-auto">
                                {cell.source.slice(0, 500)}
                                {cell.source.length > 500 && "..."}
                            </pre>
                        </div>
                    ))}
                    {notebook.cells.length > 10 && (
                        <p className="text-sm text-muted-foreground text-center py-2">
                            + {notebook.cells.length - 10} more cells
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Actions */}
            <div className="flex justify-between pt-4 border-t">
                <Button variant="outline" onClick={() => setNotebook(null)}>
                    Generate Different
                </Button>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={downloadNotebook}>
                        <Download className="h-4 w-4 mr-2" />
                        Download
                    </Button>
                    {onComplete && (
                        <Button onClick={onComplete}>
                            Continue to Report
                        </Button>
                    )}
                </div>
            </div>
        </div>
    )
}
