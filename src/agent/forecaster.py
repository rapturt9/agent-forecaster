"""Main forecasting agent using Claude Agent SDK."""

import json
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from claude_agent_sdk import AssistantMessage, TextBlock, ResultMessage

from src.agent.prompts import FORECASTER_SYSTEM_PROMPT, get_forecasting_prompt
from src.agent.tools import ALL_TOOLS
from src.models.squiggle_runner import SquiggleRunner, SquiggleModel
from src.data.kalshi import KalshiMarket


class Forecast(BaseModel):
    """Represents a forecast for a question."""

    question: str
    question_type: Literal["binary", "categorical", "numerical"]
    forecast_value: float | dict[str, float]
    confidence: str
    reasoning: str
    models: list[dict[str, Any]]
    research_summary: str
    base_rates: str | None = None
    created_at: datetime
    kalshi_ticker: str | None = None
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question": self.question,
            "question_type": self.question_type,
            "forecast_value": self.forecast_value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "models": self.models,
            "research_summary": self.research_summary,
            "base_rates": self.base_rates,
            "created_at": self.created_at.isoformat(),
            "kalshi_ticker": self.kalshi_ticker,
            "session_id": self.session_id,
        }

    def save_json(self, filepath: str) -> None:
        """Save forecast to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class ForecastingAgent:
    """AI forecasting agent powered by Claude Agent SDK."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250929",
        max_turns: int = 30,
    ):
        """Initialize the forecasting agent.

        Args:
            model: Claude model to use
            max_turns: Maximum conversation turns
        """
        self.model = model
        self.max_turns = max_turns
        self.squiggle_runner: SquiggleRunner | None = None

        # Create MCP server with custom tools
        self.mcp_server = create_sdk_mcp_server(
            name="forecasting_tools",
            version="1.0.0",
            tools=ALL_TOOLS
        )

    async def _setup_squiggle_runner(self) -> SquiggleRunner:
        """Set up Squiggle runner."""
        if not self.squiggle_runner:
            self.squiggle_runner = SquiggleRunner()
        return self.squiggle_runner

    async def forecast(
        self,
        question: str,
        question_type: Literal["binary", "categorical", "numerical"] = "binary",
        context: str = "",
        kalshi_ticker: str | None = None,
    ) -> Forecast:
        """Generate a forecast for a question.

        Args:
            question: The forecasting question
            question_type: Type of question
            context: Additional context
            kalshi_ticker: Optional Kalshi market ticker

        Returns:
            Forecast object
        """
        # Set up Claude SDK client
        options = ClaudeAgentOptions(
            system_prompt=FORECASTER_SYSTEM_PROMPT,
            mcp_servers={"forecasting": self.mcp_server},
            allowed_tools=[
                "mcp__forecasting__search_news",
                "mcp__forecasting__web_research",
            ],
            model=self.model,
            max_turns=self.max_turns,
            permission_mode="acceptEdits",  # Auto-accept for autonomous operation
        )

        # Create forecasting prompt
        prompt = get_forecasting_prompt(question, question_type, context)

        # Run the agent
        conversation_text = []
        session_id = None

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            # Collect all messages
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            conversation_text.append(block.text)
                elif isinstance(message, ResultMessage):
                    session_id = message.session_id

        # Combine conversation into full response
        full_response = "\n\n".join(conversation_text)

        # Parse the forecast from the response
        forecast = await self._parse_forecast_from_response(
            question=question,
            question_type=question_type,
            response=full_response,
            kalshi_ticker=kalshi_ticker,
            session_id=session_id,
        )

        return forecast

    async def forecast_kalshi_market(self, market: KalshiMarket) -> Forecast:
        """Generate a forecast for a Kalshi market.

        Args:
            market: KalshiMarket object

        Returns:
            Forecast object
        """
        # Use market question and metadata
        context = f"This is a Kalshi prediction market. Category: {market.category}."
        if market.close_time:
            context += f" Market closes: {market.close_time.isoformat()}"

        return await self.forecast(
            question=market.question,
            question_type=market.market_type,
            context=context,
            kalshi_ticker=market.ticker,
        )

    async def _parse_forecast_from_response(
        self,
        question: str,
        question_type: str,
        response: str,
        kalshi_ticker: str | None,
        session_id: str | None,
    ) -> Forecast:
        """Parse forecast details from agent response.

        This is a simplified parser. In production, you'd want more robust parsing.
        """
        # Extract key sections using simple heuristics
        # In a real implementation, you might use structured output or more sophisticated parsing

        # Try to extract final probability
        forecast_value: float | dict[str, float] = 0.5  # Default

        # Look for probability statements in the response
        lines = response.lower().split('\n')
        for line in lines:
            if 'final' in line and ('probability' in line or 'forecast' in line):
                # Try to extract number
                import re
                numbers = re.findall(r'(\d+(?:\.\d+)?)\s*%', line)
                if numbers:
                    forecast_value = float(numbers[0]) / 100
                else:
                    numbers = re.findall(r'0?\.\d+', line)
                    if numbers:
                        forecast_value = float(numbers[0])

        # Extract sections
        research_summary = self._extract_section(response, "research")
        base_rates = self._extract_section(response, "base rate")
        reasoning = self._extract_section(response, "reasoning")

        if not reasoning:
            reasoning = response[:500]  # First 500 chars as fallback

        # Create forecast object
        return Forecast(
            question=question,
            question_type=question_type,
            forecast_value=forecast_value,
            confidence="moderate",  # Could be extracted from response
            reasoning=reasoning,
            models=[],  # Could extract Squiggle models from response
            research_summary=research_summary or "See full response",
            base_rates=base_rates,
            created_at=datetime.now(),
            kalshi_ticker=kalshi_ticker,
            session_id=session_id,
        )

    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from the response text."""
        lines = text.split('\n')
        section_lines = []
        in_section = False

        for line in lines:
            lower_line = line.lower()
            # Check if we're entering the section
            if section_name in lower_line and ('##' in line or '**' in line or ':' in line):
                in_section = True
                continue

            # Check if we're leaving the section (next section starts)
            if in_section and ('##' in line or (line.startswith('**') and line.endswith('**'))):
                break

            if in_section:
                section_lines.append(line)

        return '\n'.join(section_lines).strip()

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.squiggle_runner:
            await self.squiggle_runner.cleanup()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


async def quick_forecast(
    question: str,
    question_type: Literal["binary", "categorical", "numerical"] = "binary",
) -> Forecast:
    """Quick helper to generate a forecast.

    Args:
        question: The forecasting question
        question_type: Type of question

    Returns:
        Forecast object
    """
    async with ForecastingAgent() as agent:
        return await agent.forecast(question, question_type)
