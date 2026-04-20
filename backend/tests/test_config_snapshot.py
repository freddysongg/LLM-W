from __future__ import annotations

from app.services.config_service import (
    compute_config_diff,
    serialize_effective_config_yaml,
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


def test_serialize_effective_config_yaml_round_trips() -> None:
    out = serialize_effective_config_yaml(raw_yaml=_BASE_YAML)
    assert "project:" in out
    assert "learning_rate: 0.0002" in out
