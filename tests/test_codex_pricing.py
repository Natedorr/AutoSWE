"""Tests for autoswe.harness.backends.codex_pricing — cost estimation."""
from autoswe.harness.backends.codex_pricing import estimate_cost

# ---------- Known model pricing ----------


def test_estimate_cost_gpt4o_basic():
    """gpt-4o: input=$2.50/M, cached=$0.25/M, output=$10.00/M."""
    usage = [
        {
            "input_tokens": 100_000,
            "cached_input_tokens": 50_000,
            "output_tokens": 10_000,
            "reasoning_output_tokens": 0,
        }
    ]
    cost = estimate_cost("gpt-4o", usage)
    # 100k * 2.50/1M + 50k * 0.25/1M + 10k * 10/1M
    # = 0.25 + 0.0125 + 0.1 = 0.3625
    assert cost is not None
    assert abs(cost - 0.3625) < 0.0001


def test_estimate_cost_gpt5_basic():
    """gpt-5: input=$120/M, cached=$12/M, output=$600/M."""
    usage = [
        {
            "input_tokens": 100_000,
            "cached_input_tokens": 0,
            "output_tokens": 10_000,
            "reasoning_output_tokens": 0,
        }
    ]
    cost = estimate_cost("gpt-5", usage)
    # 100k * 120/1M + 10k * 600/1M = 12 + 6 = 18
    assert cost is not None
    assert abs(cost - 18.0) < 0.0001


def test_estimate_cost_gpt5_codex():
    """gpt-5-codex: input=$1250/M, cached=$125/M, output=$12500/M."""
    usage = [
        {
            "input_tokens": 10_000,
            "cached_input_tokens": 0,
            "output_tokens": 1_000,
            "reasoning_output_tokens": 0,
        }
    ]
    cost = estimate_cost("gpt-5-codex", usage)
    # 10k * 1250/1M + 1k * 12500/1M = 12.5 + 12.5 = 25
    assert cost is not None
    assert abs(cost - 25.0) < 0.0001


def test_estimate_cost_case_insensitive():
    """Model lookup is case-insensitive."""
    usage = [{"input_tokens": 1_000, "output_tokens": 100}]
    assert estimate_cost("GPT-4O", usage) == estimate_cost("gpt-4o", usage)
    assert estimate_cost("GPT-5", usage) == estimate_cost("gpt-5", usage)


# ---------- Reasoning output tokens ----------


def test_estimate_cost_reasoning_output_tokens():
    """reasoning_output_tokens are billed at the output rate."""
    usage = [
        {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 1_000,
            "reasoning_output_tokens": 4_000,
        }
    ]
    cost = estimate_cost("gpt-4o", usage)
    # (1000 + 4000) * 10/1M = 5000 * 10/1M = 0.05
    assert cost is not None
    assert abs(cost - 0.05) < 0.0001


# ---------- Multi-turn summation ----------


def test_estimate_cost_multi_turn():
    """Token usage is summed across multiple turns."""
    usage = [
        {"input_tokens": 5_000, "cached_input_tokens": 0, "output_tokens": 1_000},
        {"input_tokens": 5_000, "cached_input_tokens": 0, "output_tokens": 1_000},
    ]
    cost = estimate_cost("gpt-4o", usage)
    # Total: 10000 * 2.50/1M + 2000 * 10/1M = 0.025 + 0.02 = 0.045
    assert cost is not None
    assert abs(cost - 0.045) < 0.0001


# ---------- Edge cases ----------


def test_estimate_cost_empty_usage():
    """Empty usage list returns None."""
    assert estimate_cost("gpt-4o", []) is None


def test_estimate_cost_zero_tokens():
    """Zero total tokens returns None."""
    usage = [{"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}]
    assert estimate_cost("gpt-4o", usage) is None


def test_estimate_cost_unknown_model():
    """Unknown model returns None (never guesses)."""
    usage = [{"input_tokens": 1_000, "output_tokens": 100}]
    assert estimate_cost("unknown-model", usage) is None


def test_estimate_cost_none_model():
    """None model returns None."""
    usage = [{"input_tokens": 1_000, "output_tokens": 100}]
    assert estimate_cost(None, usage) is None


def test_estimate_cost_empty_model():
    """Empty string model returns None."""
    usage = [{"input_tokens": 1_000, "output_tokens": 100}]
    assert estimate_cost("", usage) is None


def test_estimate_cost_missing_optional_fields():
    """Missing optional fields (cached_input_tokens, reasoning_output_tokens) default to 0."""
    usage = [{"input_tokens": 1_000, "output_tokens": 100}]
    cost = estimate_cost("gpt-4o", usage)
    assert cost is not None
    # 1000 * 2.50/1M + 100 * 10/1M = 0.0025 + 0.001 = 0.0035
    assert abs(cost - 0.0035) < 0.0001


def test_estimate_cost_prefix_match():
    """Model variants (e.g. gpt-5-2025-08-07) match by prefix."""
    usage = [{"input_tokens": 1_000, "output_tokens": 100}]
    cost = estimate_cost("gpt-5-mini-2025-08-07", usage)
    # Should match gpt-5-mini prefix
    assert cost is not None
    # 1000 * 25/1M + 100 * 125/1M = 0.025 + 0.0125 = 0.0375
    assert abs(cost - 0.0375) < 0.0001


def test_estimate_cost_rounding():
    """Cost is rounded to 6 decimal places."""
    usage = [{"input_tokens": 333, "cached_input_tokens": 0, "output_tokens": 111}]
    cost = estimate_cost("gpt-4o", usage)
    assert cost is not None
    # Check it doesn't have floating-point artifacts beyond 6 places
    assert cost == round(cost, 6)
