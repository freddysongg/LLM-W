from __future__ import annotations

from pydantic import BaseModel


class CurrentUserResponse(BaseModel):
    id: str
    name: str
    email: str
