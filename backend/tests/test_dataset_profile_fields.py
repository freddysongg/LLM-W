from __future__ import annotations

from app.schemas.dataset import SplitCounts
from app.services.dataset_service import (
    _compute_eval_leakage,
    _derive_format_tag,
)


def test_derive_format_tag_maps_openai_to_chatml() -> None:
    assert _derive_format_tag("openai") == "chatml"


def test_derive_format_tag_maps_sharegpt_to_chatml() -> None:
    assert _derive_format_tag("sharegpt") == "chatml"


def test_derive_format_tag_maps_alpaca_to_alpaca() -> None:
    assert _derive_format_tag("alpaca") == "alpaca"


def test_derive_format_tag_maps_default_to_paired() -> None:
    assert _derive_format_tag("default") == "paired"


def test_derive_format_tag_returns_none_for_custom() -> None:
    assert _derive_format_tag("custom") is None


def test_compute_eval_leakage_returns_zero_when_validation_is_none() -> None:
    rows = [{"prompt": "a"}, {"prompt": "b"}]
    counts = SplitCounts(train=2, validation=None, test=None)

    assert _compute_eval_leakage(rows=rows, split_counts=counts) == 0


def test_compute_eval_leakage_returns_zero_when_validation_is_zero() -> None:
    rows = [{"prompt": "a"}, {"prompt": "b"}]
    counts = SplitCounts(train=2, validation=0, test=None)

    assert _compute_eval_leakage(rows=rows, split_counts=counts) == 0


def test_compute_eval_leakage_counts_duplicates_between_train_and_validation() -> None:
    rows = [
        {"prompt": "a", "response": "1"},
        {"prompt": "b", "response": "2"},
        {"prompt": "c", "response": "3"},
        {"prompt": "a", "response": "1"},
        {"prompt": "b", "response": "2"},
        {"prompt": "d", "response": "4"},
    ]
    counts = SplitCounts(train=3, validation=3, test=None)

    assert _compute_eval_leakage(rows=rows, split_counts=counts) == 2


def test_compute_eval_leakage_returns_zero_for_disjoint_splits() -> None:
    rows = [
        {"prompt": "a"},
        {"prompt": "b"},
        {"prompt": "c"},
        {"prompt": "d"},
    ]
    counts = SplitCounts(train=2, validation=2, test=None)

    assert _compute_eval_leakage(rows=rows, split_counts=counts) == 0


def test_compute_eval_leakage_ignores_test_slice() -> None:
    """A duplicate that sits in the train and test slices but not in validation
    must not be counted — leakage is specifically train↔validation overlap."""
    rows = [
        {"prompt": "a"},
        {"prompt": "b"},
        {"prompt": "a"},
    ]
    counts = SplitCounts(train=1, validation=1, test=1)

    assert _compute_eval_leakage(rows=rows, split_counts=counts) == 0
