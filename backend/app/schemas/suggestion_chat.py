from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SuggestionChatRole = Literal["user", "assistant"]


class SuggestionChatMessageResponse(BaseModel):
    id: str
    suggestion_id: str
    role: SuggestionChatRole
    content: str
    created_at: str

    model_config = {"from_attributes": True}


class SuggestionChatListResponse(BaseModel):
    messages: list[SuggestionChatMessageResponse]


class SendSuggestionChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
