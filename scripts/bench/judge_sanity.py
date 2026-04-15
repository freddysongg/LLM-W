"""Post-training judge-sanity step for the bench pipeline (W2.5).

Loads the just-saved LoRA adapter, generates completions on a fixed 50-prompt
disjoint set, scores each (prompt, output) with the v1 ``faithfulness`` and
``instruction_following`` rubrics via the Tier-2 G-Eval judge, and mutates the
bench ``summary.json`` in place to populate ``judge_pass_rate`` plus a
per-rubric ``judge_breakdown``.

Design choices:
  * Runs as its own script so training-loop metrics collection stays focused
    and so the judge step can be re-run against an existing generations file
    without paying the generate cost.
  * Stage-1 (generate) idempotency: if ``judge_sanity_generations.jsonl``
    already has 50 entries, the adapter/model load is skipped entirely.
  * Failure resilience: any exception in Stage-1 or Stage-2 is swallowed into
    ``metric_unavailable_reasons.judge_pass_rate``. The script exits 0 — the
    training run itself was successful even if best-effort scoring was not.
  * Disjointness: SHA256 of every prompt is cross-checked against the frozen
    eval split. Any collision is a hard-fail at startup. The calibration set
    hash (``eval/calibration/v1_raw.hash``) is checked if present and softly
    skipped with a warning otherwise — #21 will populate it.
  * Reference handling for faithfulness: ``EvaluationCase.reference`` is left
    as ``None``. Per the v4 plan §W2.5 the goal is *equivalent quality across
    backends*, not perfect rubric semantics — what matters is that all three
    backends score under the same conditions. The rubric's few-shot examples
    carry a reference, so the judge still sees correctly-framed exemplars.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import yaml

if TYPE_CHECKING:
    from app.schemas.eval import Score
    from app.schemas.rubric import Rubric
    from app.services.eval import GEvalJudge


_STDERR_PREFIX = "[bench]"
_EXPECTED_PROMPT_COUNT = 50
_GENERATIONS_FILENAME = "judge_sanity_generations.jsonl"
_DEFAULT_MAX_NEW_TOKENS = 256
_DEFAULT_TEMPERATURE = 0.0

_RUBRIC_FAITHFULNESS = "faithfulness"
_RUBRIC_INSTRUCTION_FOLLOWING = "instruction_following"
_RUBRIC_NAMES: tuple[str, ...] = (_RUBRIC_FAITHFULNESS, _RUBRIC_INSTRUCTION_FOLLOWING)

_CALIBRATION_HASH_RELATIVE_PATH = Path("eval") / "calibration" / "v1_raw.hash"
_EVAL_SPLIT_RELATIVE_PATH = Path("configs") / "bench" / "eval_split.jsonl"

DeviceLiteral = Literal["cuda", "mps", "cpu"]
_VALID_DEVICES: tuple[DeviceLiteral, ...] = ("cuda", "mps", "cpu")


@dataclass(frozen=True)
class JudgeSanityArgs:
    summary_path: Path
    config_path: Path
    repo_root: Path
    device: DeviceLiteral
    adapter_path: Path | None
    output_dir: Path


@dataclass(frozen=True)
class PromptRecord:
    prompt_id: str
    prompt: str


@dataclass(frozen=True)
class GenerationRecord:
    prompt_id: str
    prompt: str
    output: str


@dataclass(frozen=True)
class RubricScoreSummary:
    rubric_id: str
    pass_count: int
    total: int

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.pass_count / self.total


def _eprint(message: str) -> None:
    print(f"{_STDERR_PREFIX} {message}", file=sys.stderr, flush=True)


def _read_prompt_records(*, prompts_path: Path) -> list[PromptRecord]:
    records: list[PromptRecord] = []
    with prompts_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            parsed = json.loads(stripped)
            if not isinstance(parsed, dict):
                raise RuntimeError(
                    f"{prompts_path}:{line_number} does not deserialize to a JSON object"
                )
            prompt_id = parsed.get("prompt_id")
            prompt_text = parsed.get("prompt")
            if not isinstance(prompt_id, str) or not isinstance(prompt_text, str):
                raise RuntimeError(
                    f"{prompts_path}:{line_number} missing str prompt_id/prompt fields"
                )
            records.append(PromptRecord(prompt_id=prompt_id, prompt=prompt_text))
    return records


def _compute_file_sha256(*, path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _collect_eval_split_prompts(*, eval_split_path: Path) -> set[str]:
    collected: set[str] = set()
    with eval_split_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped:
                continue
            parsed = json.loads(stripped)
            if not isinstance(parsed, dict):
                continue
            prompt_value = parsed.get("prompt")
            if isinstance(prompt_value, str):
                collected.add(prompt_value)
            messages = parsed.get("messages")
            if isinstance(messages, list):
                for turn in messages:
                    if not isinstance(turn, dict):
                        continue
                    if turn.get("role") == "user":
                        content = turn.get("content")
                        if isinstance(content, str):
                            collected.add(content)
    return collected


@dataclass(frozen=True)
class BenchSidecar:
    judge_sanity_prompts_path: Path
    judge_sanity_prompts_hash: str | None
    judge_sanity_prompts_source: str | None


def _extract_bench_sidecar(
    *, raw_config: dict[str, object], repo_root: Path
) -> BenchSidecar:
    bench_raw = raw_config.get("bench")
    if not isinstance(bench_raw, dict):
        raise RuntimeError("config missing 'bench' sidecar required for judge sanity")

    prompts_path_raw = bench_raw.get("judge_sanity_prompts_path")
    if not isinstance(prompts_path_raw, str) or not prompts_path_raw:
        raise RuntimeError(
            "bench.judge_sanity_prompts_path is not set in the bench config"
        )
    candidate = Path(prompts_path_raw)
    prompts_path = candidate if candidate.is_absolute() else (repo_root / candidate)

    hash_raw = bench_raw.get("judge_sanity_prompts_hash")
    judge_sanity_prompts_hash = (
        hash_raw if isinstance(hash_raw, str) and hash_raw else None
    )

    source_raw = bench_raw.get("judge_sanity_prompts_source")
    judge_sanity_prompts_source = (
        source_raw if isinstance(source_raw, str) and source_raw else None
    )

    return BenchSidecar(
        judge_sanity_prompts_path=prompts_path,
        judge_sanity_prompts_hash=judge_sanity_prompts_hash,
        judge_sanity_prompts_source=judge_sanity_prompts_source,
    )


def _verify_prompts_hash(*, prompts_path: Path, expected_hash: str | None) -> None:
    if expected_hash is None:
        _eprint(
            "warning: bench.judge_sanity_prompts_hash is null; skipping integrity check"
        )
        return
    actual = _compute_file_sha256(path=prompts_path)
    if actual != expected_hash:
        raise RuntimeError(
            f"judge_sanity_prompts.jsonl SHA256 mismatch: "
            f"YAML={expected_hash} disk={actual}"
        )


def _assert_disjoint_from_eval_split(
    *, prompts: list[PromptRecord], eval_split_path: Path
) -> None:
    if not eval_split_path.exists():
        raise RuntimeError(
            f"eval_split.jsonl missing at {eval_split_path}; "
            "cannot verify judge-sanity disjointness"
        )
    eval_prompts = _collect_eval_split_prompts(eval_split_path=eval_split_path)
    collisions = [
        record.prompt_id for record in prompts if record.prompt in eval_prompts
    ]
    if collisions:
        raise RuntimeError(
            f"judge-sanity prompts overlap with eval_split.jsonl: "
            f"{collisions[:5]} (total={len(collisions)})"
        )


def _assert_disjoint_from_calibration(*, prompts_path: Path, repo_root: Path) -> None:
    calibration_hash_path = repo_root / _CALIBRATION_HASH_RELATIVE_PATH
    if not calibration_hash_path.exists():
        _eprint(
            "warning: calibration hash file not found at "
            f"{calibration_hash_path} (likely #21 has not landed); "
            "skipping calibration-disjointness check"
        )
        return
    calibration_hash = calibration_hash_path.read_text(encoding="utf-8").strip()
    prompts_file_hash = _compute_file_sha256(path=prompts_path)
    if prompts_file_hash == calibration_hash:
        raise RuntimeError(
            "judge_sanity_prompts.jsonl hash equals calibration set hash; "
            "the two sets must not share bytes"
        )


def _find_latest_checkpoint(*, project_dir: Path) -> Path | None:
    checkpoints_dir = project_dir / "checkpoints"
    if not checkpoints_dir.exists():
        return None
    candidates = [
        entry
        for entry in checkpoints_dir.iterdir()
        if entry.is_dir() and entry.name.startswith("checkpoint-")
    ]
    if not candidates:
        return None

    def _step_number(entry: Path) -> int:
        suffix = entry.name.removeprefix("checkpoint-")
        try:
            return int(suffix)
        except ValueError:
            return -1

    ranked = sorted(candidates, key=_step_number)
    return ranked[-1] if ranked else None


def _resolve_base_model_id(*, raw_config: dict[str, object]) -> str:
    model_raw = raw_config.get("model")
    if not isinstance(model_raw, dict):
        raise RuntimeError("config missing 'model' section")
    model_id = model_raw.get("model_id")
    if not isinstance(model_id, str) or not model_id:
        raise RuntimeError("config 'model.model_id' must be a non-empty string")
    return model_id


def _load_generations_if_complete(*, path: Path) -> list[GenerationRecord] | None:
    if not path.exists():
        return None
    loaded: list[GenerationRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped:
                continue
            parsed = json.loads(stripped)
            if not isinstance(parsed, dict):
                return None
            prompt_id = parsed.get("prompt_id")
            prompt = parsed.get("prompt")
            output = parsed.get("output")
            if not (
                isinstance(prompt_id, str)
                and isinstance(prompt, str)
                and isinstance(output, str)
            ):
                return None
            loaded.append(
                GenerationRecord(prompt_id=prompt_id, prompt=prompt, output=output)
            )
    if len(loaded) != _EXPECTED_PROMPT_COUNT:
        return None
    return loaded


def _write_generations(
    *, generations: list[GenerationRecord], destination: Path
) -> None:
    lines: list[str] = []
    for record in generations:
        payload = {
            "prompt_id": record.prompt_id,
            "prompt": record.prompt,
            "output": record.output,
        }
        lines.append(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp_path.replace(destination)


def _generate_completions(
    *,
    prompts: list[PromptRecord],
    base_model_id: str,
    adapter_path: Path,
    device: DeviceLiteral,
    max_new_tokens: int,
    temperature: float,
) -> list[GenerationRecord]:
    """Load base model + LoRA adapter and generate a completion per prompt.

    Imports are kept inside the function so the script remains importable for
    unit tests even when the ``training`` extras are not installed.
    """
    try:
        import torch  # noqa: PLC0415
        from peft import PeftModel  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            AutoModelForCausalLM,
            AutoTokenizer,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PEFT/transformers not installed; install backend[training] extras"
        ) from exc

    torch_device = torch.device(device)
    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    base_model = AutoModelForCausalLM.from_pretrained(base_model_id)
    base_model = base_model.to(torch_device)
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    model.eval()

    generations: list[GenerationRecord] = []
    for record in prompts:
        messages = [{"role": "user", "content": record.prompt}]
        if hasattr(tokenizer, "apply_chat_template"):
            prompt_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            prompt_text = record.prompt
        inputs = tokenizer(prompt_text, return_tensors="pt").to(torch_device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0.0,
                pad_token_id=tokenizer.pad_token_id,
            )
        generated = output_ids[0][inputs["input_ids"].shape[-1] :]
        decoded = tokenizer.decode(generated, skip_special_tokens=True).strip()
        generations.append(
            GenerationRecord(
                prompt_id=record.prompt_id, prompt=record.prompt, output=decoded
            )
        )
    return generations


def _load_rubrics_from_disk(*, repo_root: Path) -> dict[str, Rubric]:
    from app.schemas.rubric import Rubric  # noqa: PLC0415

    rubrics_dir = repo_root / "rubrics"
    loaded: dict[str, Rubric] = {}
    for rubric_name in _RUBRIC_NAMES:
        yaml_path = rubrics_dir / f"{rubric_name}.yaml"
        if not yaml_path.exists():
            raise RuntimeError(f"rubric YAML missing: {yaml_path}")
        parsed = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise RuntimeError(f"rubric YAML at {yaml_path} must be a mapping")
        loaded[rubric_name] = Rubric.model_validate(parsed)
    return loaded


async def _score_all(
    *,
    generations: list[GenerationRecord],
    rubrics: dict[str, Rubric],
    judge: GEvalJudge,
) -> dict[str, list[Score]]:
    from app.schemas.eval import EvaluationCase  # noqa: PLC0415

    per_rubric_scores: dict[str, list[Score]] = {name: [] for name in rubrics}
    tasks: list[tuple[str, asyncio.Future[Score]]] = []
    for rubric_id, rubric in rubrics.items():
        for record in generations:
            case = EvaluationCase(prompt=record.prompt, output=record.output)
            tasks.append(
                (
                    rubric_id,
                    asyncio.ensure_future(judge.evaluate(case=case, rubric=rubric)),
                )
            )

    for rubric_id, future in tasks:
        score = await future
        per_rubric_scores[rubric_id].append(score)
    return per_rubric_scores


def _summarize_scores(
    *, per_rubric_scores: dict[str, list[Score]]
) -> list[RubricScoreSummary]:
    summaries: list[RubricScoreSummary] = []
    for rubric_id, scores in per_rubric_scores.items():
        pass_count = sum(1 for score in scores if score.verdict == "pass")
        summaries.append(
            RubricScoreSummary(
                rubric_id=rubric_id, pass_count=pass_count, total=len(scores)
            )
        )
    return summaries


def _mutate_summary(
    *,
    summary_path: Path,
    judge_pass_rate: float | None,
    judge_breakdown: dict[str, float] | None,
    failure_reason: str | None,
) -> None:
    payload_raw = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload_raw, dict):
        raise RuntimeError(f"summary.json at {summary_path} is not a JSON object")
    payload: dict[str, object] = payload_raw

    payload["judge_pass_rate"] = judge_pass_rate
    if judge_breakdown is not None:
        payload["judge_breakdown"] = judge_breakdown

    reasons_raw = payload.get("metric_unavailable_reasons")
    reasons: dict[str, object] = reasons_raw if isinstance(reasons_raw, dict) else {}
    if failure_reason is None:
        reasons.pop("judge_pass_rate", None)
    else:
        reasons["judge_pass_rate"] = failure_reason
    payload["metric_unavailable_reasons"] = reasons

    tmp_path = summary_path.with_suffix(summary_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(summary_path)


def _ensure_backend_on_path(*, repo_root: Path) -> None:
    backend_path = repo_root / "backend"
    if not backend_path.exists():
        raise RuntimeError(f"backend directory not found at {backend_path}")
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))


def _resolve_adapter_path(*, explicit: Path | None, output_dir: Path) -> Path:
    if explicit is not None:
        if not explicit.exists():
            raise RuntimeError(f"--adapter-path does not exist: {explicit}")
        return explicit
    project_dir = output_dir / "project"
    located = _find_latest_checkpoint(project_dir=project_dir)
    if located is None:
        raise RuntimeError(
            f"no checkpoint found under {project_dir / 'checkpoints'}; "
            "pass --adapter-path explicitly"
        )
    return located


def _run_stage_one(
    *,
    args: JudgeSanityArgs,
    raw_config: dict[str, object],
    prompts: list[PromptRecord],
) -> list[GenerationRecord]:
    generations_path = args.output_dir / _GENERATIONS_FILENAME
    cached = _load_generations_if_complete(path=generations_path)
    if cached is not None:
        _eprint(f"using cached generations from {generations_path}")
        return cached

    adapter_path = _resolve_adapter_path(
        explicit=args.adapter_path, output_dir=args.output_dir
    )
    base_model_id = _resolve_base_model_id(raw_config=raw_config)
    _eprint(
        f"generating {len(prompts)} completions with adapter={adapter_path} "
        f"base={base_model_id} device={args.device}"
    )
    generations = _generate_completions(
        prompts=prompts,
        base_model_id=base_model_id,
        adapter_path=adapter_path,
        device=args.device,
        max_new_tokens=_DEFAULT_MAX_NEW_TOKENS,
        temperature=_DEFAULT_TEMPERATURE,
    )
    _write_generations(generations=generations, destination=generations_path)
    return generations


async def _run_stage_two(
    *,
    generations: list[GenerationRecord],
    repo_root: Path,
) -> list[RubricScoreSummary]:
    from app.services.eval import GEvalJudge, OpenAIJudge  # noqa: PLC0415

    rubrics = _load_rubrics_from_disk(repo_root=repo_root)
    judge = GEvalJudge(base_judge=OpenAIJudge())
    per_rubric_scores = await _score_all(
        generations=generations, rubrics=rubrics, judge=judge
    )
    return _summarize_scores(per_rubric_scores=per_rubric_scores)


def _parse_args(*, argv: list[str]) -> JudgeSanityArgs:
    parser = argparse.ArgumentParser(
        prog="judge_sanity.py",
        description=(
            "Post-training judge-sanity step: generates 50 completions with "
            "the just-saved adapter and scores them via the Tier-2 G-Eval judge."
        ),
    )
    parser.add_argument(
        "--summary",
        required=True,
        help="Path to the bench summary.json written by run_local.py.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the bench YAML config (same one passed to run_local.py).",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repo root; defaults to the parent of the script's dir.",
    )
    parser.add_argument(
        "--device",
        required=True,
        choices=list(_VALID_DEVICES),
        help="Execution device for inference.",
    )
    parser.add_argument(
        "--adapter-path",
        default=None,
        help=(
            "Explicit path to the saved adapter directory. Defaults to the "
            "latest checkpoint under <output-dir>/project/checkpoints/."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Bench output dir (where generations and summary.json live). "
            "Defaults to the parent of --summary."
        ),
    )
    parsed = parser.parse_args(argv)

    summary_path = Path(parsed.summary).resolve()
    config_arg = Path(parsed.config)
    repo_root = (
        Path(parsed.repo_root).resolve()
        if parsed.repo_root
        else Path(__file__).resolve().parent.parent.parent
    )
    config_path = (
        config_arg if config_arg.is_absolute() else (repo_root / config_arg).resolve()
    )
    output_dir = (
        Path(parsed.output_dir).resolve() if parsed.output_dir else summary_path.parent
    )
    adapter_path = Path(parsed.adapter_path).resolve() if parsed.adapter_path else None
    device = cast(DeviceLiteral, parsed.device)

    return JudgeSanityArgs(
        summary_path=summary_path,
        config_path=config_path,
        repo_root=repo_root,
        device=device,
        adapter_path=adapter_path,
        output_dir=output_dir,
    )


def run(*, argv: list[str]) -> int:
    try:
        args = _parse_args(argv=argv)
    except SystemExit as exit_exc:
        return int(exit_exc.code or 0)

    if not args.summary_path.exists():
        _eprint(f"summary.json not found: {args.summary_path}")
        return 2
    if not args.config_path.exists():
        _eprint(f"config not found: {args.config_path}")
        return 2

    _ensure_backend_on_path(repo_root=args.repo_root)

    raw_config_loaded = yaml.safe_load(args.config_path.read_text(encoding="utf-8"))
    if not isinstance(raw_config_loaded, dict):
        _eprint("config YAML must be a mapping at the top level")
        return 2
    raw_config: dict[str, object] = raw_config_loaded

    try:
        bench_sidecar = _extract_bench_sidecar(
            raw_config=raw_config, repo_root=args.repo_root
        )
    except RuntimeError as exc:
        _eprint(str(exc))
        return 2

    prompts_path = bench_sidecar.judge_sanity_prompts_path
    if not prompts_path.exists():
        _eprint(f"judge_sanity_prompts.jsonl not found: {prompts_path}")
        return 2

    try:
        _verify_prompts_hash(
            prompts_path=prompts_path,
            expected_hash=bench_sidecar.judge_sanity_prompts_hash,
        )
    except RuntimeError as exc:
        _eprint(str(exc))
        return 3

    prompts = _read_prompt_records(prompts_path=prompts_path)
    if len(prompts) != _EXPECTED_PROMPT_COUNT:
        _eprint(
            f"expected {_EXPECTED_PROMPT_COUNT} prompts, got {len(prompts)} "
            f"from {prompts_path}"
        )
        return 3

    eval_split_path = args.repo_root / _EVAL_SPLIT_RELATIVE_PATH
    try:
        _assert_disjoint_from_eval_split(
            prompts=prompts, eval_split_path=eval_split_path
        )
        _assert_disjoint_from_calibration(
            prompts_path=prompts_path, repo_root=args.repo_root
        )
    except RuntimeError as exc:
        _eprint(str(exc))
        return 4

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        generations = _run_stage_one(args=args, raw_config=raw_config, prompts=prompts)
    except Exception as exc:
        reason = f"judge harness failed during generation: {exc}"
        _eprint(reason)
        traceback.print_exc(file=sys.stderr)
        try:
            _mutate_summary(
                summary_path=args.summary_path,
                judge_pass_rate=None,
                judge_breakdown=None,
                failure_reason=reason,
            )
        except OSError as write_exc:
            _eprint(f"failed to update summary.json: {write_exc}")
        return 0

    try:
        summaries = asyncio.run(
            _run_stage_two(generations=generations, repo_root=args.repo_root)
        )
    except Exception as exc:
        reason = f"judge harness failed during scoring: {exc}"
        _eprint(reason)
        traceback.print_exc(file=sys.stderr)
        try:
            _mutate_summary(
                summary_path=args.summary_path,
                judge_pass_rate=None,
                judge_breakdown=None,
                failure_reason=reason,
            )
        except OSError as write_exc:
            _eprint(f"failed to update summary.json: {write_exc}")
        return 0

    breakdown = {summary.rubric_id: summary.pass_rate for summary in summaries}
    overall = sum(breakdown.values()) / len(breakdown) if breakdown else 0.0

    try:
        _mutate_summary(
            summary_path=args.summary_path,
            judge_pass_rate=overall,
            judge_breakdown=breakdown,
            failure_reason=None,
        )
    except OSError as exc:
        _eprint(f"failed to update summary.json: {exc}")
        return 5

    _eprint(
        f"judge sanity complete: judge_pass_rate={overall:.3f} breakdown={breakdown}"
    )
    return 0


def main() -> int:
    return run(argv=sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
