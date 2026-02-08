import { useState, useEffect, useCallback } from "react"
import { Loader2, ArrowRight, FileCode, FolderOpen, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { ExistingScriptInfo, SelectedReference } from "@/types"

interface HypothesisFormProps {
  manifestId: string
  onComplete: () => void
  onBack?: () => void
}

export function HypothesisForm({ manifestId, onComplete, onBack }: HypothesisFormProps) {
  const [whatIsWrong, setWhatIsWrong] = useState("")
  const [whatToProve, setWhatToProve] = useState("")
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)

  // Reference selection state
  const [existingScripts, setExistingScripts] = useState<ExistingScriptInfo[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loadingScripts, setLoadingScripts] = useState(true)

  // Load existing hypotheses
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/analyze/hypothesis/${manifestId}`)
        if (res.ok) {
          const data = await res.json()
          setWhatIsWrong(data.hypothesis_set.what_is_wrong)
          setWhatToProve(data.hypothesis_set.what_to_prove)
        }
      } catch {
        // No saved data yet
      } finally {
        setLoaded(true)
      }
    }
    load()
  }, [manifestId])

  // Load existing scripts and saved reference selections
  useEffect(() => {
    async function loadRefs() {
      try {
        const scriptsRes = await fetch(`/scripts/existing/${manifestId}`)
        if (scriptsRes.ok) {
          const data = await scriptsRes.json()
          setExistingScripts(data.scripts || [])
        }

        const refsRes = await fetch(`/analyze/references/${manifestId}`)
        if (refsRes.ok) {
          const data = await refsRes.json()
          const paths = new Set<string>(
            (data.references || []).map((r: SelectedReference) => r.path)
          )
          setSelected(paths)
        }
      } catch {
        // OK if no data yet
      } finally {
        setLoadingScripts(false)
      }
    }
    loadRefs()
  }, [manifestId])

  const toggleSelect = useCallback((path: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      // Save hypotheses
      await fetch("/analyze/hypothesis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manifest_id: manifestId,
          what_is_wrong: whatIsWrong,
          what_to_prove: whatToProve,
          hypotheses: [],
        }),
      })

      // Save references
      const references: SelectedReference[] = existingScripts
        .filter((s) => selected.has(s.path))
        .map((s) => ({
          path: s.path,
          name: s.name,
          ref_type: s.source === "previous_run" ? "prior_run" as const : "script" as const,
          description: s.preview.split("\n").slice(0, 3).join(" ").slice(0, 120),
        }))

      await fetch("/analyze/references", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manifest_id: manifestId,
          references,
        }),
      })
    } catch (e) {
      console.error("Failed to save:", e)
    } finally {
      setSaving(false)
    }
  }, [manifestId, whatIsWrong, whatToProve, existingScripts, selected])

  const handleContinue = useCallback(async () => {
    await handleSave()
    onComplete()
  }, [handleSave, onComplete])

  if (!loaded) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const dataScripts = existingScripts.filter((s) => s.source === "data_dir")
  const priorScripts = existingScripts.filter((s) => s.source === "previous_run")

  const sourceIcon = (source: string) =>
    source === "previous_run" ? (
      <FolderOpen className="h-3.5 w-3.5" />
    ) : (
      <FileCode className="h-3.5 w-3.5" />
    )

  const renderScriptList = (scripts: ExistingScriptInfo[], title: string, emptyMsg: string) => (
    <>
      <h5 className="text-xs font-semibold text-muted-foreground mt-4 mb-2">{title}</h5>
      {scripts.length === 0 ? (
        <p className="text-xs text-muted-foreground text-center py-3 border border-dashed rounded">
          {emptyMsg}
        </p>
      ) : (
        <div className="space-y-2">
          {scripts.map((script) => {
            const isSelected = selected.has(script.path)
            return (
              <button
                key={script.path}
                onClick={() => toggleSelect(script.path)}
                className={cn(
                  "w-full text-left border rounded p-3 transition-all",
                  isSelected
                    ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                    : "hover:border-border hover:bg-muted/30"
                )}
              >
                <div className="flex items-start gap-2">
                  <div
                    className={cn(
                      "flex-shrink-0 w-5 h-5 rounded border flex items-center justify-center mt-0.5 transition-colors",
                      isSelected
                        ? "bg-primary border-primary text-primary-foreground"
                        : "border-border"
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {sourceIcon(script.source)}
                      <span className="text-sm font-medium truncate">
                        {script.name}
                      </span>
                      <Badge variant="outline" className="text-[9px] ml-auto flex-shrink-0">
                        {(script.size_bytes / 1024).toFixed(1)} KB
                      </Badge>
                    </div>
                    <pre className="text-[10px] text-muted-foreground mt-1.5 font-mono whitespace-pre-wrap line-clamp-3 overflow-hidden">
                      {script.preview}
                    </pre>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </>
  )

  return (
    <div className="space-y-6">
      {/* What is wrong */}
      {/* What is wrong (Hidden as per user request) */}
      <div className="hidden">
        <label className="block text-sm font-semibold mb-2">
          What do you think is wrong?
        </label>
        <Textarea
          value={whatIsWrong}
          onChange={(e) => setWhatIsWrong(e.target.value)}
        />
      </div>

      {/* What to prove */}
      {/* What to prove (Hidden as per user request) */}
      <div className="hidden">
        <label className="block text-sm font-semibold mb-2">
          What do you want to prove?
        </label>
        <Textarea
          value={whatToProve}
          onChange={(e) => setWhatToProve(e.target.value)}
        />
      </div>

      {/* Reference selection */}
      <Card>
        <CardContent className="pt-6">
          <label className="block text-sm font-semibold mb-1">
            Reference Scripts
          </label>
          <p className="text-xs text-muted-foreground mb-3">
            Select scripts from your data directory or prior runs.
            The LLM will analyze these to extract intent and parameters (without rewriting them).
          </p>
          {loadingScripts ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : existingScripts.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4 border border-dashed rounded">
              No scripts found in data directory or prior runs.
            </p>
          ) : (
            <>
              {dataScripts.length > 0 && renderScriptList(dataScripts, "Scripts in Data Directory", "")}
              {priorScripts.length > 0 && renderScriptList(priorScripts, "Scripts from Prior Runs", "")}
              <p className="text-xs text-muted-foreground mt-3">
                {selected.size} reference{selected.size !== 1 ? "s" : ""} selected
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-between pt-2">
        {onBack ? (
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
        ) : (
          <div />
        )}
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
            Save Draft
          </Button>
          <Button onClick={handleContinue} disabled={saving}>
            Continue <ArrowRight className="h-3.5 w-3.5 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  )
}
