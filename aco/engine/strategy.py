"""Analysis strategy generation.

Given an ExperimentUnderstanding, user hypotheses, and selected references,
the LLM produces an AnalysisStrategy -- a structured plan that maps
hypotheses to tests, defines QC gates, and lists execution steps.

For reference scripts the model performs *safe analysis* only:
- Script intent extraction
- Parameter extraction
- Diff-aware adaptation suggestions

It does NOT rewrite the scripts.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from aco.engine.gemini import GeminiClient, get_gemini_client
from aco.engine.models import (
    AnalysisStrategy,
    ExperimentUnderstanding,
    HypothesisSet,
    ScriptInsight,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

STRATEGY_SYSTEM = """You are an expert bioinformatics scientist. Your job is to produce
a structured analysis strategy for a sequencing QC run.

You will receive:
1. An experiment understanding (JSON).
2. User hypotheses -- what they think is wrong and what they want to prove.
3. Selected reference scripts (full source code via the Files API).

Your output MUST be a valid AnalysisStrategy JSON object.

IMPORTANT rules for reference scripts:
- Do NOT rewrite or regenerate the scripts.
- Instead, extract their *intent* (what do they do?), *parameters* (expected
  columns, paths, barcode sequences), and produce *diff-aware adaptation
  suggestions* (the new run differs from the original -- what params need
  updating?).
- These insights go in the `script_insights` field.

For the gate checklist, prefer concrete pass/fail criteria (e.g.
"mapping rate >= 80%" rather than "check mapping rate").

For the execution plan, mark steps as `is_deterministic: true` if a
registered QC module can handle them, otherwise false (LLM-generated).
"""

STRATEGY_PROMPT = """# Experiment Understanding

{understanding_json}

# User Hypotheses

What is wrong: {what_is_wrong}
What to prove: {what_to_prove}

Structured hypotheses:
{hypotheses_list}

# Instructions

Produce a comprehensive AnalysisStrategy that:
1. Maps each user hypothesis to a concrete test method and expected outcome.
2. Defines a gate checklist with pass/fail criteria.
3. Lists required modules/tools.
4. Provides an ordered execution plan.
5. Analyses any reference scripts (see attached files) for intent, params,
   and adaptation notes.

Return structured JSON only.
"""


SCRIPT_INSIGHT_PROMPT = """# Reference Script Analysis

Analyze the attached script and extract:
1. **Intent**: What does this script do? (1-2 sentences)
2. **Parameters**: What key parameters does it expect? (as a dict)
3. **Adaptation notes**: Given the new experiment context below, what
   parameters or paths would need changing?

## New Experiment Context
{context_summary}

Return structured JSON with fields: script_path, intent, parameters, adaptation_notes.
"""


# ---------------------------------------------------------------------------
# Strategy generation
# ---------------------------------------------------------------------------

def _format_hypotheses(hypothesis_set: HypothesisSet | None) -> tuple[str, str, str]:
    """Extract and format hypothesis info for the prompt."""
    if hypothesis_set is None:
        return ("(none provided)", "(none provided)", "(none)")
    what_wrong = hypothesis_set.what_is_wrong or "(none provided)"
    what_prove = hypothesis_set.what_to_prove or "(none provided)"
    if hypothesis_set.hypotheses:
        lines = []
        for h in hypothesis_set.hypotheses:
            lines.append(f"- [{h.priority.upper()}] {h.text}")
            if h.rationale:
                lines.append(f"  Rationale: {h.rationale}")
        hyp_list = "\n".join(lines)
    else:
        hyp_list = "(none)"
    return what_wrong, what_prove, hyp_list


async def generate_strategy(
    understanding: ExperimentUnderstanding,
    hypothesis_set: HypothesisSet | None = None,
    reference_paths: list[str] | None = None,
    client: GeminiClient | None = None,
    user_approach: str | None = None,
) -> AnalysisStrategy:
    """Generate an analysis strategy from understanding + hypotheses + refs.

    Args:
        understanding: The experiment understanding.
        hypothesis_set: Optional user hypotheses.
        reference_paths: Optional script paths to upload for safe analysis.
        client: Optional Gemini client.

    Returns:
        AnalysisStrategy with structured plan.
    """
    if client is None:
        client = get_gemini_client()

    what_wrong, what_prove, hyp_list = _format_hypotheses(hypothesis_set)

    understanding_json = json.dumps(
        understanding.model_dump(mode="json"), indent=2, default=str
    )

    prompt = STRATEGY_PROMPT.format(
        understanding_json=understanding_json,
        what_is_wrong=what_wrong,
        what_to_prove=what_prove,
        hypotheses_list=hyp_list,
    )

    if user_approach:
        prompt += f"\n\n# User-Specified Analysis Approach\n\nThe user has specified their preferred analysis approach:\n{user_approach}\n"

    # Filter to existing files
    valid_paths = [p for p in (reference_paths or []) if Path(p).exists()]

    if valid_paths:
        logger.info(
            "Generating strategy with %d reference file(s)", len(valid_paths)
        )
        strategy = await client.generate_structured_with_files_async(
            prompt=prompt,
            file_paths=valid_paths,
            response_schema=AnalysisStrategy,
            system_instruction=STRATEGY_SYSTEM,
            temperature=0.3,
            max_output_tokens=8192,
        )
    else:
        strategy = await client.generate_structured_async(
            prompt=prompt,
            response_schema=AnalysisStrategy,
            system_instruction=STRATEGY_SYSTEM,
            temperature=0.3,
            max_output_tokens=8192,
        )

    # Metadata
    strategy.model_used = client.model_name
    strategy.generated_at = datetime.now()
    if user_approach:
        strategy.user_approach = user_approach

    return strategy


# ---------------------------------------------------------------------------
# Safe script analysis (standalone, used for individual insights)
# ---------------------------------------------------------------------------

async def analyze_script_safely(
    script_path: str,
    understanding: ExperimentUnderstanding,
    client: GeminiClient | None = None,
) -> ScriptInsight:
    """Analyze a reference script without rewriting it.

    Extracts intent, parameters, and adaptation suggestions.
    """
    if client is None:
        client = get_gemini_client()

    context_summary = (
        f"Experiment: {understanding.assay_name} ({understanding.experiment_type.value})\n"
        f"Platform: {understanding.assay_platform.value}\n"
        f"Summary: {understanding.summary[:400]}"
    )

    prompt = SCRIPT_INSIGHT_PROMPT.format(context_summary=context_summary)

    if not Path(script_path).exists():
        return ScriptInsight(
            script_path=script_path,
            intent="(file not found)",
            parameters={},
            adaptation_notes=["Script file not found on disk."],
        )

    insight = await client.generate_structured_with_files_async(
        prompt=prompt,
        file_paths=[script_path],
        response_schema=ScriptInsight,
        system_instruction=(
            "You are a bioinformatics code analyst. Extract the script's intent, "
            "parameters, and adaptation notes. Do NOT produce new code."
        ),
        temperature=0.2,
    )
    insight.script_path = script_path
    return insight
