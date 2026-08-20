"""Documented public list prices (USD per 1M tokens) for known scan models.

These are provider list prices, not RAPTOR invoices. Admins can override them
on the connection's model row. Unknown models stay at $0 and the live console
shows tokens only.
"""

from typing import Optional, Tuple

# Longer ids first so claude-sonnet-4-5 wins over claude-sonnet-4.
_DOCUMENTED = (
    ("claude-sonnet-4-6", (3.0, 15.0)),
    ("claude-sonnet-4.6", (3.0, 15.0)),
    ("claude-sonnet-4-5", (3.0, 15.0)),
    ("claude-sonnet-4.5", (3.0, 15.0)),
    ("claude-sonnet-5", (2.0, 10.0)),
    ("claude-opus-4-6", (5.0, 25.0)),
    ("claude-opus-4.6", (5.0, 25.0)),
    ("claude-opus-4-5", (5.0, 25.0)),
    ("claude-opus-4.5", (5.0, 25.0)),
    ("claude-haiku-4-5", (1.0, 5.0)),
    ("claude-haiku-4.5", (1.0, 5.0)),
    ("gpt-4.1", (2.0, 8.0)),
)


def documented_rates(model_id: str) -> Optional[Tuple[float, float]]:
    key = str(model_id or "").strip().lower().replace("_", "-")
    if not key:
        return None
    for needle, pair in _DOCUMENTED:
        if needle == key or needle in key:
            return pair
    return None


def apply_documented_rates(model: dict) -> dict:
    item = dict(model or {})
    if item.get("input_cost_per_1m") not in (None, "") and item.get("output_cost_per_1m") not in (None, ""):
        return item
    pair = documented_rates(str(item.get("id") or ""))
    if not pair:
        return item
    if item.get("input_cost_per_1m") in (None, ""):
        item["input_cost_per_1m"] = pair[0]
    if item.get("output_cost_per_1m") in (None, ""):
        item["output_cost_per_1m"] = pair[1]
    return item


__all__ = ["apply_documented_rates", "documented_rates"]
