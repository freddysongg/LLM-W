from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import ProjectNotFoundError, SuggestionNotFoundError
from app.schemas.suggestion_chat import (
    SendSuggestionChatMessageRequest,
    SuggestionChatListResponse,
    SuggestionChatMessageResponse,
)
from app.services import suggestion_chat_service
from app.services.llm_chat import LLMChatError

router = APIRouter(prefix="/api/v1/projects", tags=["suggestion-chat"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get(
    "/{project_id}/suggestions/{suggestion_id}/chat",
    response_model=SuggestionChatListResponse,
)
async def list_suggestion_chat(
    project_id: str,
    suggestion_id: str,
    session: DbSession,
) -> SuggestionChatListResponse:
    try:
        return await suggestion_chat_service.list_messages(
            session=session, project_id=project_id, suggestion_id=suggestion_id
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except SuggestionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SUGGESTION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc


@router.post(
    "/{project_id}/suggestions/{suggestion_id}/chat",
    response_model=SuggestionChatMessageResponse,
    status_code=201,
)
async def send_suggestion_chat_message(
    project_id: str,
    suggestion_id: str,
    payload: SendSuggestionChatMessageRequest,
    session: DbSession,
) -> SuggestionChatMessageResponse:
    try:
        return await suggestion_chat_service.send_message(
            session=session,
            project_id=project_id,
            suggestion_id=suggestion_id,
            message=payload.message,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "PROJECT_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except SuggestionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SUGGESTION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    except LLMChatError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "LLM_CHAT_ERROR", "message": str(exc), "details": {}},
        ) from exc
