from datetime import datetime

import pytest

pytest.importorskip("fastapi")

from aco.api.routes.scripts import _build_usage_instructions
from aco.engine.scripts import GeneratedScript, ScriptCategory, ScriptPlan, ScriptType
from aco.manifest.models import FileMetadata, FileType, Manifest, ScanResult, UserIntake


def _file(path: str, filename: str, file_type: FileType, read_number: int | None, lane: str | None):
    return FileMetadata(
        path=path,
        filename=filename,
        file_type=file_type,
        size_bytes=123,
        size_human="123 B",
        modified_at=datetime.now(),
        is_compressed=path.endswith(".gz"),
        compression_type="gz" if path.endswith(".gz") else None,
        parent_dir="cite_fastq",
        sample_name="AA-4446",
        read_number=read_number,
        lane=lane,
    )


def _make_plan(usage_instructions: str | None) -> ScriptPlan:
    script = GeneratedScript(
        name="detect_hashtag_v2.py",
        category=ScriptCategory.QC_METRICS,
        script_type=ScriptType.PYTHON,
        description="Detect hashtag reads",
        code=(
            "parser.add_argument('--fastq', required=True)\n"
            "parser.add_argument('--oligo_tsv', required=True)\n"
            "parser.add_argument('--hashtag_tsv', required=True)\n"
            "parser.add_argument('--out', required=True)\n"
            "parser.add_argument('--stats_out', required=True)\n"
        ),
        dependencies=["umi-tools"],
        input_files=[],
        output_files=[],
    )
    return ScriptPlan(
        manifest_id="manifest_test",
        scripts=[script],
        execution_order=[script.name],
        total_estimated_runtime="5m",
        usage_instructions=usage_instructions,
    )


def test_usage_instructions_include_lane_loop_and_generated_script():
    files = [
        _file(
            path=f"cite_fastq/AA-4446_FateSeq2_CITE_IGO_12437_MT_5_S12_L00{i}_R1_001.fastq.gz",
            filename=f"AA-4446_FateSeq2_CITE_IGO_12437_MT_5_S12_L00{i}_R1_001.fastq.gz",
            file_type=FileType.FASTQ,
            read_number=1,
            lane=f"L00{i}",
        )
        for i in range(5, 9)
    ]
    files.extend(
        [
            _file(
                path=f"cite_fastq/AA-4446_FateSeq2_CITE_IGO_12437_MT_5_S12_L00{i}_R2_001.fastq.gz",
                filename=f"AA-4446_FateSeq2_CITE_IGO_12437_MT_5_S12_L00{i}_R2_001.fastq.gz",
                file_type=FileType.FASTQ,
                read_number=2,
                lane=f"L00{i}",
            )
            for i in range(5, 9)
        ]
    )
    files.extend(
        [
            _file(
                path="cite_hashtag/outputs/whitelist_translated.txt",
                filename="whitelist_translated.txt",
                file_type=FileType.UNKNOWN,
                read_number=None,
                lane=None,
            ),
            _file(
                path="oligo_seq.tsv",
                filename="oligo_seq.tsv",
                file_type=FileType.UNKNOWN,
                read_number=None,
                lane=None,
            ),
            _file(
                path="hashtag.tsv",
                filename="hashtag.tsv",
                file_type=FileType.UNKNOWN,
                read_number=None,
                lane=None,
            ),
        ]
    )

    manifest = Manifest(
        id="manifest_test",
        user_intake=UserIntake(
            experiment_description="test",
            target_directory=".",
        ),
        scan_result=ScanResult(scan_path=".", files=files),
    )
    plan = _make_plan("Use generated scripts carefully.")

    usage = _build_usage_instructions(plan, manifest)
    assert usage is not None
    assert "for LANE in L005 L006 L007 L008; do" in usage
    assert 'python scripts/detect_hashtag_v2.py \\' in usage
    assert 'WHITELIST="cite_hashtag/outputs/whitelist_translated.txt"' in usage
    assert "## Notes" in usage
    assert "Use generated scripts carefully." in usage


def test_usage_instructions_preserve_notes_without_duplication():
    plan = _make_plan(
        "## Run Commands\n\n```bash\nold command\n```\n\n## Notes\nKeep these notes."
    )
    usage = _build_usage_instructions(plan, manifest=None)
    assert usage is not None
    assert usage.count("## Run Commands") == 1
    assert usage.count("## Notes") == 1
    assert "Keep these notes." in usage
    assert "old command" not in usage
