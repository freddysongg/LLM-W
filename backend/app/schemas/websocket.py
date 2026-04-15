from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

WebSocketChannel = Literal["run_state", "metrics", "logs", "system", "eval"]


class _WsInboundFrameBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WsSubscribePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channels: list[WebSocketChannel]


class WsUnsubscribePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channels: list[WebSocketChannel]


class WsSubscribeFrame(_WsInboundFrameBase):
    type: Literal["subscribe"]
    payload: WsSubscribePayload


class WsUnsubscribeFrame(_WsInboundFrameBase):
    type: Literal["unsubscribe"]
    payload: WsUnsubscribePayload


class WsPingFrame(_WsInboundFrameBase):
    type: Literal["ping"]


WsInboundEnvelope = Annotated[
    WsSubscribeFrame | WsUnsubscribeFrame | WsPingFrame,
    Field(discriminator="type"),
]


ws_inbound_envelope_adapter: TypeAdapter[WsInboundEnvelope] = TypeAdapter(WsInboundEnvelope)
