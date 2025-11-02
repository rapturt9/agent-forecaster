"""Simplified forecasting agent without Squiggle."""

import os
import re
from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from claude_agent_sdk import AssistantMessage, TextBlock, ResultMessage

from src.agent.simple_prompts import SIMPLE_FORECASTER_PROMPT, get_simple_forecasting_prompt
from src.agent.tools import ALL_TOOLS

# Load environment variables
load_dotenv()


class SimpleForecast(BaseModel):
    """Simple forecast result."""
    question: str
    question_type: str
    forecast_value: float | str
    confidence: str
    reasoning: str
    full_response: str
    created_at: datetime


class SimpleForecastingAgent:
    """Simplified forecasting agent."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", max_turns: int = 20):
        """Initialize agent."""
        self.model = model
        self.max_turns = max_turns

        # Create MCP server with tools
        self.mcp_server = create_sdk_mcp_server(
            name="forecasting_tools",
            version="1.0.0",
            tools=ALL_TOOLS
        )

    async def forecast(
        self,
        question: str,
        question_type: Literal["binary", "categorical", "numerical"] = "binary",
        context: str = "",
    ) -> SimpleForecast:
        """Generate a forecast for a question."""

        # Set up Claude SDK client
        options = ClaudeAgentOptions(
            system_prompt=SIMPLE_FORECASTER_PROMPT,
            mcp_servers={"forecasting": self.mcp_server},
            allowed_tools=[
                "mcp__forecasting__search_news",
                "mcp__forecasting__web_research",
            ],
            model=self.model,
            max_turns=self.max_turns,
            permission_mode="bypassPermissions",  # Auto-approve all tools including WebSearch
        )

        # Create prompt
        prompt = get_simple_forecasting_prompt(question, question_type, context)

        # Run the agent
        conversation_text = []

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            # Collect all messages
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            conversation_text.append(block.text)

        # Combine conversation into full response
        full_response = "\n\n".join(conversation_text)

        # Parse the forecast from the response
        forecast_value, confidence, reasoning = self._extract_forecast(full_response, question_type)

        return SimpleForecast(
            question=question,
            question_type=question_type,
            forecast_value=forecast_value,
            confidence=confidence,
            reasoning=reasoning,
            full_response=full_response,
            created_at=datetime.now()
        )

    def _extract_forecast(self, text: str, question_type: str) -> tuple:
        """Extract forecast value, confidence, and reasoning from response.

        Returns:
            Tuple of (forecast_value, confidence, reasoning)
        """
        # Default values
        forecast_value = 0.5 if question_type == "binary" else "unknown"
        confidence = "unknown"
        reasoning = ""

        # Look for FINAL FORECAST pattern
        forecast_match = re.search(r'FINAL FORECAST:\s*([0-9.]+|[^\n]+)', text, re.IGNORECASE)
        if forecast_match:
            forecast_str = forecast_match.group(1).strip()
            if question_type == "binary":
                try:
                    forecast_value = float(forecast_str)
                    # Ensure it's in valid range
                    forecast_value = max(0.01, min(0.99, forecast_value))
                except:
                    # Try to find any probability in the text
                    prob_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', text)
                    if prob_matches:
                        forecast_value = float(prob_matches[0]) / 100
                    else:
                        prob_matches = re.findall(r'(0\.\d+)', text)
                        if prob_matches:
                            forecast_value = float(prob_matches[0])
            else:
                forecast_value = forecast_str

        # Look for CONFIDENCE
        conf_match = re.search(r'CONFIDENCE:\s*([^\n]+)', text, re.IGNORECASE)
        if conf_match:
            confidence = conf_match.group(1).strip().lower()

        # Look for REASONING
        reason_match = re.search(r'REASONING:\s*([^\n]+(?:\n(?!FINAL|CONFIDENCE)[^\n]+)*)', text, re.IGNORECASE)
        if reason_match:
            reasoning = reason_match.group(1).strip()

        # Fallback: try to extract from the last part of the text
        if reasoning == "":
            lines = text.split('\n')
            # Get last few non-empty lines
            last_lines = [l.strip() for l in lines if l.strip()][-3:]
            reasoning = " ".join(last_lines)

        return forecast_value, confidence, reasoning

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
