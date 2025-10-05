"""Utilities for generating AI-powered summaries for trading signals."""

import logging
from dataclasses import dataclass
from string import Template
from typing import Any, Dict, Optional

from apps.api.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMClient:
    """Simple client wrapper describing the configured LLM provider.

    The default implementation simply echoes the rendered prompt. This keeps the
    system functional without an external dependency while providing a clear
    extension point for integrating a real LLM provider in the future.
    """

    provider: str
    api_key: str
    model: str
    max_tokens: int

    @property
    def is_configured(self) -> bool:
        """Return True when an API key is present."""

        return bool(self.api_key)

    def generate(self, prompt: str, *, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a summary for the supplied prompt.

        The base implementation just echoes the prompt. Downstream projects can
        subclass :class:`LLMClient` and override :meth:`generate` to call the
        provider-specific API.
        """

        logger.debug(
            "LLM client for provider %s is operating in echo mode; returning prompt.",
            self.provider,
        )
        return prompt


def _build_template_context(
    signal_data: Dict[str, Any],
    model_info: Optional[Dict[str, Any]] = None,
    inference_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a context dictionary used for summary templating."""

    model_info = model_info or {}
    inference_metadata = inference_metadata or {}

    def _coerce_side(value: Any) -> str:
        if hasattr(value, "value"):
            return str(value.value)
        return str(value) if value is not None else ""

    def _fmt_float(value: Any, precision: int = 2) -> str:
        try:
            return f"{float(value):.{precision}f}"
        except (TypeError, ValueError):
            return ""

    def _fmt_pct(value: Any, precision: int = 2) -> str:
        try:
            return f"{float(value):.{precision}f}"
        except (TypeError, ValueError):
            return ""

    context: Dict[str, Any] = {
        "signal_id": signal_data.get("signal_id", ""),
        "symbol": signal_data.get("symbol", ""),
        "side": _coerce_side(signal_data.get("side")),
        "entry_price": _fmt_float(signal_data.get("entry_price")),
        "tp1_price": _fmt_float(signal_data.get("tp1_price")),
        "tp2_price": _fmt_float(signal_data.get("tp2_price")),
        "tp3_price": _fmt_float(signal_data.get("tp3_price")),
        "sl_price": _fmt_float(signal_data.get("sl_price")),
        "confidence": _fmt_pct(signal_data.get("confidence")),
        "expected_net_profit_pct": _fmt_pct(signal_data.get("expected_net_profit_pct")),
        "risk_reward_ratio": _fmt_float(signal_data.get("risk_reward_ratio")),
        "model_id": model_info.get("model_id", signal_data.get("model_id", "")),
        "model_version": model_info.get("version", signal_data.get("model_version", "")),
        "timeframe": signal_data.get("timeframe") or inference_metadata.get("timeframe", ""),
    }

    return context


def _render_template(template_text: str, context: Dict[str, Any]) -> str:
    template = Template(template_text)
    return template.safe_substitute(context)


def get_default_llm_client() -> Optional[LLMClient]:
    """Create a default LLM client based on configuration.

    Returns ``None`` when no API key is configured so that callers can fall back
    to deterministic templated summaries.
    """

    client = LLMClient(
        provider=settings.LLM_PROVIDER,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
    if not client.is_configured:
        return None
    return client


def generate_signal_summary(
    signal_data: Dict[str, Any],
    model_info: Optional[Dict[str, Any]] = None,
    inference_metadata: Optional[Dict[str, Any]] = None,
    *,
    client: Optional[LLMClient] = None,
    template: Optional[str] = None,
) -> Optional[str]:
    """Generate an explanatory summary for a signal.

    The function first renders the configured template to build a concise prompt
    describing the signal. When an LLM client is configured it is used to
    generate an enriched summary, otherwise the rendered template is returned.
    Any exception raised by downstream providers is caught and logged so signal
    generation can proceed safely.
    """

    template_text = template or settings.LLM_SUMMARY_TEMPLATE
    context = _build_template_context(signal_data, model_info, inference_metadata)

    prompt = _render_template(template_text, context)

    summary_client = client if client is not None else get_default_llm_client()

    if summary_client is None:
        return prompt

    try:
        summary = summary_client.generate(prompt, context=context)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to generate LLM summary; falling back to template output.")
        return prompt

    return summary or prompt
