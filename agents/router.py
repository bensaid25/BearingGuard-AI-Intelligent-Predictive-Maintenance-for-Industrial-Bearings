"""
agents/router.py
==================

The orchestrator: runs the classifier agent, then the predictor agent,
and returns one combined result. This is the "multi-agent system" your
supervisor described -- two separate LLM agents, each with its own system
prompt and tools, chained together. This file itself makes NO LLM calls
-- it's plain Python glue.
"""

import logging

from .classifier_agent import ClassificationResult, classify_pipeline
from .predictor_agent import run_predictor_agent

logger = logging.getLogger("agents.router")


class AgentPipelineResult:
    def __init__(self, classification: ClassificationResult, summary: str):
        self.classification = classification
        self.summary = summary

    def to_dict(self) -> dict:
        return {
            "pipeline": self.classification.pipeline,
            "classification_confidence": self.classification.confidence,
            "classification_reasoning": self.classification.reasoning,
            "summary": self.summary,
        }


def run_agent_pipeline(payload: dict, models: dict) -> AgentPipelineResult:
    """Full agentic flow: classify, then predict + summarize.

    payload: the raw incoming request dict (whatever shape it turns out
        to be -- the classifier agent figures out which pipeline it is).
    models: the dict returned by api/model_loader.py's load_all_models().
    """
    logger.info("Router: running classifier agent...")
    classification = classify_pipeline(payload)
    logger.info(
        "Router: classifier chose '%s' (confidence=%.2f)",
        classification.pipeline,
        classification.confidence,
    )

    logger.info("Router: running predictor agent...")
    summary = run_predictor_agent(classification.pipeline, payload, models)

    return AgentPipelineResult(classification=classification, summary=summary)
