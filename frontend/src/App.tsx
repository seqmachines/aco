import { useState, useCallback } from "react"
import { Dna, Github, Settings as SettingsIcon, Moon, Sun } from "lucide-react"
import { ProgressSteps } from "@/components/ui/progress-steps"
import { IntakeForm } from "@/components/IntakeForm"
import { FileScanner } from "@/components/FileScanner"
import { ManifestViewer } from "@/components/ManifestViewer"
import { UnderstandingEditor } from "@/components/UnderstandingEditor"
import { Settings } from "@/components/Settings"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useIntake, useManifest, useUnderstanding } from "@/hooks/useApi"
import { useTheme } from "@/hooks/useTheme"
import { useSettings } from "@/hooks/useSettings"
import type { AppStep, Manifest, ExperimentUnderstanding } from "@/types"

function App() {
  const [currentStep, setCurrentStep] = useState<AppStep>("intake")
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [understanding, setUnderstanding] = useState<ExperimentUnderstanding | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const { theme, toggleTheme } = useTheme()
  const { settings, updateSettings, availableModels } = useSettings()

  const { submitIntake, isLoading: intakeLoading } = useIntake()
  const { updateManifest, isLoading: manifestLoading } = useManifest()
  const {
    generateUnderstanding,
    approveUnderstanding,
    isLoading: understandingLoading,
  } = useUnderstanding()

  const handleIntakeSubmit = useCallback(
    async (data: {
      experiment_description: string
      target_directory: string
      goals?: string
      known_issues?: string
      additional_notes?: string
    }) => {
      setError(null)
      setCurrentStep("scanning")

      const result = await submitIntake(data)
      if (result) {
        setManifest(result.manifest)
        setCurrentStep("manifest")
      } else {
        setError("Failed to submit intake. Please check your input and try again.")
        setCurrentStep("intake")
      }
    },
    [submitIntake]
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
  }, [])

  const isLoading = intakeLoading || manifestLoading || understandingLoading

  return (
    <div className="min-h-screen bg-background bg-grid-pattern">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Dna className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">aco</h1>
                <p className="text-xs text-muted-foreground">
                  agentic sequencing quality control
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="hidden sm:flex">
                v0.1.0
              </Badge>
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
              >
                {theme === "light" ? (
                  <Moon className="h-5 w-5" />
                ) : (
                  <Sun className="h-5 w-5" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSettingsOpen(true)}
                title="Settings"
              >
                <SettingsIcon className="h-5 w-5" />
              </Button>
              <a
                href="https://github.com/seqmachines/aco"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors p-2"
              >
                <Github className="h-5 w-5" />
              </a>
            </div>
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

      {/* Progress Steps */}
      <div className="container mx-auto px-4 py-6">
        <ProgressSteps currentStep={currentStep} />
      </div>

      {/* Main Content */}
      <main className="container mx-auto px-4 pb-12">
        {/* Error Banner */}
        {error && (
          <Card className="mb-6 border-destructive/50 bg-destructive/10">
            <CardContent className="py-4">
              <p className="text-destructive text-sm">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Step Content */}
        {currentStep === "intake" && (
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold mb-2">Welcome to aco</h2>
              <p className="text-muted-foreground">
                Start by describing your sequencing experiment and pointing to your data.
              </p>
            </div>
            <IntakeForm onSubmit={handleIntakeSubmit} isLoading={isLoading} />
          </div>
        )}

        {currentStep === "scanning" && (
          <div className="max-w-3xl mx-auto">
            <FileScanner scanResult={null} isLoading={true} />
          </div>
        )}

        {currentStep === "manifest" && manifest && (
          <div className="max-w-4xl mx-auto">
            <ManifestViewer
              manifest={manifest}
              onUpdate={handleManifestUpdate}
              onProceed={handleProceedToUnderstanding}
              isLoading={isLoading}
            />
          </div>
        )}

        {currentStep === "understanding" && (
          <div className="max-w-4xl mx-auto">
            <UnderstandingEditor
              understanding={understanding}
              isLoading={understandingLoading}
              onRegenerate={handleRegenerate}
              onApprove={handleApprove}
            />
          </div>
        )}

        {currentStep === "approved" && understanding && (
          <div className="max-w-4xl mx-auto">
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
      <footer className="border-t border-border py-6 mt-auto">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>aco - agentic sequencing quality control</p>
          <p className="mt-1">
            Powered by{" "}
            <a href="https://ai.google.dev" className="text-primary hover:underline">
              Google Gemini
            </a>
            {settings.model && (
              <span className="ml-1">({settings.model})</span>
            )}
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
