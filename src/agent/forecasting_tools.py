"""Simple, clean forecasting tools - only 2 tools: Perplexity and AskNews."""

import os
from typing import Any
from dotenv import load_dotenv
from claude_agent_sdk import tool

# Load environment variables at module level
load_dotenv()


@tool(
    "perplexity_web_research",
    "Deep web research using Perplexity with citations and real-time data",
    {"query": str, "focus": str}
)
async def perplexity_web_research(args: dict[str, Any]) -> dict[str, Any]:
    """Research using Perplexity API with sophisticated prompts.

    Args:
        query: Research query
        focus: Focus area - 'exact_data', 'base_rates', 'trends', 'expert_predictions', 'general'
    """
    import aiohttp

    # Load API key
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return {
            "content": [{
                "type": "text",
                "text": "❌ PERPLEXITY_API_KEY not found. Set it in .env file."
            }],
            "isError": True
        }

    query_text = args["query"]
    focus = args.get("focus", "general")

    # Enhance query based on focus
    if focus == "exact_data":
        enhanced_query = f"""{query_text}

Please provide:
- Exact numbers, percentages, and dates
- Historical progression with specific data points
- Month-over-month or year-over-year growth rates
- Comparison metrics with specific figures
- Recent announcements with dates
"""
    elif focus == "base_rates":
        enhanced_query = f"""{query_text}

Please provide:
- Historical frequency and occurrence rates
- Statistical patterns and distributions
- Success/failure rates with percentages
- Trend analysis over time
- Relevant conditional probabilities
"""
    elif focus == "trends":
        enhanced_query = f"""{query_text}

Please provide:
- Current trajectory and growth rates
- Historical progression with dates
- Inflection points and key changes
- Driving factors and constraints
- Future projections based on data
"""
    elif focus == "expert_predictions":
        enhanced_query = f"""{query_text}

Please provide:
- Specific expert predictions with names and dates
- Consensus views and contrarian opinions
- Confidence levels and uncertainties
- Track records of predictors
- Recent updates or changes
"""
    else:
        enhanced_query = query_text

    # Call Perplexity API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar-reasoning",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a research assistant helping a superforecaster. Provide detailed, data-driven analysis with specific numbers, dates, and citations."
                        },
                        {
                            "role": "user",
                            "content": enhanced_query
                        }
                    ],
                    "return_citations": True,
                }
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    citations = result.get("citations", [])

                    output = f"**Research Results** (Focus: {focus})\n\n{content}"
                    if citations:
                        output += f"\n\n**Sources:**\n" + "\n".join(f"- {c}" for c in citations[:10])

                    return {
                        "content": [{
                            "type": "text",
                            "text": output
                        }]
                    }
                else:
                    error_text = await response.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"❌ Perplexity API error ({response.status}): {error_text}"
                        }],
                        "isError": True
                    }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Error calling Perplexity: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "asknews_search",
    "Search recent news articles using AskNews with time filtering",
    {"query": str, "days_back": int, "focus": str}
)
async def asknews_search(args: dict[str, Any]) -> dict[str, Any]:
    """Search news using AskNews API.

    Args:
        query: Search query
        days_back: How many days back to search (default: 30)
        focus: Focus area - 'timeline', 'metrics', 'announcements', 'general'
    """
    from asknews_sdk import AsyncAskNewsSDK

    # Load API credentials
    client_id = os.getenv("ASKNEWS_CLIENT_ID")
    client_secret = os.getenv("ASKNEWS_SECRET")

    if not client_id or not client_secret:
        return {
            "content": [{
                "type": "text",
                "text": "❌ AskNews credentials not found. Set ASKNEWS_CLIENT_ID and ASKNEWS_SECRET in .env file."
            }],
            "isError": True
        }

    query_text = args["query"]
    days_back = args.get("days_back", 30)
    focus = args.get("focus", "general")

    # Enhance query based on focus
    if focus == "timeline":
        enhanced_query = f"{query_text} announcements dates timeline schedule"
    elif focus == "metrics":
        enhanced_query = f"{query_text} numbers metrics benchmarks performance data"
    elif focus == "announcements":
        enhanced_query = f"{query_text} announcement release launch official statement"
    else:
        enhanced_query = query_text

    try:
        async with AsyncAskNewsSDK(
            client_id=client_id,
            client_secret=client_secret,
            scopes=["news"]
        ) as ask:
            # Search news
            response = await ask.news.search_news(
                query=enhanced_query,
                n_articles=10,
                return_type="both",
                historical=True,
                hours_back=days_back * 24
            )

            # Format response
            summary = response.as_string if hasattr(response, 'as_string') else str(response)

            return {
                "content": [{
                    "type": "text",
                    "text": f"**News Search Results** (Focus: {focus}, Last {days_back} days)\n\n{summary}"
                }]
            }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Error calling AskNews: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "execute_squiggle",
    "Execute Squiggle probability code and return the result",
    {"code": str, "model_name": str}
)
async def execute_squiggle(args: dict[str, Any]) -> dict[str, Any]:
    """Execute Squiggle code to calculate probabilities.

    Args:
        code: Squiggle code to execute
        model_name: Name of the model for logging
    """
    import subprocess
    import json
    import tempfile
    from pathlib import Path

    code = args["code"]
    model_name = args.get("model_name", "unnamed_model")

    try:
        # Create temporary file for Squiggle code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.squiggle', delete=False) as f:
            f.write(code)
            temp_file = f.name

        # Try to execute with squiggle-cli if available
        try:
            result = subprocess.run(
                ['squiggle', 'run', temp_file],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                return {
                    "content": [{
                        "type": "text",
                        "text": f"✅ Squiggle executed successfully for {model_name}:\n\n```\n{output}\n```"
                    }]
                }
            else:
                error = result.stderr.strip()
                return {
                    "content": [{
                        "type": "text",
                        "text": f"⚠️ Squiggle execution error for {model_name}:\n{error}\n\nCode will be saved for manual review."
                    }]
                }
        except FileNotFoundError:
            # squiggle-cli not installed
            return {
                "content": [{
                    "type": "text",
                    "text": f"ℹ️ Squiggle CLI not installed. Code saved for {model_name}:\n\n```squiggle\n{code}\n```\n\nInstall with: npm install -g @quantified-uncertainty/squiggle-cli"
                }]
            }
        finally:
            # Clean up temp file
            Path(temp_file).unlink(missing_ok=True)

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Error executing Squiggle: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "write_markdown_report",
    "Write a markdown report to the file system",
    {"filepath": str, "content": str, "title": str}
)
async def write_markdown_report(args: dict[str, Any]) -> dict[str, Any]:
    """Write markdown report autonomously."""
    from pathlib import Path
    from datetime import datetime

    try:
        filepath = args["filepath"]
        content = args["content"]
        title = args.get("title", "Forecast Report")

        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)

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
                "text": f"❌ Error writing markdown: {str(e)}"
            }],
            "isError": True
        }


# Export all tools
ALL_FORECASTING_TOOLS = [
    perplexity_web_research,
    asknews_search,
    execute_squiggle,
    write_markdown_report,
]
