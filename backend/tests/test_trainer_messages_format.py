"""Trainer tokenization + profiling coverage for OpenAI messages-shape datasets.

The sanitizer's ``normalize=true`` path writes rows as
``{"messages": [{"role": "user", ...}, {"role": "assistant", ...}]}``. The
trainer must detect that shape and render each row through
``tokenizer.apply_chat_template`` instead of looking up flat ``input_field`` /
``target_field`` columns. A chat-tuned tokenizer ships with a ``chat_template``
attribute; base models that lack one must surface a typed error pointing the
operator at the two remediation paths.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("transformers")

from app.services import trainer  # noqa: E402


class _FakeDataset:
    """In-memory stand-in for the HuggingFace Dataset surface area the trainer
    touches during tokenization and profiling tests.
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    @property
    def column_names(self) -> list[str]:
        if not self._rows:
            return []
        return list(self._rows[0].keys())

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self._rows[index]

    def map(self, fn: Any, batched: bool = False) -> _FakeDataset:
        if not self._rows:
            return _FakeDataset([])
        batch: dict[str, list[Any]] = {}
        for column in self._rows[0]:
            batch[column] = [row[column] for row in self._rows]
        out = fn(batch)
        out_rows: list[dict[str, Any]] = []
        length = len(next(iter(out.values())))
        for i in range(length):
            out_rows.append({key: out[key][i] for key in out})
        return _FakeDataset(out_rows)


def test_is_messages_only_dataset_true_when_messages_is_the_sole_column() -> None:
    assert trainer._is_messages_only_dataset(["messages"]) is True


def test_is_messages_only_dataset_false_when_flat_field_is_present() -> None:
    assert trainer._is_messages_only_dataset(["messages", "prompt"]) is False
    assert trainer._is_messages_only_dataset(["messages", "response"]) is False


def test_is_messages_only_dataset_false_when_messages_is_missing() -> None:
    assert trainer._is_messages_only_dataset(["prompt", "response"]) is False
    assert trainer._is_messages_only_dataset([]) is False


def test_stage_tokenization_routes_messages_shape_through_chat_template() -> None:
    rows = [
        {
            "messages": [
                {"role": "user", "content": "ping"},
                {"role": "assistant", "content": "pong"},
            ]
        }
    ]
    train_dataset = _FakeDataset(rows)
    rendered_calls: list[list[dict[str, str]]] = []

    def fake_apply_chat_template(messages: list[dict[str, str]], tokenize: bool) -> str:
        assert tokenize is False
        rendered_calls.append(messages)
        return "<rendered>"

    def fake_tokenize(
        texts: list[str], truncation: bool, max_length: int, padding: bool
    ) -> dict[str, list[Any]]:
        return {"input_ids": [[1, 2, 3] for _ in texts]}

    tokenizer = MagicMock()
    tokenizer.chat_template = "{{ messages[0].content }}"
    tokenizer.apply_chat_template = fake_apply_chat_template
    tokenizer.side_effect = fake_tokenize

    train_out, eval_out = trainer._stage_tokenization_preprocessing(
        train_dataset=train_dataset,
        eval_dataset=None,
        tokenizer=tokenizer,
        raw_config={"preprocessing": {"max_seq_length": 64}},
    )
    assert eval_out is None
    assert len(train_out) == 1
    assert rendered_calls == [rows[0]["messages"]]


def test_stage_tokenization_raises_typed_error_when_chat_template_missing() -> None:
    rows = [{"messages": [{"role": "user", "content": "ping"}]}]
    train_dataset = _FakeDataset(rows)

    tokenizer = MagicMock()
    tokenizer.chat_template = None

    with pytest.raises(trainer.ChatTemplateMissingError, match="chat_template"):
        trainer._stage_tokenization_preprocessing(
            train_dataset=train_dataset,
            eval_dataset=None,
            tokenizer=tokenizer,
            raw_config={"preprocessing": {"max_seq_length": 64}},
        )


def test_stage_dataset_profiling_uses_apply_chat_template_for_messages_shape() -> None:
    rows = [
        {
            "messages": [
                {"role": "user", "content": "hello world"},
                {"role": "assistant", "content": "hi back"},
            ]
        }
    ]
    train_dataset = _FakeDataset(rows)
    seen_messages: list[list[dict[str, str]]] = []

    def fake_apply_chat_template(messages: list[dict[str, str]], tokenize: bool) -> str:
        seen_messages.append(messages)
        return "user: hello world\nassistant: hi back"

    tokenizer = MagicMock()
    tokenizer.chat_template = "anything"
    tokenizer.apply_chat_template = fake_apply_chat_template

    trainer._stage_dataset_profiling(
        train_dataset=train_dataset,
        tokenizer=tokenizer,
        raw_config={},
    )
    assert seen_messages == [rows[0]["messages"]]


def test_stage_dataset_profiling_falls_back_to_input_field_for_flat_rows() -> None:
    rows = [{"prompt": "tell me a story", "response": "once upon a time"}]
    train_dataset = _FakeDataset(rows)

    tokenizer = MagicMock()
    tokenizer.apply_chat_template = MagicMock(side_effect=AssertionError("should not be called"))

    trainer._stage_dataset_profiling(
        train_dataset=train_dataset,
        tokenizer=tokenizer,
        raw_config={"dataset": {"input_field": "prompt"}},
    )
    tokenizer.apply_chat_template.assert_not_called()
