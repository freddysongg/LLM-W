"""Tests for scripts/bench/judge_sanity.py.

These tests avoid any real model load or OpenAI call: ML dependencies are
stubbed by monkeypatching the generation path, and the judge is replaced
with a canned-score stub.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

_SCRIPTS_BENCH_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SCRIPTS_BENCH_DIR.parent.parent
_BENCH_CONFIG_PATH = _REPO_ROOT / "configs" / "bench" / "qwen15b-lora.yaml"
_PROMPTS_PATH = _REPO_ROOT / "configs" / "bench" / "judge_sanity_prompts.jsonl"
_PROMPTS_HASH_PATH = _REPO_ROOT / "configs" / "bench" / "judge_sanity_prompts.hash"
_EVAL_SPLIT_PATH = _REPO_ROOT / "configs" / "bench" / "eval_split.jsonl"

sys.path.insert(0, str(_SCRIPTS_BENCH_DIR))
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from judge_sanity import (  # noqa: E402
    GenerationRecord,
    JudgeSanityArgs,
    PromptRecord,
    RubricScoreSummary,
    _assert_disjoint_from_eval_split,
    _compute_file_sha256,
    _extract_bench_sidecar,
    _find_latest_checkpoint,
    _load_generations_if_complete,
    _mutate_summary,
    _read_prompt_records,
    _run_stage_one,
    _summarize_scores,
    _verify_prompts_hash,
    run,
)


def _build_summary_payload() -> dict[str, object]:
    return {
        "tokens_per_sec": 1.0,
        "time_to_first_checkpoint_s": 2.0,
        "wall_clock_s": 3.0,
        "peak_memory_mb": 4.0,
        "final_training_loss": 0.5,
        "heldout_perplexity": None,
        "cost_usd": 0.0,
        "judge_pass_rate": None,
        "run_id": "bench-cpu-test",
        "device": "cpu",
        "config_hash": "0" * 64,
        "eval_split_hash": None,
        "started_at": "2026-04-13T12:00:00+00:00",
        "completed_at": "2026-04-13T12:30:00+00:00",
        "metric_unavailable_reasons": {
            "heldout_perplexity": "deferred to post-train eval",
            "judge_pass_rate": "deferred to judge-harness runner",
        },
    }


def test_committed_prompts_file_count_is_fifty() -> None:
    records = _read_prompt_records(prompts_path=_PROMPTS_PATH)
    assert len(records) == 50
    prompt_ids = {record.prompt_id for record in records}
    assert len(prompt_ids) == 50
    prompt_texts = {record.prompt for record in records}
    assert len(prompt_texts) == 50


def test_committed_prompts_hash_matches_on_disk_file() -> None:
    declared = _PROMPTS_HASH_PATH.read_text(encoding="utf-8").strip()
    actual = _compute_file_sha256(path=_PROMPTS_PATH)
    assert declared == actual


def test_bench_sidecar_declared_hash_matches_prompts_file() -> None:
    raw = yaml.safe_load(_BENCH_CONFIG_PATH.read_text(encoding="utf-8"))
    sidecar = _extract_bench_sidecar(raw_config=raw, repo_root=_REPO_ROOT)
    assert sidecar.judge_sanity_prompts_hash == _compute_file_sha256(path=_PROMPTS_PATH)
    assert sidecar.judge_sanity_prompts_source == "synthetic-placeholder-v1"


def test_verify_prompts_hash_raises_on_mismatch(tmp_path: Path) -> None:
    prompts_file = tmp_path / "prompts.jsonl"
    prompts_file.write_bytes(b"{}\n")
    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        _verify_prompts_hash(prompts_path=prompts_file, expected_hash="0" * 64)


def test_verify_prompts_hash_warns_when_hash_is_null(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompts_file = tmp_path / "prompts.jsonl"
    prompts_file.write_bytes(b"{}\n")
    _verify_prompts_hash(prompts_path=prompts_file, expected_hash=None)
    captured = capsys.readouterr()
    assert "judge_sanity_prompts_hash is null" in captured.err


def test_committed_prompts_disjoint_from_eval_split() -> None:
    if not _EVAL_SPLIT_PATH.exists():
        pytest.skip("eval_split.jsonl not present in this checkout")
    records = _read_prompt_records(prompts_path=_PROMPTS_PATH)
    _assert_disjoint_from_eval_split(prompts=records, eval_split_path=_EVAL_SPLIT_PATH)


def test_disjoint_check_rejects_overlap(tmp_path: Path) -> None:
    eval_split_file = tmp_path / "eval_split.jsonl"
    overlap_prompt = "What is the capital of France?"
    eval_split_file.write_text(
        json.dumps({"prompt": overlap_prompt, "prompt_id": "x"}) + "\n"
    )
    records = [
        PromptRecord(prompt_id="sanity-0", prompt=overlap_prompt),
        PromptRecord(prompt_id="sanity-1", prompt="a unique prompt"),
    ]
    with pytest.raises(RuntimeError, match="overlap with eval_split.jsonl"):
        _assert_disjoint_from_eval_split(
            prompts=records, eval_split_path=eval_split_file
        )


def test_disjoint_check_inspects_messages_user_turns(tmp_path: Path) -> None:
    eval_split_file = tmp_path / "eval_split.jsonl"
    overlap_prompt = "Summarize this article in one sentence."
    eval_split_file.write_text(
        json.dumps(
            {
                "prompt_id": "x",
                "prompt": "other field",
                "messages": [{"role": "user", "content": overlap_prompt}],
            }
        )
        + "\n"
    )
    records = [PromptRecord(prompt_id="s", prompt=overlap_prompt)]
    with pytest.raises(RuntimeError, match="overlap"):
        _assert_disjoint_from_eval_split(
            prompts=records, eval_split_path=eval_split_file
        )


def test_find_latest_checkpoint_picks_highest_step(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    ckpt_dir = project_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True)
    (ckpt_dir / "checkpoint-5").mkdir()
    (ckpt_dir / "checkpoint-50").mkdir()
    (ckpt_dir / "checkpoint-12").mkdir()
    resolved = _find_latest_checkpoint(project_dir=project_dir)
    assert resolved is not None
    assert resolved.name == "checkpoint-50"


def test_find_latest_checkpoint_returns_none_for_empty_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    (project_dir / "checkpoints").mkdir(parents=True)
    assert _find_latest_checkpoint(project_dir=project_dir) is None


def _make_generation(prompt_id: str, prompt: str, output: str) -> GenerationRecord:
    return GenerationRecord(prompt_id=prompt_id, prompt=prompt, output=output)


def test_load_generations_if_complete_skips_when_count_matches(
    tmp_path: Path,
) -> None:
    generations_file = tmp_path / "gens.jsonl"
    lines: list[str] = []
    for index in range(50):
        payload = {
            "prompt_id": f"p-{index}",
            "prompt": f"prompt {index}",
            "output": f"answer {index}",
        }
        lines.append(json.dumps(payload))
    generations_file.write_text("\n".join(lines) + "\n")
    loaded = _load_generations_if_complete(path=generations_file)
    assert loaded is not None
    assert len(loaded) == 50


def test_load_generations_if_complete_returns_none_when_short(tmp_path: Path) -> None:
    generations_file = tmp_path / "gens.jsonl"
    generations_file.write_text(
        json.dumps({"prompt_id": "p", "prompt": "q", "output": "a"}) + "\n"
    )
    assert _load_generations_if_complete(path=generations_file) is None


def test_stage_one_uses_cached_generations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    generations_path = output_dir / "judge_sanity_generations.jsonl"

    lines: list[str] = []
    prompts: list[PromptRecord] = []
    for index in range(50):
        prompt_id = f"synth-{index:03d}"
        prompt_text = f"cached prompt {index}"
        output_text = f"cached output {index}"
        lines.append(
            json.dumps(
                {"prompt_id": prompt_id, "prompt": prompt_text, "output": output_text}
            )
        )
        prompts.append(PromptRecord(prompt_id=prompt_id, prompt=prompt_text))
    generations_path.write_text("\n".join(lines) + "\n")

    args = JudgeSanityArgs(
        summary_path=output_dir / "summary.json",
        config_path=_BENCH_CONFIG_PATH,
        repo_root=_REPO_ROOT,
        device="cpu",
        adapter_path=None,
        output_dir=output_dir,
    )
    raw_config = yaml.safe_load(_BENCH_CONFIG_PATH.read_text(encoding="utf-8"))
    generations = _run_stage_one(args=args, raw_config=raw_config, prompts=prompts)
    assert len(generations) == 50
    captured = capsys.readouterr()
    assert "using cached generations" in captured.err


def test_summarize_scores_computes_pass_rate() -> None:
    class _FakeScore:
        def __init__(self, verdict: str) -> None:
            self.verdict = verdict

    per_rubric_scores = {
        "faithfulness": [_FakeScore("pass"), _FakeScore("fail"), _FakeScore("pass")],
        "instruction_following": [_FakeScore("pass"), _FakeScore("pass")],
    }
    summaries = _summarize_scores(per_rubric_scores=cast(Any, per_rubric_scores))
    by_id = {entry.rubric_id: entry for entry in summaries}
    assert by_id["faithfulness"].pass_count == 2
    assert by_id["faithfulness"].total == 3
    assert by_id["instruction_following"].pass_rate == 1.0


def test_mutate_summary_writes_judge_fields(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(_build_summary_payload()))
    _mutate_summary(
        summary_path=summary_path,
        judge_pass_rate=0.82,
        judge_breakdown={"faithfulness": 0.8, "instruction_following": 0.84},
        failure_reason=None,
    )
    parsed = json.loads(summary_path.read_text())
    assert parsed["judge_pass_rate"] == 0.82
    assert parsed["judge_breakdown"]["faithfulness"] == 0.8
    assert parsed["judge_breakdown"]["instruction_following"] == 0.84
    assert "judge_pass_rate" not in parsed["metric_unavailable_reasons"]


def test_mutate_summary_records_failure_reason(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(_build_summary_payload()))
    _mutate_summary(
        summary_path=summary_path,
        judge_pass_rate=None,
        judge_breakdown=None,
        failure_reason="judge harness failed: boom",
    )
    parsed = json.loads(summary_path.read_text())
    assert parsed["judge_pass_rate"] is None
    assert "judge_breakdown" not in parsed
    assert (
        parsed["metric_unavailable_reasons"]["judge_pass_rate"]
        == "judge harness failed: boom"
    )


class _StubScore:
    """Minimal stand-in for ``app.schemas.eval.Score`` for summary tests."""

    def __init__(self, verdict: str) -> None:
        self.verdict = verdict


def test_end_to_end_with_stubbed_generate_and_judge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(_build_summary_payload()))

    def _fake_generate_completions(
        *,
        prompts: list[PromptRecord],
        base_model_id: str,
        adapter_path: Path,
        device: str,
        max_new_tokens: int,
        temperature: float,
    ) -> list[GenerationRecord]:
        return [
            GenerationRecord(
                prompt_id=record.prompt_id,
                prompt=record.prompt,
                output=f"stub-output-for-{record.prompt_id}",
            )
            for record in prompts
        ]

    import judge_sanity

    monkeypatch.setattr(
        judge_sanity, "_generate_completions", _fake_generate_completions
    )

    project_dir = output_dir / "project"
    adapter_dir = project_dir / "checkpoints" / "checkpoint-10"
    adapter_dir.mkdir(parents=True)

    class _FakeJudge:
        async def evaluate(self, *, case: Any, rubric: Any) -> _StubScore:
            return _StubScore(verdict="pass" if len(case.output) % 2 == 0 else "fail")

    def _fake_stage_two_factory() -> Any:
        async def stage_two(
            *, generations: list[GenerationRecord], repo_root: Path
        ) -> list[RubricScoreSummary]:
            pass_count = sum(1 for record in generations if len(record.output) % 2 == 0)
            return [
                RubricScoreSummary(
                    rubric_id="faithfulness",
                    pass_count=pass_count,
                    total=len(generations),
                ),
                RubricScoreSummary(
                    rubric_id="instruction_following",
                    pass_count=len(generations),
                    total=len(generations),
                ),
            ]

        return stage_two

    monkeypatch.setattr(judge_sanity, "_run_stage_two", _fake_stage_two_factory())

    exit_code = run(
        argv=[
            "--summary",
            str(summary_path),
            "--config",
            str(_BENCH_CONFIG_PATH),
            "--repo-root",
            str(_REPO_ROOT),
            "--device",
            "cpu",
            "--output-dir",
            str(output_dir),
            "--adapter-path",
            str(adapter_dir),
        ]
    )
    assert exit_code == 0

    parsed = json.loads(summary_path.read_text())
    assert parsed["judge_pass_rate"] is not None
    assert "faithfulness" in parsed["judge_breakdown"]
    assert "instruction_following" in parsed["judge_breakdown"]
    assert "judge_pass_rate" not in parsed["metric_unavailable_reasons"]


def test_generation_failure_leaves_judge_pass_rate_null(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(_build_summary_payload()))

    adapter_dir = output_dir / "project" / "checkpoints" / "checkpoint-1"
    adapter_dir.mkdir(parents=True)

    import judge_sanity

    def _boom(**_kwargs: Any) -> list[GenerationRecord]:
        raise RuntimeError("simulated generation crash")

    monkeypatch.setattr(judge_sanity, "_generate_completions", _boom)

    exit_code = run(
        argv=[
            "--summary",
            str(summary_path),
            "--config",
            str(_BENCH_CONFIG_PATH),
            "--repo-root",
            str(_REPO_ROOT),
            "--device",
            "cpu",
            "--output-dir",
            str(output_dir),
            "--adapter-path",
            str(adapter_dir),
        ]
    )
    assert exit_code == 0

    parsed = json.loads(summary_path.read_text())
    assert parsed["judge_pass_rate"] is None
    reason = parsed["metric_unavailable_reasons"]["judge_pass_rate"]
    assert "judge harness failed during generation" in reason


def test_scoring_failure_leaves_judge_pass_rate_null(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(_build_summary_payload()))

    prompts = _read_prompt_records(prompts_path=_PROMPTS_PATH)
    generations_path = output_dir / "judge_sanity_generations.jsonl"
    lines = [
        json.dumps(
            {
                "prompt_id": record.prompt_id,
                "prompt": record.prompt,
                "output": "cached-output",
            }
        )
        for record in prompts
    ]
    generations_path.write_text("\n".join(lines) + "\n")

    import judge_sanity

    async def _boom_stage_two(
        *, generations: list[GenerationRecord], repo_root: Path
    ) -> list[RubricScoreSummary]:
        raise RuntimeError("simulated judge failure")

    monkeypatch.setattr(judge_sanity, "_run_stage_two", _boom_stage_two)

    exit_code = run(
        argv=[
            "--summary",
            str(summary_path),
            "--config",
            str(_BENCH_CONFIG_PATH),
            "--repo-root",
            str(_REPO_ROOT),
            "--device",
            "cpu",
            "--output-dir",
            str(output_dir),
        ]
    )
    assert exit_code == 0

    parsed = json.loads(summary_path.read_text())
    assert parsed["judge_pass_rate"] is None
    reason = parsed["metric_unavailable_reasons"]["judge_pass_rate"]
    assert "judge harness failed during scoring" in reason


def test_reference_handling_leaves_faithfulness_reference_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Document behaviour: faithfulness runs with ``EvaluationCase.reference``
    set to ``None``. The rubric's few-shot examples carry references, so the
    judge still sees properly-formatted exemplars; cross-backend sanity only
    requires consistent application, not perfect rubric semantics.
    """
    from app.schemas.eval import EvaluationCase
    from app.schemas.rubric import Rubric

    rubric_path = _REPO_ROOT / "rubrics" / "faithfulness.yaml"
    parsed_yaml = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
    rubric = Rubric.model_validate(parsed_yaml)
    assert rubric.id == "faithfulness"

    case = EvaluationCase(prompt="p", output="o")
    assert case.reference is None


def test_prompts_file_hash_is_deterministic() -> None:
    expected = _PROMPTS_HASH_PATH.read_text(encoding="utf-8").strip()
    digest = hashlib.sha256()
    digest.update(_PROMPTS_PATH.read_bytes())
    assert digest.hexdigest() == expected
