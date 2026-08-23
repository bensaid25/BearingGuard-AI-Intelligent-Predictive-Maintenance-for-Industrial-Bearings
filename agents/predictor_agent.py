"""
agents/predictor_agent.py
============================

The "predictor agent": given a request payload AND the pipeline the
classifier agent already chose, runs the correct prediction (by calling
the SAME api/inference_*.py functions your FastAPI endpoints use -- not a
reimplementation) and produces a short, human-readable summary using a
local LLM (via Ollama) with tool calling.

Design note: the raw request payload is NOT put into the LLM's context
(same reasoning as the classifier agent). Each tool below takes NO
arguments from the model -- it runs the already-known payload (captured
via closure) through the matching inference function and returns a small
structured result, which the model DOES see and summarizes.
"""

import logging
from typing import Literal

from api.inference_cmapss import predict_cmapss
from api.inference_cwru import predict_cwru
from api.inference_ims import predict_ims
from api.schemas import CMAPSSRequest, CWRURequest, IMSRequest

from .llm_client import DEFAULT_MODEL, chat_with_tools

logger = logging.getLogger("agents.predictor_agent")

SYSTEM_PROMPT = """You are the prediction agent for a predictive-maintenance API.

You will be told which pipeline applies: "cwru", "ims", or "cmapss".
Call the ONE matching tool (run_cwru_prediction, run_ims_prediction, or
run_cmapss_prediction) exactly once to get the raw model result. Then
write a short (2-4 sentence), plain-language summary of what that result
means for someone monitoring this equipment. Do not call more than one
prediction tool. Do not invent numbers -- only report what the tool
actually returned."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_cwru_prediction",
            "description": "Run the CWRU bearing-fault classifier on the current request.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_ims_prediction",
            "description": "Run the IMS bearing anomaly detector on the current request.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_cmapss_prediction",
            "description": "Run the C-MAPSS remaining-useful-life predictor on the current request.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_predictor_agent(
    pipeline: Literal["cwru", "ims", "cmapss"],
    payload: dict,
    models: dict,
    model: str = DEFAULT_MODEL,
) -> str:
    """Run the predictor agent.

    payload: the same raw request dict the classifier agent looked at.
    models: the dict returned by api/model_loader.py's load_all_models().
    """

    def run_cwru_prediction() -> dict:
        request = CWRURequest(**payload)
        result = predict_cwru(request, models["cwru"])
        return result.model_dump()

    def run_ims_prediction() -> dict:
        request = IMSRequest(**payload)
        ims_run_artifacts = models["ims"][request.run]
        result = predict_ims(request, ims_run_artifacts)
        return result.model_dump()

    def run_cmapss_prediction() -> dict:
        request = CMAPSSRequest(**payload)
        result = predict_cmapss(request, models["cmapss"])
        return result.model_dump()

    tool_functions = {
        "run_cwru_prediction": run_cwru_prediction,
        "run_ims_prediction": run_ims_prediction,
        "run_cmapss_prediction": run_cmapss_prediction,
    }

    return chat_with_tools(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        user_message=(
            f"The classifier determined this is a '{pipeline}' request. "
            f"Run the matching prediction and summarize it."
        ),
        tools=TOOLS,
        tool_functions=tool_functions,
    )
