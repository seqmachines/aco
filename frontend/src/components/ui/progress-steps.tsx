import { cn } from "@/lib/utils"
import { Check } from "lucide-react"
import type { AppStep } from "@/types"
import { PHASES, phaseForStep } from "@/types"

interface ProgressStepsProps {
  currentStep: AppStep
}

export function ProgressSteps({ currentStep }: ProgressStepsProps) {
  const currentPhase = phaseForStep(currentStep)
  const phaseIds = PHASES.map((p) => p.id)
  const currentPhaseIdx = phaseIds.indexOf(currentPhase)

  return (
    <nav aria-label="Progress" className="w-full">
      <ol className="flex items-center justify-between">
        {PHASES.map((phase, index) => {
          const isComplete = index < currentPhaseIdx
          const isCurrent = index === currentPhaseIdx

          return (
            <li key={phase.id} className="relative flex flex-1 flex-col items-center">
              {/* Connector line */}
              {index !== 0 && (
                <div
                  className={cn(
                    "absolute left-0 right-1/2 top-4 h-0.5 -translate-y-1/2",
                    isComplete ? "bg-primary" : "bg-border"
                  )}
                />
              )}
              {index !== PHASES.length - 1 && (
                <div
                  className={cn(
                    "absolute left-1/2 right-0 top-4 h-0.5 -translate-y-1/2",
                    isComplete ? "bg-primary" : "bg-border"
                  )}
                />
              )}

              {/* Phase indicator */}
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

              {/* Phase label */}
              <div className="mt-2 text-center">
                <p
                  className={cn(
                    "text-sm font-medium",
                    isCurrent ? "text-primary" : isComplete ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {phase.label}
                </p>
              </div>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
