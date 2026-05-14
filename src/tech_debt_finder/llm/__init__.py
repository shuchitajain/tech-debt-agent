"""
LLM integration for tech-debt-finder.

This package provides AI-powered features:
- Theme grouping: Cluster similar TODOs together
- Priority explanations: Explain why certain TODOs should be fixed first
"""

from tech_debt_finder.llm.client import is_configured
from tech_debt_finder.llm.theme_grouper import group_by_theme
from tech_debt_finder.llm.explainer import explain_priorities

__all__ = [
    "is_configured", 
    "group_by_theme",
    "explain_priorities",
]
