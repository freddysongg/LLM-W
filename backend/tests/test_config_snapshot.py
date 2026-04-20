from __future__ import annotations

import pytest

from app.core.exceptions import ConfigValidationError
from app.services.config_service import (
    compute_config_diff,
    serialize_config_yaml_snapshot,
)

_BASE_YAML = """\
project:
  name: p
  mode: single_user_local
training:
  learning_rate: 0.0002
  batch_size: 4
"""

_CHANGED_YAML = """\
project:
  name: p
  mode: single_user_local
training:
  learning_rate: 0.0003
  batch_size: 4
  epochs: 3
"""


def test_compute_config_diff_reports_changed_and_added() -> None:
    diff = compute_config_diff(old_yaml=_BASE_YAML, new_yaml=_CHANGED_YAML)
    assert diff["changed"]["training.learning_rate"] == {"old": 0.0002, "new": 0.0003}
    assert diff["added"]["training.epochs"] == 3
    assert diff["removed"] == {}


def test_compute_config_diff_handles_identical_yaml() -> None:
    diff = compute_config_diff(old_yaml=_BASE_YAML, new_yaml=_BASE_YAML)
    assert diff == {"changed": {}, "added": {}, "removed": {}}


def test_compute_config_diff_reports_removed_keys() -> None:
    diff = compute_config_diff(old_yaml=_CHANGED_YAML, new_yaml=_BASE_YAML)
    assert diff["removed"]["training.epochs"] == 3
    assert diff["changed"]["training.learning_rate"] == {"old": 0.0003, "new": 0.0002}


def test_compute_config_diff_accepts_empty_input() -> None:
    diff = compute_config_diff(old_yaml="", new_yaml=_BASE_YAML)
    assert "project.name" in diff["added"]
    assert diff["changed"] == {}
    assert diff["removed"] == {}


def test_serialize_config_yaml_snapshot_round_trips() -> None:
    out = serialize_config_yaml_snapshot(raw_yaml=_BASE_YAML)
    assert "project:" in out
    assert "learning_rate: 0.0002" in out


def test_serialize_config_yaml_snapshot_rejects_non_mapping() -> None:
    with pytest.raises(ConfigValidationError):
        serialize_config_yaml_snapshot(raw_yaml="- just\n- a\n- list\n")


def test_serialize_config_yaml_snapshot_wraps_yaml_parse_errors() -> None:
    with pytest.raises(ConfigValidationError):
        serialize_config_yaml_snapshot(raw_yaml=": :: : bad")
