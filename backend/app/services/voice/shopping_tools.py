"""Mock shopping tools surfaced to the Pipecat LLM service.

The tools return deterministic stub data so the rubric in
`rubrics/shopping_assistant.yaml` can grade tool selection, argument fidelity,
and recovery-from-error behavior without exercising a real catalog. Each
handler records its invocation to the bound `TranscriptWriter` so the tool
trace is captured at the source rather than via Pipecat frame inspection.

The `pipecat.adapters.schemas.*` imports live inside `build_shopping_tools_schema`
and `register_shopping_handlers` so this module is importable without the
optional `voice` extra installed.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from app.services.voice.transcript_writer import TranscriptWriter

if TYPE_CHECKING:
    from pipecat.adapters.schemas.tools_schema import ToolsSchema  # noqa: F401
    from pipecat.services.openai.llm import OpenAILLMService  # noqa: F401


@dataclass(frozen=True)
class ProductRecord:
    """One catalog row with the minimum fields the demo tools surface."""

    sku: str
    name: str
    price_usd: float
    category: str
    description: str


_CATALOG: dict[str, ProductRecord] = {
    "DEMO-001": ProductRecord(
        sku="DEMO-001",
        name="Nimbus Lite Running Shoe",
        price_usd=89.0,
        category="footwear",
        description="A lightweight cushioned road-running shoe.",
    ),
    "DEMO-002": ProductRecord(
        sku="DEMO-002",
        name="Trailstride Trail Runner",
        price_usd=119.0,
        category="footwear",
        description="A rugged trail-running shoe with extra grip.",
    ),
    "DEMO-003": ProductRecord(
        sku="DEMO-003",
        name="ZenFlex Yoga Mat",
        price_usd=45.0,
        category="yoga",
        description="A 6mm cushioned non-slip yoga mat.",
    ),
    "DEMO-004": ProductRecord(
        sku="DEMO-004",
        name="ZenFlex Yoga Block Set",
        price_usd=22.0,
        category="yoga",
        description="A pair of high-density foam yoga blocks.",
    ),
    "DEMO-005": ProductRecord(
        sku="DEMO-005",
        name="Hydrate Pro Water Bottle",
        price_usd=18.0,
        category="hydration",
        description="A 24oz insulated stainless steel water bottle.",
    ),
}


@dataclass
class CartState:
    """In-memory cart for a single session, keyed by SKU."""

    items: dict[str, int] = field(default_factory=dict)

    def total_usd(self) -> float:
        return round(
            sum(
                _CATALOG[sku].price_usd * quantity
                for sku, quantity in self.items.items()
                if sku in _CATALOG
            ),
            2,
        )


class _FunctionCallParams(Protocol):
    """Subset of pipecat.services.llm_service.FunctionCallParams we depend on."""

    arguments: dict[str, object]
    tool_call_id: str

    async def result_callback(self, result: dict[str, object]) -> None: ...


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _filter_catalog_by_query(query: str) -> list[ProductRecord]:
    needle = query.strip().lower()
    if not needle:
        return list(_CATALOG.values())[:3]
    matches = [
        record
        for record in _CATALOG.values()
        if needle in record.name.lower()
        or needle in record.description.lower()
        or needle in record.category.lower()
    ]
    if matches:
        return matches[:3]
    return list(_CATALOG.values())[:3]


def search_products(
    *,
    query: str,
    max_price_usd: float | None,
    cart: CartState,
) -> dict[str, object]:
    """Return up to 3 stub products that match `query`.

    `cart` is unused for searches but kept on the signature so a future cart-
    aware ranking heuristic can land without changing callers. Including it
    also keeps every tool's signature shape consistent.
    """
    del cart
    candidates = _filter_catalog_by_query(query)
    if max_price_usd is not None:
        candidates = [
            candidate for candidate in candidates if candidate.price_usd <= max_price_usd
        ]
    results: list[dict[str, object]] = [
        {
            "sku": candidate.sku,
            "name": candidate.name,
            "price_usd": candidate.price_usd,
        }
        for candidate in candidates
    ]
    return {"results": results}


def get_product_detail(*, sku: str, cart: CartState) -> dict[str, object]:
    """Return the full product record for `sku` or an error marker when unknown."""
    del cart
    record = _CATALOG.get(sku)
    if record is None:
        return {"error": "sku_not_found"}
    return {
        "sku": record.sku,
        "name": record.name,
        "price_usd": record.price_usd,
        "category": record.category,
        "description": record.description,
    }


def add_to_cart(*, sku: str, quantity: int, cart: CartState) -> dict[str, object]:
    """Append `quantity` units of `sku` to `cart`. Surface a helpful error otherwise."""
    if sku not in _CATALOG:
        return {
            "status": "error",
            "message": f"unknown sku: {sku}",
        }
    if quantity <= 0:
        return {
            "status": "error",
            "message": "quantity must be a positive integer",
        }
    cart.items[sku] = cart.items.get(sku, 0) + quantity
    return {
        "status": "ok",
        "cart_total_usd": cart.total_usd(),
    }


def handoff_checkout(*, shipping_address_id: str, cart: CartState) -> dict[str, object]:
    """Return a pending-confirmation summary; never a completed purchase."""
    return {
        "status": "pending_confirmation",
        "summary": {
            "shipping_address_id": shipping_address_id,
            "items": [
                {"sku": sku, "quantity": quantity} for sku, quantity in cart.items.items()
            ],
            "cart_total_usd": cart.total_usd(),
        },
    }


async def _record_and_invoke(
    *,
    params: _FunctionCallParams,
    writer: TranscriptWriter,
    name: str,
    result: dict[str, object],
    started_at_iso: str,
) -> None:
    ended_at_iso = _now_iso()
    is_error = "error" in result or result.get("status") == "error"
    writer.record_tool_call(
        tool_call_id=params.tool_call_id,
        name=name,
        arguments=dict(params.arguments),
        result=result,
        started_at_iso=started_at_iso,
        ended_at_iso=ended_at_iso,
        is_error=is_error,
    )
    await params.result_callback(result)


async def handle_search_products(
    params: _FunctionCallParams,
    *,
    writer: TranscriptWriter,
    cart: CartState,
) -> None:
    started = _now_iso()
    arguments = params.arguments
    query = str(arguments.get("query", ""))
    raw_price = arguments.get("max_price_usd")
    max_price_usd = float(raw_price) if isinstance(raw_price, (int, float)) else None
    result = search_products(query=query, max_price_usd=max_price_usd, cart=cart)
    await _record_and_invoke(
        params=params,
        writer=writer,
        name="search_products",
        result=result,
        started_at_iso=started,
    )


async def handle_get_product_detail(
    params: _FunctionCallParams,
    *,
    writer: TranscriptWriter,
    cart: CartState,
) -> None:
    started = _now_iso()
    sku = str(params.arguments.get("sku", ""))
    result = get_product_detail(sku=sku, cart=cart)
    await _record_and_invoke(
        params=params,
        writer=writer,
        name="get_product_detail",
        result=result,
        started_at_iso=started,
    )


async def handle_add_to_cart(
    params: _FunctionCallParams,
    *,
    writer: TranscriptWriter,
    cart: CartState,
) -> None:
    started = _now_iso()
    arguments = params.arguments
    sku_value = arguments.get("sku")
    quantity_value = arguments.get("quantity")
    if not isinstance(sku_value, str) or not sku_value:
        result: dict[str, object] = {
            "status": "error",
            "message": "missing required field: sku",
        }
    elif not isinstance(quantity_value, int):
        result = {
            "status": "error",
            "message": "missing required field: quantity",
        }
    else:
        result = add_to_cart(sku=sku_value, quantity=quantity_value, cart=cart)
    await _record_and_invoke(
        params=params,
        writer=writer,
        name="add_to_cart",
        result=result,
        started_at_iso=started,
    )


async def handle_handoff_checkout(
    params: _FunctionCallParams,
    *,
    writer: TranscriptWriter,
    cart: CartState,
) -> None:
    started = _now_iso()
    shipping_address_id = str(params.arguments.get("shipping_address_id", ""))
    result = handoff_checkout(shipping_address_id=shipping_address_id, cart=cart)
    await _record_and_invoke(
        params=params,
        writer=writer,
        name="handoff_checkout",
        result=result,
        started_at_iso=started,
    )


def build_shopping_tools_schema() -> ToolsSchema:
    """Construct the Pipecat ToolsSchema describing the four mock tools.

    Imports of `pipecat.adapters.schemas.*` are deferred to the call site so the
    module can be imported without `pipecat-ai` installed.
    """
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema

    return ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name="search_products",
                description=(
                    "Search the catalog for products matching a free-text query, "
                    "optionally constrained by max price."
                ),
                properties={
                    "query": {
                        "type": "string",
                        "description": "Free-text product query, e.g. 'running shoes'.",
                    },
                    "max_price_usd": {
                        "type": "number",
                        "description": "Optional upper bound on price in USD.",
                    },
                },
                required=["query"],
            ),
            FunctionSchema(
                name="get_product_detail",
                description="Fetch full details for a single product by SKU.",
                properties={
                    "sku": {
                        "type": "string",
                        "description": "Catalog SKU returned by search_products.",
                    },
                },
                required=["sku"],
            ),
            FunctionSchema(
                name="add_to_cart",
                description="Add a product to the user's cart by SKU and quantity.",
                properties={
                    "sku": {"type": "string", "description": "Catalog SKU."},
                    "quantity": {
                        "type": "integer",
                        "description": "Positive integer quantity.",
                    },
                },
                required=["sku", "quantity"],
            ),
            FunctionSchema(
                name="handoff_checkout",
                description=(
                    "Summarize the cart and initiate checkout. Caller must have user "
                    "confirmation."
                ),
                properties={
                    "shipping_address_id": {
                        "type": "string",
                        "description": (
                            "Identifier of the shipping address the user confirmed."
                        ),
                    },
                },
                required=["shipping_address_id"],
            ),
        ]
    )


def register_shopping_handlers(
    *,
    llm: OpenAILLMService,
    writer: TranscriptWriter,
    cart: CartState,
) -> None:
    """Register the four mock tool handlers on the Pipecat LLM service.

    `cancel_on_interruption=True` mirrors the Pipecat docs and prevents a stuck
    tool call when the user barges in. `timeout_secs=10.0` keeps a slow stub
    from blocking the pipeline forever.
    """
    ToolHandler = Callable[..., Awaitable[None]]
    handler_specs: tuple[tuple[str, ToolHandler], ...] = (
        ("search_products", handle_search_products),
        ("get_product_detail", handle_get_product_detail),
        ("add_to_cart", handle_add_to_cart),
        ("handoff_checkout", handle_handoff_checkout),
    )
    for name, handler in handler_specs:
        bound = functools.partial(handler, writer=writer, cart=cart)
        llm.register_function(
            name,
            bound,
            cancel_on_interruption=True,
            timeout_secs=10.0,
        )
