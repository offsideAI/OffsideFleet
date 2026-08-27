import os
from pathlib import Path

import pytest

from agent import costs

REPO_PRICES = Path(__file__).parents[2] / "packages" / "ir" / "prices.json"


@pytest.fixture(autouse=True)
def use_repo_prices() -> None:
    os.environ["FLEET_PRICES_PATH"] = str(REPO_PRICES)
    costs.price_table.cache_clear()


def test_cost_exactness_opus5() -> None:
    # claude-opus-5: $5/M in, $25/M out -> microUSD per token: 5 in, 25 out.
    assert costs.cost_microusd("claude-opus-5", 1000, 100) == 1000 * 5 + 100 * 25


def test_cost_exactness_all_models_at_1m_tokens() -> None:
    table = costs.price_table()["models"]
    for model, entry in table.items():
        expected = int(round((entry["input"] + entry["output"]) * 1_000_000))
        assert costs.cost_microusd(model, 1_000_000, 1_000_000) == expected, model


def test_zero_tokens_zero_cost() -> None:
    assert costs.cost_microusd("claude-opus-5", 0, 0) == 0


def test_unknown_model_raises() -> None:
    with pytest.raises(costs.UnknownModel):
        costs.cost_microusd("gpt-nonexistent", 10, 10)


def test_price_table_version() -> None:
    assert costs.price_table_version() == "offsidefleet.prices.v1"
