import sys
from types import ModuleType

import pytest

from tests.helpers import install_package_stub, load_module

install_package_stub("usage_pkg")
config = load_module("usage_pkg.config", "config.py")

model_module = ModuleType("usage_pkg.model")


class FakeTokenUsage:
    pass


model_module.TokenUsage = FakeTokenUsage
sys.modules["usage_pkg.model"] = model_module

usage = load_module("usage_pkg.usage", "usage.py")


def test_estimate_cost_prefers_callback_cost():
    assert (
        usage.estimate_cost(
            prompt_tokens=1000,
            completion_tokens=1000,
            cached_tokens=0,
            callback_cost=0.12,
            input_cost_per_million=2.0,
            output_cost_per_million=8.0,
            cached_input_cost_per_million=0.4,
        )
        == 0.12
    )


def test_estimate_cost_uses_long_context_rates():
    cost = usage.estimate_cost(
        prompt_tokens=300000,
        completion_tokens=5000,
        cached_tokens=100000,
        callback_cost=0.0,
        input_cost_per_million=2.0,
        output_cost_per_million=8.0,
        cached_input_cost_per_million=0.4,
        long_context_threshold_tokens=256000,
        long_input_cost_per_million=6.0,
        long_output_cost_per_million=24.0,
        long_cached_input_cost_per_million=1.2,
    )

    assert cost == pytest.approx(1.44)


def test_usage_config_cost_estimation_matches_defaults():
    cfg = config.ScopedConfig()

    cost = usage.estimate_cost_from_config(
        prompt_tokens=10000,
        completion_tokens=1000,
        cached_tokens=2000,
        callback_cost=0.0,
        config=cfg,
    )

    assert cost == pytest.approx(0.0248)
