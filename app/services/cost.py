# USD per 1M tokens — placeholder rates; VERIFY against current provider
# pricing pages and keep this table in one place.
PRICE_TABLE = {
    ("openai", "gpt-4o"): {"prompt": 2.50, "completion": 10.00},
    ("openai", "gpt-4o-mini"): {"prompt": 0.15, "completion": 0.60},
    ("groq", "_default"): {"prompt": 0.0, "completion": 0.0},  # free tier
    ("ollama", "_default"): {"prompt": 0.0, "completion": 0.0},  # local
    ("openrouter", "_default"): {"prompt": 0.0, "completion": 0.0},  # varies by model
}


def cost_usd(provider: str, model: str, pt: int, ct: int) -> float:
    rates = PRICE_TABLE.get((provider, model)) or PRICE_TABLE.get(
        (provider, "_default"), {"prompt": 0.0, "completion": 0.0}
    )
    return (pt * rates["prompt"] + ct * rates["completion"]) / 1_000_000
