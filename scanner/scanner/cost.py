"""Token counting and USD cost estimation for Bedrock Claude models."""


class TokenTracker:
    """Accumulates token usage and computes cost using admin-configured per-token pricing."""

    def __init__(self, cost_limit_usd: float, input_cost_per_1m: float, output_cost_per_1m: float):
        self.cost_limit_usd = cost_limit_usd
        self.input_cost_per_1m = input_cost_per_1m
        self.output_cost_per_1m = output_cost_per_1m
        self.input_tokens = 0
        self.output_tokens = 0

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    @property
    def cost_usd(self) -> float:
        return round(
            (self.input_tokens * self.input_cost_per_1m
             + self.output_tokens * self.output_cost_per_1m) / 1_000_000,
            6,
        )

    @property
    def over_limit(self) -> bool:
        return self.cost_usd >= self.cost_limit_usd


__all__ = ["TokenTracker"]
