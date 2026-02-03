"""Notebook generation engine using LLM.

This module generates Jupyter notebooks or R Markdown files for 
statistical analysis and visualization of QC results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from aco.engine.gemini import GeminiClient, get_gemini_client
from aco.engine.models import ExperimentUnderstanding
from aco.engine.scripts import ExecutionResult


class NotebookLanguage(str, Enum):
    """Supported notebook languages."""
    
    PYTHON = "python"
    R = "r"


class NotebookCell(BaseModel):
    """A single cell in a notebook."""
    
    cell_type: str = Field(..., description="markdown or code")
    source: str = Field(..., description="Cell content")
    outputs: list[Any] = Field(default_factory=list, description="Cell outputs (for executed cells)")


class GeneratedNotebook(BaseModel):
    """A generated notebook."""
    
    name: str = Field(..., description="Notebook filename without extension")
    language: NotebookLanguage = Field(..., description="Python or R")
    title: str = Field(..., description="Notebook title")
    description: str = Field(..., description="What the notebook analyzes")
    cells: list[NotebookCell] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, description="Required packages")
    generated_at: datetime = Field(default_factory=datetime.now)


NOTEBOOK_SYSTEM = """You are an expert bioinformatics analyst creating analysis notebooks.
Your notebooks should:
1. Be well-structured with clear markdown sections
2. Include comprehensive visualizations (plots, heatmaps)
3. Perform statistical tests where appropriate
4. Highlight key findings and potential issues
5. Use best practices for the language (Python: matplotlib/seaborn/plotly, R: ggplot2)

For Python notebooks:
- Use pandas, matplotlib, seaborn, plotly for visualization
- Use scipy for statistical tests
- Use scanpy for single-cell analysis if applicable

For R notebooks:
- Use tidyverse, ggplot2 for visualization
- Use standard R stats functions
- Use Seurat for single-cell analysis if applicable
"""


NOTEBOOK_PROMPT = """Generate an analysis notebook based on the following experiment and QC results.

# Experiment Understanding

{understanding_summary}

Assay Type: {assay_type}
Species: {species}
Sample Count: {sample_count}

# QC Script Results

{script_results}

# Output Files Available

{output_files}

# Instructions

Generate a {language} notebook that:
1. Loads and summarizes the QC results
2. Creates visualizations for key metrics
3. Performs statistical tests if appropriate
4. Highlights any quality issues or concerns
5. Provides actionable recommendations

Structure the notebook with:
- Introduction and experiment overview
- Data loading and preprocessing
- QC metrics visualization
- Statistical analysis (if applicable)
- Summary and recommendations

Generate the notebook cells in order. Use markdown cells for explanations
and code cells for analysis.
"""


async def generate_notebook(
    understanding: ExperimentUnderstanding,
    script_results: list[ExecutionResult],
    language: NotebookLanguage,
    output_dir: Path,
    client: GeminiClient | None = None,
) -> GeneratedNotebook:
    """Generate an analysis notebook.
    
    Args:
        understanding: Experiment understanding
        script_results: Results from script execution
        language: Python or R
        output_dir: Where to save the notebook
        client: Optional Gemini client
    
    Returns:
        Generated notebook
    """
    if client is None:
        client = get_gemini_client()
    
    # Format script results
    results_str = ""
    output_files = []
    for result in script_results:
        results_str += f"\n## {result.script_name}\n"
        results_str += f"Status: {'Success' if result.success else 'Failed'}\n"
        if result.stdout:
            results_str += f"Output:\n{result.stdout[:1000]}\n"
        if result.output_files:
            output_files.extend(result.output_files)
            results_str += f"Files: {', '.join(result.output_files)}\n"
    
    prompt = NOTEBOOK_PROMPT.format(
        understanding_summary=understanding.summary,
        assay_type=understanding.assay_type,
        species=understanding.species,
        sample_count=understanding.sample_count,
        script_results=results_str or "No script results available yet.",
        output_files="\n".join(f"- {f}" for f in output_files) or "None",
        language=language.value.upper(),
    )
    
    notebook = await client.generate_structured_async(
        prompt=prompt,
        response_schema=GeneratedNotebook,
        system_instruction=NOTEBOOK_SYSTEM,
        temperature=0.3,
    )
    
    notebook.language = language
    return notebook


def notebook_to_jupyter(notebook: GeneratedNotebook) -> dict[str, Any]:
    """Convert a GeneratedNotebook to Jupyter notebook format.
    
    Args:
        notebook: The generated notebook
    
    Returns:
        Jupyter notebook as a dict (can be serialized to JSON)
    """
    kernel_spec = {
        NotebookLanguage.PYTHON: {
            "name": "python3",
            "display_name": "Python 3",
            "language": "python",
        },
        NotebookLanguage.R: {
            "name": "ir",
            "display_name": "R",
            "language": "R",
        },
    }[notebook.language]
    
    cells = []
    for cell in notebook.cells:
        jupyter_cell = {
            "cell_type": cell.cell_type,
            "metadata": {},
            "source": cell.source.split("\n"),
        }
        if cell.cell_type == "code":
            jupyter_cell["outputs"] = cell.outputs
            jupyter_cell["execution_count"] = None
        cells.append(jupyter_cell)
    
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": kernel_spec,
            "language_info": {
                "name": notebook.language.value,
            },
        },
        "cells": cells,
    }


def notebook_to_rmarkdown(notebook: GeneratedNotebook) -> str:
    """Convert a GeneratedNotebook to R Markdown format.
    
    Args:
        notebook: The generated notebook
    
    Returns:
        R Markdown content as a string
    """
    lines = []
    
    # YAML header
    lines.append("---")
    lines.append(f'title: "{notebook.title}"')
    lines.append(f'date: "{notebook.generated_at.strftime("%Y-%m-%d")}"')
    lines.append("output:")
    lines.append("  html_document:")
    lines.append("    toc: true")
    lines.append("    toc_float: true")
    lines.append("---")
    lines.append("")
    
    for cell in notebook.cells:
        if cell.cell_type == "markdown":
            lines.append(cell.source)
            lines.append("")
        elif cell.cell_type == "code":
            lang = "r" if notebook.language == NotebookLanguage.R else "python"
            lines.append(f"```{{{lang}}}")
            lines.append(cell.source)
            lines.append("```")
            lines.append("")
    
    return "\n".join(lines)


def save_notebook(
    notebook: GeneratedNotebook,
    output_dir: Path,
) -> Path:
    """Save notebook to disk in appropriate format.
    
    Args:
        notebook: The notebook to save
        output_dir: Directory to save to
    
    Returns:
        Path to saved file
    """
    import json
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if notebook.language == NotebookLanguage.PYTHON:
        # Save as Jupyter notebook
        filepath = output_dir / f"{notebook.name}.ipynb"
        jupyter_nb = notebook_to_jupyter(notebook)
        filepath.write_text(json.dumps(jupyter_nb, indent=2))
    else:
        # Save as R Markdown
        filepath = output_dir / f"{notebook.name}.Rmd"
        rmd_content = notebook_to_rmarkdown(notebook)
        filepath.write_text(rmd_content)
    
    return filepath
