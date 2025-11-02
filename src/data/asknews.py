"""AskNews API client for fetching recent news articles."""

import os
import httpx
from datetime import datetime, timedelta
from typing import Any
from pydantic import BaseModel


class NewsArticle(BaseModel):
    """Represents a news article from AskNews."""

    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    relevance_score: float | None = None


class AskNewsClient:
    """Client for interacting with AskNews API."""

    BASE_URL = "https://api.asknews.app/v1"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        """Initialize AskNews client.

        Args:
            client_id: AskNews client ID (defaults to ASKNEWS_CLIENT_ID env var)
            client_secret: AskNews client secret (defaults to ASKNEWS_CLIENT_SECRET env var)
        """
        self.client_id = client_id or os.getenv("ASKNEWS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("ASKNEWS_CLIENT_SECRET")

        if not all([self.client_id, self.client_secret]):
            raise ValueError(
                "AskNews credentials not found. Set ASKNEWS_CLIENT_ID and "
                "ASKNEWS_CLIENT_SECRET environment variables."
            )

        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=30.0)
        self.access_token: str | None = None
        self.token_expiry: datetime | None = None

    async def _authenticate(self) -> None:
        """Authenticate with AskNews API and get access token."""
        response = await self.client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        data = response.json()

        self.access_token = data["access_token"]
        # Set expiry to 1 hour from now (tokens typically last longer, but being conservative)
        self.token_expiry = datetime.now() + timedelta(hours=1)

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token."""
        if not self.access_token or not self.token_expiry or datetime.now() >= self.token_expiry:
            await self._authenticate()

    async def search_news(
        self,
        query: str,
        days_back: int = 7,
        max_results: int = 20,
        categories: list[str] | None = None,
    ) -> list[NewsArticle]:
        """Search for news articles related to a query.

        Args:
            query: Search query
            days_back: How many days back to search
            max_results: Maximum number of results to return
            categories: Optional list of categories to filter by

        Returns:
            List of news articles
        """
        await self._ensure_authenticated()

        params: dict[str, Any] = {
            "query": query,
            "n_articles": max_results,
            "return_type": "both",  # Get both headlines and summaries
            "strategy": "latest news",
            "historical_days": days_back,
        }

        if categories:
            params["categories"] = ",".join(categories)

        response = await self.client.get(
            "/news/search",
            params=params,
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        response.raise_for_status()
        data = response.json()

        articles = []
        for article_data in data.get("articles", []):
            article = NewsArticle(
                title=article_data.get("headline", ""),
                summary=article_data.get("summary", article_data.get("snippet", "")),
                url=article_data.get("article_url", ""),
                source=article_data.get("source_id", ""),
                published_at=datetime.fromisoformat(
                    article_data["pub_date"].replace("Z", "+00:00")
                )
                if article_data.get("pub_date")
                else datetime.now(),
                relevance_score=article_data.get("score"),
            )
            articles.append(article)

        return articles

    async def get_recent_news(
        self,
        query: str,
        hours: int = 24,
        max_results: int = 10,
    ) -> list[NewsArticle]:
        """Get the most recent news articles for a query.

        Args:
            query: Search query
            hours: How many hours back to search
            max_results: Maximum number of results

        Returns:
            List of recent news articles
        """
        days_back = max(1, hours // 24 + 1)
        articles = await self.search_news(
            query=query,
            days_back=days_back,
            max_results=max_results
        )

        # Filter to only articles within the specified hours
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_articles = [
            article for article in articles
            if article.published_at >= cutoff_time
        ]

        return recent_articles[:max_results]

    async def summarize_context(
        self,
        query: str,
        days_back: int = 7,
    ) -> str:
        """Get a text summary of news context for a forecasting question.

        Args:
            query: The forecasting question or topic
            days_back: How many days of news to consider

        Returns:
            Text summary of relevant news context
        """
        articles = await self.search_news(query, days_back=days_back, max_results=15)

        if not articles:
            return "No recent news found for this topic."

        # Create a structured summary
        summary_parts = [f"Recent news context for: {query}\n"]

        for i, article in enumerate(articles[:10], 1):
            date_str = article.published_at.strftime("%Y-%m-%d %H:%M")
            summary_parts.append(
                f"{i}. [{article.source}] {article.title}\n"
                f"   Published: {date_str}\n"
                f"   Summary: {article.summary}\n"
                f"   URL: {article.url}\n"
            )

        return "\n".join(summary_parts)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
