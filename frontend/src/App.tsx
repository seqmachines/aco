import { useState, useCallback } from "react"
import { Dna, Github, Settings as SettingsIcon, Moon, Sun, Check, Circle, Loader2, PanelLeftClose, PanelLeft } from "lucide-react"
import { IntakeForm } from "@/components/IntakeForm"
import { FileScanner } from "@/components/FileScanner"
import { ManifestViewer } from "@/components/ManifestViewer"
import { UnderstandingEditor } from "@/components/UnderstandingEditor"
import { Settings } from "@/components/Settings"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { useIntake, useManifest, useUnderstanding, useConfig } from "@/hooks/useApi"
import { useTheme } from "@/hooks/useTheme"
import { useSettings } from "@/hooks/useSettings"
import { useAutoSave } from "@/hooks/useAutoSave"
import type { AppStep, Manifest, ExperimentUnderstanding, IntakeFormData } from "@/types"

interface SidebarSection {
  id: AppStep
  label: string
  shortLabel: string
}

const sections: SidebarSection[] = [
  { id: "intake", label: "Describe Your Experiment", shortLabel: "Describe" },
  { id: "scanning", label: "Scanning Files", shortLabel: "Scan" },
  { id: "manifest", label: "Review Discovered Data", shortLabel: "Review" },
  { id: "understanding", label: "AI-Powered Analysis", shortLabel: "Analyze" },
  { id: "approved", label: "Analysis Complete", shortLabel: "Complete" },
]

function App() {
  const [currentStep, setCurrentStep] = useState<AppStep>("intake")
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [understanding, setUnderstanding] = useState<ExperimentUnderstanding | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const { theme, toggleTheme } = useTheme()
  const { settings, updateSettings, availableModels } = useSettings()
  const { config } = useConfig()
  const { savedData, saveData, clearData } = useAutoSave()

  const { submitIntake, isLoading: intakeLoading } = useIntake()
  const { updateManifest, isLoading: manifestLoading } = useManifest()
  const {
    generateUnderstanding,
    approveUnderstanding,
    isLoading: understandingLoading,
  } = useUnderstanding()

  // Get the default directory from config (where aco was started)
  const defaultDirectory = config?.working_dir || ""

  const handleIntakeSubmit = useCallback(
    async (data: IntakeFormData) => {
      setError(null)
      setCurrentStep("scanning")

      const result = await submitIntake(data)
      if (result) {
        setManifest(result.manifest)
        setCurrentStep("manifest")
        // Clear saved draft after successful submission
        clearData()
      } else {
        setError("Failed to submit intake. Please check your input and try again.")
        setCurrentStep("intake")
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
        setError("Failed to update manifest.")
      }
    },
    [manifest, updateManifest]
  )

  const handleProceedToUnderstanding = useCallback(async () => {
    if (!manifest) return

    setError(null)
    setCurrentStep("understanding")

    const result = await generateUnderstanding(manifest.id)
    if (result) {
      setUnderstanding(result.understanding)
    } else {
      setError("Failed to generate understanding. Make sure GOOGLE_API_KEY is set.")
    }
  }, [manifest, generateUnderstanding])

  const handleRegenerate = useCallback(async () => {
    if (!manifest) return

    setError(null)
    const result = await generateUnderstanding(manifest.id, true)
    if (result) {
      setUnderstanding(result.understanding)
    } else {
      setError("Failed to regenerate understanding.")
    }
  }, [manifest, generateUnderstanding])

  const handleApprove = useCallback(
    async (edits?: Record<string, string>) => {
      if (!manifest) return

      setError(null)
      const result = await approveUnderstanding(manifest.id, edits)
      if (result) {
        setUnderstanding(result.understanding)
        setCurrentStep("approved")
      } else {
        setError("Failed to approve understanding.")
      }
    },
    [manifest, approveUnderstanding]
  )

  const handleStartOver = useCallback(() => {
    setCurrentStep("intake")
    setManifest(null)
    setUnderstanding(null)
    setError(null)
    clearData()
  }, [clearData])

  // Handle sidebar navigation
  const handleSectionClick = (sectionId: AppStep) => {
    const currentIndex = sections.findIndex(s => s.id === currentStep)
    const targetIndex = sections.findIndex(s => s.id === sectionId)
    
    // Only allow navigating to completed or current sections
    if (targetIndex <= currentIndex) {
      setCurrentStep(sectionId)
    }
  }

  const isLoading = intakeLoading || manifestLoading || understandingLoading
  const currentIndex = sections.findIndex(s => s.id === currentStep)

  return (
    <div className="min-h-screen bg-background flex">
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

        {/* Navigation Sections */}
        <nav className={cn("flex-1 py-2", sidebarCollapsed ? "px-2" : "px-2")}>
          {sections.map((section, index) => {
            const isComplete = index < currentIndex
            const isCurrent = index === currentIndex
            const isAccessible = index <= currentIndex

            return (
              <button
                key={section.id}
                onClick={() => handleSectionClick(section.id)}
                disabled={!isAccessible}
                title={sidebarCollapsed ? section.label : undefined}
                className={cn(
                  "w-full flex items-center gap-2 rounded transition-all duration-200 mb-0.5",
                  sidebarCollapsed ? "px-0 py-2 justify-center" : "px-2 py-2",
                  isCurrent && "bg-foreground/10",
                  isComplete && "hover:bg-muted/50 cursor-pointer",
                  !isAccessible && "opacity-35 cursor-not-allowed",
                  isAccessible && !isCurrent && "hover:bg-muted/50"
                )}
              >
                {/* Status Indicator */}
                <div
                  className={cn(
                    "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-semibold transition-all duration-300",
                    isComplete && "bg-foreground text-background",
                    isCurrent && "bg-foreground/20 text-foreground ring-1 ring-foreground/30",
                    !isComplete && !isCurrent && "bg-muted text-muted-foreground"
                  )}
                >
                  {isComplete ? (
                    <Check className="h-3 w-3" />
                  ) : isCurrent && isLoading ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <span>{index + 1}</span>
                  )}
                </div>

                {/* Label - only show when not collapsed */}
                {!sidebarCollapsed && (
                  <span
                    className={cn(
                      "text-xs font-medium truncate",
                      isCurrent && "text-foreground",
                      isComplete && "text-foreground",
                      !isComplete && !isCurrent && "text-muted-foreground"
                    )}
                  >
                    {section.shortLabel}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Header */}
        <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-sm px-6 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">
                {sections.find(s => s.id === currentStep)?.label}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              {currentStep === "intake" && savedData && (
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
        />

        {/* Main Content */}
        <main className="flex-1 p-6 overflow-auto">
          {/* Error Banner */}
          {error && (
            <Card className="mb-6 border-destructive/50 bg-destructive/10">
              <CardContent className="py-3">
                <p className="text-destructive text-sm">{error}</p>
              </CardContent>
            </Card>
          )}

          {/* Step Content */}
          {currentStep === "intake" && (
            <div className="max-w-3xl">
              <IntakeForm
                onSubmit={handleIntakeSubmit}
                isLoading={isLoading}
                defaultDirectory={defaultDirectory}
                savedData={savedData}
                onSave={saveData}
              />
            </div>
          )}

          {currentStep === "scanning" && (
            <div className="max-w-3xl">
              <FileScanner scanResult={null} isLoading={true} />
            </div>
          )}

          {currentStep === "manifest" && manifest && (
            <div className="max-w-4xl">
              <ManifestViewer
                manifest={manifest}
                onUpdate={handleManifestUpdate}
                onProceed={handleProceedToUnderstanding}
                isLoading={isLoading}
              />
            </div>
          )}

          {currentStep === "understanding" && (
            <div className="max-w-4xl">
              <UnderstandingEditor
                understanding={understanding}
                isLoading={understandingLoading}
                onRegenerate={handleRegenerate}
                onApprove={handleApprove}
              />
            </div>
          )}

          {currentStep === "approved" && understanding && (
            <div className="max-w-4xl">
              <Card className="border-success/30 bg-success/5">
                <CardContent className="py-8 text-center">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-success/20 mb-4">
                    <Dna className="h-8 w-8 text-success" />
                  </div>
                  <h2 className="text-2xl font-bold mb-2">Analysis Complete!</h2>
                  <p className="text-muted-foreground mb-6">
                    Your experiment understanding has been approved and is ready for QC.
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
    </div>
  )
}

export default App
