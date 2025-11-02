"""Quick test to show Claude Agent SDK in action."""

import asyncio
import json
from dotenv import load_dotenv
from src.agent.simple_forecaster import SimpleForecastingAgent
from src.evaluation.scorer import brier_score

load_dotenv()


async def test_single_forecast():
    """Test a single forecast with detailed output."""

    # Load one question from current.json
    with open("current.json") as f:
        questions = json.load(f)

    # Use the Tampa temperature question (index 1)
    question = questions[1]

    print("=" * 80)
    print("Testing Claude Agent SDK Forecaster")
    print("=" * 80)
    print(f"\nQuestion: {question['title']}")
    print(f"Type: {question['type']}")
    print(f"Actual Answer: {question['actual_answer']}\n")

    print("Initializing SimpleForecastingAgent (uses Claude Agent SDK)...")
    print("- Creates MCP server with search_news and web_research tools")
    print("- Configures ClaudeSDKClient with system prompt")
    print("- Sets up async conversation handling\n")

    async with SimpleForecastingAgent() as agent:
        print("Running forecast with Claude Agent SDK...")
        print("- Agent will research using MCP tools")
        print("- Multiple turns of conversation")
        print("- Real-time API calls to Perplexity/AskNews\n")

        forecast = await agent.forecast(
            question=question['title'],
            question_type="binary",
            context=f"Question opened on {question['open_time']}"
        )

        print("=" * 80)
        print("FORECAST RESULT")
        print("=" * 80)
        print(f"\nForecast Value: {forecast.forecast_value}")
        print(f"Confidence: {forecast.confidence}")
        print(f"\nReasoning:\n{forecast.reasoning}")

        # Calculate score
        actual = question['actual_answer'].lower() == 'yes'
        if isinstance(forecast.forecast_value, float):
            score = brier_score(forecast.forecast_value, actual)
            print(f"\nBrier Score: {score:.4f}")
            print(f"(0.0 = perfect, 0.25 = random, 1.0 = worst)")

        print("\n" + "=" * 80)
        print("FULL CONVERSATION (showing Claude SDK interaction)")
        print("=" * 80)
        print(forecast.full_response[:1000])  # First 1000 chars
        print("\n...(truncated)")


if __name__ == "__main__":
    asyncio.run(test_single_forecast())
