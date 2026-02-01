import { cn } from "@/lib/utils"
import { Check } from "lucide-react"
import type { AppStep } from "@/types"

interface Step {
  id: AppStep
  name: string
  description: string
}

const steps: Step[] = [
  { id: "intake", name: "Intake", description: "Describe your experiment" },
  { id: "scanning", name: "Scanning", description: "Discovering files" },
  { id: "manifest", name: "Manifest", description: "Review data" },
  { id: "understanding", name: "Analysis", description: "LLM processing" },
  { id: "approved", name: "Complete", description: "Ready for QC" },
]

interface ProgressStepsProps {
  currentStep: AppStep
}

export function ProgressSteps({ currentStep }: ProgressStepsProps) {
  const currentIndex = steps.findIndex((s) => s.id === currentStep)

  return (
    <nav aria-label="Progress" className="w-full">
      <ol className="flex items-center justify-between">
        {steps.map((step, index) => {
          const isComplete = index < currentIndex
          const isCurrent = index === currentIndex

          return (
            <li key={step.id} className="relative flex flex-1 flex-col items-center">
              {/* Connector line */}
              {index !== 0 && (
                <div
                  className={cn(
                    "absolute left-0 right-1/2 top-4 h-0.5 -translate-y-1/2",
                    isComplete ? "bg-primary" : "bg-border"
                  )}
                />
              )}
              {index !== steps.length - 1 && (
                <div
                  className={cn(
                    "absolute left-1/2 right-0 top-4 h-0.5 -translate-y-1/2",
                    isComplete ? "bg-primary" : "bg-border"
                  )}
                />
              )}

              {/* Step indicator */}
              <div
                className={cn(
                  "relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 transition-all duration-300",
                  isComplete
                    ? "border-primary bg-primary text-primary-foreground"
                    : isCurrent
                    ? "border-primary bg-background text-primary glow-primary"
                    : "border-border bg-background text-muted-foreground"
                )}
              >
                {isComplete ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <span className="text-xs font-semibold">{index + 1}</span>
                )}
              </div>

              {/* Step label */}
              <div className="mt-2 text-center">
                <p
                  className={cn(
                    "text-sm font-medium",
                    isCurrent ? "text-primary" : isComplete ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {step.name}
                </p>
                <p className="text-xs text-muted-foreground hidden sm:block">
                  {step.description}
                </p>
              </div>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
