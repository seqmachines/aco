import { useState, useEffect } from "react"
import {
    ArrowLeftRight,
    Loader2,
    CheckCircle,
    AlertCircle,
    X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface RunInfo {
    manifest_id: string
    experiment_name: string | null
    assay_type: string | null
    stages_completed: string[]
}

interface ComparisonMetric {
    manifest_id: string
    assay_type: string | null
    species: string | null
    sample_count: number | null
    read_count: number | null
}

interface RunComparisonProps {
    onClose: () => void
}

export function RunComparison({ onClose }: RunComparisonProps) {
    const [availableRuns, setAvailableRuns] = useState<RunInfo[]>([])
    const [selectedRuns, setSelectedRuns] = useState<string[]>([])
    const [comparisonData, setComparisonData] = useState<ComparisonMetric[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [isComparing, setIsComparing] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        fetchRuns()
    }, [])

    const fetchRuns = async () => {
        setIsLoading(true)
        setError(null)
        try {
            const response = await fetch("/runs/list")
            if (!response.ok) throw new Error("Failed to fetch runs")
            const data = await response.json()
            setAvailableRuns(data.runs.filter((r: RunInfo) => r.stages_completed.includes("understanding")))
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setIsLoading(false)
        }
    }

    const toggleRun = (manifestId: string) => {
        if (selectedRuns.includes(manifestId)) {
            setSelectedRuns(selectedRuns.filter(id => id !== manifestId))
        } else if (selectedRuns.length < 5) {
            setSelectedRuns([...selectedRuns, manifestId])
        }
    }

    const compareRuns = async () => {
        if (selectedRuns.length < 2) return

        setIsComparing(true)
        setError(null)
        try {
            const response = await fetch("/runs/compare", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(selectedRuns),
            })
            if (!response.ok) throw new Error("Failed to compare runs")
            const data = await response.json()
            setComparisonData(data.metrics)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setIsComparing(false)
        }
    }

    return (
        <Card className="w-full">
            <CardHeader className="flex flex-row items-center justify-between">
                <div>
                    <CardTitle className="text-lg flex items-center gap-2">
                        <ArrowLeftRight className="h-5 w-5 text-primary" />
                        Compare Runs
                    </CardTitle>
                    <CardDescription>
                        Select 2-5 runs to compare their results
                    </CardDescription>
                </div>
                <Button variant="ghost" size="icon" onClick={onClose}>
                    <X className="h-4 w-4" />
                </Button>
            </CardHeader>
            <CardContent className="space-y-4">
                {error && (
                    <div className="p-3 bg-destructive/10 text-destructive rounded text-sm flex items-center gap-2">
                        <AlertCircle className="h-4 w-4" />
                        {error}
                    </div>
                )}

                {!comparisonData.length && (
                    <>
                        <div className="text-sm text-muted-foreground">
                            Select runs to compare ({selectedRuns.length}/5 selected)
                        </div>

                        {isLoading ? (
                            <div className="flex justify-center py-8">
                                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : availableRuns.length === 0 ? (
                            <div className="text-center py-8 text-muted-foreground">
                                No runs with understanding available for comparison
                            </div>
                        ) : (
                            <div className="grid gap-2 max-h-64 overflow-y-auto">
                                {availableRuns.map((run) => (
                                    <button
                                        key={run.manifest_id}
                                        className={cn(
                                            "p-3 rounded-lg border text-left transition-colors",
                                            selectedRuns.includes(run.manifest_id)
                                                ? "border-primary bg-primary/5"
                                                : "border-border hover:border-primary/50"
                                        )}
                                        onClick={() => toggleRun(run.manifest_id)}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <span className="font-medium text-sm">
                                                    {run.experiment_name || run.manifest_id.slice(0, 12)}
                                                </span>
                                                {run.assay_type && (
                                                    <Badge variant="outline" className="ml-2 text-[10px]">
                                                        {run.assay_type}
                                                    </Badge>
                                                )}
                                            </div>
                                            {selectedRuns.includes(run.manifest_id) ? (
                                                <CheckCircle className="h-4 w-4 text-primary" />
                                            ) : (
                                                <div className="h-4 w-4 rounded-full border-2 border-muted-foreground/30" />
                                            )}
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}

                        <Button
                            onClick={compareRuns}
                            disabled={selectedRuns.length < 2 || isComparing}
                            className="w-full"
                        >
                            {isComparing ? (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            ) : (
                                <ArrowLeftRight className="h-4 w-4 mr-2" />
                            )}
                            Compare {selectedRuns.length} Runs
                        </Button>
                    </>
                )}

                {comparisonData.length > 0 && (
                    <>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b">
                                        <th className="text-left py-2 px-3 font-medium">Metric</th>
                                        {comparisonData.map((run) => (
                                            <th key={run.manifest_id} className="text-left py-2 px-3 font-medium">
                                                {run.manifest_id.slice(0, 8)}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr className="border-b">
                                        <td className="py-2 px-3 text-muted-foreground">Assay Type</td>
                                        {comparisonData.map((run) => (
                                            <td key={run.manifest_id} className="py-2 px-3">
                                                <Badge variant="outline">{run.assay_type || "Unknown"}</Badge>
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="border-b">
                                        <td className="py-2 px-3 text-muted-foreground">Species</td>
                                        {comparisonData.map((run) => (
                                            <td key={run.manifest_id} className="py-2 px-3">
                                                {run.species || "Unknown"}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="border-b">
                                        <td className="py-2 px-3 text-muted-foreground">Sample Count</td>
                                        {comparisonData.map((run) => (
                                            <td key={run.manifest_id} className="py-2 px-3">
                                                {run.sample_count?.toLocaleString() || "N/A"}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr>
                                        <td className="py-2 px-3 text-muted-foreground">Read Count</td>
                                        {comparisonData.map((run) => (
                                            <td key={run.manifest_id} className="py-2 px-3">
                                                {run.read_count?.toLocaleString() || "N/A"}
                                            </td>
                                        ))}
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <Button
                            variant="outline"
                            onClick={() => {
                                setComparisonData([])
                                setSelectedRuns([])
                            }}
                            className="w-full"
                        >
                            Compare Different Runs
                        </Button>
                    </>
                )}
            </CardContent>
        </Card>
    )
}
