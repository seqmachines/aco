import { useState, useEffect } from "react"
import {
    Play,
    CheckCircle,
    XCircle,
    FileCode,
    Terminal,
    ChevronDown,
    ChevronRight,
    Loader2,
    RefreshCw,
    Wand2,
    Check,
    Circle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type {
    ScriptPlan,
    PlannedScript,
    PipelinePhase,
    ExecutionResult,
    ExperimentUnderstanding,
} from "@/types"

interface ScriptRunnerProps {
    manifestId: string
    initialPlan?: ScriptPlan | null
    understanding?: ExperimentUnderstanding | null
    onPlanUpdate?: (plan: ScriptPlan) => void
    onComplete?: (results: ExecutionResult[]) => void
    onBack?: () => void
    onProceed?: () => void
}

const categoryLabels: Record<string, string> = {
    parse_assay: "Parse Assay",
    sequencing_health: "Sequencing Health",
    qc_metrics: "QC Metrics",
    data_extraction: "Data Extraction",
    custom: "Custom",
}

const categoryColors: Record<string, string> = {
    parse_assay: "bg-blue-500/20 text-blue-600 border-blue-500/30",
    sequencing_health: "bg-green-500/20 text-green-600 border-green-500/30",
    qc_metrics: "bg-purple-500/20 text-purple-600 border-purple-500/30",
    data_extraction: "bg-orange-500/20 text-orange-600 border-orange-500/30",
    custom: "bg-slate-500/20 text-slate-600 border-slate-500/30",
}

const pipelineSteps = [
    { key: "generating_code", label: "Generating Code" },
    { key: "creating_env", label: "Creating Environment" },
    { key: "installing_deps", label: "Installing Dependencies" },
    { key: "executing", label: "Executing Scripts" },
] as const

function PlanScriptCard({ script }: { script: PlannedScript }) {
    const [expanded, setExpanded] = useState(false)
    const displayOutputs = script.output_files.filter((file) => {
        const lower = file.toLowerCase()
        return !lower.endsWith(".json") && !lower.endsWith(".jsonl") && !lower.endsWith(".ndjson")
    })

    return (
        <div
            className={cn(
                "p-3 rounded-lg border border-border bg-muted/20 cursor-pointer transition-all",
                expanded && "ring-1 ring-border"
            )}
            onClick={() => setExpanded(!expanded)}
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {expanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                    <FileCode className="h-3.5 w-3.5 text-primary" />
                    <span className="text-sm font-medium">{script.name}</span>
                </div>
                <Badge variant="outline" className={categoryColors[script.category] || ""}>
                    {categoryLabels[script.category] || script.category}
                </Badge>
            </div>
            <p className="text-sm text-muted-foreground mt-1 ml-7">{script.description}</p>
            {expanded && (
                <div className="mt-2 ml-7 space-y-1">
                    {script.dependencies.length > 0 && (
                        <div>
                            <span className="text-xs text-muted-foreground">Dependencies: </span>
                            <span className="text-xs font-mono">{script.dependencies.join(", ")}</span>
                        </div>
                    )}
                    {script.input_files.length > 0 && (
                        <div>
                            <span className="text-xs text-muted-foreground">Input patterns: </span>
                            <span className="text-xs font-mono">{script.input_files.join(", ")}</span>
                        </div>
                    )}
                    {displayOutputs.length > 0 && (
                        <div>
                            <span className="text-xs text-muted-foreground">Outputs: </span>
                            <span className="text-xs font-mono">{displayOutputs.join(", ")}</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

function PipelineProgress({
    phase,
    completedSteps,
    error,
}: {
    phase: PipelinePhase
    completedSteps: string[]
    error: string | null
}) {
    if (phase === "idle") return null

    return (
        <Card className={cn(
            "border-primary/30",
            phase === "complete" && "border-green-500/30 bg-green-500/5",
            phase === "failed" && "border-destructive/30 bg-destructive/5",
        )}>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                    {phase === "complete" ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : phase === "failed" ? (
                        <XCircle className="h-4 w-4 text-destructive" />
                    ) : (
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    )}
                    {phase === "complete"
                        ? "Pipeline Complete"
                        : phase === "failed"
                            ? "Pipeline Failed"
                            : "Running Pipeline..."}
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {pipelineSteps.map((step) => {
                        const isCompleted = completedSteps.includes(step.key)
                        const isCurrent = phase === step.key
                        const isFailed = phase === "failed" && isCurrent

                        return (
                            <div key={step.key} className="flex items-center gap-2">
                                {isCompleted ? (
                                    <Check className="h-4 w-4 text-green-500" />
                                ) : isCurrent ? (
                                    isFailed ? (
                                        <XCircle className="h-4 w-4 text-destructive" />
                                    ) : (
                                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                    )
                                ) : (
                                    <Circle className="h-4 w-4 text-muted-foreground/40" />
                                )}
                                <span
                                    className={cn(
                                        "text-sm",
                                        isCompleted && "text-foreground",
                                        isCurrent && "text-foreground font-medium",
                                        !isCompleted && !isCurrent && "text-muted-foreground/50",
                                    )}
                                >
                                    {step.label}
                                </span>
                            </div>
                        )
                    })}
                </div>
                {error && (
                    <div className="mt-3 p-2 bg-destructive/10 text-destructive rounded text-xs">
                        {error}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function ExecutionResultCard({ result }: { result: ExecutionResult }) {
    const [expanded, setExpanded] = useState(false)

    return (
        <div
            className={cn(
                "p-3 rounded-lg border cursor-pointer transition-all",
                result.success
                    ? "border-green-500/30 bg-green-500/5"
                    : "border-destructive/30 bg-destructive/5",
            )}
            onClick={() => setExpanded(!expanded)}
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {expanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                    {result.success ? (
                        <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                    ) : (
                        <XCircle className="h-3.5 w-3.5 text-destructive" />
                    )}
                    <span className="text-sm font-medium">{result.script_name}</span>
                </div>
                <div className="flex items-center gap-2">
                    <Badge variant={result.success ? "success" : "destructive"} className="text-xs">
                        exit {result.exit_code}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                        {result.duration_seconds.toFixed(1)}s
                    </span>
                </div>
            </div>
            {expanded && (
                <div className="mt-2 ml-7 space-y-2">
                    {result.stdout && (
                        <div>
                            <span className="text-xs text-muted-foreground">stdout:</span>
                            <pre className="p-2 bg-muted rounded text-xs font-mono overflow-x-auto max-h-32 mt-1">
                                {result.stdout.slice(0, 1000)}
                            </pre>
                        </div>
                    )}
                    {result.stderr && (
                        <div>
                            <span className="text-xs text-destructive">stderr:</span>
                            <pre className="p-2 bg-destructive/10 rounded text-xs font-mono overflow-x-auto max-h-32 mt-1">
                                {result.stderr.slice(0, 1000)}
                            </pre>
                        </div>
                    )}
                    {result.output_files.length > 0 && (
                        <div>
                            <span className="text-xs text-muted-foreground">Output files:</span>
                            <ul className="text-xs font-mono ml-4 mt-1">
                                {result.output_files.map((f, i) => (
                                    <li key={i}>{f}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export function ScriptRunner({ manifestId, initialPlan, understanding, onPlanUpdate, onComplete, onBack, onProceed }: ScriptRunnerProps) {
    const [plan, setPlan] = useState<ScriptPlan | null>(initialPlan || null)
    const [isGeneratingPlan, setIsGeneratingPlan] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Pipeline state
    const [pipelinePhase, setPipelinePhase] = useState<PipelinePhase>("idle")
    const [completedPipelineSteps, setCompletedPipelineSteps] = useState<string[]>([])
    const [pipelineError, setPipelineError] = useState<string | null>(null)
    const [executionResults, setExecutionResults] = useState<ExecutionResult[]>([])

    // Sync with parent plan
    useEffect(() => {
        if (initialPlan) {
            setPlan(initialPlan)
        }
    }, [initialPlan])

    // Load existing plan if not passed from parent
    useEffect(() => {
        if (!plan) {
            loadExistingPlan()
        }
    }, [manifestId])

    const loadExistingPlan = async () => {
        try {
            const response = await fetch(`/scripts/plan/${manifestId}`)
            if (response.ok) {
                const data = await response.json()
                if (data.plan) {
                    setPlan(data.plan)
                    onPlanUpdate?.(data.plan)
                }
            }
        } catch (_e) {
            // No existing plan
        }
    }

    const generatePlan = async () => {
        setIsGeneratingPlan(true)
        setError(null)
        try {
            const response = await fetch("/scripts/plan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || "Failed to generate plan")
            }
            const data = await response.json()
            setPlan(data.plan)
            onPlanUpdate?.(data.plan)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setIsGeneratingPlan(false)
        }
    }

    const executePipeline = async () => {
        if (!plan) return

        setPipelinePhase("generating_code")
        setCompletedPipelineSteps([])
        setPipelineError(null)
        setExecutionResults([])
        setError(null)

        try {
            // Step 1: Generate all code
            const codeRes = await fetch("/scripts/generate-all-code", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            if (!codeRes.ok) {
                const data = await codeRes.json()
                throw new Error(data.detail || "Code generation failed")
            }
            const codeData = await codeRes.json()
            if (codeData.failed && codeData.failed.length > 0) {
                throw new Error(`Code generation failed for: ${codeData.failed.join(", ")}`)
            }
            setCompletedPipelineSteps(prev => [...prev, "generating_code"])

            // Step 2: Create environment
            setPipelinePhase("creating_env")
            const envRes = await fetch("/scripts/create-env", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            if (!envRes.ok) {
                const data = await envRes.json()
                throw new Error(data.detail || "Environment creation failed")
            }
            const envData = await envRes.json()
            if (!envData.success) {
                throw new Error(envData.message || "Environment creation failed")
            }
            setCompletedPipelineSteps(prev => [...prev, "creating_env"])

            // Step 3: Install dependencies
            setPipelinePhase("installing_deps")
            const depsRes = await fetch("/scripts/install-deps", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            if (!depsRes.ok) {
                const data = await depsRes.json()
                throw new Error(data.detail || "Dependency installation failed")
            }
            const depsData = await depsRes.json()
            if (!depsData.success) {
                throw new Error(depsData.error || "Dependency installation failed")
            }
            setCompletedPipelineSteps(prev => [...prev, "installing_deps"])

            // Step 4: Execute all scripts
            setPipelinePhase("executing")
            const execRes = await fetch("/scripts/execute-all", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            if (!execRes.ok) {
                const data = await execRes.json()
                throw new Error(data.detail || "Script execution failed")
            }
            const execData = await execRes.json()
            setCompletedPipelineSteps(prev => [...prev, "executing"])
            setExecutionResults(execData.results || [])

            if (execData.all_succeeded) {
                setPipelinePhase("complete")
                // Reload plan with code
                const planResponse = await fetch(`/scripts/plan/${manifestId}`)
                if (planResponse.ok) {
                    const planData = await planResponse.json()
                    setPlan(planData.plan)
                    onPlanUpdate?.(planData.plan)
                }
                sendNotification("Analysis Complete", "All scripts executed successfully.")
                if (onComplete) {
                    onComplete(execData.results)
                }
            } else {
                setPipelinePhase("failed")
                const failedScripts = (execData.results || [])
                    .filter((r: ExecutionResult) => !r.success)
                    .map((r: ExecutionResult) => r.script_name)
                    .join(", ")
                setPipelineError(`Scripts failed: ${failedScripts}`)
                sendNotification("Pipeline Failed", "Some scripts failed during execution")
            }
        } catch (e) {
            const errorMsg = e instanceof Error ? e.message : "Pipeline failed"
            setPipelinePhase("failed")
            setPipelineError(errorMsg)
            sendNotification("Pipeline Failed", errorMsg)
        }
    }

    const sendNotification = (title: string, body: string) => {
        if ("Notification" in window && Notification.permission === "granted") {
            new Notification(`ACO: ${title}`, { body })
        } else if ("Notification" in window && Notification.permission !== "denied") {
            Notification.requestPermission().then((permission) => {
                if (permission === "granted") {
                    new Notification(`ACO: ${title}`, { body })
                }
            })
        }
    }

    // No plan yet — show generate button
    if (!plan) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                        <FileCode className="h-5 w-5 text-primary" />
                        Script Generation
                    </CardTitle>
                    <CardDescription>
                        Generate and execute QC scripts based on your experiment understanding
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {error && (
                        <div className="p-3 mb-4 bg-destructive/10 text-destructive rounded text-sm">
                            {error}
                        </div>
                    )}
                    <Button onClick={generatePlan} disabled={isGeneratingPlan}>
                        {isGeneratingPlan ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <Wand2 className="h-4 w-4 mr-2" />
                        )}
                        Generate Script Plan
                    </Button>
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="space-y-4">
            {/* Error display */}
            {error && (
                <div className="p-3 bg-destructive/10 text-destructive rounded text-sm">
                    {error}
                </div>
            )}

            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <FileCode className="h-5 w-5 text-primary" />
                        Script Plan
                    </h3>
                    <p className="text-sm text-muted-foreground">
                        {plan.scripts.length} scripts planned — refine below or approve and execute
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {pipelinePhase === "idle" && (
                        <Button
                            onClick={generatePlan}
                            disabled={isGeneratingPlan}
                            size="sm"
                            variant="outline"
                        >
                            {isGeneratingPlan ? (
                                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            ) : (
                                <RefreshCw className="h-3 w-3 mr-1" />
                            )}
                            Regenerate Plan
                        </Button>
                    )}
                    {pipelinePhase === "complete" && (
                        <Badge variant="success" className="flex items-center gap-1">
                            <CheckCircle className="h-3 w-3" />
                            All Completed
                        </Badge>
                    )}
                    {pipelinePhase === "failed" && (
                        <Button onClick={executePipeline} size="sm" variant="outline">
                            <RefreshCw className="h-3 w-3 mr-1" />
                            Retry Pipeline
                        </Button>
                    )}
                </div>
            </div>

            {/* Detected Existing Scripts */}
            {understanding?.detected_scripts?.length ? (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center gap-2">
                            <FileCode className="h-4 w-4 text-primary" />
                            Detected Scripts ({understanding.detected_scripts.length})
                        </CardTitle>
                        <CardDescription>
                            Existing scripts can be adapted to the current dataset
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {understanding.detected_scripts.map((script, i) => (
                                <div key={i} className="p-3 rounded-lg border border-border bg-muted/20">
                                    <div className="flex items-center justify-between">
                                        <code className="text-xs font-mono">{script.filename || script.name}</code>
                                        {script.purpose && (
                                            <Badge variant="outline" className="text-[10px]">
                                                {script.purpose}
                                            </Badge>
                                        )}
                                    </div>
                                    {script.description && (
                                        <p className="text-xs text-muted-foreground mt-1">{script.description}</p>
                                    )}
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            ) : null}

            {/* Script Plan Cards */}
            <div className="space-y-2">
                {plan.scripts.map((script, index) => (
                    <PlanScriptCard key={`${script.name}-${index}`} script={script} />
                ))}
            </div>

            {/* Pipeline Progress */}
            <PipelineProgress
                phase={pipelinePhase}
                completedSteps={completedPipelineSteps}
                error={pipelineError}
            />

            {/* Execution Results */}
            {executionResults.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Terminal className="h-4 w-4 text-primary" />
                            Execution Results
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {executionResults.map((result, i) => (
                                <ExecutionResultCard key={i} result={result} />
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Footer Actions */}
            <div className="flex justify-between mt-6 pt-4 border-t border-border">
                <Button variant="outline" onClick={onBack}>
                    Back to Understanding
                </Button>
                {pipelinePhase === "complete" ? (
                    <Button onClick={onProceed}>
                        <ChevronRight className="h-4 w-4 mr-1" />
                        Proceed to Notebook
                    </Button>
                ) : (
                    <Button
                        onClick={executePipeline}
                        disabled={isGeneratingPlan || (pipelinePhase !== "idle" && pipelinePhase !== "failed")}
                    >
                        <Play className="h-4 w-4 mr-1" />
                        Approve & Execute
                    </Button>
                )}
            </div>
        </div>
    )
}
