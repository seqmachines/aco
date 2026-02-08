import { useState, useEffect, useCallback } from "react"
import { Loader2, ArrowRight, BarChart3, FlaskConical } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { PlotSelection } from "@/types"

interface PlotChooserProps {
  manifestId: string
  onComplete: () => void
  onBack?: () => void
}

const AVAILABLE_PLOTS = [
  { id: "quality_scores", label: "Base quality score distribution", category: "Quality" },
  { id: "read_length_dist", label: "Read length distribution", category: "Quality" },
  { id: "gc_content", label: "GC content distribution", category: "Quality" },
  { id: "adapter_content", label: "Adapter content", category: "Quality" },
  { id: "duplication_rate", label: "Duplication rate", category: "Quality" },
  { id: "barcode_rank", label: "Barcode rank plot (knee plot)", category: "Single-cell" },
  { id: "umi_per_cell", label: "UMIs per cell distribution", category: "Single-cell" },
  { id: "genes_per_cell", label: "Genes per cell distribution", category: "Single-cell" },
  { id: "mito_fraction", label: "Mitochondrial fraction per cell", category: "Single-cell" },
  { id: "saturation_curve", label: "Sequencing saturation curve", category: "Single-cell" },
  { id: "mapping_rate", label: "Mapping rate summary", category: "Alignment" },
  { id: "coverage_uniformity", label: "Coverage uniformity", category: "Alignment" },
  { id: "insert_size", label: "Insert size distribution", category: "Alignment" },
]

const AVAILABLE_TESTS = [
  { id: "t_test", label: "t-test (two-sample)" },
  { id: "wilcoxon", label: "Wilcoxon rank-sum test" },
  { id: "chi_square", label: "Chi-square test" },
  { id: "fisher_exact", label: "Fisher's exact test" },
  { id: "ks_test", label: "Kolmogorov-Smirnov test" },
  { id: "anova", label: "ANOVA (one-way)" },
  { id: "correlation", label: "Pearson/Spearman correlation" },
]

export function PlotChooser({ manifestId, onComplete, onBack }: PlotChooserProps) {
  const [selectedPlots, setSelectedPlots] = useState<Set<string>>(new Set())
  const [selectedTests, setSelectedTests] = useState<Set<string>>(new Set())
  const [customRequests, setCustomRequests] = useState("")
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)

  // Load existing selection
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/analyze/plots/${manifestId}`)
        if (res.ok) {
          const data = await res.json()
          const sel: PlotSelection = data.selection
          setSelectedPlots(new Set(sel.selected_plots))
          setSelectedTests(new Set(sel.selected_tests))
          setCustomRequests(sel.custom_plot_requests)
        }
      } catch { /* no data yet */ }
      setLoaded(true)
    }
    load()
  }, [manifestId])

  const togglePlot = useCallback((id: string) => {
    setSelectedPlots((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const toggleTest = useCallback((id: string) => {
    setSelectedTests((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      await fetch("/analyze/plots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manifest_id: manifestId,
          selected_plots: Array.from(selectedPlots),
          custom_plot_requests: customRequests,
          selected_tests: Array.from(selectedTests),
        }),
      })
    } catch (e) {
      console.error("Failed to save plot selection:", e)
    } finally {
      setSaving(false)
    }
  }, [manifestId, selectedPlots, selectedTests, customRequests])

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

  const categories = [...new Set(AVAILABLE_PLOTS.map((p) => p.category))]

  return (
    <div className="space-y-6">
      {/* Plot types */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="h-4 w-4 text-primary" />
            <h4 className="text-sm font-semibold">Select Plots</h4>
          </div>
          {categories.map((cat) => (
            <div key={cat} className="mb-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">
                {cat}
              </p>
              <div className="grid grid-cols-2 gap-2">
                {AVAILABLE_PLOTS.filter((p) => p.category === cat).map((plot) => {
                  const checked = selectedPlots.has(plot.id)
                  return (
                    <button
                      key={plot.id}
                      onClick={() => togglePlot(plot.id)}
                      className={cn(
                        "text-left text-xs p-2 rounded border transition-all",
                        checked
                          ? "border-primary bg-primary/5 font-medium"
                          : "border-border hover:border-border hover:bg-muted/30"
                      )}
                    >
                      <span className={cn(
                        "inline-block w-3 h-3 rounded-sm border mr-2 align-text-bottom",
                        checked ? "bg-primary border-primary" : "border-border"
                      )} />
                      {plot.label}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Statistical tests */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical className="h-4 w-4 text-primary" />
            <h4 className="text-sm font-semibold">Statistical Tests</h4>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {AVAILABLE_TESTS.map((test) => {
              const checked = selectedTests.has(test.id)
              return (
                <button
                  key={test.id}
                  onClick={() => toggleTest(test.id)}
                  className={cn(
                    "text-left text-xs p-2 rounded border transition-all",
                    checked
                      ? "border-primary bg-primary/5 font-medium"
                      : "border-border hover:border-border hover:bg-muted/30"
                  )}
                >
                  <span className={cn(
                    "inline-block w-3 h-3 rounded-sm border mr-2 align-text-bottom",
                    checked ? "bg-primary border-primary" : "border-border"
                  )} />
                  {test.label}
                </button>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Custom requests */}
      <Card>
        <CardContent className="pt-6">
          <label className="block text-sm font-semibold mb-2">Custom Plot Requests</label>
          <p className="text-xs text-muted-foreground mb-3">
            Describe any additional plots or visualizations you want in the notebook.
          </p>
          <Textarea
            value={customRequests}
            onChange={(e) => setCustomRequests(e.target.value)}
            placeholder="e.g., Heatmap of top variable genes, UMAP colored by sample..."
            className="min-h-[80px]"
          />
        </CardContent>
      </Card>

      <div className="text-xs text-muted-foreground">
        {selectedPlots.size} plot(s) and {selectedTests.size} test(s) selected
      </div>

      {/* Actions */}
      <div className="flex justify-between pt-2">
        {onBack ? <Button variant="outline" onClick={onBack}>Back</Button> : <div />}
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
            Save
          </Button>
          <Button onClick={handleContinue} disabled={saving}>
            Continue to Notebook <ArrowRight className="h-3.5 w-3.5 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  )
}
