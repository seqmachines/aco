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
    Box,
    Download,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface GeneratedScript {
    name: string
    category: string
    script_type: string
    description: string
    code: string
    dependencies: string[]
    input_files: string[]
    output_files: string[]
    estimated_runtime: string | null
    requires_approval: boolean
}

interface ScriptPlan {
    manifest_id: string
    scripts: GeneratedScript[]
    execution_order: string[]
    total_estimated_runtime: string | null
    generated_at: string
    is_approved: boolean
}

interface ExecutionResult {
    script_name: string
    success: boolean
    exit_code: number
    stdout: string
    stderr: string
    duration_seconds: number
    started_at: string
    completed_at: string | null
    error_message: string | null
    output_files: string[]
}

interface ScriptRunnerProps {
    manifestId: string
    onComplete?: (results: ExecutionResult[]) => void
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

function ScriptCard({
    script,
    index: _index,
    isGenerating,
    isExecuting,
    result,
    onGenerateCode,
    onExecute,
}: {
    script: GeneratedScript
    index: number
    isGenerating: boolean
    isExecuting: boolean
    result: ExecutionResult | null
    onGenerateCode: () => void
    onExecute: () => void
}) {
    const [expanded, setExpanded] = useState(false)
    const hasCode = Boolean(script.code)

    return (
        <Card className={cn("transition-all", expanded && "ring-1 ring-border")}>
            <CardHeader className="pb-2 cursor-pointer" onClick={() => setExpanded(!expanded)}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        {expanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}
                        <FileCode className="h-4 w-4 text-primary" />
                        <CardTitle className="text-sm">{script.name}</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge variant="outline" className={categoryColors[script.category]}>
                            {categoryLabels[script.category] || script.category}
                        </Badge>
                        {result && (
                            result.success ? (
                                <CheckCircle className="h-4 w-4 text-success" />
                            ) : (
                                <XCircle className="h-4 w-4 text-destructive" />
                            )
                        )}
                    </div>
                </div>
                <CardDescription className="ml-6">{script.description}</CardDescription>
            </CardHeader>

            {expanded && (
                <CardContent className="space-y-4">
                    {/* Dependencies */}
                    {script.dependencies.length > 0 && (
                        <div>
                            <span className="text-xs text-muted-foreground">Dependencies: </span>
                            <span className="text-xs font-mono">
                                {script.dependencies.join(", ")}
                            </span>
                        </div>
                    )}

                    {/* Code preview */}
                    {hasCode && (
                        <div>
                            <span className="text-xs text-muted-foreground block mb-1">Code Preview:</span>
                            <pre className="p-3 bg-muted rounded text-xs font-mono overflow-x-auto max-h-48">
                                {script.code.slice(0, 500)}
                                {script.code.length > 500 && "\n..."}
                            </pre>
                        </div>
                    )}

                    {/* Execution result */}
                    {result && (
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <Terminal className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm font-medium">Execution Result</span>
                                <Badge variant={result.success ? "success" : "destructive"}>
                                    Exit code: {result.exit_code}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                    {result.duration_seconds.toFixed(2)}s
                                </span>
                            </div>

                            {result.stdout && (
                                <div>
                                    <span className="text-xs text-muted-foreground">stdout:</span>
                                    <pre className="p-2 bg-muted rounded text-xs font-mono overflow-x-auto max-h-32">
                                        {result.stdout.slice(0, 1000)}
                                    </pre>
                                </div>
                            )}

                            {result.stderr && (
                                <div>
                                    <span className="text-xs text-destructive">stderr:</span>
                                    <pre className="p-2 bg-destructive/10 rounded text-xs font-mono overflow-x-auto max-h-32">
                                        {result.stderr.slice(0, 1000)}
                                    </pre>
                                </div>
                            )}

                            {result.output_files.length > 0 && (
                                <div>
                                    <span className="text-xs text-muted-foreground">Output files:</span>
                                    <ul className="text-xs font-mono ml-4">
                                        {result.output_files.map((f, i) => (
                                            <li key={i}>{f}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2 pt-2 border-t">
                        {!hasCode && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={(e) => {
                                    e.stopPropagation()
                                    onGenerateCode()
                                }}
                                disabled={isGenerating}
                            >
                                {isGenerating ? (
                                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                                ) : (
                                    <Wand2 className="h-3 w-3 mr-1" />
                                )}
                                Generate Code
                            </Button>
                        )}
                        {hasCode && !result && (
                            <Button
                                size="sm"
                                onClick={(e) => {
                                    e.stopPropagation()
                                    onExecute()
                                }}
                                disabled={isExecuting}
                            >
                                {isExecuting ? (
                                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                                ) : (
                                    <Play className="h-3 w-3 mr-1" />
                                )}
                                Execute
                            </Button>
                        )}
                        {result && !result.success && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={(e) => {
                                    e.stopPropagation()
                                    onExecute()
                                }}
                                disabled={isExecuting}
                            >
                                <RefreshCw className="h-3 w-3 mr-1" />
                                Retry
                            </Button>
                        )}
                    </div>
                </CardContent>
            )}
        </Card>
    )
}

export function ScriptRunner({ manifestId, onComplete }: ScriptRunnerProps) {
    const [plan, setPlan] = useState<ScriptPlan | null>(null)
    const [isGeneratingPlan, setIsGeneratingPlan] = useState(false)
    const [generatingScriptIndex, setGeneratingScriptIndex] = useState<number | null>(null)
    const [executingScript, setExecutingScript] = useState<string | null>(null)
    const [results, setResults] = useState<Record<string, ExecutionResult>>({})
    const [error, setError] = useState<string | null>(null)

    // Environment state
    const [envExists, setEnvExists] = useState(false)
    const [isCreatingEnv, setIsCreatingEnv] = useState(false)
    const [isInstallingDeps, setIsInstallingDeps] = useState(false)
    const [isGeneratingAllCode, setIsGeneratingAllCode] = useState(false)
    const [envMessage, setEnvMessage] = useState<string | null>(null)

    // Check environment status on mount
    useEffect(() => {
        checkEnvStatus()
    }, [manifestId])

    const checkEnvStatus = async () => {
        try {
            const response = await fetch(`/scripts/env-status/${manifestId}`)
            if (response.ok) {
                const data = await response.json()
                setEnvExists(data.exists)
            }
        } catch (_e) {
            // Ignore errors
        }
    }

    // Load existing plan from disk on mount
    const loadExistingPlan = async () => {
        try {
            const response = await fetch(`/scripts/plan/${manifestId}`)
            if (response.ok) {
                const data = await response.json()
                if (data.plan) {
                    setPlan(data.plan)
                    console.log("Loaded existing plan from disk:", data.message)
                }
            }
        } catch (_e) {
            // No existing plan, that's fine
        }
    }

    // Load existing plan when component mounts
    useEffect(() => {
        loadExistingPlan()
    }, [manifestId])

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
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setIsGeneratingPlan(false)
        }
    }

    const generateCode = async (scriptIndex: number) => {
        if (!plan) return
        setGeneratingScriptIndex(scriptIndex)
        setError(null)
        try {
            const response = await fetch("/scripts/generate-code", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    manifest_id: manifestId,
                    script_index: scriptIndex,
                }),
            })
            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || "Failed to generate code")
            }
            const data = await response.json()
            // Update the plan with generated code
            const updatedScripts = [...plan.scripts]
            updatedScripts[scriptIndex] = {
                ...updatedScripts[scriptIndex],
                code: data.code,
            }
            setPlan({ ...plan, scripts: updatedScripts })
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setGeneratingScriptIndex(null)
        }
    }

    const executeScript = async (scriptName: string) => {
        setExecutingScript(scriptName)
        setError(null)
        try {
            const response = await fetch("/scripts/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    manifest_id: manifestId,
                    script_name: scriptName,
                }),
            })
            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || "Failed to execute script")
            }
            const data = await response.json()
            setResults((prev) => ({ ...prev, [scriptName]: data.result }))
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setExecutingScript(null)
        }
    }

    const executeAll = async () => {
        if (!plan) return
        setError(null)
        try {
            const response = await fetch("/scripts/execute-all", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || "Failed to execute scripts")
            }
            const data = await response.json()
            const newResults: Record<string, ExecutionResult> = {}
            for (const result of data.results) {
                newResults[result.script_name] = result
            }
            setResults(newResults)
            if (onComplete) {
                onComplete(data.results)
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        }
    }

    const createEnv = async () => {
        setIsCreatingEnv(true)
        setEnvMessage(null)
        setError(null)
        try {
            const response = await fetch("/scripts/create-env", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            const data = await response.json()
            if (data.success) {
                setEnvExists(true)
                setEnvMessage(data.message)
            } else {
                throw new Error(data.message)
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to create environment")
        } finally {
            setIsCreatingEnv(false)
        }
    }

    const installDeps = async () => {
        setIsInstallingDeps(true)
        setEnvMessage(null)
        setError(null)
        try {
            const response = await fetch("/scripts/install-deps", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            const data = await response.json()
            if (data.success) {
                setEnvMessage(`Installed: ${data.installed.join(", ") || "all dependencies"}`)
            } else {
                throw new Error(data.error || "Installation failed")
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to install dependencies")
        } finally {
            setIsInstallingDeps(false)
        }
    }

    const generateAllCode = async () => {
        console.log("generateAllCode called, plan:", plan, "manifestId:", manifestId)
        if (!plan) {
            console.log("No plan, returning early")
            return
        }
        setIsGeneratingAllCode(true)
        setError(null)
        console.log("Starting generateAllCode request...")
        try {
            const response = await fetch("/scripts/generate-all-code", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manifest_id: manifestId }),
            })
            console.log("Response status:", response.status)
            if (!response.ok) {
                const data = await response.json()
                console.log("Error response:", data)
                throw new Error(data.detail || "Failed to generate code")
            }
            const data = await response.json()
            console.log("Success response:", data)
            // Reload the plan to get updated code
            const planResponse = await fetch(`/scripts/plan/${manifestId}`)
            if (planResponse.ok) {
                const planData = await planResponse.json()
                setPlan(planData.plan)
                console.log("Plan updated with code")
            }
            if (data.failed.length > 0) {
                setError(`Some scripts failed: ${data.failed.join(", ")}`)
            }
        } catch (e) {
            console.error("generateAllCode error:", e)
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setIsGeneratingAllCode(false)
            console.log("generateAllCode finished")
        }
    }

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

    const allHaveCode = plan.scripts.every((s) => s.code)
    const allExecuted = plan.scripts.every((s) => results[s.name])
    const allSucceeded = allExecuted && Object.values(results).every((r) => r.success)

    return (
        <div className="space-y-4">
            {/* Error display */}
            {error && (
                <div className="p-3 bg-destructive/10 text-destructive rounded text-sm">
                    {error}
                </div>
            )}

            {/* Environment message */}
            {envMessage && (
                <div className="p-3 bg-green-500/10 text-green-600 rounded text-sm">
                    {envMessage}
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
                        {plan.scripts.length} scripts to generate and execute
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {/* Generate All Code button */}
                    {!allHaveCode && (
                        <Button
                            onClick={generateAllCode}
                            disabled={isGeneratingAllCode}
                            size="sm"
                            variant="outline"
                        >
                            {isGeneratingAllCode ? (
                                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            ) : (
                                <Wand2 className="h-3 w-3 mr-1" />
                            )}
                            Generate All Code
                        </Button>
                    )}

                    {/* Create Environment button */}
                    {allHaveCode && !envExists && (
                        <Button
                            onClick={createEnv}
                            disabled={isCreatingEnv}
                            size="sm"
                            variant="outline"
                        >
                            {isCreatingEnv ? (
                                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            ) : (
                                <Box className="h-3 w-3 mr-1" />
                            )}
                            Create Environment
                        </Button>
                    )}

                    {/* Install Dependencies button */}
                    {allHaveCode && envExists && (
                        <Button
                            onClick={installDeps}
                            disabled={isInstallingDeps}
                            size="sm"
                            variant="outline"
                        >
                            {isInstallingDeps ? (
                                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            ) : (
                                <Download className="h-3 w-3 mr-1" />
                            )}
                            Install Dependencies
                        </Button>
                    )}

                    {/* Execute All button */}
                    {allHaveCode && !allExecuted && (
                        <Button onClick={executeAll} size="sm">
                            <Play className="h-3 w-3 mr-1" />
                            Execute All
                        </Button>
                    )}
                    {allSucceeded && (
                        <Badge variant="success" className="flex items-center gap-1">
                            <CheckCircle className="h-3 w-3" />
                            All Completed
                        </Badge>
                    )}
                </div>
            </div>

            {error && (
                <div className="p-3 bg-destructive/10 text-destructive rounded text-sm">
                    {error}
                </div>
            )}

            {/* Script Cards */}
            <div className="space-y-3">
                {plan.scripts.map((script, index) => (
                    <ScriptCard
                        key={script.name}
                        script={script}
                        index={index}
                        isGenerating={generatingScriptIndex === index}
                        isExecuting={executingScript === script.name}
                        result={results[script.name] || null}
                        onGenerateCode={() => generateCode(index)}
                        onExecute={() => executeScript(script.name)}
                    />
                ))}
            </div>
        </div>
    )
}
