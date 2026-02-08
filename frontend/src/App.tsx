import { useState, useCallback, useEffect } from "react"
import { Dna, Github, Settings as SettingsIcon, Moon, Sun, Check, Circle, Loader2, PanelLeftClose, PanelLeft, ChevronRight } from "lucide-react"
import { IntakeForm } from "@/components/IntakeForm"
import { FileScanner } from "@/components/FileScanner"
import { ManifestViewer } from "@/components/ManifestViewer"
import { UnderstandingEditor, type UnderstandingGenerateOptions } from "@/components/UnderstandingEditor"
import { HypothesisForm } from "@/components/HypothesisForm"
// ReferenceSelector merged into HypothesisForm

import { StrategyViewer } from "@/components/StrategyViewer"
import { ScriptRunner } from "@/components/ScriptRunner"
import { PlotChooser } from "@/components/PlotChooser"
import { NotebookEditor } from "@/components/NotebookEditor"
import { ReportViewer } from "@/components/ReportViewer"
import { RunSelector } from "@/components/RunSelector"
import { Settings } from "@/components/Settings"
import { ChatPanel } from "@/components/ChatPanel"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { useIntake, useManifest, useUnderstanding, useConfig } from "@/hooks/useApi"
import { useTheme } from "@/hooks/useTheme"
import { useSettings } from "@/hooks/useSettings"
import { useAutoSave } from "@/hooks/useAutoSave"
import type { AppStep, Manifest, ExperimentUnderstanding, IntakeFormData, ScriptPlan } from "@/types"
import { PHASES, stepIndex, stepDef, phaseForStep } from "@/types"

function App() {
  const [currentStep, setCurrentStep] = useState<AppStep>("describe")
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [understanding, setUnderstanding] = useState<ExperimentUnderstanding | null>(null)
  const [scriptPlan, setScriptPlan] = useState<ScriptPlan | null>(null)
  const [, setScriptPlanLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [chatCollapsed, setChatCollapsed] = useState(false)
  // Track the highest step ever reached so users can navigate back to any visited step
  const [highestVisitedIdx, setHighestVisitedIdx] = useState(0)

  const { theme, toggleTheme } = useTheme()
  const { settings, updateSettings, availableModels } = useSettings()
  const { config, fetchRevealedApiKey } = useConfig()
  const { savedData, saveData, clearData } = useAutoSave()

  const { submitIntake, isLoading: intakeLoading, error: intakeError } = useIntake()
  const { updateManifest, isLoading: manifestLoading, error: manifestError } = useManifest()
  const {
    generateUnderstanding,
    approveUnderstanding,
    isLoading: understandingLoading,
    error: understandingError,
  } = useUnderstanding()

  // Get the default directory from config (where aco was started)
  const defaultDirectory = config?.working_dir || ""

  // Keep highestVisitedIdx in sync with navigation
  useEffect(() => {
    const idx = stepIndex(currentStep)
    setHighestVisitedIdx((prev) => Math.max(prev, idx))
  }, [currentStep])

  // Auto-generate script plan after understanding is available
  const generateScriptPlan = useCallback(
    async (manifestId: string) => {
      setScriptPlanLoading(true)
      try {
        // Try loading existing plan first
        const existingRes = await fetch(`/scripts/plan/${manifestId}`)
        if (existingRes.ok) {
          const data = await existingRes.json()
          if (data.plan) {
            setScriptPlan(data.plan)
            setScriptPlanLoading(false)
            return
          }
        }

        // Generate new plan
        const response = await fetch("/scripts/plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            manifest_id: manifestId,
            model: settings.model || undefined,
            api_key: settings.apiKey || undefined,
          }),
        })
        if (response.ok) {
          const data = await response.json()
          setScriptPlan(data.plan)
        }
      } catch (e) {
        console.error("Failed to generate script plan:", e)
      } finally {
        setScriptPlanLoading(false)
      }
    },
    [settings.model, settings.apiKey]
  )

  // Load latest run on startup
  useEffect(() => {
    const loadLatestRun = async () => {
      try {
        const res = await fetch("/manifest/latest")
        if (res.ok) {
          const data = await res.json()
          if (data.manifest) {
            setManifest(data.manifest)

            // Check for understanding
            const understandingRes = await fetch(`/understanding/${data.manifest.id}`)
            if (understandingRes.ok) {
              const uData = await understandingRes.json()
              setUnderstanding(uData.understanding)
              // Try loading existing script plan
              try {
                const planRes = await fetch(`/scripts/plan/${data.manifest.id}`)
                if (planRes.ok) {
                  const planData = await planRes.json()
                  if (planData.plan) setScriptPlan(planData.plan)
                }
              } catch (_e) { /* no plan yet, that's fine */ }
              // If we have understanding, check runs to see how far we got
              const runRes = await fetch(`/runs/${data.manifest.id}`)
              if (runRes.ok) {
                const runData = await runRes.json()
                // Determine step based on completed stages
                const stages = runData.stages_completed
                if (stages.includes("report")) setCurrentStep("report")
                else if (stages.includes("notebook")) setCurrentStep("notebook")
                else if (stages.includes("execute")) setCurrentStep("execute")
                else if (stages.includes("understanding")) setCurrentStep("understanding")
                else setCurrentStep("scan")
              } else {
                setCurrentStep("understanding")
              }
            } else {
              setCurrentStep("scan")
            }
          }
        }
      } catch (e) {
        console.error("Failed to load latest run:", e)
      }
    }

    loadLatestRun()
  }, [])

  const handleIntakeSubmit = useCallback(
    async (data: IntakeFormData) => {
      setError(null)
      // Briefly show scanning state within the scan step
      setCurrentStep("scan")

      const result = await submitIntake(data)
      if (result) {
        setManifest(result.manifest)
        // Stay on scan step which now shows the ManifestViewer
        setCurrentStep("scan")
        // Clear saved draft after successful submission
        clearData()
      } else {
        setError("Failed to submit intake. Please check your input and try again.")
        setCurrentStep("describe")
      }
    },
    [submitIntake, clearData]
  )

  const handleManifestUpdate = useCallback(
    async (data: {
      experiment_description?: string
      goals?: string
      known_issues?: string
      additional_notes?: string
      rescan?: boolean
    }) => {
      if (!manifest) return

      setError(null)
      const result = await updateManifest(manifest.id, data)
      if (result) {
        setManifest(result.manifest)
      } else {
        setError("Failed to update run data.")
      }
    },
    [manifest, updateManifest]
  )

  const handleProceedToUnderstanding = useCallback(async () => {
    if (!manifest) return

    setError(null)
    setCurrentStep("understanding")
    setScriptPlan(null)

    const result = await generateUnderstanding(
      manifest.id,
      false,
      settings.model,
      settings.apiKey
    )
    if (result) {
      setUnderstanding(result.understanding)
      // Auto-generate script plan after understanding
      generateScriptPlan(manifest.id)
    } else {
      // Go back to Scan & Review step and open settings
      setCurrentStep("scan")
      setSettingsOpen(true)
    }
  }, [manifest, generateUnderstanding, generateScriptPlan, settings.model, settings.apiKey])

  const handleRegenerate = useCallback(async (options?: UnderstandingGenerateOptions) => {
    if (!manifest) return

    setError(null)
    setScriptPlan(null)
    const result = await generateUnderstanding(
      manifest.id,
      true,
      settings.model,
      settings.apiKey,
      options,
    )
    if (result) {
      setUnderstanding(result.understanding)
      // Auto-regenerate script plan after understanding
      generateScriptPlan(manifest.id)
    } else {
      // Go back to Scan & Review step and open settings
      setCurrentStep("scan")
      setSettingsOpen(true)
    }
  }, [manifest, generateUnderstanding, generateScriptPlan, settings.model, settings.apiKey])

  const handleApprove = useCallback(
    async (edits?: Record<string, string>) => {
      if (!manifest) return

      setError(null)
      const result = await approveUnderstanding(manifest.id, edits)
      if (result) {
        setUnderstanding(result.understanding)
        setCurrentStep("hypothesis")
      } else {
        setError("Failed to approve understanding.")
      }
    },
    [manifest, approveUnderstanding]
  )

  const handleStartOver = useCallback(() => {
    setCurrentStep("describe")
    setHighestVisitedIdx(0)
    setManifest(null)
    setUnderstanding(null)
    setScriptPlan(null)
    setError(null)
    clearData()
  }, [clearData])

  // Handle artifact updates from chat panel
  const handleArtifactUpdate = useCallback((step: AppStep, data: Record<string, unknown>) => {
    if (step === "understanding") {
      setUnderstanding(data as unknown as ExperimentUnderstanding)
    } else if (step === "execute") {
      // Trust the chat update payload as the freshest plan state.
      setScriptPlan(data as unknown as ScriptPlan)
    }
  }, [])

  // Handle sidebar navigation -- allow jumping to any previously visited step
  const handleStepClick = (targetStep: AppStep) => {
    const tgtIdx = stepIndex(targetStep)
    if (tgtIdx <= highestVisitedIdx) {
      setCurrentStep(targetStep)
    }
  }

  const isLoading = intakeLoading || manifestLoading || understandingLoading
  const currentPhase = phaseForStep(currentStep)
  const currentStepDef = stepDef(currentStep)

  return (
    <div className="h-screen overflow-hidden bg-background flex">
      {/* Collapse Button - Fixed at viewport center */}
      <button
        onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
        style={{ left: sidebarCollapsed ? "44px" : "180px" }}
        className="fixed top-1/2 -translate-y-1/2 z-50 w-6 h-6 rounded-full bg-background border border-border shadow-sm flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-all duration-300"
        title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {sidebarCollapsed ? (
          <PanelLeft className="h-3 w-3" />
        ) : (
          <PanelLeftClose className="h-3 w-3" />
        )}
      </button>

      {/* Sidebar Navigation */}
      <aside
        className={cn(
          "border-r border-border bg-card/50 flex flex-col transition-all duration-300 ease-in-out",
          sidebarCollapsed ? "w-14" : "w-48"
        )}
      >
        {/* Logo + Actions */}
        <div className={cn(
          "border-b border-border flex items-center",
          sidebarCollapsed ? "p-3 justify-center" : "p-4 justify-between"
        )}>
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded bg-foreground/5 ring-1 ring-border">
                <Dna className="h-4 w-4 text-foreground" />
              </div>
              <h1 className="text-sm font-bold tracking-tight">aco</h1>
            </div>
          )}
          {sidebarCollapsed && (
            <div className="p-1.5 rounded bg-foreground/5 ring-1 ring-border">
              <Dna className="h-4 w-4 text-foreground" />
            </div>
          )}
          {!sidebarCollapsed && (
            <div className="flex items-center gap-0.5">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                className="text-muted-foreground hover:text-foreground h-7 w-7"
                title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
              >
                {theme === "light" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSettingsOpen(true)}
                className="text-muted-foreground hover:text-foreground h-7 w-7"
                title="Settings"
              >
                <SettingsIcon className="h-3.5 w-3.5" />
              </Button>
              <a
                href="https://github.com/seqmachines/aco"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground p-1.5 rounded hover:bg-muted/50 transition-colors"
                title="GitHub"
              >
                <Github className="h-3.5 w-3.5" />
              </a>
            </div>
          )}
        </div>

        {/* Run Selector */}
        {!sidebarCollapsed && (
          <div className="px-2 py-2 border-b border-border">
            <RunSelector
              currentManifestId={manifest?.id || null}
              onSelectRun={async (manifestId) => {
                // Load run - fetch manifest and understanding
                try {
                  const manifestRes = await fetch(`/manifest/${manifestId}`)
                  if (manifestRes.ok) {
                    const data = await manifestRes.json()
                    setManifest(data.manifest)
                  }
                  const understandingRes = await fetch(`/understanding/${manifestId}`)
                  if (understandingRes.ok) {
                    const data = await understandingRes.json()
                    setUnderstanding(data.understanding)
                    setCurrentStep("understanding")
                  } else {
                    setCurrentStep("scan")
                  }
                } catch (e) {
                  setError("Failed to load run")
                }
              }}
              onNewRun={handleStartOver}
            />
          </div>
        )}

        {/* Phase-grouped navigation */}
        <nav className={cn("flex-1 py-2 overflow-y-auto", sidebarCollapsed ? "px-2" : "px-2")}>
          {PHASES.map((phase, phaseIdx) => {
            const phaseStepIndices = phase.steps.map((s) => stepIndex(s.id))
            const phaseLastIdx = phaseStepIndices[phaseStepIndices.length - 1]
            const isPhaseComplete = highestVisitedIdx > phaseLastIdx
            const isPhaseCurrent = currentPhase === phase.id
            return (
              <div key={phase.id} className="mb-1">
                {/* Phase header */}
                {!sidebarCollapsed ? (
                  <div
                    className={cn(
                      "flex items-center gap-1.5 px-2 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider",
                      isPhaseComplete && "text-foreground",
                      isPhaseCurrent && "text-foreground",
                      !isPhaseComplete && !isPhaseCurrent && "text-muted-foreground/60"
                    )}
                  >
                    <div
                      className={cn(
                        "flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold",
                        isPhaseComplete && "bg-foreground text-background",
                        isPhaseCurrent && "bg-foreground/20 text-foreground ring-1 ring-foreground/30",
                        !isPhaseComplete && !isPhaseCurrent && "bg-muted text-muted-foreground"
                      )}
                    >
                      {isPhaseComplete ? (
                        <Check className="h-2.5 w-2.5" />
                      ) : (
                        <span>{phaseIdx + 1}</span>
                      )}
                    </div>
                    <span>{phase.shortLabel}</span>
                  </div>
                ) : (
                  <div
                    className={cn(
                      "flex justify-center py-1.5",
                    )}
                    title={phase.label}
                  >
                    <div
                      className={cn(
                        "w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold",
                        isPhaseComplete && "bg-foreground text-background",
                        isPhaseCurrent && "bg-foreground/20 text-foreground ring-1 ring-foreground/30",
                        !isPhaseComplete && !isPhaseCurrent && "bg-muted text-muted-foreground"
                      )}
                    >
                      {isPhaseComplete ? (
                        <Check className="h-2.5 w-2.5" />
                      ) : (
                        <span>{phaseIdx + 1}</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Sub-steps */}
                {!sidebarCollapsed && (
                  <div className="ml-4 border-l border-border/50 pl-2">
                    {phase.steps.map((step) => {
                      const idx = stepIndex(step.id)
                      const isVisited = idx < highestVisitedIdx
                      const isCurrent = step.id === currentStep
                      const isAccessible = idx <= highestVisitedIdx

                      return (
                        <button
                          key={step.id}
                          onClick={() => handleStepClick(step.id)}
                          disabled={!isAccessible}
                          className={cn(
                            "w-full flex items-center gap-1.5 rounded transition-all duration-200 px-2 py-1.5 mb-0.5",
                            isCurrent && "bg-foreground/10",
                            isVisited && !isCurrent && "hover:bg-muted/50 cursor-pointer",
                            !isAccessible && "opacity-35 cursor-not-allowed",
                            isAccessible && !isCurrent && "hover:bg-muted/50"
                          )}
                        >
                          <div
                            className={cn(
                              "flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center transition-all duration-300",
                              isVisited && !isCurrent && "bg-foreground text-background",
                              isCurrent && "bg-foreground/20 text-foreground ring-1 ring-foreground/30",
                              !isVisited && !isCurrent && "bg-muted text-muted-foreground"
                            )}
                          >
                            {isVisited && !isCurrent ? (
                              <Check className="h-2.5 w-2.5" />
                            ) : isCurrent && isLoading ? (
                              <Loader2 className="h-2.5 w-2.5 animate-spin" />
                            ) : (
                              <ChevronRight className="h-2.5 w-2.5" />
                            )}
                          </div>
                          <span
                            className={cn(
                              "text-[11px] font-medium truncate",
                              isCurrent && "text-foreground",
                              isVisited && "text-foreground",
                              !isVisited && !isCurrent && "text-muted-foreground"
                            )}
                          >
                            {step.shortLabel}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full min-w-0">
        {/* Header */}
        <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-sm px-6 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">
                {currentStepDef?.label ?? currentStep}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              {manifest && (
                <Badge variant="outline" className="text-[10px] font-mono">
                  {manifest.id.replace("manifest_", "run_")}
                </Badge>
              )}
              {currentStep === "describe" && savedData && (
                <Badge variant="secondary" className="text-[10px]">
                  <Circle className="h-1.5 w-1.5 mr-1 fill-success text-success" />
                  Draft saved
                </Badge>
              )}
              {sidebarCollapsed && (
                <div className="flex items-center gap-0.5 border-l border-border pl-2 ml-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleTheme}
                    className="text-muted-foreground hover:text-foreground h-7 w-7"
                  >
                    {theme === "light" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setSettingsOpen(true)}
                    className="text-muted-foreground hover:text-foreground h-7 w-7"
                  >
                    <SettingsIcon className="h-3.5 w-3.5" />
                  </Button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Settings Modal */}
        <Settings
          isOpen={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          settings={settings}
          onUpdateSettings={updateSettings}
          theme={theme}
          onToggleTheme={toggleTheme}
          availableModels={availableModels}
          config={config}
          onRevealServerKey={fetchRevealedApiKey}
        />

        {/* Main Content */}
        <main className="flex-1 p-6 overflow-auto">
          {/* Error Banner */}
          {/* Error Banner */}
          {(error || intakeError || manifestError || understandingError) && (
            <Card className="mb-6 border-destructive/50 bg-destructive/10">
              <CardContent className="py-3">
                <p className="text-destructive text-sm">
                  {error || intakeError || manifestError || understandingError}
                </p>
              </CardContent>
            </Card>
          )}

          {/* ---- Phase 1: Understand ---- */}

          {currentStep === "describe" && (
            <div className="max-w-4xl mx-auto">
              <IntakeForm
                onSubmit={handleIntakeSubmit}
                isLoading={isLoading}
                defaultDirectory={defaultDirectory}
                savedData={savedData}
                onSave={saveData}
              />
            </div>
          )}

          {currentStep === "scan" && !manifest && (
            <div className="max-w-4xl mx-auto">
              <FileScanner scanResult={null} isLoading={true} />
            </div>
          )}

          {currentStep === "scan" && manifest && (
            <div className="max-w-5xl mx-auto">
              <ManifestViewer
                manifest={manifest}
                onUpdate={handleManifestUpdate}
                onProceed={handleProceedToUnderstanding}
                isLoading={isLoading}
              />
            </div>
          )}

          {currentStep === "understanding" && (
            <div className="max-w-5xl mx-auto">
              <UnderstandingEditor
                understanding={understanding}
                isLoading={understandingLoading}
                onRegenerate={handleRegenerate}
                onApprove={handleApprove}
              />
            </div>
          )}

          {/* ---- Phase 2: Analyze ---- */}

          {currentStep === "hypothesis" && manifest && (
            <div className="max-w-5xl mx-auto">
              <HypothesisForm
                manifestId={manifest.id}
                onComplete={() => setCurrentStep("strategy")}
                onBack={() => setCurrentStep("understanding")}
              />
            </div>
          )}

          {currentStep === "strategy" && manifest && (
            <div className="max-w-5xl mx-auto">
              <StrategyViewer
                manifestId={manifest.id}
                model={settings.model}
                apiKey={settings.apiKey}
                onComplete={() => setCurrentStep("execute")}
                onBack={() => setCurrentStep("hypothesis")}
              />
            </div>
          )}

          {currentStep === "execute" && manifest && (
            <div className="max-w-5xl mx-auto">
              <ScriptRunner
                manifestId={manifest.id}
                initialPlan={scriptPlan}
                understanding={understanding}
                model={settings.model}
                apiKey={settings.apiKey}
                onPlanUpdate={setScriptPlan}
                onComplete={() => setCurrentStep("plots")}
                onBack={() => setCurrentStep("strategy")}
                onProceed={() => setCurrentStep("plots")}
              />
            </div>
          )}

          {/* ---- Phase 3: Summarize ---- */}

          {currentStep === "plots" && manifest && (
            <div className="max-w-5xl mx-auto">
              <PlotChooser
                manifestId={manifest.id}
                onComplete={() => setCurrentStep("notebook")}
                onBack={() => setCurrentStep("execute")}
              />
            </div>
          )}

          {currentStep === "notebook" && manifest && (
            <div className="max-w-5xl mx-auto">
              <NotebookEditor
                manifestId={manifest.id}
                onComplete={() => setCurrentStep("report")}
              />
              <div className="flex justify-between mt-6 pt-4 border-t">
                <Button variant="outline" onClick={() => setCurrentStep("plots")}>
                  Back to Plot Selection
                </Button>
                <Button onClick={() => setCurrentStep("report")}>
                  Proceed to Report
                </Button>
              </div>
            </div>
          )}

          {currentStep === "report" && manifest && (
            <div className="max-w-5xl mx-auto">
              <ReportViewer
                manifestId={manifest.id}
                onComplete={() => setCurrentStep("optimize")}
              />
              <div className="flex justify-between mt-6 pt-4 border-t">
                <Button variant="outline" onClick={() => setCurrentStep("notebook")}>
                  Back to Notebook
                </Button>
                <Button onClick={() => setCurrentStep("optimize")}>
                  Continue to Optimization
                </Button>
              </div>
            </div>
          )}

          {currentStep === "optimize" && understanding && (
            <div className="max-w-5xl mx-auto">
              <Card className="border-success/30 bg-success/5">
                <CardContent className="py-8 text-center">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-success/20 mb-4">
                    <Dna className="h-8 w-8 text-success" />
                  </div>
                  <h2 className="text-2xl font-bold mb-2">Analysis Complete</h2>
                  <p className="text-muted-foreground mb-6">
                    Use the chat panel to discuss optimization strategies, protocol improvements, and next steps.
                  </p>
                  <div className="flex justify-center gap-4">
                    <Button variant="outline" onClick={handleStartOver}>
                      Start New Analysis
                    </Button>
                    <Button onClick={() => setCurrentStep("understanding")}>
                      Review Understanding
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Summary */}
              <div className="mt-6">
                <UnderstandingEditor
                  understanding={understanding}
                  isLoading={false}
                  onRegenerate={handleRegenerate}
                  onApprove={handleApprove}
                />
              </div>
            </div>
          )}
        </main>

        {/* Footer */}
        <footer className="border-t border-border py-3 px-6">
          <div className="flex items-center justify-between text-[10px] text-muted-foreground">
            <p>aco v0.1.0</p>
            <p>
              Powered by{" "}
              <a href="https://ai.google.dev" className="hover:underline">
                Google Gemini
              </a>
              {settings.model && (
                <span className="ml-1">({settings.model})</span>
              )}
            </p>
          </div>
        </footer>
      </div>

      {/* Chat Panel - Right Sidebar (show for all steps except describe) */}
      {currentStep !== "describe" && (
        <ChatPanel
          manifestId={manifest?.id}
          currentStep={currentStep}
          collapsed={chatCollapsed}
          onToggle={() => setChatCollapsed(!chatCollapsed)}
          onArtifactUpdate={handleArtifactUpdate}
          model={settings.model}
          apiKey={settings.apiKey}
        />
      )}
    </div>
  )
}

export default App
