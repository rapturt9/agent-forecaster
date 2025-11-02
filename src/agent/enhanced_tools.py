"""Enhanced MCP tools with sophisticated research prompts for forecasting."""

from typing import Any
from claude_agent_sdk import tool
from src.data.asknews import AskNewsClient
from src.data.perplexity import PerplexityClient


# Global clients
_asknews_client: AskNewsClient | None = None
_perplexity_client: PerplexityClient | None = None


async def get_asknews_client() -> AskNewsClient:
    """Get or create AskNews client."""
    global _asknews_client
    if _asknews_client is None:
        _asknews_client = AskNewsClient()
    return _asknews_client


async def get_perplexity_client() -> PerplexityClient:
    """Get or create Perplexity client."""
    global _perplexity_client
    if _perplexity_client is None:
        _perplexity_client = PerplexityClient()
    return _perplexity_client


@tool(
    "search_news_enhanced",
    "Search for recent news with enhanced context for forecasting",
    {"query": str, "days_back": int, "max_results": int, "focus": str}
)
async def search_news_enhanced(args: dict[str, Any]) -> dict[str, Any]:
    """Enhanced news search with forecasting-focused context.

    Args:
        query: Search query
        days_back: How many days back to search (default: 14)
        max_results: Maximum results (default: 20)
        focus: Focus area - 'timeline', 'metrics', 'expert_opinion', 'base_rates'
    """
    client = await get_asknews_client()

    query = args["query"]
    days_back = args.get("days_back", 14)
    max_results = args.get("max_results", 20)
    focus = args.get("focus", "timeline")

    # Enhance query based on focus
    enhanced_query = query
    if focus == "timeline":
        enhanced_query += " recent announcements dates timeline schedule"
    elif focus == "metrics":
        enhanced_query += " performance numbers benchmarks metrics exact figures"
    elif focus == "expert_opinion":
        enhanced_query += " expert predictions forecasts analyst estimates"
    elif focus == "base_rates":
        enhanced_query += " historical frequency trends patterns statistics"

    try:
        summary = await client.summarize_context(enhanced_query, days_back=days_back)

        return {
            "content": [{
                "type": "text",
                "text": f"[News Search - Focus: {focus}]\n\n{summary}"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error searching news: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "research_with_exact_data",
    "Research with focus on exact numbers, dates, and quantitative data",
    {"topic": str, "data_type": str, "time_period": str}
)
async def research_with_exact_data(args: dict[str, Any]) -> dict[str, Any]:
    """Research focusing on exact quantitative data - pattern from trading_tools.py.

    Args:
        topic: Topic to research
        data_type: Type of data needed - 'benchmarks', 'releases', 'performance', 'market_data'
        time_period: Time period - 'current', 'last_6_months', 'year_over_year', 'historical'
    """
    client = await get_perplexity_client()

    topic = args["topic"]
    data_type = args.get("data_type", "benchmarks")
    time_period = args.get("time_period", "current")

    # Construct sophisticated query based on trading_tools.py pattern
    if data_type == "benchmarks":
        query = f"""{topic} current performance on benchmarks with exact numbers and exact progress over months.
Include:
- Current scores and metrics (2024-2025)
- Historical progression with dates (2020-2024)
- Comparison to competitors with specific numbers
- Recent announcements from companies with dates
- Trend analysis with growth rates and percentages
"""
    elif data_type == "releases":
        query = f"""{topic} release timeline and schedule with exact dates.
Include:
- Official announcements with dates
- Developer statements and blog posts
- Leaked information and rumors with sources
- Historical release patterns with dates
- Expected timeline based on evidence
"""
    elif data_type == "performance":
        query = f"""{topic} performance metrics with exact numbers over time.
Include:
- Current performance numbers
- Month-over-month improvements with percentages
- Comparison to previous versions
- Technical specifications
- Independent evaluations and reviews
"""
    elif data_type == "market_data":
        query = f"""{topic} market dynamics and competitive landscape.
Include:
- Market share with percentages
- Adoption metrics and user numbers
- Competitive positioning
- Analyst predictions with dates
- Industry trends
"""
    else:
        query = f"{topic} with recent data and analysis focusing on {time_period} period"

    try:
        result = await client.research_question(query)

        return {
            "content": [{
                "type": "text",
                "text": f"[Research: {data_type} - {time_period}]\n\n{result}"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error performing research: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "get_base_rates_comprehensive",
    "Get comprehensive base rate data for forecasting",
    {"event_type": str, "reference_class": str}
)
async def get_base_rates_comprehensive(args: dict[str, Any]) -> dict[str, Any]:
    """Get comprehensive base rate data for superforecasting.

    Args:
        event_type: Type of event to get base rates for
        reference_class: Reference class for comparison
    """
    client = await get_perplexity_client()

    event_type = args["event_type"]
    reference_class = args.get("reference_class", "similar events")

    query = f"""Historical base rates and frequency for: {event_type}

Reference class: {reference_class}

Please provide:
1. Historical frequency - How often has this type of event occurred?
2. Time periods - When did similar events happen? Include exact dates.
3. Success/failure rates - What percentage succeeded vs failed?
4. Trend analysis - Is frequency increasing or decreasing?
5. Relevant statistics - Any statistical patterns or distributions
6. Conditional factors - What factors influenced outcomes?
7. Recent changes - Have base rates changed recently?

Include specific numbers, percentages, and dates."""

    try:
        result = await client.search(query)

        return {
            "content": [{
                "type": "text",
                "text": f"[Base Rates: {event_type}]\n\n{result.answer}\n\nSources: {', '.join(result.sources)}"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error getting base rates: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "research_expert_predictions",
    "Research expert predictions and forecasts on a topic",
    {"topic": str, "expert_type": str}
)
async def research_expert_predictions(args: dict[str, Any]) -> dict[str, Any]:
    """Research expert predictions and consensus.

    Args:
        topic: Topic to research predictions for
        expert_type: Type of experts - 'industry', 'analysts', 'researchers', 'forecasters'
    """
    client = await get_perplexity_client()

    topic = args["topic"]
    expert_type = args.get("expert_type", "industry")

    query = f"""Expert predictions and forecasts about: {topic}

From {expert_type} experts, please provide:
1. Specific predictions with dates and probabilities
2. Expert names and their credentials
3. Consensus view - What do most experts agree on?
4. Contrarian views - What dissenting opinions exist?
5. Track records - How accurate have these experts been?
6. Confidence levels - How confident are the predictions?
7. Key uncertainties - What factors could change predictions?
8. Recent updates - Have predictions changed recently?

Include specific numbers, dates, and source citations."""

    try:
        result = await client.search(query)

        return {
            "content": [{
                "type": "text",
                "text": f"[Expert Predictions: {expert_type}]\n\n{result.answer}\n\nSources: {', '.join(result.sources)}"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error researching expert predictions: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "analyze_trend_trajectory",
    "Analyze trends and trajectories with quantitative data",
    {"metric": str, "time_range": str}
)
async def analyze_trend_trajectory(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze trends and project trajectories.

    Args:
        metric: Metric or trend to analyze
        time_range: Time range - 'short_term', 'medium_term', 'long_term'
    """
    client = await get_perplexity_client()

    metric = args["metric"]
    time_range = args.get("time_range", "medium_term")

    query = f"""Trend analysis for: {metric} over {time_range}

Please provide:
1. Current state - Latest numbers and status
2. Historical progression - How has it changed over time? Include specific data points with dates
3. Growth rate - Calculate year-over-year or month-over-month growth with percentages
4. Trajectory - Project future trend based on current data
5. Inflection points - When did significant changes occur?
6. Drivers - What factors are driving the trend?
7. Constraints - What could slow or accelerate the trend?
8. Comparison - How does this compare to similar metrics?

Include exact numbers, percentages, dates, and calculations."""

    try:
        result = await client.search(query)

        return {
            "content": [{
                "type": "text",
                "text": f"[Trend Analysis: {metric}]\n\n{result.answer}\n\nSources: {', '.join(result.sources)}"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error analyzing trend: {str(e)}"
            }],
            "isError": True
        }


# Keep original tools for backward compatibility
@tool(
    "search_news",
    "Search for recent news articles related to a query using AskNews",
    {"query": str, "days_back": int, "max_results": int}
)
async def search_news(args: dict[str, Any]) -> dict[str, Any]:
    """Search for news articles using AskNews."""
    client = await get_asknews_client()

    query = args["query"]
    days_back = args.get("days_back", 7)
    max_results = args.get("max_results", 10)

    try:
        summary = await client.summarize_context(query, days_back=days_back)

        return {
            "content": [{
                "type": "text",
                "text": summary
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error searching news: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "web_research",
    "Research a topic using Perplexity web search with real-time data",
    {"query": str, "context": str}
)
async def web_research(args: dict[str, Any]) -> dict[str, Any]:
    """Research a topic using Perplexity."""
    client = await get_perplexity_client()

    query = args["query"]
    context = args.get("context", "")

    try:
        result = await client.research_question(query, context=context if context else None)

        return {
            "content": [{
                "type": "text",
                "text": result
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error performing web research: {str(e)}"
            }],
            "isError": True
        }


# File system tools for autonomous report generation
@tool(
    "write_markdown_report",
    "Write a markdown report to the file system",
    {"filepath": str, "content": str, "title": str}
)
async def write_markdown_report(args: dict[str, Any]) -> dict[str, Any]:
    """Write a markdown report file.

    Args:
        filepath: Path to save the markdown file (e.g., 'research_reports/my_forecast.md')
        content: Markdown content to write
        title: Report title
    """
    from pathlib import Path
    from datetime import datetime

    try:
        filepath = args["filepath"]
        content = args["content"]
        title = args.get("title", "Forecast Report")

        # Ensure directory exists
        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write markdown file with header
        with open(file_path, 'w') as f:
            f.write(f"# {title}\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(content)

        return {
            "content": [{
                "type": "text",
                "text": f"✅ Successfully wrote markdown report to: {filepath}\n\nFile size: {file_path.stat().st_size} bytes"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error writing markdown report: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "write_json_data",
    "Write JSON data to the file system",
    {"filepath": str, "data": dict}
)
async def write_json_data(args: dict[str, Any]) -> dict[str, Any]:
    """Write JSON data to a file.

    Args:
        filepath: Path to save the JSON file (e.g., 'research_reports/forecast_data.json')
        data: Dictionary/object to save as JSON
    """
    import json
    from pathlib import Path

    try:
        filepath = args["filepath"]
        data = args["data"]

        # Ensure directory exists
        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON file
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        return {
            "content": [{
                "type": "text",
                "text": f"✅ Successfully wrote JSON data to: {filepath}\n\nFile size: {file_path.stat().st_size} bytes"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error writing JSON data: {str(e)}"
            }],
            "isError": True
        }
