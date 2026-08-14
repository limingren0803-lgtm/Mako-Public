"""Provider-neutral model usage metrics."""
from collections.abc import Mapping
from typing import Any

from prometheus_client import Counter


MODEL_REQUESTS = Counter(
    "mako_model_requests_total",
    "Model requests by operation and outcome",
    ("operation", "model", "outcome"),
)
MODEL_TOKENS = Counter(
    "mako_model_tokens_total",
    "Tokens reported by the model provider",
    ("operation", "model", "kind"),
)


def usage_tokens(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    result = {}
    for name in (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ):
        value = usage.get(name, 0) if isinstance(usage, Mapping) else getattr(usage, name, 0)
        result[name] = value if isinstance(value, int) and value > 0 else 0
    return result


async def create_message(client: Any, *, operation: str, **kwargs: Any) -> Any:
    model = str(kwargs.get("model") or "unknown")
    try:
        response = await client.messages.create(**kwargs)
    except Exception:
        MODEL_REQUESTS.labels(operation, model, "error").inc()
        raise

    MODEL_REQUESTS.labels(operation, model, "success").inc()
    for kind, count in usage_tokens(response).items():
        if count:
            MODEL_TOKENS.labels(operation, model, kind).inc(count)
    return response
