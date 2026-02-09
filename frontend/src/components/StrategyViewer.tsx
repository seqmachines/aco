import { useState, useEffect, useCallback } from "react"
import { Loader2, ArrowRight, AlertTriangle, CheckCircle2, Zap, FileCode, RefreshCw, Trash2, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { AnalysisStrategy } from "@/types"

interface StrategyViewerProps {
  manifestId: string
  model?: string
  apiKey?: string
  onComplete: () => void
  onBack?: () => void
}

export function StrategyViewer({ manifestId, model, apiKey, onComplete, onBack }: StrategyViewerProps) {
  const [strategy, setStrategy] = useState<AnalysisStrategy | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [userApproach, setUserApproach] = useState("")

  // Load existing strategy
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/analyze/strategy/${manifestId}`)
        if (res.ok) {
          const data = await res.json()
          setStrategy(data.strategy)
          if (data.strategy?.user_approach) {
            setUserApproach(data.strategy.user_approach)
          }
        }
      } catch {
        // No strategy yet
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [manifestId])

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    setError(null)
    try {
      const res = await fetch("/analyze/strategy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manifest_id: manifestId,
          model: model || undefined,
          api_key: apiKey || undefined,
          user_approach: userApproach || undefined,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setStrategy(data.strategy)
      } else {
        const errData = await res.json().catch(() => ({ detail: "Unknown error" }))
        setError(errData.detail || "Failed to generate strategy")
      }
    } catch (e) {
      setError("Network error generating strategy")
    } finally {
      setGenerating(false)
    }
  }, [manifestId, model, apiKey, userApproach])

  const handleSaveStrategy = useCallback(async () => {
    if (!strategy) return
    try {
      await fetch(`/analyze/strategy/${manifestId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy }),
      })
    } catch (e) {
      console.error("Failed to save strategy", e)
    }
  }, [manifestId, strategy])

  const handleContinue = useCallback(async () => {
    await handleSaveStrategy()
    onComplete()
  }, [handleSaveStrategy, onComplete])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // No strategy yet -- prompt to generate
  if (!strategy) {
    return (
      <div className="space-y-6">
        {/* User approach input */}
        <Card>
          <CardContent className="pt-6">
            <label className="block text-sm font-semibold mb-2">
              How should the analysis be done?
            </label>
            <p className="text-xs text-muted-foreground mb-3">
              Optionally describe your preferred analysis approach, tools, or methods. This will guide
              the strategy generation.
            </p>
            <Textarea
              value={userApproach}
              onChange={(e) => setUserApproach(e.target.value)}
              placeholder="Describe your preferred analysis approach, tools, or methods..."
              className="min-h-[200px]"
            />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-8 text-center">
            <Zap className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
            <h3 className="text-lg font-semibold mb-2">Generate Analysis Strategy</h3>
            <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
              The LLM will generate a structured analysis strategy based on your experiment understanding,
              hypotheses, and selected references.
            </p>
            {error && (
              <p className="text-destructive text-sm mb-4">{error}</p>
            )}
            <Button onClick={handleGenerate} disabled={generating}>
              {generating ? (
                <><Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> Generating...</>
              ) : (
                "Generate Strategy"
              )}
            </Button>
          </CardContent>
        </Card>
        <div className="flex justify-between">
          {onBack ? <Button variant="outline" onClick={onBack}>Back</Button> : <div />}
          <Button onClick={async () => {
            onComplete()
          }}>Skip to Execute</Button>
        </div>
      </div>
    )
  }

  // Render strategy
  return (
    <div className="space-y-6">
      {/* Summary */}
      {strategy.summary && (
        <Card>
          <CardContent className="pt-6">
            <h4 className="text-sm font-semibold mb-2">Strategy Summary</h4>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">{strategy.summary}</p>
          </CardContent>
        </Card>
      )}



      {/* Hypotheses to test */}
      {strategy.hypotheses_to_test?.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold">References & Hypotheses</h4>
            </div>
            <div className="space-y-3">
              {strategy.hypotheses_to_test.map((ht, i) => (
                <div key={i} className="border rounded p-3 relative group">
                  <button
                    onClick={() => {
                      const newHypotheses = [...strategy.hypotheses_to_test]
                      newHypotheses.splice(i, 1)
                      setStrategy({ ...strategy, hypotheses_to_test: newHypotheses })
                    }}
                    className="absolute top-2 right-2 p-1 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Delete hypothesis"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>

                  <div className="space-y-2 pr-6">
                    <Input
                      value={ht.hypothesis}
                      onChange={(e) => {
                        const newHypotheses = [...strategy.hypotheses_to_test]
                        newHypotheses[i] = { ...newHypotheses[i], hypothesis: e.target.value }
                        setStrategy({ ...strategy, hypotheses_to_test: newHypotheses })
                      }}
                      className="font-medium h-8 text-sm"
                      placeholder="Hypothesis statement"
                    />
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="font-medium text-foreground block mb-1">Test method:</span>
                        <Input
                          value={ht.test_method}
                          onChange={(e) => {
                            const newHypotheses = [...strategy.hypotheses_to_test]
                            newHypotheses[i] = { ...newHypotheses[i], test_method: e.target.value }
                            setStrategy({ ...strategy, hypotheses_to_test: newHypotheses })
                          }}
                          className="h-7 text-xs"
                          placeholder="How to test"
                        />
                      </div>
                      <div>
                        <span className="font-medium text-foreground block mb-1">Expected:</span>
                        <Input
                          value={ht.expected_outcome}
                          onChange={(e) => {
                            const newHypotheses = [...strategy.hypotheses_to_test]
                            newHypotheses[i] = { ...newHypotheses[i], expected_outcome: e.target.value }
                            setStrategy({ ...strategy, hypotheses_to_test: newHypotheses })
                          }}
                          className="h-7 text-xs"
                          placeholder="Expected outcome"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Add new hypothesis */}
            <div className="mt-4 pt-4 border-t">
              <Button
                variant="outline"
                size="sm"
                className="w-full border-dashed text-muted-foreground"
                onClick={() => {
                  const newHypothesis = {
                    hypothesis: "New hypothesis",
                    test_method: "Describe test method",
                    expected_outcome: "Describe expected outcome",
                    required_data: []
                  }
                  setStrategy({
                    ...strategy,
                    hypotheses_to_test: [...strategy.hypotheses_to_test, newHypothesis]
                  })
                }}
              >
                <Plus className="h-3.5 w-3.5 mr-2" />
                Add Hypothesis
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Gate Checklist */}
      {strategy.gate_checklist?.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <h4 className="text-sm font-semibold mb-3">QC Gate Checklist</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="text-left py-2 pr-3 font-medium">Gate</th>
                    <th className="text-left py-2 pr-3 font-medium">Pass Criteria</th>
                    <th className="text-left py-2 pr-3 font-medium">Fail Criteria</th>
                    <th className="text-left py-2 pr-3 font-medium">Module</th>
                    <th className="text-left py-2 font-medium">Priority</th>
                  </tr>
                </thead>
                <tbody>
                  {strategy.gate_checklist.map((gate, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-2 pr-3 font-medium">{gate.gate_name}</td>
                      <td className="py-2 pr-3">
                        <span className="flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3 text-green-500 flex-shrink-0" />
                          {gate.pass_criteria}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        <span className="flex items-center gap-1">
                          <AlertTriangle className="h-3 w-3 text-red-500 flex-shrink-0" />
                          {gate.fail_criteria}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        {gate.module_name ? (
                          <Badge variant="outline" className="text-[9px]">{gate.module_name}</Badge>
                        ) : (
                          <span className="text-muted-foreground">--</span>
                        )}
                      </td>
                      <td className="py-2">
                        <Badge
                          variant={gate.priority === "required" ? "default" : "secondary"}
                          className="text-[9px]"
                        >
                          {gate.priority}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Execution Plan */}
      {strategy.execution_plan?.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <h4 className="text-sm font-semibold mb-3">Suggested Execution Plan</h4>
            <div className="space-y-2">
              {strategy.execution_plan.map((step, i) => (
                <div key={i} className="flex items-start gap-3 border rounded p-3">
                  <div className={cn(
                    "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold",
                    step.is_deterministic
                      ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                      : "bg-muted text-muted-foreground"
                  )}>
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{step.name}</span>
                      {step.is_deterministic && (
                        <Badge variant="outline" className="text-[9px] text-green-600 border-green-300">
                          Deterministic
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
                    {step.tool_or_module && (
                      <span className="text-[10px] text-muted-foreground">
                        Tool: {step.tool_or_module}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Script Insights */}
      {strategy.script_insights?.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <h4 className="text-sm font-semibold mb-3">Reference Script Insights</h4>
            <div className="space-y-3">
              {strategy.script_insights.map((insight, i) => (
                <div key={i} className="border rounded p-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-sm font-mono font-medium truncate">
                      {insight.script_path.split("/").pop()}
                    </span>
                  </div>
                  <p className="text-xs mb-2"><span className="font-medium">Intent:</span> {insight.intent}</p>
                  {Object.keys(insight.parameters).length > 0 && (
                    <div className="mb-2">
                      <span className="text-xs font-medium">Parameters:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {Object.entries(insight.parameters).map(([k, v]) => (
                          <Badge key={k} variant="outline" className="text-[9px] font-mono">
                            {k}={v}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {insight.adaptation_notes.length > 0 && (
                    <div>
                      <span className="text-xs font-medium">Adaptation notes:</span>
                      <ul className="text-xs text-muted-foreground ml-4 mt-1 list-disc">
                        {insight.adaptation_notes.map((note, j) => (
                          <li key={j}>{note}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Required tools & modules */}
      {(strategy.required_modules?.length > 0 || strategy.required_tools?.length > 0) && (
        <Card>
          <CardContent className="pt-6">
            <h4 className="text-sm font-semibold mb-3">Required Tools & Modules</h4>
            <div className="flex flex-wrap gap-2">
              {strategy.required_modules.map((m) => (
                <Badge key={m} variant="default" className="text-[10px]">{m}</Badge>
              ))}
              {strategy.required_tools.map((t) => (
                <Badge key={t} variant="secondary" className="text-[10px]">{t}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      <div className="flex justify-between pt-2">
        {onBack ? <Button variant="outline" onClick={onBack}>Back</Button> : <div />}
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleGenerate} disabled={generating}>
            <RefreshCw className={cn("h-3.5 w-3.5 mr-1", generating && "animate-spin")} />
            Regenerate
          </Button>
          <Button onClick={handleContinue}>
            Continue to Execute <ArrowRight className="h-3.5 w-3.5 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  )
}
