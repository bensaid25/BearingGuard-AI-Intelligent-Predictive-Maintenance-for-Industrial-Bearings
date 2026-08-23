"""
agents/classifier_agent.py
============================

The "classifier agent": decides WHICH prediction pipeline (cwru / ims /
cmapss) an incoming raw request belongs to, using a local LLM (via
Ollama) with tool calling.

Design note: raw sensor arrays (e.g. a 20,480-sample IMS signal, or a
30x225 C-MAPSS sequence) are NEVER put into the LLM's context -- that
would be slow and pointless. Instead the agent is given a small
STRUCTURAL SUMMARY of the payload (top-level keys, types, lengths) via a
tool, and reasons about that summary instead of the raw values.
"""

import logging
from typing import Literal

from pydantic import BaseModel

from .llm_client import DEFAULT_MODEL, chat_with_tools

logger = logging.getLogger("agents.classifier_agent")

SYSTEM_PROMPT = """You are a routing classifier for a predictive-maintenance API.

You will be given a structural summary of an incoming JSON request (its
top-level keys and shapes -- NOT the raw sensor values). Decide which of
these three prediction pipelines the request belongs to:

- "cwru": a bearing-fault classifier. Requests have exactly these 12
  top-level numeric keys: rms, kurtosis, skewness, peak_to_peak, std,
  dominant_freq, spectral_energy, spectral_centroid, energy_0_1000,
  energy_1000_2500, energy_2500_5000, load.

- "ims": a bearing anomaly detector. Requests have a "run" key (one of
  "1st_test", "2nd_test", "3rd_test") and a "channels" key holding a
  list of {"channel": ..., "signal": [...20480 numbers...]} objects.

- "cmapss": a remaining-useful-life predictor. Requests have a "sequence"
  key holding a list of 30 dicts, each with 225 named sensor feature
  keys (e.g. "sensor_2", "sensor_2_roll5_mean").

First call get_payload_summary to see the structure of the current
request. Then call submit_classification exactly once with your decision.
Always call submit_classification -- never just answer in plain text."""


class ClassificationResult(BaseModel):
    pipeline: Literal["cwru", "ims", "cmapss"]
    confidence: float
    reasoning: str


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_payload_summary",
            "description": (
                "Get a structural summary (keys, types, lengths) of the "
                "incoming request payload -- NOT the raw values."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_classification",
            "description": "Report the final routing decision. Must be called exactly once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {"type": "string", "enum": ["cwru", "ims", "cmapss"]},
                    "confidence": {"type": "number", "description": "0.0 to 1.0"},
                    "reasoning": {"type": "string"},
                },
                "required": ["pipeline", "confidence", "reasoning"],
            },
        },
    },
]


def _summarize_payload(payload: dict) -> dict:
    """Small structural summary of a JSON payload: keys, types, and
    lengths -- never raw numeric values. This is what get_payload_summary
    hands back to the model."""
    summary = {}
    for key, value in payload.items():
        if isinstance(value, list):
            first_type = type(value[0]).__name__ if value else "unknown"
            summary[key] = f"list of {len(value)} items (first item type: {first_type})"
            if value and isinstance(value[0], dict):
                summary[f"{key}[0]_keys"] = sorted(value[0].keys())
        elif isinstance(value, dict):
            summary[key] = f"dict with keys: {sorted(value.keys())}"
        else:
            summary[key] = type(value).__name__
    return summary


def classify_pipeline(payload: dict, model: str = DEFAULT_MODEL) -> ClassificationResult:
    """Run the classifier agent on one incoming request payload."""
    captured_result: dict = {}

    def get_payload_summary() -> dict:
        return _summarize_payload(payload)

    def submit_classification(pipeline: str, confidence: float, reasoning: str) -> dict:
        captured_result["pipeline"] = pipeline
        captured_result["confidence"] = confidence
        captured_result["reasoning"] = reasoning
        return {"status": "received"}

    tool_functions = {
        "get_payload_summary": get_payload_summary,
        "submit_classification": submit_classification,
    }

    chat_with_tools(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        user_message="Classify this request.",
        tools=TOOLS,
        tool_functions=tool_functions,
    )

    if "pipeline" not in captured_result:
        raise RuntimeError("Classifier agent did not call submit_classification.")

    return ClassificationResult(**captured_result)
