from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.exceptions import DatasetNormalizationError
from app.schemas.dataset_sanitizer import (
    RedactionManifest,
    SanitizeDatasetResponse,
    SplitAssignment,
    SplitRatios,
)
from app.services import dataset_sanitizer
from app.services.dataset_sanitizer import (
    PERSISTED_DATASET_FILENAME,
    PERSISTED_MANIFEST_FILENAME,
    compute_deterministic_splits,
    default_sanitization_rules,
    normalize_to_openai_messages,
    persist_sanitized_artifact,
    sanitize_rows,
)


def _rules():
    return default_sanitization_rules()


def test_email_redaction_hit() -> None:
    rows = [{"text": "Contact: alice@example.com please"}]
    result = sanitize_rows(rows=rows, rules=_rules())
    assert result.sanitized_rows[0]["text"] == "Contact: [REDACTED_EMAIL] please"
    assert result.manifest.per_pattern["email"] == 1
    assert result.manifest.total_redactions == 1


def test_email_redaction_miss() -> None:
    rows = [{"text": "no addresses here at all"}]
    result = sanitize_rows(rows=rows, rules=_rules())
    assert result.sanitized_rows[0]["text"] == "no addresses here at all"
    assert result.manifest.per_pattern["email"] == 0


def test_us_phone_redaction_hit_and_miss() -> None:
    rows = [
        {"text": "Call 415-555-1234 today"},
        {"text": "no phone numbers here"},
    ]
    result = sanitize_rows(rows=rows, rules=_rules())
    assert result.sanitized_rows[0]["text"] == "Call [REDACTED_PHONE] today"
    assert result.sanitized_rows[1]["text"] == "no phone numbers here"
    assert result.manifest.per_pattern["us_phone"] == 1


def test_credit_card_redaction_hit_and_miss() -> None:
    rows = [
        {"text": "card 4111-1111-1111-1111 stored"},
        {"text": "card not present"},
    ]
    result = sanitize_rows(rows=rows, rules=_rules())
    assert "[REDACTED_CARD]" in result.sanitized_rows[0]["text"]
    assert result.manifest.per_pattern["credit_card"] >= 1
    assert result.sanitized_rows[1]["text"] == "card not present"


def test_ssn_redaction_hit_and_miss() -> None:
    rows = [
        {"text": "SSN 123-45-6789 on file"},
        {"text": "no ssn here"},
    ]
    result = sanitize_rows(rows=rows, rules=_rules())
    assert result.sanitized_rows[0]["text"] == "SSN [REDACTED_SSN] on file"
    assert result.sanitized_rows[1]["text"] == "no ssn here"
    assert result.manifest.per_pattern["ssn"] == 1


def test_ipv4_redaction_hit_and_miss() -> None:
    rows = [
        {"text": "connect to 10.0.0.1 quickly"},
        {"text": "no ip here"},
    ]
    result = sanitize_rows(rows=rows, rules=_rules())
    assert result.sanitized_rows[0]["text"] == "connect to [REDACTED_IP] quickly"
    assert result.sanitized_rows[1]["text"] == "no ip here"
    assert result.manifest.per_pattern["ipv4"] == 1


def test_redaction_walks_nested_structures() -> None:
    rows = [
        {
            "messages": [
                {"role": "user", "content": "Reach me at alice@example.com please"},
                {"role": "assistant", "content": "Sure."},
            ],
            "meta": {"contact": {"email": "bob@example.com"}},
        }
    ]
    result = sanitize_rows(rows=rows, rules=_rules())
    sanitized = result.sanitized_rows[0]
    first_user_content = sanitized["messages"][0]["content"]
    nested_contact = sanitized["meta"]["contact"]["email"]
    assert "[REDACTED_EMAIL]" in first_user_content
    assert nested_contact == "[REDACTED_EMAIL]"
    assert result.manifest.per_pattern["email"] == 2
    assert result.manifest.total_redactions == 2


def test_manifest_counts_match_total_redactions() -> None:
    rows = [
        {"text": "Email a@b.com and SSN 111-22-3333"},
        {"text": "IP 192.168.0.1"},
    ]
    result = sanitize_rows(rows=rows, rules=_rules())
    assert result.manifest.total_redactions == sum(result.manifest.per_pattern.values())
    assert result.manifest.per_pattern["email"] == 1
    assert result.manifest.per_pattern["ssn"] == 1
    assert result.manifest.per_pattern["ipv4"] == 1


def test_split_determinism_same_input_yields_same_assignment() -> None:
    rows: list[dict[str, object]] = [{"index": i, "content": f"row-{i}"} for i in range(50)]
    ratios = SplitRatios(train=0.8, val=0.1, test=0.1)
    first = compute_deterministic_splits(rows=rows, ratios=ratios)
    second = compute_deterministic_splits(rows=rows, ratios=ratios)
    assert first.assignments == second.assignments
    assert first.counts == second.counts


def test_split_stability_adding_rows_preserves_prior_assignments() -> None:
    base_rows: list[dict[str, object]] = [{"i": i, "content": f"r-{i}"} for i in range(30)]
    extra_rows: list[dict[str, object]] = [{"i": i, "content": f"r-{i}"} for i in range(30, 40)]
    ratios = SplitRatios(train=0.7, val=0.2, test=0.1)

    first = compute_deterministic_splits(rows=base_rows, ratios=ratios)
    combined = compute_deterministic_splits(rows=base_rows + extra_rows, ratios=ratios)

    for index in range(len(base_rows)):
        assert first.assignments[index] == combined.assignments[index]


def test_openai_passthrough_preserves_messages_array() -> None:
    row = {
        "messages": [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
    }
    result = normalize_to_openai_messages(row=row, source_format="openai")
    assert result["messages"] == row["messages"]


def test_alpaca_to_openai_conversion() -> None:
    row = {
        "instruction": "Translate to French",
        "input": "Hello",
        "output": "Bonjour",
    }
    result = normalize_to_openai_messages(row=row, source_format="alpaca")
    messages = result["messages"]
    assert messages[0] == {"role": "user", "content": "Translate to French Hello"}
    assert messages[1] == {"role": "assistant", "content": "Bonjour"}


def test_alpaca_to_openai_skips_empty_input() -> None:
    row = {
        "instruction": "Say hello",
        "input": "",
        "output": "Hello",
    }
    result = normalize_to_openai_messages(row=row, source_format="alpaca")
    messages = result["messages"]
    assert messages[0] == {"role": "user", "content": "Say hello"}
    assert messages[1] == {"role": "assistant", "content": "Hello"}


def test_sharegpt_to_openai_role_mapping() -> None:
    row = {
        "conversations": [
            {"from": "system", "value": "Be polite"},
            {"from": "human", "value": "What is 2+2?"},
            {"from": "gpt", "value": "4"},
        ]
    }
    result = normalize_to_openai_messages(row=row, source_format="sharegpt")
    messages = result["messages"]
    assert messages[0] == {"role": "system", "content": "Be polite"}
    assert messages[1] == {"role": "user", "content": "What is 2+2?"}
    assert messages[2] == {"role": "assistant", "content": "4"}


def test_default_format_with_no_recognizable_fields_raises() -> None:
    row: dict[str, object] = {"unknown_field": "value"}
    with pytest.raises(DatasetNormalizationError):
        normalize_to_openai_messages(row=row, source_format="default")


def test_default_format_with_prompt_response_passes() -> None:
    row = {"prompt": "Hi", "response": "Hello"}
    result = normalize_to_openai_messages(row=row, source_format="default")
    messages = result["messages"]
    assert messages[0] == {"role": "user", "content": "Hi"}
    assert messages[1] == {"role": "assistant", "content": "Hello"}


def test_sanitize_rows_returns_valid_content_hash() -> None:
    rows = [{"text": "hello"}]
    result = sanitize_rows(rows=rows, rules=_rules())
    assert len(result.content_hash) == 64
    assert all(c in "0123456789abcdef" for c in result.content_hash)


def test_default_rules_include_all_five_patterns() -> None:
    rules = dataset_sanitizer.default_sanitization_rules()
    names = {pattern.name for pattern in rules.patterns}
    assert names == {"email", "us_phone", "credit_card", "ssn", "ipv4"}


def _make_response_for_persist_test() -> SanitizeDatasetResponse:
    return SanitizeDatasetResponse(
        total_rows=2,
        sanitized_rows=[
            {"messages": [{"role": "user", "content": "ok"}]},
            {"messages": [{"role": "user", "content": "fine"}]},
        ],
        manifest=RedactionManifest(per_pattern={"email": 1}, total_redactions=1),
        splits=SplitAssignment(
            assignments={0: "train", 1: "val"},
            counts={"train": 1, "val": 1, "test": 0},
        ),
        content_hash="a" * 64,
        source_format="default",
        normalized=True,
    )


def test_persist_sanitized_artifact_writes_jsonl_and_manifest(tmp_path: Path) -> None:
    response = _make_response_for_persist_test()
    artifact = persist_sanitized_artifact(project_dir=tmp_path, response=response)

    assert artifact == tmp_path / "datasets" / PERSISTED_DATASET_FILENAME
    assert artifact.is_file()
    lines = artifact.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["messages"][0]["content"] == "ok"

    manifest_path = tmp_path / "datasets" / PERSISTED_MANIFEST_FILENAME
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["content_hash"] == "a" * 64
    assert manifest["total_rows"] == 2
    assert manifest["redaction_counts"] == {"email": 1}


def test_persist_sanitized_artifact_overwrites_atomically(tmp_path: Path) -> None:
    """A second persist must replace the previous file without leaving .tmp leftovers."""
    response_one = _make_response_for_persist_test()
    persist_sanitized_artifact(project_dir=tmp_path, response=response_one)

    response_two = SanitizeDatasetResponse(
        total_rows=1,
        sanitized_rows=[{"messages": [{"role": "user", "content": "second"}]}],
        manifest=RedactionManifest(per_pattern={}, total_redactions=0),
        splits=SplitAssignment(
            assignments={0: "train"}, counts={"train": 1, "val": 0, "test": 0}
        ),
        content_hash="b" * 64,
        source_format="default",
        normalized=True,
    )
    persist_sanitized_artifact(project_dir=tmp_path, response=response_two)

    lines = (tmp_path / "datasets" / PERSISTED_DATASET_FILENAME).read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["messages"][0]["content"] == "second"
    # No .tmp files left behind from the atomic write.
    assert not list((tmp_path / "datasets").glob("*.tmp"))


def test_get_sanitize_status_reports_missing_when_no_artifact(tmp_path: Path) -> None:
    status = dataset_sanitizer.get_sanitize_status(project_dir=tmp_path)
    assert status.exists is False
    assert status.content_hash is None
    assert status.sanitized_at is None


def test_get_sanitize_status_reports_existing_artifact_with_hash_and_timestamp(
    tmp_path: Path,
) -> None:
    response = _make_response_for_persist_test()
    persist_sanitized_artifact(project_dir=tmp_path, response=response)

    status = dataset_sanitizer.get_sanitize_status(project_dir=tmp_path)
    assert status.exists is True
    assert status.content_hash == "a" * 64
    assert status.sanitized_at is not None
    assert status.sanitized_at.endswith("+00:00")


def test_run_pipeline_content_hash_reflects_persisted_rows_when_normalize_true() -> None:
    """The artifact's content_hash must change when normalization rewrites the rows.

    The Modal upload-skip check at `_remote_sanitized_hash_matches` keys on this
    hash. If the hash were computed over the pre-normalized rows, a remote
    artifact written from a prior `normalize=true` run would be silently reused
    after the local rows changed shape — leaving the trainer reading the wrong
    schema. Pin: normalize=true must hash the normalized rows.
    """
    from app.schemas.dataset_sanitizer import SanitizeDatasetRequest, SplitRatios
    from app.services.dataset_sanitizer import _compute_content_hash, run_sanitization_pipeline

    rows = [{"prompt": "hi", "response": "hello"}]
    request = SanitizeDatasetRequest(
        source_format="default",
        normalize=True,
        split_ratios=SplitRatios(train=1.0, val=0.0, test=0.0),
    )

    response = run_sanitization_pipeline(rows=rows, request=request)
    expected_hash = _compute_content_hash(response.sanitized_rows)
    assert response.content_hash == expected_hash
    # And to make sure the pre-normalization hash would differ, sanity-check
    # the raw shape against the normalized one.
    raw_hash = _compute_content_hash(rows)
    assert response.content_hash != raw_hash


def test_run_pipeline_content_hash_unchanged_when_normalize_false() -> None:
    """normalize=false → hash matches sanitize_rows' hash (no second pass needed)."""
    from app.schemas.dataset_sanitizer import SanitizeDatasetRequest, SplitRatios
    from app.services.dataset_sanitizer import run_sanitization_pipeline

    rows = [{"text": "hi"}]
    request = SanitizeDatasetRequest(
        source_format="default",
        normalize=False,
        split_ratios=SplitRatios(train=1.0, val=0.0, test=0.0),
    )

    response = run_sanitization_pipeline(rows=rows, request=request)
    sanitized = sanitize_rows(rows=rows, rules=default_sanitization_rules())
    assert response.content_hash == sanitized.content_hash
