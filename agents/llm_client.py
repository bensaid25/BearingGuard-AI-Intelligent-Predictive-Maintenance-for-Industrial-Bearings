"""
agents/llm_client.py
======================

A thin wrapper around Ollama's tool-calling chat API, so the classifier
and predictor agents don't each need to know the details of talking to
Ollama directly.

Requires Ollama running locally (default: http://localhost:11434) with a
tool-calling-capable model already pulled. To set this up:

    1. Install Ollama:  https://ollama.com/download
    2. Pull a model:    ollama pull llama3.1:8b
       (lighter option: ollama pull llama3.2:3b)
    3. pip install ollama

NOTE: the exact shape of Ollama's response objects (dict-like vs.
attribute-like access) has changed slightly across `ollama` package
versions. This code uses .get()-style dict access, which works with
recent versions -- if you hit an AttributeError/KeyError here, check
`pip show ollama` and the tool-calling example in Ollama's docs for your
installed version.
"""

import logging
from typing import Callable, Dict, List

import ollama

logger = logging.getLogger("agents.llm_client")

# Swap this if your hardware can't comfortably run an 8B model.
DEFAULT_MODEL = "llama3.1:8b"


def chat_with_tools(
    model: str,
    system_prompt: str,
    user_message: str,
    tools: List[dict],
    tool_functions: Dict[str, Callable],
    max_tool_rounds: int = 4,
) -> str:
    """Run a tool-calling conversation until the model stops calling tools.

    tools: list of tool schemas in OpenAI/Ollama function-calling format.
    tool_functions: maps each tool's "name" to the Python function that
        actually implements it. Called with the model's chosen arguments.

    Returns the model's final text response (once it stops calling tools).
    Raises RuntimeError if the model never produces a final answer within
    max_tool_rounds -- this is a safety limit against infinite tool loops.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for round_num in range(max_tool_rounds):
        response = ollama.chat(model=model, messages=messages, tools=tools)
        message = response["message"]
        messages.append(dict(message))

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # No more tools requested -- treat this as the final answer.
            return message.get("content", "")

        for call in tool_calls:
            fn_name = call["function"]["name"]
            fn_args = call["function"].get("arguments", {}) or {}
            logger.info("Round %d: model called tool %s(%s)", round_num, fn_name, fn_args)

            if fn_name not in tool_functions:
                result = {"error": f"Unknown tool: {fn_name}"}
            else:
                try:
                    result = tool_functions[fn_name](**fn_args)
                except Exception as exc:
                    logger.exception("Tool %s raised an error", fn_name)
                    result = {"error": str(exc)}

            messages.append({"role": "tool", "content": str(result)})

    raise RuntimeError(
        f"Model did not produce a final answer within {max_tool_rounds} tool-call rounds."
    )
