import { useState, useEffect } from "react"
import {
    ChevronDown,
    History,
    Trash2,
    Clock,
    CheckCircle,
    AlertCircle,
    Loader2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface RunInfo {
    manifest_id: string
    created_at: string | null
    updated_at: string | null
    stages_completed: string[]
    has_understanding: boolean
    has_scripts: boolean
    has_notebook: boolean
    has_report: boolean
    experiment_name: string | null
    assay_type: string | null
}

interface RunSelectorProps {
    currentManifestId: string | null
    onSelectRun: (manifestId: string) => void
    onNewRun: () => void
}

export function RunSelector({ currentManifestId, onSelectRun, onNewRun }: RunSelectorProps) {
    const [runs, setRuns] = useState<RunInfo[]>([])
    const [isOpen, setIsOpen] = useState(false)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchRuns = async () => {
        setIsLoading(true)
        setError(null)
        try {
            const response = await fetch("/runs/list")
            if (!response.ok) throw new Error("Failed to fetch runs")
            const data = await response.json()
            setRuns(data.runs)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setIsLoading(false)
        }
    }

    const deleteRun = async (manifestId: string, e: React.MouseEvent) => {
        e.stopPropagation()
        if (!confirm("Delete this run and all its data?")) return

        try {
            const response = await fetch(`/runs/${manifestId}`, { method: "DELETE" })
            if (!response.ok) throw new Error("Failed to delete run")
            fetchRuns()
        } catch (err) {
            setError(err instanceof Error ? err.message : "Delete failed")
        }
    }

    useEffect(() => {
        if (isOpen && runs.length === 0) {
            fetchRuns()
        }
    }, [isOpen, runs.length])

    const currentRun = runs.find(r => r.manifest_id === currentManifestId)

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return "Unknown"
        return new Date(dateStr).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        })
    }

    const getProgressPercent = (run: RunInfo) => {
        const stages = ["understanding", "scripts", "notebook", "report"]
        const completed = stages.filter(s => run.stages_completed.includes(s)).length
        return Math.round((completed / stages.length) * 100)
    }

    return (
        <div className="relative">
            <Button
                variant="ghost"
                size="sm"
                className="w-full justify-between text-left font-normal"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex items-center gap-2 overflow-hidden">
                    <History className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    <span className="truncate">
                        {currentRun?.experiment_name || currentManifestId?.slice(0, 8) || "No run selected"}
                    </span>
                </div>
                <ChevronDown className={cn(
                    "h-4 w-4 flex-shrink-0 transition-transform text-muted-foreground",
                    isOpen && "rotate-180"
                )} />
            </Button>

            {isOpen && (
                <div className="absolute left-0 right-0 top-full mt-1 z-50 bg-popover border rounded-lg shadow-lg max-h-80 overflow-y-auto">
                    <button
                        className="w-full px-3 py-2 text-left text-sm hover:bg-accent flex items-center gap-2 border-b"
                        onClick={() => {
                            onNewRun()
                            setIsOpen(false)
                        }}
                    >
                        <span className="text-primary font-medium">+ New Analysis</span>
                    </button>

                    {isLoading && (
                        <div className="p-4 text-center text-muted-foreground">
                            <Loader2 className="h-4 w-4 animate-spin mx-auto" />
                        </div>
                    )}

                    {error && (
                        <div className="p-3 text-sm text-destructive flex items-center gap-2">
                            <AlertCircle className="h-4 w-4" />
                            {error}
                        </div>
                    )}

                    {!isLoading && runs.length === 0 && (
                        <div className="p-4 text-center text-sm text-muted-foreground">
                            No previous runs found
                        </div>
                    )}

                    {runs.map((run) => (
                        <div
                            key={run.manifest_id}
                            className={cn(
                                "px-3 py-2 hover:bg-accent cursor-pointer border-b last:border-0",
                                run.manifest_id === currentManifestId && "bg-accent/50"
                            )}
                            onClick={() => {
                                onSelectRun(run.manifest_id)
                                setIsOpen(false)
                            }}
                        >
                            <div className="flex items-start justify-between gap-2">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        {run.manifest_id === currentManifestId && (
                                            <CheckCircle className="h-3 w-3 text-success flex-shrink-0" />
                                        )}
                                        <span className="text-sm font-medium truncate">
                                            {run.experiment_name || run.manifest_id.slice(0, 12)}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2 mt-1">
                                        {run.assay_type && (
                                            <Badge variant="outline" className="text-[10px] px-1">
                                                {run.assay_type}
                                            </Badge>
                                        )}
                                        <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                                            <Clock className="h-3 w-3" />
                                            {formatDate(run.updated_at)}
                                        </span>
                                    </div>
                                    <div className="mt-2 h-1 bg-muted rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-primary transition-all"
                                            style={{ width: `${getProgressPercent(run)}%` }}
                                        />
                                    </div>
                                </div>
                                <div className="flex items-center gap-1">
                                    <button
                                        className="p-1 hover:bg-destructive/10 rounded text-muted-foreground hover:text-destructive"
                                        onClick={(e) => deleteRun(run.manifest_id, e)}
                                        title="Delete run"
                                    >
                                        <Trash2 className="h-3 w-3" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}

                    {runs.length > 0 && (
                        <button
                            className="w-full px-3 py-2 text-center text-xs text-muted-foreground hover:bg-accent"
                            onClick={fetchRuns}
                        >
                            Refresh list
                        </button>
                    )}
                </div>
            )}
        </div>
    )
}
