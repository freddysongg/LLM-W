"""Provider-neutral chat-completion helper.

The recommendation engine in ``ai_recommender`` sends a single prompt and gets
back a JSON suggestion. Suggestion follow-up chat needs a multi-turn message
list with a system prompt that frames the conversation, so this module ports
the same Anthropic / OpenAI-compatible plumbing into a small public function
that takes ``messages`` directly. Sync SDK calls are dispatched to the default
executor so the event loop stays free.
"""

from __future__ import annotations

import asyncio
from typing import Literal

ChatRole = Literal["user", "assistant"]


class LLMChatError(RuntimeError):
    """Raised when the upstream provider call fails for a recoverable reason
    (auth, network, malformed response). Surfaced to the route as a typed
    error so the operator gets a useful message rather than a 500.
    """


async def chat_completion(
    *,
    provider: str,
    api_key: str | None,
    model_id: str,
    base_url: str | None,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int = 1024,
) -> str:
    """Issue a chat completion against the configured provider.

    ``messages`` is a list of ``{"role": "user"|"assistant", "content": str}``
    entries in chronological order. The system prompt is passed via the
    provider-native channel: Anthropic accepts ``system=...`` alongside the
    messages list; OpenAI-compatible APIs expect a leading
    ``{"role": "system"}`` entry.
    """
    if not api_key:
        raise LLMChatError(
            "AI provider is not configured — set an API key in Settings before "
            "starting a follow-up conversation."
        )

    if provider == "anthropic":
        return await _call_anthropic(
            api_key=api_key,
            model_id=model_id,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
    if provider in ("openai", "openai_compatible"):
        return await _call_openai(
            api_key=api_key,
            base_url=base_url,
            model_id=model_id,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
    raise LLMChatError(f"Unsupported AI provider for chat: {provider}")


async def _call_anthropic(
    *,
    api_key: str,
    model_id: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    import anthropic

    def _sync_call() -> str:
        client = anthropic.Anthropic(api_key=api_key)
        try:
            response = client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                system=system,
                messages=[
                    {"role": message["role"], "content": message["content"]}
                    for message in messages
                ],
            )
        except anthropic.AuthenticationError as exc:
            raise LLMChatError(f"Anthropic authentication failed: {exc}") from exc
        except anthropic.APIError as exc:
            raise LLMChatError(f"Anthropic API error: {exc}") from exc

        text_blocks: list[str] = []
        for block in response.content:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                text_blocks.append(block_text)
        if not text_blocks:
            raise LLMChatError("Anthropic response contained no text blocks.")
        return "\n".join(text_blocks)

    return await asyncio.get_running_loop().run_in_executor(None, _sync_call)


async def _call_openai(
    *,
    api_key: str,
    base_url: str | None,
    model_id: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    import openai

    def _sync_call() -> str:
        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        try:
            response = client.chat.completions.create(
                model=model_id,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    *(
                        {"role": message["role"], "content": message["content"]}
                        for message in messages
                    ),
                ],
            )
        except openai.AuthenticationError as exc:
            raise LLMChatError(f"OpenAI authentication failed: {exc}") from exc
        except openai.APIError as exc:
            raise LLMChatError(f"OpenAI API error: {exc}") from exc

        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message.content is None:
            raise LLMChatError("OpenAI response contained no message content.")
        return choice.message.content

    return await asyncio.get_running_loop().run_in_executor(None, _sync_call)
