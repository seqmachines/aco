from types import SimpleNamespace

import pytest

pytest.importorskip("google")
pytest.importorskip("google.genai")

from aco.engine.scripts import (
    BatchedCodeAndUsageSchema,
    GeneratedScript,
    ScriptCategory,
    ScriptPlan,
    ScriptType,
    generate_all_script_code_with_usage,
)


def _valid_python_code() -> str:
    lines = [
        "#!/usr/bin/env python3",
        "import argparse",
        "import sys",
        "",
        "def parse_args():",
        "    p = argparse.ArgumentParser()",
        "    p.add_argument('--input', required=True)",
        "    p.add_argument('--out', required=True)",
        "    return p.parse_args()",
        "",
        "def main():",
        "    args = parse_args()",
        "    with open(args.out, 'w') as fh:",
        "        fh.write('ok')",
        "    print(args.input)",
        "    return 0",
        "",
        "if __name__ == '__main__':",
        "    raise SystemExit(main())",
        "",
        "# end",
    ]
    return "\n".join(lines)


class _FakeClient:
    def __init__(self, response: BatchedCodeAndUsageSchema):
        self.response = response
        self.last_prompt = ""

    async def generate_structured_async(self, prompt, response_schema, system_instruction, temperature, max_output_tokens):  # noqa: ARG002
        self.last_prompt = prompt
        return self.response

    async def generate_structured_with_files_async(self, prompt, file_paths, response_schema, system_instruction, temperature, max_output_tokens):  # noqa: ARG002
        self.last_prompt = prompt
        return self.response


def _mock_understanding():
    enum_like = lambda value: SimpleNamespace(value=value)
    return SimpleNamespace(
        assay_name="CITE",
        experiment_type=enum_like("single_cell_rna_seq"),
        assay_platform=enum_like("10x_chromium"),
        summary="Mock summary",
        key_parameters={"chemistry": "v3"},
        pipeline_parameters={"threads": "8"},
        sample_count=1,
        expected_cells_total=5000,
    )


def _mock_strategy():
    return SimpleNamespace(
        summary="Strategy summary",
        required_modules=["sequencing_health"],
        required_tools=["umi_tools"],
        execution_plan=[
            SimpleNamespace(
                name="preflight",
                description="prepare env",
                tool_or_module="bash",
                depends_on=[],
                is_deterministic=True,
                estimated_runtime="2m",
            )
        ],
        gate_checklist=[
            SimpleNamespace(
                gate_name="reads",
                pass_criteria=">=1M",
                fail_criteria="<1M",
                module_name="sequencing_health",
                priority="required",
            )
        ],
    )


async def test_batched_generation_uses_strategy_context():
    script = GeneratedScript(
        name="detect_hashtag_v2.py",
        category=ScriptCategory.QC_METRICS,
        script_type=ScriptType.PYTHON,
        description="Detect hashtag",
        code="",
        dependencies=["pandas"],
        input_files=["*.fastq.gz"],
        output_files=["out.tsv"],
    )
    plan = ScriptPlan(
        manifest_id="manifest_x",
        scripts=[script],
        execution_order=[script.name],
    )
    response = BatchedCodeAndUsageSchema(
        scripts=[{"name": script.name, "code": _valid_python_code()}],
        usage_instructions="## Run Commands\n```bash\npython scripts/detect_hashtag_v2.py --input x --out y\n```\n## Notes\nok",
        warnings=[],
    )
    client = _FakeClient(response)

    code_by_name, usage = await generate_all_script_code_with_usage(
        plan=plan,
        understanding=_mock_understanding(),
        file_list=["a/b/c.fastq.gz"],
        output_dirs_by_script={script.name: "/tmp/out"},
        analysis_strategy=_mock_strategy(),
        client=client,
        reference_script_paths=None,
    )

    assert script.name in code_by_name
    assert "## Run Commands" in usage
    assert "preflight" in client.last_prompt


async def test_batched_generation_requires_run_commands_and_notes():
    script = GeneratedScript(
        name="x.py",
        category=ScriptCategory.CUSTOM,
        script_type=ScriptType.PYTHON,
        description="x",
        code="",
        dependencies=[],
        input_files=[],
        output_files=[],
    )
    plan = ScriptPlan(manifest_id="m", scripts=[script], execution_order=[script.name])
    response = BatchedCodeAndUsageSchema(
        scripts=[{"name": script.name, "code": _valid_python_code()}],
        usage_instructions="just text",
        warnings=[],
    )
    client = _FakeClient(response)

    try:
        await generate_all_script_code_with_usage(
            plan=plan,
            understanding=_mock_understanding(),
            file_list=[],
            output_dirs_by_script={script.name: "/tmp/out"},
            analysis_strategy=_mock_strategy(),
            client=client,
            reference_script_paths=None,
        )
        assert False, "Expected ValueError for missing required markdown sections"
    except ValueError as exc:
        assert "missing required sections" in str(exc)
