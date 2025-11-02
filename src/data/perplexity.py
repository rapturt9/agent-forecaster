"""Perplexity API client for web search and research."""

import os
import httpx
from typing import Any
from pydantic import BaseModel


class SearchResult(BaseModel):
    """Represents a search result from Perplexity."""

    answer: str
    sources: list[str]
    search_query: str


class PerplexityClient:
    """Client for interacting with Perplexity API."""

    BASE_URL = "https://api.perplexity.ai"

    def __init__(self, api_key: str | None = None):
        """Initialize Perplexity client.

        Args:
            api_key: Perplexity API key (defaults to PERPLEXITY_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Perplexity API key not found. Set PERPLEXITY_API_KEY environment variable."
            )

        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=60.0)

    async def search(
        self,
        query: str,
        model: str = "llama-3.1-sonar-large-128k-online",
        return_citations: bool = True,
    ) -> SearchResult:
        """Perform a web search using Perplexity.

        Args:
            query: Search query or question
            model: Perplexity model to use (default: sonar-large for better quality)
            return_citations: Whether to return source URLs

        Returns:
            SearchResult with answer and sources
        """
        messages = [
            {
                "role": "system",
                "content": "You are a helpful research assistant. Provide accurate, "
                "up-to-date information with sources."
            },
            {
                "role": "user",
                "content": query
            }
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "return_citations": return_citations,
            "return_images": False,
        }

        response = await self.client.post(
            "/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        data = response.json()

        # Extract answer
        answer = data["choices"][0]["message"]["content"]

        # Extract citations/sources
        sources = []
        if return_citations and "citations" in data:
            sources = data.get("citations", [])

        return SearchResult(
            answer=answer,
            sources=sources,
            search_query=query
        )

    async def research_question(
        self,
        question: str,
        context: str | None = None,
    ) -> str:
        """Research a forecasting question using web search.

        Args:
            question: The forecasting question
            context: Optional additional context

        Returns:
            Detailed research summary with sources
        """
        # Construct research query
        research_query = f"Research the following forecasting question with recent data and analysis: {question}"
        if context:
            research_query += f"\n\nAdditional context: {context}"

        result = await self.search(research_query)

        # Format result with sources
        output_parts = [
            f"Research for: {question}\n",
            "=" * 80,
            "\n",
            result.answer,
            "\n\n",
            "Sources:",
        ]

        for i, source in enumerate(result.sources, 1):
            output_parts.append(f"{i}. {source}")

        return "\n".join(output_parts)

    async def get_base_rates(self, topic: str) -> str:
        """Get base rate information for a forecasting topic.

        Args:
            topic: The topic to research base rates for

        Returns:
            Base rate information and historical context
        """
        query = (
            f"What are the historical base rates and frequency for: {topic}? "
            f"Include relevant statistics, trends, and historical data."
        )

        result = await self.search(query)
        return result.answer

    async def fact_check(self, claim: str) -> str:
        """Fact-check a specific claim.

        Args:
            claim: The claim to fact-check

        Returns:
            Fact-check result with sources
        """
        query = f"Fact-check this claim with recent, authoritative sources: {claim}"
        result = await self.search(query)

        output_parts = [
            f"Fact-check: {claim}\n",
            "=" * 80,
            "\n",
            result.answer,
            "\n\n",
            "Sources:",
        ]

        for i, source in enumerate(result.sources, 1):
            output_parts.append(f"{i}. {source}")

        return "\n".join(output_parts)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
