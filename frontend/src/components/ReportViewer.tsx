import { useState } from "react"
import {
    Play,
    Download,
    FileText,
    CheckCircle,
    AlertTriangle,
    AlertCircle,
    Info,
    Loader2,
    ExternalLink,
    Lightbulb,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface Insight {
    title: string
    description: string
    severity: string
    category: string
    evidence: string | null
    recommendation: string | null
}

interface Hypothesis {
    hypothesis: string
    priority: number
    rationale: string
    supporting_evidence: string[]
    suggested_tests: string[]
}

interface ReportSection {
    title: string
    content: string
    level: number
}

interface GeneratedReport {
    title: string
    summary: string
    sections: ReportSection[]
    insights: Insight[]
    hypotheses: Hypothesis[]
    generated_at: string
    format: string
}

interface ReportViewerProps {
    manifestId: string
    onComplete?: () => void
}

const severityIcons = {
    critical: AlertCircle,
    warning: AlertTriangle,
    info: Info,
}

const severityColors = {
    critical: "bg-destructive/10 text-destructive border-destructive/30",
    warning: "bg-warning/10 text-warning border-warning/30",
    info: "bg-blue-500/10 text-blue-600 border-blue-500/30",
}

export function ReportViewer({ manifestId, onComplete }: ReportViewerProps) {
    const [report, setReport] = useState<GeneratedReport | null>(null)
    const [savedPath, setSavedPath] = useState<string | null>(null)
    const [isGenerating, setIsGenerating] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [activeTab, setActiveTab] = useState<"summary" | "insights" | "hypotheses" | "preview">("summary")

    const generateReport = async () => {
        setIsGenerating(true)
        setError(null)
        try {
            const response = await fetch("/reports/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    manifest_id: manifestId,
                    format: "html",
                }),
            })
            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || "Failed to generate report")
            }
            const data = await response.json()
            setReport(data.report)
            setSavedPath(data.saved_path)
        } catch (e) {
            setError(e instanceof Error ? e.message : "Unknown error")
        } finally {
            setIsGenerating(false)
        }
    }

    const downloadReport = () => {
        if (!savedPath) return
        window.open(`/reports/${manifestId}/html`, "_blank")
    }

    if (!report) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                        <FileText className="h-5 w-5 text-primary" />
                        QC Report
                    </CardTitle>
                    <CardDescription>
                        Generate a comprehensive QC report with insights and recommendations
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {error && (
                        <div className="p-3 mb-4 bg-destructive/10 text-destructive rounded text-sm">
                            {error}
                        </div>
                    )}
                    <Button onClick={generateReport} disabled={isGenerating}>
                        {isGenerating ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <Play className="h-4 w-4 mr-2" />
                        )}
                        Generate Report
                    </Button>
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <FileText className="h-5 w-5 text-primary" />
                        {report.title}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                        Generated {new Date(report.generated_at).toLocaleString()}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Badge variant="success" className="flex items-center gap-1">
                        <CheckCircle className="h-3 w-3" />
                        Complete
                    </Badge>
                    <Button variant="outline" size="sm" onClick={downloadReport}>
                        <Download className="h-4 w-4 mr-1" />
                        Download
                    </Button>
                </div>
            </div>

            {error && (
                <div className="p-3 bg-destructive/10 text-destructive rounded text-sm">
                    {error}
                </div>
            )}

            {/* Tabs */}
            <div className="flex gap-2 border-b">
                {[
                    { id: "summary", label: "Summary" },
                    { id: "insights", label: `Insights (${report.insights.length})` },
                    { id: "hypotheses", label: `Hypotheses (${report.hypotheses.length})` },
                    { id: "preview", label: "Preview" },
                ].map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id as typeof activeTab)}
                        className={cn(
                            "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
                            activeTab === tab.id
                                ? "border-primary text-primary"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Summary Tab */}
            {activeTab === "summary" && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-sm">Executive Summary</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm leading-relaxed">{report.summary}</p>

                        <div className="grid grid-cols-3 gap-4 mt-6">
                            <div className="p-4 rounded-lg bg-destructive/5 border border-destructive/20">
                                <div className="text-2xl font-bold text-destructive">
                                    {report.insights.filter(i => i.severity === "critical").length}
                                </div>
                                <div className="text-xs text-muted-foreground">Critical Issues</div>
                            </div>
                            <div className="p-4 rounded-lg bg-warning/5 border border-warning/20">
                                <div className="text-2xl font-bold text-warning">
                                    {report.insights.filter(i => i.severity === "warning").length}
                                </div>
                                <div className="text-xs text-muted-foreground">Warnings</div>
                            </div>
                            <div className="p-4 rounded-lg bg-blue-500/5 border border-blue-500/20">
                                <div className="text-2xl font-bold text-blue-600">
                                    {report.hypotheses.length}
                                </div>
                                <div className="text-xs text-muted-foreground">Hypotheses</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Insights Tab */}
            {activeTab === "insights" && (
                <div className="space-y-3">
                    {report.insights.length === 0 ? (
                        <Card>
                            <CardContent className="py-8 text-center text-muted-foreground">
                                No insights generated.
                            </CardContent>
                        </Card>
                    ) : (
                        report.insights.map((insight, idx) => {
                            const sev = insight.severity.toLowerCase() as keyof typeof severityIcons
                            const Icon = severityIcons[sev] || Info
                            return (
                                <Card key={idx} className={cn("border", severityColors[sev])}>
                                    <CardContent className="py-4">
                                        <div className="flex items-start gap-3">
                                            <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="font-medium">{insight.title}</span>
                                                    <Badge variant="outline" className="text-xs">
                                                        {insight.category}
                                                    </Badge>
                                                </div>
                                                <p className="text-sm">{insight.description}</p>
                                                {insight.recommendation && (
                                                    <p className="text-sm mt-2 text-muted-foreground">
                                                        <strong>Recommendation:</strong> {insight.recommendation}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            )
                        })
                    )}
                </div>
            )}

            {/* Hypotheses Tab */}
            {activeTab === "hypotheses" && (
                <div className="space-y-3">
                    {report.hypotheses.length === 0 ? (
                        <Card>
                            <CardContent className="py-8 text-center text-muted-foreground">
                                No hypotheses generated.
                            </CardContent>
                        </Card>
                    ) : (
                        report.hypotheses
                            .sort((a, b) => a.priority - b.priority)
                            .map((hyp, idx) => (
                                <Card key={idx}>
                                    <CardContent className="py-4">
                                        <div className="flex items-start gap-3">
                                            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold flex-shrink-0">
                                                {hyp.priority}
                                            </div>
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <Lightbulb className="h-4 w-4 text-primary" />
                                                    <span className="font-medium">{hyp.hypothesis}</span>
                                                </div>
                                                <p className="text-sm text-muted-foreground">{hyp.rationale}</p>
                                                {hyp.suggested_tests.length > 0 && (
                                                    <div className="mt-2">
                                                        <span className="text-xs font-medium">Suggested tests:</span>
                                                        <ul className="text-xs text-muted-foreground ml-4 mt-1">
                                                            {hyp.suggested_tests.map((test, i) => (
                                                                <li key={i}>• {test}</li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))
                    )}
                </div>
            )}

            {/* Preview Tab */}
            {activeTab === "preview" && (
                <Card>
                    <CardContent className="p-0">
                        <iframe
                            src={`/reports/${manifestId}/html`}
                            className="w-full h-[600px] border-0 rounded-lg"
                            title="Report Preview"
                        />
                        <div className="p-3 border-t flex justify-end">
                            <Button variant="outline" size="sm" onClick={() => window.open(`/reports/${manifestId}/html`, "_blank")}>
                                <ExternalLink className="h-4 w-4 mr-1" />
                                Open in New Tab
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Actions */}
            <div className="flex justify-between pt-4 border-t">
                <Button variant="outline" onClick={() => setReport(null)}>
                    Regenerate
                </Button>
                {onComplete && (
                    <Button onClick={onComplete}>
                        Complete Analysis
                    </Button>
                )}
            </div>
        </div>
    )
}
