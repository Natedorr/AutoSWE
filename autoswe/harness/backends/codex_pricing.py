"""Codex pricing — estimate USD cost from token usage.

Maintains a price table mapping model IDs to documented input/output/cached
prices (USD per 1M tokens).  ``estimate_cost`` sums token counts across all
turns and applies the matching model's rates.  Returns ``None`` for unknown
models (never guesses — downstream already treats ``None`` as "no cost
reported").
"""
from __future__ import annotations

# USD per 1M tokens, keyed by model ID (lowercase for case-insensitive match).
# Sources: OpenAI pricing pages, updated June 2026.
_PRICES: dict[str, dict[str, float]] = {
    "gpt-5-codex": {
        "input": 1_250.0,
        "cached_input": 125.0,
        "output": 12_500.0,
    },
    "gpt-5": {
        "input": 120.0,
        "cached_input": 12.0,
        "output": 600.0,
    },
    "gpt-5-mini": {
        "input": 25.0,
        "cached_input": 2.5,
        "output": 125.0,
    },
    "gpt-5-nano": {
        "input": 10.0,
        "cached_input": 1.0,
        "output": 50.0,
    },
    "gpt-4o": {
        "input": 2.50,
        "cached_input": 0.25,
        "output": 10.0,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "cached_input": 0.01,
        "output": 0.60,
    },
    # Aliases
    "gpt4o": {
        "input": 2.50,
        "cached_input": 0.25,
        "output": 10.0,
    },
    "o3": {
        "input": 100.0,
        "cached_input": 10.0,
        "output": 400.0,
    },
    "o4": {
        "input": 120.0,
        "cached_input": 12.0,
        "output": 600.0,
    },
}


def estimate_cost(model: str, usage: list[dict]) -> float | None:
    """Convert accumulated token usage to an estimated USD cost.

    Args:
        model: The model ID string (e.g. ``"gpt-5"``, ``"gpt-4o"``).
        usage: List of usage dicts from ``turn.completed`` events, each
               containing keys like ``input_tokens``, ``cached_input_tokens``,
               ``output_tokens``, and optionally ``reasoning_output_tokens``.

    Returns:
        Estimated cost in USD, or ``None`` if the model is not in the
        price table or usage is empty.
    """
    if not usage or not model:
        return None

    # Case-insensitive lookup
    prices = _PRICES.get(model.lower())
    if prices is None:
        # Try longest prefix match for model variants (e.g. "gpt-5-2025-08-07"
        # should match "gpt-5" not "gpt-5-codex"; "gpt-5-mini-2025-08-07" should
        # match "gpt-5-mini" not "gpt-5").
        best_key = None
        best_len = 0
        for key in _PRICES:
            if model.lower().startswith(key) and len(key) > best_len:
                best_key = key
                best_len = len(key)
        if best_key is not None:
            prices = _PRICES[best_key]
        else:
            return None

    input_price = prices["input"]
    cached_input_price = prices["cached_input"]
    output_price = prices["output"]

    total_input = 0
    total_cached_input = 0
    total_output = 0

    for turn in usage:
        total_input += turn.get("input_tokens", 0) or 0
        total_cached_input += turn.get("cached_input_tokens", 0) or 0
        total_output += turn.get("output_tokens", 0) or 0
        # Reasoning output tokens billed at the output rate
        reasoning = turn.get("reasoning_output_tokens", 0) or 0
        total_output += reasoning

    total_tokens = total_input + total_cached_input + total_output
    if total_tokens == 0:
        return None

    cost = (
        total_input * input_price / 1_000_000
        + total_cached_input * cached_input_price / 1_000_000
        + total_output * output_price / 1_000_000
    )

    return round(cost, 6)
