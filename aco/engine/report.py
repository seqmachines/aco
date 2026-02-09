"""Report generation engine using LLM.

This module generates HTML/PDF reports summarizing QC analysis results,
with insights and prioritized hypotheses.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from aco.engine.gemini import GeminiClient, get_gemini_client
from aco.engine.models import ExperimentUnderstanding
from aco.engine.scripts import ExecutionResult
from aco.engine.notebook import GeneratedNotebook


class ReportFormat(str, Enum):
    """Supported report formats."""
    
    HTML = "html"
    PDF = "pdf"


class ReportSection(BaseModel):
    """A section of the report."""
    
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content (markdown)")
    level: int = Field(default=2, description="Heading level (1-3)")


class Insight(BaseModel):
    """An insight or finding from the analysis."""
    
    title: str = Field(..., description="Short insight title")
    description: str = Field(..., description="Detailed description")
    severity: str = Field(..., description="info, warning, or critical")
    category: str = Field(..., description="Category of insight")
    evidence: str | None = Field(default=None, description="Supporting evidence")
    recommendation: str | None = Field(default=None, description="Suggested action")


class Hypothesis(BaseModel):
    """A prioritized hypothesis about the data."""
    
    hypothesis: str = Field(..., description="The hypothesis statement")
    priority: int = Field(..., description="Priority rank (1 = highest)")
    rationale: str = Field(..., description="Why this hypothesis matters")
    supporting_evidence: list[str] = Field(default_factory=list)
    suggested_tests: list[str] = Field(default_factory=list)


class GeneratedReport(BaseModel):
    """A generated QC report."""
    
    title: str = Field(..., description="Report title")
    summary: str = Field(..., description="Executive summary")
    sections: list[ReportSection] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    format: ReportFormat = Field(default=ReportFormat.HTML)


REPORT_SYSTEM = """You are an expert bioinformatics analyst creating QC reports.
Your reports should:
1. Be clear and actionable for both biologists and bioinformaticians
2. Highlight critical issues prominently
3. Provide specific recommendations
4. Prioritize hypotheses based on evidence strength
5. Include relevant statistics and visualizations

Structure reports with:
- Executive summary (key findings in 2-3 sentences)
- QC overview with metrics
- Critical issues and warnings
- Detailed analysis by category
- Prioritized hypotheses for follow-up
- Recommendations and next steps
"""


REPORT_PROMPT = """Generate a comprehensive QC report based on the analysis results.

# Experiment Information

Title: {experiment_title}
Assay Type: {assay_type}
Species: {species}
Sample Count: {sample_count}

## Understanding Summary
{understanding_summary}

# QC Script Execution Results

{script_results}

# Notebook Analysis Summary

{notebook_summary}

# Instructions

Generate a comprehensive report that:
1. Summarizes all QC findings
2. Highlights critical issues and warnings
3. Provides insights organized by category
4. Lists prioritized hypotheses for follow-up
5. Gives actionable recommendations

For each insight, assign a severity:
- critical: Immediate action required
- warning: Should be addressed
- info: Worth noting

For hypotheses:
- Rank by priority (1 = highest)
- Provide supporting evidence
- Suggest tests to validate

Make the report suitable for sharing with collaborators.
"""


async def generate_report(
    understanding: ExperimentUnderstanding,
    script_results: list[ExecutionResult],
    notebook: GeneratedNotebook | None = None,
    client: GeminiClient | None = None,
) -> GeneratedReport:
    """Generate a QC report.
    
    Args:
        understanding: Experiment understanding
        script_results: Results from script execution
        notebook: Optional generated notebook
        client: Optional Gemini client
    
    Returns:
        Generated report
    """
    if client is None:
        client = get_gemini_client()
    
    # Format script results
    results_str = ""
    for result in script_results:
        results_str += f"\n### {result.script_name}\n"
        results_str += f"- Status: {'✓ Success' if result.success else '✗ Failed'}\n"
        results_str += f"- Duration: {result.duration_seconds:.2f}s\n"
        if result.stdout:
            results_str += f"- Output:\n```\n{result.stdout[:1500]}\n```\n"
        if result.stderr and not result.success:
            results_str += f"- Errors:\n```\n{result.stderr[:500]}\n```\n"
    
    notebook_summary = "No notebook analysis performed."
    if notebook:
        notebook_summary = f"- Notebook: {notebook.name} ({notebook.language.value})\n"
        notebook_summary += f"- Title: {notebook.title}\n"
        notebook_summary += f"- Cells: {len(notebook.cells)} analysis cells\n"
        notebook_summary += f"- Description: {notebook.description}\n"
    
    prompt = REPORT_PROMPT.format(
        experiment_title=understanding.summary.split(".")[0] if understanding.summary else "Experiment Analysis",
        assay_type=understanding.assay_type,
        species=understanding.species,
        sample_count=understanding.sample_count,
        understanding_summary=understanding.summary,
        script_results=results_str or "No scripts executed.",
        notebook_summary=notebook_summary,
    )
    
    report = await client.generate_structured_async(
        prompt=prompt,
        response_schema=GeneratedReport,
        system_instruction=REPORT_SYSTEM,
        temperature=0.3,
    )
    
    return report


def report_to_html(report: GeneratedReport) -> str:
    """Convert a report to HTML format.
    
    Args:
        report: The generated report
    
    Returns:
        HTML content as a string
    """
    import html
    
    severity_colors = {
        "critical": "#dc2626",
        "warning": "#f59e0b", 
        "info": "#3b82f6",
    }
    
    severity_icons = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🔵",
    }
    
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"<title>{html.escape(report.title)}</title>",
        "<style>",
        """
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               line-height: 1.6; color: #1f2937; max-width: 900px; margin: 0 auto; padding: 2rem; }
        h1 { font-size: 2rem; margin-bottom: 0.5rem; color: #111827; }
        h2 { font-size: 1.5rem; margin: 2rem 0 1rem; color: #374151; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }
        h3 { font-size: 1.25rem; margin: 1.5rem 0 0.75rem; color: #4b5563; }
        p { margin-bottom: 1rem; }
        .summary { background: #f3f4f6; padding: 1.5rem; border-radius: 8px; margin-bottom: 2rem; }
        .meta { color: #6b7280; font-size: 0.875rem; margin-bottom: 1rem; }
        .insight { padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid; }
        .insight-critical { background: #fef2f2; border-color: #dc2626; }
        .insight-warning { background: #fffbeb; border-color: #f59e0b; }
        .insight-info { background: #eff6ff; border-color: #3b82f6; }
        .insight-title { font-weight: 600; margin-bottom: 0.5rem; }
        .hypothesis { background: #f9fafb; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; }
        .hypothesis-rank { display: inline-block; background: #6366f1; color: white; width: 24px; height: 24px; 
                           border-radius: 50%; text-align: center; font-size: 0.875rem; margin-right: 0.5rem; }
        ul { margin-left: 1.5rem; margin-bottom: 1rem; }
        code { background: #f3f4f6; padding: 0.125rem 0.25rem; border-radius: 4px; font-size: 0.875rem; }
        pre { background: #1f2937; color: #f9fafb; padding: 1rem; border-radius: 8px; overflow-x: auto; margin: 1rem 0; }
        pre code { background: transparent; padding: 0; }
        """,
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(report.title)}</h1>",
        f"<p class='meta'>Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M')}</p>",
        "<div class='summary'>",
        f"<p><strong>Executive Summary:</strong> {html.escape(report.summary)}</p>",
        "</div>",
    ]
    
    # Insights section
    if report.insights:
        html_parts.append("<h2>Key Insights</h2>")
        for insight in report.insights:
            sev = insight.severity.lower()
            icon = severity_icons.get(sev, "•")
            html_parts.append(f"<div class='insight insight-{sev}'>")
            html_parts.append(f"<div class='insight-title'>{icon} {html.escape(insight.title)}</div>")
            html_parts.append(f"<p>{html.escape(insight.description)}</p>")
            if insight.recommendation:
                html_parts.append(f"<p><strong>Recommendation:</strong> {html.escape(insight.recommendation)}</p>")
            html_parts.append("</div>")
    
    # Report sections
    for section in report.sections:
        level = min(max(section.level, 1), 3)
        html_parts.append(f"<h{level}>{html.escape(section.title)}</h{level}>")
        # Simple markdown to HTML conversion for content
        content = section.content
        content = content.replace("\n\n", "</p><p>")
        content = f"<p>{content}</p>"
        html_parts.append(content)
    
    # Hypotheses section
    if report.hypotheses:
        html_parts.append("<h2>Prioritized Hypotheses</h2>")
        for hyp in sorted(report.hypotheses, key=lambda h: h.priority):
            html_parts.append("<div class='hypothesis'>")
            html_parts.append(f"<p><span class='hypothesis-rank'>{hyp.priority}</span><strong>{html.escape(hyp.hypothesis)}</strong></p>")
            html_parts.append(f"<p>{html.escape(hyp.rationale)}</p>")
            if hyp.suggested_tests:
                html_parts.append("<p><strong>Suggested tests:</strong></p><ul>")
                for test in hyp.suggested_tests:
                    html_parts.append(f"<li>{html.escape(test)}</li>")
                html_parts.append("</ul>")
            html_parts.append("</div>")
    
    html_parts.extend([
        "</body>",
        "</html>",
    ])
    
    return "\n".join(html_parts)


def save_report(
    report: GeneratedReport,
    output_dir: Path,
    format: ReportFormat = ReportFormat.HTML,
) -> Path:
    """Save report to disk.
    
    Args:
        report: The report to save
        output_dir: Directory to save to
        format: Output format
    
    Returns:
        Path to saved file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if format == ReportFormat.HTML:
        filepath = output_dir / "qc_report.html"
        html_content = report_to_html(report)
        filepath.write_text(html_content)
    else:
        # For PDF, we'll save HTML and note that weasyprint can be used
        filepath = output_dir / "qc_report.html"
        html_content = report_to_html(report)
        filepath.write_text(html_content)
        # PDF generation would require weasyprint: pip install weasyprint
        # from weasyprint import HTML
        # pdf_path = output_dir / "qc_report.pdf"
        # HTML(string=html_content).write_pdf(pdf_path)
    
    return filepath
