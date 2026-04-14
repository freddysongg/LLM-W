from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.schemas.rubric import Rubric

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUBRICS_DIR = _REPO_ROOT / "rubrics"
_EXPECTED_RUBRIC_STEMS = {"faithfulness", "instruction_following", "safety", "hallucination"}
_KNOWN_R_IDS = {"R1", "R3", "R4", "R5", "R6", "R11", "R12"}
_MIN_EXAMPLES = 5
_LATEST_ALIAS_MARKER = "-latest"


def _yaml_paths() -> list[Path]:
    return sorted(_RUBRICS_DIR.glob("*.yaml"))


def _load(path: Path) -> Rubric:
    return Rubric.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def test_rubrics_directory_contains_the_expected_four_files() -> None:
    discovered_stems = {path.stem for path in _yaml_paths()}
    assert discovered_stems == _EXPECTED_RUBRIC_STEMS


@pytest.mark.parametrize("yaml_path", _yaml_paths(), ids=lambda path: path.stem)
def test_all_four_yamls_load_via_pydantic(yaml_path: Path) -> None:
    rubric = _load(yaml_path)
    assert rubric.id == yaml_path.stem


@pytest.mark.parametrize("yaml_path", _yaml_paths(), ids=lambda path: path.stem)
def test_each_rubric_has_minimum_five_examples(yaml_path: Path) -> None:
    rubric = _load(yaml_path)
    assert len(rubric.few_shot_examples) >= _MIN_EXAMPLES


@pytest.mark.parametrize("yaml_path", _yaml_paths(), ids=lambda path: path.stem)
def test_each_rubric_mixes_pass_and_fail(yaml_path: Path) -> None:
    rubric = _load(yaml_path)
    verdicts = {example.verdict for example in rubric.few_shot_examples}
    assert "pass" in verdicts
    assert "fail" in verdicts


def test_hallucination_has_chainpoll_others_do_not() -> None:
    for yaml_path in _yaml_paths():
        rubric = _load(yaml_path)
        if rubric.id == "hallucination":
            assert rubric.chainpoll is not None
            assert rubric.chainpoll.n == 3
            assert rubric.chainpoll.model == "gpt-4o-mini-2024-07-18"
            assert rubric.chainpoll.temperature == pytest.approx(0.3)
        else:
            assert rubric.chainpoll is None


@pytest.mark.parametrize("yaml_path", _yaml_paths(), ids=lambda path: path.stem)
def test_no_rubric_uses_latest_aliases(yaml_path: Path) -> None:
    raw_text = yaml_path.read_text(encoding="utf-8").lower()
    assert _LATEST_ALIAS_MARKER not in raw_text


@pytest.mark.parametrize("yaml_path", _yaml_paths(), ids=lambda path: path.stem)
def test_research_basis_references_real_r_ids(yaml_path: Path) -> None:
    rubric = _load(yaml_path)
    unknown_ids = set(rubric.research_basis) - _KNOWN_R_IDS
    assert unknown_ids == set(), f"unknown R-IDs in {yaml_path.stem}: {unknown_ids}"


@pytest.mark.parametrize("yaml_path", _yaml_paths(), ids=lambda path: path.stem)
def test_judge_model_pin_is_the_plan_default(yaml_path: Path) -> None:
    rubric = _load(yaml_path)
    assert rubric.judge_model_pin == "gpt-4o-mini-2024-07-18"


@pytest.mark.parametrize("yaml_path", _yaml_paths(), ids=lambda path: path.stem)
def test_version_is_string_one(yaml_path: Path) -> None:
    rubric = _load(yaml_path)
    assert rubric.version == "1"
