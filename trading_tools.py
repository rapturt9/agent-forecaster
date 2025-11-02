#!/usr/bin/env python3
"""
Consolidated Trading Tools for AutoGen Agents

This file provides a curated set of tools for the trading agent, focusing on
data analysis and research, backed by a realistic historical data simulator.
It adheres to the principle of only providing tools for which local data is available.
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import pandas as pd
import requests
import sympy
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.cache_store.diskcache import DiskCacheStore
from autogen_ext.models.cache import CHAT_CACHE_VALUE_TYPE, ChatCompletionCache
from autogen_ext.models.openai import OpenAIChatCompletionClient
from bs4 import BeautifulSoup
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from diskcache import Cache
from dotenv import load_dotenv
from markdownify import markdownify as md

from data.kalshi_historical.kalshi_api_simulator import (
    KalshiAPISimulator,
    create_kalshi_simulator,
)

from .kalshi_clients import Environment, KalshiHttpClient

load_dotenv()

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# --- Research Tools ---


def format_news_objects_for_llm(news_objects: List[Any]) -> str:
    """
    Parses a list of news article objects into a formatted string for an LLM.

    Args:
        news_objects: A list of article objects (e.g., SearchResponseDictItem).

    Returns:
        A single formatted string containing summaries of all articles.
    """
    if not news_objects:
        return "------No News Summaries Found------"

    summaries = ["------News Summaries Start------"]

    for item in news_objects:
        # Use getattr() for safe attribute access instead of .get()
        key_points = getattr(item, "key_points", [])
        formatted_key_points = "\n".join(f"• {point}" for point in key_points)

        pub_date_obj = getattr(item, "pub_date", None)
        formatted_date = (
            pub_date_obj.strftime("%B %d %Y, %H:%M") if pub_date_obj else "N/A"
        )

        # Build the document string using getattr()
        doc_string = f"""<doc>
Citation key: {getattr(item, 'as_string_key', 'N/A')}
Article URL: {getattr(item, 'article_url', 'N/A')}
Title: {getattr(item, 'title', 'No Title')}

Key Points:
{formatted_key_points}

Published date: {formatted_date}

Source: {getattr(item, 'source_id', 'N/A')}
Classification: {getattr(item, 'classification', 'N/A')}
Sentiment: {getattr(item, 'sentiment', 'N/A')}
Reporting voice: {getattr(item, 'reporting_voice', 'N/A')}
Continent: {getattr(item, 'continent', 'N/A')}
</doc>"""
        summaries.append(doc_string)

    summaries.append("------News Summaries End------")
    return "\n\n".join(summaries)


class ResearchTools:
    """
    A class to encapsulate external research tools like Perplexity and AskNews.
    It respects the simulation time to ensure point-in-time analysis.
    """

    def __init__(self, simulation_time: Optional[pd.Timestamp] = None, caching=True):
        self.simulation_time = simulation_time

        self.client = OpenAIChatCompletionClient(
            model="openai/gpt-5-mini",
            api_key=os.getenv("OPENROUTER_BACKUP_KEY"),
            base_url="https://openrouter.ai/api/v1",
            model_info={
                "family": "OpenAI",
                "context_length": 200000,
                "vision": True,
                "function_calling": True,
                "json_output": True,
                "structured_output": True,
            },
        )
        self.caching = False
        if caching:
            self.caching = True
            # Use absolute path to avoid issues when running from different directories
            self.cache_dir = Path("metac_bot_template/openevolve/cache/research")
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            cache_path = "metac_bot_template/openevolve/cache"
            cache_store = DiskCacheStore[CHAT_CACHE_VALUE_TYPE](Cache(cache_path))
            self.client = ChatCompletionCache(self.client, cache_store)

    def _get_cache_filepath(self, key_tuple: tuple) -> Path:
        """Generate a filepath for a given cache key."""
        # Convert tuple to a JSON string to handle different types
        key_str = json.dumps(key_tuple, default=str)
        # Hash the string to create a unique, filesystem-safe filename
        filename = hashlib.sha256(key_str.encode()).hexdigest()
        return self.cache_dir / filename

    async def url_query(
        self,
        url: str,
        query: str = "Create a markdown summary of the key information in the following text.",
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        """
        Fetches content from a URL, converts it to markdown, and uses an LLM to answer a query.
        """
        if query is None:
            query = (
                "Create a markdown summary of the key information in the following text.",
            )
        logger.info(
            f"TOOL CALL: url_query(url='{url}', query='{query}', reasoning='{reasoning}')"
        )

        cache_file = None

        if self.caching:
            cache_key = ("url_query", url, query)
            cache_file = self._get_cache_filepath(cache_key)
            if cache_file.exists():
                logger.info(f"Returning cached result for url_query(url='{url}')")
                with cache_file.open("r") as f:
                    return json.load(f)

        # Define headers to mimic a web browser request with retry logic
        USER_AGENTS = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/125.0.2535.51 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        ]

        REFERERS = [
            "https://www.google.com/",
            "https://www.bing.com/",
            "https://duckduckgo.com/",
            "https://www.yahoo.com/",
            "https://www.reddit.com/",
            "https://twitter.com/",
            "https://www.facebook.com/",
            "https://www.linkedin.com/",
            "https://news.ycombinator.com/",
            "https://medium.com/",
            "https://github.com/",
        ]

        try:
            # Retry logic with different user agents and referers
            max_retries = 12
            last_error = None

            for attempt in range(max_retries):
                try:
                    # Randomize headers for each attempt
                    user_agent = random.choice(USER_AGENTS)
                    referer = random.choice(REFERERS)

                    # Randomize additional headers for better anti-detection
                    accept_languages = [
                        "en-US,en;q=0.9",
                        "en-US,en;q=0.8",
                        "en-GB,en;q=0.9",
                        "en-CA,en;q=0.9",
                        "en-AU,en;q=0.9",
                    ]

                    # Randomize Sec-Ch-Ua headers based on user agent
                    if "Chrome" in user_agent:
                        chrome_version = (
                            "125"
                            if "125" in user_agent
                            else (
                                "124"
                                if "124" in user_agent
                                else "123" if "123" in user_agent else "122"
                            )
                        )
                        sec_ch_ua = f'"Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}", "Not=A?Brand";v="99"'
                        sec_ch_ua_platform = (
                            '"Windows"'
                            if "Windows" in user_agent
                            else '"macOS"' if "Macintosh" in user_agent else '"Linux"'
                        )
                    elif "Firefox" in user_agent:
                        firefox_version = "126" if "126" in user_agent else "125"
                        sec_ch_ua = (
                            f'"Mozilla";v="{firefox_version}", "Not_A Brand";v="99"'
                        )
                        sec_ch_ua_platform = (
                            '"Windows"'
                            if "Windows" in user_agent
                            else '"macOS"' if "Macintosh" in user_agent else '"Linux"'
                        )
                    elif "Safari" in user_agent:
                        safari_version = "17.5" if "17.5" in user_agent else "17.4"
                        sec_ch_ua = (
                            f'"Safari";v="{safari_version}", "Not_A Brand";v="99"'
                        )
                        sec_ch_ua_platform = '"macOS"'
                    else:
                        sec_ch_ua = '"Google Chrome";v="125", "Chromium";v="125", "Not=A?Brand";v="99"'
                        sec_ch_ua_platform = '"Windows"'

                    headers = {
                        "User-Agent": user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": random.choice(accept_languages),
                        "Accept-Encoding": "gzip, deflate, br",
                        "Referer": referer,
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Cache-Control": "max-age=0",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "cross-site",
                        "Sec-Fetch-User": "?1",
                        "DNT": "1",
                        "Sec-Ch-Ua": sec_ch_ua,
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": sec_ch_ua_platform,
                    }

                    logger.info(
                        f"Attempt {attempt + 1}/{max_retries} with User-Agent: {user_agent[:50]}..."
                    )

                    # Add exponential backoff delay between attempts to avoid rate limiting
                    if attempt > 0:
                        base_delay = (
                            1.1**attempt
                        )  # Exponential backoff: 1.1, 1.21, 1.331, 1.4641 seconds
                        jitter = random.uniform(
                            0.5, 1.5
                        )  # Add randomness to avoid synchronized requests
                        delay = base_delay * jitter
                        logger.info(
                            f"Waiting {delay:.1f} seconds before retry (attempt {attempt + 1})..."
                        )
                        await asyncio.sleep(delay)

                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()

                    # If we get here, the request was successful
                    logger.info(f"Successfully fetched URL on attempt {attempt + 1}")
                    break

                except requests.exceptions.HTTPError as e:
                    last_error = e
                    status_code = e.response.status_code
                    if status_code == 403:
                        logger.warning(
                            f"Attempt {attempt + 1} failed with 403 Forbidden. Trying different headers..."
                        )
                    elif status_code == 429:
                        logger.warning(
                            f"Attempt {attempt + 1} failed with 429 Too Many Requests. Waiting longer..."
                        )
                        await asyncio.sleep(random.uniform(5, 10))
                    elif status_code == 503:
                        logger.warning(
                            f"Attempt {attempt + 1} failed with 503 Service Unavailable. Server may be overloaded..."
                        )
                        await asyncio.sleep(random.uniform(10, 20))
                    elif status_code == 502:
                        logger.warning(
                            f"Attempt {attempt + 1} failed with 502 Bad Gateway. Waiting before retry..."
                        )
                        await asyncio.sleep(random.uniform(5, 15))
                    elif status_code >= 500:
                        logger.warning(
                            f"Attempt {attempt + 1} failed with server error {status_code}. Waiting before retry..."
                        )
                        await asyncio.sleep(random.uniform(3, 8))
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1} failed with HTTP {status_code}: {e}"
                        )
                except requests.exceptions.RequestException as e:
                    last_error = e
                    logger.warning(
                        f"Attempt {attempt + 1} failed with request error: {e}"
                    )
                    await asyncio.sleep(random.uniform(2, 5))
            else:
                # All retries failed
                logger.error(
                    f"All {max_retries} attempts failed. Last error: {last_error}"
                )
                return {
                    "success": False,
                    "error": f"Failed after {max_retries} attempts. Last error: {last_error}",
                }

            response_content = response.content

            print("Response content: ", response_content)

            soup = BeautifulSoup(response_content, "html.parser")
            markdown_content = md(str(soup.body))

            if (
                markdown_content is None
                or markdown_content.strip() == ""
                or markdown_content == "None"
            ):
                markdown_content = response_content

            # LLM part from utils.py
            def _build_agent() -> AssistantAgent:
                client = self.client

                return AssistantAgent(
                    name="parser_agent",
                    model_client=client,
                    system_message="You are a helpful assistant that extracts information from text.",
                )

            agent = _build_agent()
            prompt = f"Based on the following text, please answer this query: '{query}'\n\n---\n\n{markdown_content}"

            if self.simulation_time:
                prompt = (
                    prompt
                    + f" The date is {self.simulation_time.strftime('%m/%d/%Y')}. Do not use any information that is clearly leaked after this date and strip them from the output."
                )
            result = await agent.run(task=prompt)

            result_text = result.messages[-1].content

            result = {"success": True, "result": result_text}

            if self.caching:
                with cache_file.open("w") as f:
                    json.dump(result, f)

            return result

        except Exception as e:
            logger.error(f"Error in url_query: {e}")
            return {"success": False, "error": str(e)}

    async def call_perplexity(
        self,
        query: str,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        """Call Perplexity API for research and analysis, respecting the simulation time."""
        model = "sonar-reasoning-pro"
        cache_file = None
        if self.caching:
            cache_key = ("perplexity", str(self.simulation_time), query, model)
            cache_file = self._get_cache_filepath(cache_key)

            if cache_file.exists():
                logger.info(
                    f"Returning cached result for call_perplexity(query='{query}')"
                )
                with cache_file.open("r") as f:
                    return json.load(f)

        print(
            f"TOOL CALL: call_perplexity(query='{query}', reasoning='{reasoning}', simulation_time='{self.simulation_time}')"
        )
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "call_perplexity called without reasoning - this reduces analysis quality"
            )
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            logger.error("PERPLEXITY_API_KEY not found, unable to proceed.")
            return {
                "success": False,
                "error": "PERPLEXITY_API_KEY is required but not set.",
            }

        system_prompt = """You are an assistant to a superforecaster.
                The superforecaster will give you a question they intend to forecast on.
                To be a great assistant, you generate a concise but detailed rundown of the most relevant news and information requested, including if the question would resolve Yes or No based on current information.
                You do not produce forecasts yourself."""

        if self.simulation_time:
            system_prompt = (
                system_prompt
                + " The date is "
                + self.simulation_time.strftime("%m/%d/%Y")
                + ". Do not use any information from after this date and remove them from the output."
            )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "return_citations": True,
        }
        if self.simulation_time:
            payload["search_before_date_filter"] = self.simulation_time.strftime(
                "%m/%d/%Y"
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = (
                            result.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )

                        if self.simulation_time:
                            client = self.client

                            agent = AssistantAgent(
                                name="parser_agent",
                                model_client=client,
                                system_message="You are a helpful assistant that copys and pastes the exact content, only stripping out content that is clearly disallowed like it is very clear that information was leaked after the simulation time (but the output should have the same format and content as the input but maybe with some information stripped out)",
                            )
                            # stri out content after simulation time
                            task = f"Strip out all any information in the content clearly leaked after {self.simulation_time.strftime('%m/%d/%Y')} (but output all of the rest of the content exactly): {content}"
                            agent_result = await agent.run(task=task)
                            content = agent_result.messages[-1].content
                        citations = result["citations"]
                        output = {
                            "success": True,
                            "analysis": content,
                            "citations": citations,
                        }
                        if self.caching:
                            with cache_file.open("w") as f:
                                json.dump(output, f)
                        return output
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Perplexity API error {response.status}: {error_text}"
                        )
                        return {"success": False, "error": error_text}
        except Exception as e:
            logger.error(f"Error calling Perplexity: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def call_asknews(
        self, query: str, n_articles: int = 10, reasoning: str = "No reasoning provided"
    ) -> str:
        """Call AskNews API to get news articles, respecting the simulation time."""
        cache_file = None
        if self.caching:
            cache_key = ("asknews", str(self.simulation_time), query, n_articles)
            cache_file = self._get_cache_filepath(cache_key)

            if cache_file.exists():
                logger.info(
                    f"Returning cached result for call_asknews(query='{query}')"
                )
                with cache_file.open("r") as f:
                    return json.load(f)

        logger.info(
            f"TOOL CALL: call_asknews(query='{query}', reasoning='{reasoning}', simulation_time='{self.simulation_time}')"
        )
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "call_asknews called without reasoning - this reduces analysis quality"
            )
        client_id = os.getenv("ASKNEWS_CLIENT_ID")
        client_secret = os.getenv("ASKNEWS_SECRET")
        if not client_id or not client_secret:
            logger.error("ASKNEWS credentials not found, unable to proceed.")
            return {
                "success": False,
                "error": "ASKNEWS credentials are required but not set.",
            }

        try:
            from asknews_sdk import AsyncAskNewsSDK

            async with AsyncAskNewsSDK(
                client_id=client_id, client_secret=client_secret, scopes={"news"}
            ) as ask:
                search_params = {
                    "query": query,
                    "n_articles": n_articles,
                    "return_type": "both",
                }
                if self.simulation_time:
                    search_params["start_timestamp"] = int(
                        (self.simulation_time - pd.Timedelta(days=2)).timestamp()
                    )
                    search_params["end_timestamp"] = int(
                        self.simulation_time.timestamp()
                    )
                    search_params["historical"] = True

                response = await ask.news.search_news(**search_params)
                try:
                    dicts = response.as_dicts

                    # Format the list of dictionaries into the desired string
                    response = format_news_objects_for_llm(dicts)
                except Exception as e:
                    response = response.as_string

                if self.caching:
                    with cache_file.open("w") as f:
                        json.dump(response, f)
                return response
        except Exception as e:
            logger.error(f"Error calling AskNews: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


# --- Kalshi Tools ---


class KalshiTools:
    """
    A class to encapsulate all supported Kalshi API read-only tools.
    It operates on a simulator that uses real historical data.
    Uses official Kalshi API parameter schemas for consistency.
    """

    def __init__(self, kalshi_simulator: KalshiAPISimulator):
        self.simulator = kalshi_simulator
        self._trade_lock = threading.Lock()

    # --- Kalshi Data Tools ---
    def get_events(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        cursor: Optional[str] = None,
        with_nested_markets: bool = False,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        """
        Retrieves a list of events, which are containers for markets, with pagination support.

        This method provides access to Kalshi events with comprehensive filtering and
        pagination capabilities. It supports both modern offset-based pagination and
        legacy cursor-based pagination for backward compatibility.

        Args:
            limit (int): Maximum number of results to return per page.
                        Default: 20. Recommended range: 10-100 for optimal performance.
            offset (int): Number of results to skip for pagination.
                         Default: 0. Used for offset-based pagination to traverse large datasets.
            status (Optional[str]): Filter events by status ('open', 'closed', 'all').
                                   Default: None (returns events of all statuses).
            series_ticker (Optional[str]): Filter events by series ticker.
                                          Default: None (no series filter applied).
            cursor (Optional[str]): Legacy pagination cursor from previous response.
                                   Default: None. Maintained for backward compatibility.
            with_nested_markets (bool): Include full markets array within each event.
                                       Default: False. When True, provides complete market data.
            reasoning (str): Explanation for why this API call is being made.
                           Default: "No reasoning provided". Used for analysis quality tracking.

        Returns:
            Dict[str, Any]: Response containing:
                - 'events': List of event objects (containers for related markets)
                - 'total': Total count of available events (before pagination)
                - 'next_offset': Next offset value if more results exist
                - 'cursor': Legacy cursor (always None in current implementation)

        Example:
            # Basic pagination - get first 20 events
            response = kalshi_tools.get_events(
                limit=20,
                offset=0,
                reasoning="Initial exploration of available prediction events"
            )

            # Get next page using offset
            if 'next_offset' in response:
                next_page = kalshi_tools.get_events(
                    limit=20,
                    offset=response['next_offset'],
                    reasoning="Continue paginating through events"
                )

            # Filter with nested markets for comprehensive analysis
            election_events = kalshi_tools.get_events(
                limit=10,
                offset=0,
                series_ticker='ELECTION2024',
                with_nested_markets=True,
                reasoning="Analyze election prediction markets with full market details"
            )
        """

        logger.info(
            f"TOOL CALL: get_events(limit={limit}, offset={offset}, status='{status}', series_ticker='{series_ticker}', cursor='{cursor}', with_nested_markets={with_nested_markets}, reasoning='{reasoning}')"
        )
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "get_events called without reasoning - this reduces analysis quality"
            )

        # Convert to API parameters
        api_params = {
            "limit": limit,
            "offset": offset,
            "series_ticker": series_ticker,
            "cursor": cursor,
            "with_nested_markets": with_nested_markets,
        }
        if status and status != "all":
            api_params["status"] = status

        # Remove None values
        api_params = {k: v for k, v in api_params.items() if v is not None}

        return self.simulator.get_events(**api_params)

    def get_markets(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        cursor: Optional[str] = None,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        """
        Retrieves a list of prediction markets with comprehensive filtering and pagination support.

        This method provides access to Kalshi prediction markets with flexible filtering
        and pagination capabilities. It supports both modern offset-based pagination and
        legacy cursor-based pagination for backward compatibility.

        Args:
            limit (int): Maximum number of results to return per page.
                        Default: 20. Recommended range: 10-50 for optimal performance.
            offset (int): Number of results to skip for pagination.
                         Default: 0. Used for offset-based pagination to traverse large datasets.
            status (Optional[str]): Filter markets by status ('open', 'closed', 'all').
                                   Default: None (returns only currently open markets).
            series_ticker (Optional[str]): Filter markets by series ticker.
                                          Default: None (no series filter applied).
            event_ticker (Optional[str]): Filter markets by parent event ticker.
                                         Default: None (no event filter applied).
            cursor (Optional[str]): Legacy pagination cursor from previous response.
                                   Default: None. Maintained for backward compatibility.
            reasoning (str): Explanation for why this API call is being made.
                           Default: "No reasoning provided". Used for analysis quality tracking.

        Returns:
            Dict[str, Any]: Response containing:
                - 'markets': List of market objects with current pricing and volume data
                - 'total': Total count of available markets (before pagination)
                - 'next_offset': Next offset value if more results exist
                - 'cursor': Legacy cursor (always None in current implementation)

        Example:
            # Basic pagination - get first 20 markets
            response = kalshi_tools.get_markets(
                limit=20,
                offset=0,
                reasoning="Initial exploration of available prediction markets"
            )

            # Get next page using offset
            if 'next_offset' in response:
                next_page = kalshi_tools.get_markets(
                    limit=20,
                    offset=response['next_offset'],
                    reasoning="Continue paginating through markets"
                )

            # Filter markets by event with pagination
            election_markets = kalshi_tools.get_markets(
                limit=15,
                offset=0,
                event_ticker='ELECTION2024-PRES',
                status='open',
                reasoning="Analyze open presidential election markets for trading opportunities"
            )
        """

        logger.info(
            f"TOOL CALL: get_markets(limit={limit}, offset={offset}, status='{status}', series_ticker='{series_ticker}', event_ticker='{event_ticker}', cursor='{cursor}', reasoning='{reasoning}')"
        )
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "get_markets called without reasoning - this reduces analysis quality"
            )

        # Convert to API parameters
        api_params = {
            "limit": limit,
            "offset": offset,
            "series_ticker": series_ticker,
            "event_ticker": event_ticker,
            "cursor": cursor,
        }
        if status and status != "all":
            api_params["status"] = status

        # Remove None values
        api_params = {k: v for k, v in api_params.items() if v is not None}

        return self.simulator.get_markets(**api_params)

    def get_market(
        self, ticker: str, reasoning: str = "No reasoning provided"
    ) -> Dict[str, Any]:
        """Retrieves detailed information for a single market."""
        logger.info(
            f"TOOL CALL: get_market(ticker='{ticker}', reasoning='{reasoning}')"
        )
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "get_market called without reasoning - this reduces analysis quality"
            )
        return self.simulator.get_market(ticker=ticker)

    def get_event(
        self,
        event_ticker: str,
        with_nested_markets: bool = False,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        """
        Retrieves detailed information for a single event by its ticker.

        An event represents a real-world occurrence that can be traded on, such as an
        election, sports game, or economic indicator release. Events contain one or more
        markets where users can place trades on different outcomes.

        Args:
            event_ticker: The event ticker to retrieve information for
            with_nested_markets: If true, markets are included within the event object.
                               If false (default), markets are returned as a separate top-level field.
            reasoning: Explanation for why this API call is being made

        Returns:
            Dict containing event details including series_ticker and optionally nested markets
        """
        logger.info(
            f"TOOL CALL: get_event(event_ticker='{event_ticker}', with_nested_markets={with_nested_markets}, reasoning='{reasoning}')"
        )
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "get_event called without reasoning - this reduces analysis quality"
            )

        # For the simulator, we need to implement this by finding the event from get_events
        # Since the simulator might not have a direct get_event method
        try:
            # Try to get the event directly if the simulator supports it
            return self.simulator.get_event(
                event_ticker=event_ticker, with_nested_markets=with_nested_markets
            )
        except AttributeError:
            # Fallback: search through events if direct method doesn't exist
            events_result = self.get_events(
                limit=1000, reasoning="Finding specific event"
            )
            if events_result.get("events"):
                for event in events_result["events"]:
                    if event.get("event_ticker") == event_ticker:
                        if with_nested_markets:
                            # Get markets for this event
                            markets_result = self.get_markets(
                                event_ticker=event_ticker,
                                reasoning="Getting nested markets for event",
                            )
                            event["markets"] = markets_result.get("markets", [])
                            return {
                                "event": event,
                                "markets": markets_result.get("markets", []),
                            }
                        else:
                            markets_result = self.get_markets(
                                event_ticker=event_ticker,
                                reasoning="Getting markets for event",
                            )
                            return {
                                "event": event,
                                "markets": markets_result.get("markets", []),
                            }

            return {"success": False, "error": f"Event {event_ticker} not found"}

    def get_market_candlesticks(
        self,
        ticker: str,
        limit: int = 1000,
        offset: int = 0,
        start_time: Optional[str] = None,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        """Retrieves historical candlestick data for a market up to the simulation time.

        Args:
            ticker: Market ticker to get candlesticks for
            limit: Maximum number of results (default: 1000)
            offset: Number of results to skip (default: 0)
            start_time: Start time for data range (ISO format string)
            reasoning: Reasoning for the API call
        """
        logger.info(
            f"TOOL CALL: get_market_candlesticks(ticker='{ticker}', limit={limit}, offset={offset}, start_time='{start_time}', reasoning='{reasoning}')"
        )
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "get_market_candlesticks called without reasoning - this reduces analysis quality"
            )

        # Convert to API parameters
        api_params = {
            "ticker": ticker,
            "limit": limit,
            "offset": offset,
            "start_time": start_time,
        }

        # Remove None values
        api_params = {k: v for k, v in api_params.items() if v is not None}

        return self.simulator.get_market_candlesticks(**api_params)

    def create_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        type: str,
        price: Optional[int] = None,
        client_order_id: Optional[str] = None,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        with self._trade_lock:
            logger.info(
                f"TOOL CALL: create_order(ticker='{ticker}', side='{side}', action='{action}', "
                f"count={count}, type='{type}', price={price}, reasoning='{reasoning}')"
            )
            if not reasoning or reasoning.strip() == "":
                logger.warning(
                    "create_order called without reasoning - this reduces analysis quality"
                )

            # Risk Management: Force limit orders for all buy actions
            if action == "buy" and type != "limit":
                return {
                    "success": False,
                    "error": "Market orders are not allowed for buy actions. Please use limit orders with a specific price to control risk.",
                }

            # Generate client_order_id if not provided
            if not client_order_id:
                import time

                client_order_id = f"order-{int(time.time() * 1000)}"

            # Build parameters
            api_params = {
                "ticker": ticker,
                "client_order_id": client_order_id,
                "side": side,
                "action": action,
                "count": count,
                "type": type,
            }

            # Add price for limit orders
            if type == "limit":
                if price is None:
                    return {
                        "success": False,
                        "error": "Price is required for limit orders",
                    }
                api_params["price"] = price

            return self.simulator.create_order(**api_params)

    def cancel_order(
        self, order_id: str, reasoning: str = "No reasoning provided"
    ) -> Dict[str, Any]:
        with self._trade_lock:
            logger.info(
                f"TOOL CALL: cancel_order(order_id='{order_id}', reasoning='{reasoning}')"
            )
            if not reasoning or reasoning.strip() == "":
                logger.warning(
                    "cancel_order called without reasoning - this reduces analysis quality"
                )

            return self.simulator.cancel_order(order_id)

    def get_orders(
        self,
        ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        status: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        """
        Retrieves all orders for the member with comprehensive filtering and pagination support.

        This method provides access to the user's order history and current orders with
        flexible filtering capabilities and pagination support.

        Args:
            ticker (Optional[str]): Restricts the response to orders in a single market.
                                   Default: None (returns orders from all markets).
            event_ticker (Optional[str]): Restricts the response to orders in a single event.
                                         Default: None (returns orders from all events).
            min_ts (Optional[int]): Restricts the response to orders after a timestamp,
                                   formatted as a Unix Timestamp. Default: None.
            max_ts (Optional[int]): Restricts the response to orders before a timestamp,
                                   formatted as a Unix Timestamp. Default: None.
            status (Optional[str]): Restricts the response to orders that have a certain status:
                                   'resting', 'canceled', or 'executed'. Default: None (all statuses).
            cursor (Optional[str]): The Cursor represents a pointer to the next page of records
                                   in the pagination. Use the value returned from the previous response
                                   to get the next page. Default: None.
            limit (int): Parameter to specify the number of results per page.
                        Default: 100. Recommended range: 10-100 for optimal performance.
            reasoning (str): Explanation for why this API call is being made.
                           Default: "No reasoning provided". Used for analysis quality tracking.

        Returns:
            Dict[str, Any]: Response containing:
                - 'orders': List of order objects with details like status, fills, prices
                - 'cursor': Pagination cursor for next page (empty string if no more pages)

        Example:
            # Get all orders
            response = kalshi_tools.get_orders(
                reasoning="Review all trading history for performance analysis"
            )

            # Get orders for specific market
            market_orders = kalshi_tools.get_orders(
                ticker='PRES24-HARRIS',
                reasoning="Analyze trading activity in Harris prediction market"
            )

            # Get only resting (open) orders
            open_orders = kalshi_tools.get_orders(
                status='resting',
                reasoning="Check current open positions and pending orders"
            )

            # Paginate through orders
            if response.get('cursor'):
                next_page = kalshi_tools.get_orders(
                    cursor=response['cursor'],
                    limit=50,
                    reasoning="Continue reviewing order history"
                )
        """

        logger.info(
            f"TOOL CALL: get_orders(ticker='{ticker}', event_ticker='{event_ticker}', "
            f"min_ts={min_ts}, max_ts={max_ts}, status='{status}', cursor='{cursor}', "
            f"limit={limit}, reasoning='{reasoning}')"
        )
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "get_orders called without reasoning - this reduces analysis quality"
            )

        # Build API parameters
        api_params = {
            "ticker": ticker,
            "event_ticker": event_ticker,
            "min_ts": min_ts,
            "max_ts": max_ts,
            "status": status,
            "cursor": cursor,
            "limit": limit,
        }

        # Remove None values
        api_params = {k: v for k, v in api_params.items() if v is not None}

        return self.simulator.get_orders(**api_params)

    def get_balance(self, reasoning: str = "No reasoning provided") -> Dict[str, Any]:
        """
        Retrieves the member's available balance.

        This method provides access to the user's current account balance, which represents
        the amount available for trading. The balance value is returned in cents.

        Args:
            reasoning (str): Explanation for why this API call is being made.
                           Default: "No reasoning provided". Used for analysis quality tracking.

        Returns:
            Dict[str, Any]: Response containing:
                - 'balance': Member's available balance in cents. This represents the amount
                           available for trading.

        Example:
            # Check current balance
            balance_response = kalshi_tools.get_balance(
                reasoning="Check available funds before placing large order"
            )

            balance_cents = balance_response['balance']
            balance_dollars = balance_cents / 100
            print(f"Available balance: ${balance_dollars:.2f}")
        """

        logger.info(f"TOOL CALL: get_balance(reasoning='{reasoning}')")
        if not reasoning or reasoning.strip() == "":
            logger.warning(
                "get_balance called without reasoning - this reduces analysis quality"
            )

        return self.simulator.get_balance()


# --- Kalshi API Tools (Live Demo API) ---


class KalshiAPITools:
    """
    A class to encapsulate all supported Kalshi API tools using the live API.
    Uses official Kalshi API parameter schemas for consistency.
    """

    def __init__(self):
        # Use demo API credentials for testing
        self.api_id = os.getenv("KALSHI_DEMO_API_ID")
        private_key_str = os.getenv("KALSHI_DEMO_PRIVATE_KEY")
        self.client = None
        private_key = None

        if self.api_id:
            # First, try to load the private key from the environment variable
            if private_key_str:
                try:
                    # The key in the .env file might have escaped characters, so we fix them
                    formatted_key = (
                        private_key_str.replace('\\"', "")
                        .replace("\\\\", "\\")
                        .replace("\\ ", " ")
                        .replace("\\n", "\n")
                    )
                    private_key = serialization.load_pem_private_key(
                        formatted_key.encode(),
                        password=None,
                        backend=default_backend(),
                    )
                    logger.info(
                        "Successfully loaded private key from KALSHI_DEMO_PRIVATE_KEY env var"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to load private key from env var: {e}. Falling back to file."
                    )
                    private_key = None  # Ensure key is None if loading from env fails

            # If the key wasn't loaded from env, fall back to the .pem file
            if not private_key:
                try:
                    private_key_path = "kalshi_demo_private_key.pem"
                    if os.path.exists(private_key_path):
                        with open(private_key_path, "rb") as key_file:
                            private_key = serialization.load_pem_private_key(
                                key_file.read(),
                                password=None,
                                backend=default_backend(),
                            )
                        logger.info(
                            "Successfully loaded private key from file 'kalshi_demo_private_key.pem'"
                        )
                    else:
                        logger.error(
                            "Neither KALSHI_DEMO_PRIVATE_KEY env var nor 'kalshi_demo_private_key.pem' file were found."
                        )
                except Exception as e:
                    logger.error(f"Failed to load private key from file: {e}")

            # If a private key was successfully loaded (from either source), create the client
            if private_key:
                self.client = KalshiHttpClient(
                    key_id=self.api_id,
                    private_key=private_key,
                    environment=Environment.DEMO,
                )
                logger.info(
                    "Successfully initialized Kalshi API client with authentication"
                )
            else:
                logger.error(
                    "Kalshi API client could not be initialized because no valid private key was found."
                )
        else:
            logger.error(
                "KALSHI_DEMO_API_ID not found in environment variables. Cannot initialize Kalshi Demo API client."
            )

    def _api_call_wrapper(self, func, *args, **kwargs):
        """A wrapper to handle API calls and exceptions."""
        if not self.client:
            return {"success": False, "error": "Kalshi API client not initialized"}
        try:
            # The underlying client methods already return a dict
            return func(*args, **kwargs)
        except Exception as e:
            status_code = getattr(e, "response", None) and getattr(
                e.response, "status_code", None
            )
            error_message = f"Kalshi API call failed: {e}"
            if status_code:
                error_message += f" (Status: {status_code})"
            logger.error(error_message)

            response = {"success": False, "error": str(e)}
            if status_code:
                response["status_code"] = status_code
            return response

    def get_events(
        self,
        limit: int = 20,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        cursor: Optional[str] = None,
        with_nested_markets: bool = False,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        logger.info(
            f"TOOL CALL: KalshiAPITools.get_events(limit={limit}, status='{status}', series_ticker='{series_ticker}', cursor='{cursor}', with_nested_markets={with_nested_markets}, reasoning='{reasoning}')"
        )
        params = {
            "limit": limit,
            "status": status,
            "series_ticker": series_ticker,
            "cursor": cursor,
            "with_nested_markets": with_nested_markets,
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._api_call_wrapper(
            self.client.get, "/trade-api/v2/events", params=params
        )

    def get_markets(
        self,
        limit: int = 20,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        cursor: Optional[str] = None,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        logger.info(
            f"TOOL CALL: KalshiAPITools.get_markets(limit={limit}, status='{status}', series_ticker='{series_ticker}', event_ticker='{event_ticker}', cursor='{cursor}', reasoning='{reasoning}')"
        )
        params = {
            "limit": limit,
            "status": status,
            "series_ticker": series_ticker,
            "event_ticker": event_ticker,
            "cursor": cursor,
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._api_call_wrapper(
            self.client.get, "/trade-api/v2/markets", params=params
        )

    def get_market(
        self, ticker: str, reasoning: str = "No reasoning provided"
    ) -> Dict[str, Any]:
        logger.info(
            f"TOOL CALL: KalshiAPITools.get_market(ticker='{ticker}', reasoning='{reasoning}')"
        )
        return self._api_call_wrapper(
            self.client.get, f"/trade-api/v2/markets/{ticker}"
        )

    def get_event(
        self,
        event_ticker: str,
        with_nested_markets: bool = False,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        logger.info(
            f"TOOL CALL: KalshiAPITools.get_event(event_ticker='{event_ticker}', with_nested_markets={with_nested_markets}, reasoning='{reasoning}')"
        )
        params = {"with_nested_markets": with_nested_markets}
        return self._api_call_wrapper(
            self.client.get, f"/trade-api/v2/events/{event_ticker}", params=params
        )

    def get_market_candlesticks(
        self,
        ticker: str,
        limit: int = 1000,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        period_interval: int = 60,  # Default to 1-hour intervals
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        logger.info(
            f"TOOL CALL: KalshiAPITools.get_market_candlesticks(ticker='{ticker}', limit={limit}, start_ts='{start_ts}', end_ts='{end_ts}', reasoning='{reasoning}')"
        )

        market_response = self.get_market(
            ticker, reasoning="Get event_ticker for candlesticks"
        )
        if not market_response.get("market"):
            return {
                "success": False,
                "error": f"Could not retrieve market details for {ticker}: {market_response.get('error')}",
            }

        event_ticker = market_response["market"].get("event_ticker")
        if not event_ticker:
            return {
                "success": False,
                "error": f"Could not find event_ticker for market {ticker}",
            }

        event_response = self.get_event(
            event_ticker, reasoning="Get series_ticker for candlesticks"
        )
        if not event_response.get("event"):
            return {
                "success": False,
                "error": f"Could not retrieve event details for {event_ticker}: {event_response.get('error')}",
            }

        series_ticker = event_response["event"].get("series_ticker")
        if not series_ticker:
            return {
                "success": False,
                "error": f"Could not find series_ticker for event {event_ticker}",
            }

        params = {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "limit": limit,
            "period_interval": period_interval,
        }
        params = {k: v for k, v in params.items() if v is not None}

        return self._api_call_wrapper(
            self.client.get,
            f"/trade-api/v2/series/{series_ticker}/markets/{ticker}/candlesticks",
            params=params,
        )

    def create_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        type: str,
        price: Optional[int] = None,
        client_order_id: Optional[str] = None,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        logger.info(
            f"TOOL CALL: KalshiAPITools.create_order(ticker='{ticker}', side='{side}', action='{action}', "
            f"count={count}, type='{type}', price={price}, client_order_id='{client_order_id}', reasoning='{reasoning}')"
        )

        if not client_order_id:
            client_order_id = f"order-{int(time.time() * 1000)}"

        body = {
            "ticker": ticker,
            "client_order_id": client_order_id,
            "side": side,
            "action": action,
            "count": count,
            "type": type,
        }
        if price is not None:
            if side == "yes":
                body["yes_price"] = price
            else:
                body["no_price"] = price
        else:
            # For market orders, we need to specify prices
            # Use reasonable default prices for market orders
            if side == "yes":
                body["yes_price"] = 1  # 1 cent minimum
            else:
                body["no_price"] = 1  # 1 cent minimum

        print(f"🔍 Creating order with body: {body}")
        result = self._api_call_wrapper(
            self.client.post, "/trade-api/v2/portfolio/orders", body=body
        )
        print(f"🔍 Order creation result: {result}")
        return result

    def cancel_order(
        self, order_id: str, reasoning: str = "No reasoning provided"
    ) -> Dict[str, Any]:
        logger.info(
            f"TOOL CALL: KalshiAPITools.cancel_order(order_id='{order_id}', reasoning='{reasoning}')"
        )
        return self._api_call_wrapper(
            self.client.delete, f"/trade-api/v2/portfolio/orders/{order_id}"
        )

    def get_orders(
        self,
        ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        status: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
        reasoning: str = "No reasoning provided",
    ) -> Dict[str, Any]:
        logger.info(
            f"TOOL CALL: KalshiAPITools.get_orders(ticker='{ticker}', event_ticker='{event_ticker}', "
            f"min_ts={min_ts}, max_ts={max_ts}, status='{status}', cursor='{cursor}', "
            f"limit={limit}, reasoning='{reasoning}')"
        )
        valid_statuses = ["resting", "canceled", "executed"]
        if status and status not in valid_statuses:
            return {
                "success": False,
                "error": f"Invalid status '{status}'. Valid options are: {valid_statuses}",
            }
        params = {
            "ticker": ticker,
            "event_ticker": event_ticker,
            "min_ts": min_ts,
            "max_ts": max_ts,
            "status": status,
            "cursor": cursor,
            "limit": limit,
        }
        params = {k: v for k, v in params.items() if v is not None}
        return self._api_call_wrapper(
            self.client.get, "/trade-api/v2/portfolio/orders", params=params
        )

    def get_balance(self, reasoning: str = "No reasoning provided") -> Dict[str, Any]:
        logger.info(f"TOOL CALL: KalshiAPITools.get_balance(reasoning='{reasoning}')")
        return self._api_call_wrapper(
            self.client.get, "/trade-api/v2/portfolio/balance"
        )

    def get_positions(self, reasoning: str = "No reasoning provided") -> Dict[str, Any]:
        """
        Get current positions from the Kalshi API.

        Args:
            reasoning: Explanation for why this API call is being made.

        Returns:
            Dict containing current positions with ticker, side, and quantity information.
        """
        logger.info(f"TOOL CALL: KalshiAPITools.get_positions(reasoning='{reasoning}')")
        return self._api_call_wrapper(
            self.client.get, "/trade-api/v2/portfolio/positions"
        )


# --- Forecast Logging Tools ---

# Global storage for forecasts (in production, this would be a database)
_forecast_storage = []


def log_forecast(
    question: str,
    forecast: float,
    reasoning: str,
    confidence: Optional[float] = None,
    current_data: Optional[Dict[str, Any]] = None,
    forecast_type: str = "probability",
    forecast_range: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Logs a forecast with question, prediction, reasoning, and supporting data.
    Supports both probability and numerical forecasts.

    Args:
        question: The question being forecasted
        forecast: The forecast value
        reasoning: Detailed reasoning for the forecast
        confidence: Optional confidence level in the forecast (1-5 scale)
        current_data: Optional current market/research data supporting the forecast
        forecast_type: Type of forecast - "probability" (0.0-1.0) or "numerical" (any range)
        forecast_range: Optional dict with "min" and "max" keys for numerical forecasts
    """
    logger.info(
        f"TOOL CALL: log_forecast(question='{question}', forecast={forecast}, type='{forecast_type}', reasoning='{reasoning[:100]}...')"
    )

    # Validate forecast based on type
    if forecast_type == "probability":
        if not (0.0 <= forecast <= 1.0):
            return {
                "success": False,
                "error": "Probability forecast must be between 0.0 and 1.0. Use forecast_type='numerical' for other ranges.",
            }
    elif forecast_type == "numerical":
        if forecast_range:
            min_val = forecast_range.get("min")
            max_val = forecast_range.get("max")
            if min_val is not None and forecast < min_val:
                return {
                    "success": False,
                    "error": f"Numerical forecast {forecast} is below minimum range {min_val}",
                }
            if max_val is not None and forecast > max_val:
                return {
                    "success": False,
                    "error": f"Numerical forecast {forecast} is above maximum range {max_val}",
                }
    else:
        return {
            "success": False,
            "error": "forecast_type must be either 'probability' or 'numerical'",
        }

    # Validate confidence if provided
    if confidence is not None and not (1.0 <= confidence <= 5.0):
        return {
            "success": False,
            "error": "Confidence must be between 1.0 and 5.0 (if provided)",
        }

    forecast_entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "forecast": forecast,
        "forecast_type": forecast_type,
        "forecast_range": forecast_range,
        "reasoning": reasoning,
        "confidence": confidence,
        "current_data": current_data or {},
    }

    _forecast_storage.append(forecast_entry)

    logger.info(
        f"Forecast logged: {question} -> {forecast} ({forecast_type}, confidence: {confidence})"
    )
    return {
        "success": True,
        "forecast_id": len(_forecast_storage) - 1,
        "message": f"Forecast logged for: {question}",
        "forecast_type": forecast_type,
    }


def get_forecasts(
    question_filter: Optional[str] = None,
    limit: Optional[int] = None,
    reasoning: str = "No reasoning provided",
) -> Dict[str, Any]:
    """
    Returns all previously made forecasts, with optional filters.

    Args:
        question_filter: Optional string to filter questions containing this text
        limit: Optional limit on number of forecasts to return
        reasoning: Reasoning for why these forecasts are being retrieved
    """
    logger.info(
        f"TOOL CALL: get_forecasts(question_filter='{question_filter}', limit={limit}, reasoning='{reasoning}')"
    )
    if not reasoning or reasoning.strip() == "":
        logger.warning(
            "get_forecasts called without reasoning - this reduces analysis quality"
        )

    forecasts = _forecast_storage.copy()

    # Apply question filter if provided
    if question_filter:
        forecasts = [
            f for f in forecasts if question_filter.lower() in f["question"].lower()
        ]

    # Apply limit if provided
    if limit and limit > 0:
        forecasts = forecasts[-limit:]  # Get most recent forecasts

    return {"success": True, "forecasts": forecasts, "total_count": len(forecasts)}


# --- Utility Tools ---


def calculator(
    expression: str, reasoning: str = "No reasoning provided"
) -> Dict[str, Any]:
    """
    A robust calculator using SymPy for mathematical expressions.

    This calculator can handle:
    - Basic arithmetic: +, -, *, /, **, %
    - Mathematical functions: sin, cos, tan, log, exp, sqrt, etc.
    - Variables and symbolic expressions
    - Complex mathematical formulas
    - Scientific notation

    Args:
        expression: The mathematical expression to evaluate (any valid SymPy expression)
        reasoning: Reasoning for why this calculation is needed
    """
    logger.info(
        f"TOOL CALL: calculator(expression='{expression}', reasoning='{reasoning}')"
    )
    if not reasoning or reasoning.strip() == "":
        logger.warning(
            "calculator called without reasoning - this reduces analysis quality"
        )
    try:
        # Use sympy to safely evaluate the expression
        # This handles various mathematical operations and functions
        # It also prevents code injection and potential security issues
        # from direct eval()

        # Create a local namespace with common mathematical constants and functions
        # This ensures that 'e', 'pi', etc. are treated as mathematical constants
        # rather than symbols
        local_dict = {
            "e": sympy.E,
            "pi": sympy.pi,
            "E": sympy.E,
            "Pi": sympy.pi,
            "sin": sympy.sin,
            "cos": sympy.cos,
            "tan": sympy.tan,
            "sqrt": sympy.sqrt,
            "log": sympy.log,
            "exp": sympy.exp,
            "abs": sympy.Abs,
        }

        result = sympy.sympify(expression, locals=local_dict)

        # Check if the result is a numeric value that can be evaluated
        try:
            # Try to evaluate to a numeric value using SymPy's N() function
            # This handles constants like pi, e, etc. properly
            numeric_result = sympy.N(result)
            if numeric_result.is_real:
                result_str = float(numeric_result)
            else:
                result_str = str(result)
        except (AttributeError, TypeError, ValueError):
            # If evaluation fails, return as string
            result_str = str(result)

        log_entry = {
            "tool": "calculator",
            "expression": expression,
            "result": result_str,
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat(),
        }
        logger.info(f"Calculator result logged: {log_entry}")
        return {"success": True, "result": result_str, "reasoning": reasoning}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- Tool Creation ---


def create_all_tools(
    kalshi_tools: KalshiTools, research_tools: ResearchTools
) -> Dict[str, callable]:
    """
    Creates a dictionary of all available tools for the agent,
    binding the methods of the KalshiTools and ResearchTools instances.
    """
    # --- Tool Registration ---
    all_tools = {
        # Kalshi Data Tools
        "get_events": kalshi_tools.get_events,
        "get_markets": kalshi_tools.get_markets,
        "get_market": kalshi_tools.get_market,
        "get_event": kalshi_tools.get_event,
        "get_market_candlesticks": kalshi_tools.get_market_candlesticks,
        "get_orders": kalshi_tools.get_orders,
        "get_balance": kalshi_tools.get_balance,
        # Research Tools
        "call_perplexity": research_tools.call_perplexity,
        "call_asknews": research_tools.call_asknews,
        "url_query": research_tools.url_query,
        # Forecast Logging Tools
        "log_forecast": log_forecast,
        "get_forecasts": get_forecasts,
        # Utility Tools
        "calculator": calculator,
    }
    return all_tools


# --- Tool Testing ---


async def test_tools():
    """A test suite for the available agent tools."""
    print("--- Running Tool Test Suite ---")

    # Initialize the Kalshi simulator for a fixed point in time
    simulation_time = pd.Timestamp("2025-06-15 12:00:00")
    try:
        kalshi_simulator = create_kalshi_simulator(simulation_time=simulation_time)
    except FileNotFoundError as e:
        print(f"ERROR: Could not run tests. {e}")
        print(
            "Please ensure 'kalshi_june_2025_markets.csv' and 'kalshi_june_2025_data.csv' are present."
        )
        return

    kalshi_tools_instance = KalshiTools(kalshi_simulator)
    research_tools_instance = ResearchTools(simulation_time)

    # --- Test Kalshi API Tools (Live Demo) ---
    print("\n--- Testing Kalshi API Tools (Live Demo) ---")
    kalshi_api_tools = KalshiAPITools()
    if not kalshi_api_tools.api_id:
        print("KALSHI_API_ID not set, skipping live API tests.")
    else:
        # Test get_events
        api_events_result = kalshi_api_tools.get_events(limit=5)
        if api_events_result.get("success"):
            print("KalshiAPITools.get_events: OK")

            # Test get_markets
            api_markets_result = kalshi_api_tools.get_markets(limit=5)
            if api_markets_result.get("success"):
                print("KalshiAPITools.get_markets: OK")

                markets_data = api_markets_result.get("data", {}).get("markets", [])
                if markets_data:
                    market_ticker = markets_data[0]["ticker"]
                    # Test get_market
                    api_market_result = kalshi_api_tools.get_market(
                        ticker=market_ticker
                    )
                    if api_market_result.get("success"):
                        print("KalshiAPITools.get_market: OK")

                    # Test get_market_candlesticks
                    api_candlesticks_result = kalshi_api_tools.get_market_candlesticks(
                        ticker=market_ticker, limit=5
                    )
                    if api_candlesticks_result.get("success"):
                        print("KalshiAPITools.get_market_candlesticks: OK")

            # Test get_orders
            api_orders_result = kalshi_api_tools.get_orders(limit=5)
            if api_orders_result.get("success"):
                print("KalshiAPITools.get_orders: OK")

            # Test get_balance
            api_balance_result = kalshi_api_tools.get_balance()
            if api_balance_result.get("success"):
                print("KalshiAPITools.get_balance: OK")
        else:
            print(
                f"Kalshi API returned error, skipping remaining API tests: {api_events_result.get('error')}"
            )

    # Session is handled internally, no need to close manually

    # --- Test Kalshi Data Tools ---
    print("\n--- Testing Kalshi Data Tools (Simulator) ---")
    events_result = kalshi_tools_instance.get_events()
    assert "events" in events_result and events_result["events"], "get_events failed"
    print("get_events: OK")

    event_ticker = events_result["events"][0]["event_ticker"]
    markets_result = kalshi_tools_instance.get_markets(event_ticker=event_ticker)
    assert (
        "markets" in markets_result and markets_result["markets"]
    ), "get_markets failed"
    print("get_markets: OK")

    market_ticker = markets_result["markets"][0]["ticker"]
    market_result = kalshi_tools_instance.get_market(ticker=market_ticker)
    assert (
        "market" in market_result and "error" not in market_result
    ), "get_market failed"
    print("get_market: OK")

    candlesticks_result = kalshi_tools_instance.get_market_candlesticks(
        ticker=market_ticker
    )
    assert "history" in candlesticks_result, "get_market_candlesticks failed"
    print("get_market_candlesticks: OK")

    # Test portfolio tools
    orders_result = kalshi_tools_instance.get_orders()
    assert "orders" in orders_result, "get_orders failed"
    print("get_orders: OK")

    balance_result = kalshi_tools_instance.get_balance()
    assert "balance" in balance_result, "get_balance failed"
    print("get_balance: OK")

    # Test extended get_events
    events_limit_5 = kalshi_tools_instance.get_events(limit=5, offset=0)
    assert len(events_limit_5["events"]) == 5, "Expected 5 events but got differently"

    events_offset_5 = kalshi_tools_instance.get_events(limit=5, offset=5)
    assert len(events_offset_5["events"]) <= 5, "Expected 5 or fewer events"
    assert not set(e["event_ticker"] for e in events_limit_5["events"]).intersection(
        set(e["event_ticker"] for e in events_offset_5["events"])
    ), "Duplicate events found in pagination"

    if "next_offset" in events_limit_5:
        assert events_limit_5["next_offset"] == 5, "Incorrect next_offset"

    # Test filtering with nested markets
    election_events = kalshi_tools_instance.get_events(
        limit=5, with_nested_markets=True, reasoning="Test nested markets"
    )
    assert "events" in election_events, "get_events with nested markets failed"
    for event in election_events["events"]:
        assert "markets" in event, "Nested markets not found in event"
    print("get_events with nested markets: OK")

    # --- Test Research Tools ---
    print("\n--- Testing Research Tools ---")
    query = "What are the latest developments in AI?"
    perplexity_result = await research_tools_instance.call_perplexity(query)
    assert perplexity_result.get("success"), "Perplexity API call failed"
    print("call_perplexity: OK")

    asknews_result = await research_tools_instance.call_asknews(query)
    assert "articles" in asknews_result, "AskNews API call failed"
    print("call_asknews: OK")

    # Test URL query with a real URL (e.g., a news article)
    url = "https://www.bbc.com/news/technology-60111924"
    url_query_result = await research_tools_instance.url_query(url)
    assert url_query_result.get("success"), "URL query failed"
    print("url_query: OK")

    # Test URL query with a custom query
    custom_query = "Summarize the key points from the article."
    url_query_custom_result = await research_tools_instance.url_query(
        url, query=custom_query
    )
    assert url_query_custom_result.get("success"), "Custom URL query failed"
    print("url_query with custom query: OK")

    # --- Test Forecast Logging ---
    print("\n--- Testing Forecast Logging ---")
    log_result = log_forecast(
        question="Will it rain tomorrow in New York?",
        forecast=0.7,
        reasoning="Based on weather data and analysis.",
        confidence=4.5,
        forecast_type="probability",
    )
    assert log_result.get("success"), "Logging forecast failed"
    print("log_forecast: OK")

    get_result = get_forecasts(limit=5)
    assert get_result.get("success"), "Retrieving forecasts failed"
    assert len(get_result["forecasts"]) <= 5, "Expected 5 or fewer forecasts"
    print("get_forecasts: OK")

    # --- Test Utility Tools ---
    print("\n--- Testing Utility Tools ---")

    # Test basic arithmetic
    calc_result = calculator("2 + 2 * 2")
    assert calc_result.get("success"), "Calculator tool failed"
    assert calc_result.get("result") == 6, "Calculator result is incorrect"
    print("calculator basic arithmetic: OK")

    # Test mathematical functions
    calc_result = calculator("sin(pi/2)")
    assert calc_result.get("success"), "Calculator tool failed"
    assert (
        abs(calc_result.get("result") - 1.0) < 1e-10
    ), "Calculator result is incorrect"
    print("calculator mathematical functions: OK")

    # Test complex expressions
    calc_result = calculator("sqrt(16) + log(100, 10)")
    assert calc_result.get("success"), "Calculator tool failed"
    assert calc_result.get("result") == 6.0, "Calculator result is incorrect"
    print("calculator complex expressions: OK")

    # Test symbolic expressions
    calc_result = calculator("x**2 + 2*x + 1")
    assert calc_result.get("success"), "Calculator tool failed"
    assert "x**2 + 2*x + 1" in str(
        calc_result.get("result")
    ), "Calculator symbolic result is incorrect"
    print("calculator symbolic expressions: OK")

    print("--- Tool Test Suite Complete ---")
