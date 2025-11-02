"""Custom MCP tools for the forecasting agent.

This module imports simplified forecasting tools from forecasting_tools.py.
Only 4 essential tools: Perplexity, AskNews, Squiggle, and Markdown writing.
"""

# Import all forecasting tools from forecasting_tools.py
from src.agent.forecasting_tools import (
    perplexity_web_research,
    asknews_search,
    execute_squiggle,
    write_markdown_report,
)

# Export all tools for use in MCP server
ALL_TOOLS = [
    perplexity_web_research,
    asknews_search,
    execute_squiggle,
    write_markdown_report,
]

# Export individual tools for direct imports
__all__ = [
    "ALL_TOOLS",
    "perplexity_web_research",
    "asknews_search",
    "execute_squiggle",
    "write_markdown_report",
]
