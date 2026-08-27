"""Cost computation from the shared price table (packages/ir — the single
source of truth; baked into the agent image at build time)."""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_PRICES_PATH = Path(__file__).parent / "prices.json"


class UnknownModel(Exception):
    pass


@lru_cache(maxsize=1)
def price_table() -> dict[str, Any]:
    path = Path(os.environ.get("FLEET_PRICES_PATH", str(DEFAULT_PRICES_PATH)))
    with path.open() as f:
        data: dict[str, Any] = json.load(f)
    return data


def price_table_version() -> str:
    return str(price_table()["schema"])


def cost_microusd(model: str, tokens_in: int, tokens_out: int) -> int:
    """Cost in micro-USD (1e-6 USD). Prices are USD per million tokens, so
    price-per-token in microUSD == the per-Mtok dollar figure — exact integer
    math, no floats in the hot path."""
    models = price_table()["models"]
    if model not in models:
        raise UnknownModel(model)
    entry = models[model]
    in_per_mtok_microusd = int(round(entry["input"] * 1_000_000))
    out_per_mtok_microusd = int(round(entry["output"] * 1_000_000))
    return (tokens_in * in_per_mtok_microusd + tokens_out * out_per_mtok_microusd) // 1_000_000
