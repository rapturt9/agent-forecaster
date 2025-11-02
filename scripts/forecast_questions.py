"""Script to forecast questions from current.json using the forecasting agent."""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from src.agent.simple_forecaster import SimpleForecastingAgent
from src.evaluation.scorer import brier_score


def load_questions(filepath: str = "current.json") -> list[dict]:
    """Load questions from current.json."""
    with open(filepath) as f:
        return json.load(f)


def map_question_type(question_type: str) -> str:
    """Map question type to our format."""
    if question_type == "binary":
        return "binary"
    elif question_type == "multiple_choice":
        return "categorical"
    elif question_type in ["numeric", "discrete"]:
        return "numerical"
    return "binary"


def parse_answer(answer: str, question_type: str):
    """Parse actual answer based on question type."""
    if question_type == "binary":
        return answer.lower() == "yes"
    elif question_type == "numerical":
        try:
            return float(answer)
        except:
            return None
    return answer


async def forecast_single_question(agent: SimpleForecastingAgent, question: dict) -> dict:
    """Forecast a single question and compare to actual answer."""

    title = question["title"]
    q_type = map_question_type(question["type"])
    actual_answer = parse_answer(question["actual_answer"], question["type"])

    print(f"\n{'='*80}")
    print(f"Question: {title}")
    print(f"Type: {question['type']} -> {q_type}")
    print(f"Actual Answer: {actual_answer}")
    print(f"{'='*80}\n")

    try:
        # Generate forecast
        print("🔍 Researching and forecasting...")
        forecast = await agent.forecast(
            question=title,
            question_type=q_type,
            context=f"This question was opened on {question['open_time']}"
        )

        print(f"\n📊 Forecast: {forecast.forecast_value}")
        print(f"💭 Confidence: {forecast.confidence}")

        # Calculate score if binary
        score = None
        if question["type"] == "binary" and isinstance(forecast.forecast_value, float):
            score = brier_score(forecast.forecast_value, actual_answer)
            print(f"📈 Brier Score: {score:.4f} (lower is better)")

        # Save forecast
        output_dir = Path("forecasts/current_json")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"q_{question['question_id']}.json"

        result = {
            "question_id": question["question_id"],
            "post_id": question["post_id"],
            "question": title,
            "question_type": question["type"],
            "forecast": forecast.forecast_value,
            "actual_answer": actual_answer,
            "brier_score": score,
            "reasoning": forecast.reasoning[:500],  # First 500 chars
            "forecasted_at": datetime.now().isoformat(),
        }

        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"💾 Saved to: {output_file}")

        return result

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "question_id": question["question_id"],
            "question": title,
            "error": str(e)
        }


async def main():
    """Main forecasting loop."""
    # Load questions
    questions = load_questions()
    print(f"Loaded {len(questions)} questions from current.json")

    # Ask which questions to forecast
    print("\nOptions:")
    print("1. Forecast first question only (for testing)")
    print("2. Forecast all questions")
    print("3. Forecast specific question by index (0-based)")

    choice = input("\nChoice (1/2/3): ").strip()

    questions_to_forecast = []

    if choice == "1":
        questions_to_forecast = [questions[0]]
    elif choice == "2":
        questions_to_forecast = questions
    elif choice == "3":
        idx = int(input("Enter question index (0-based): "))
        if 0 <= idx < len(questions):
            questions_to_forecast = [questions[idx]]
        else:
            print("Invalid index!")
            return
    else:
        print("Invalid choice!")
        return

    # Forecast each question
    results = []

    async with SimpleForecastingAgent() as agent:
        for i, question in enumerate(questions_to_forecast):
            print(f"\n\n{'#'*80}")
            print(f"# Question {i+1}/{len(questions_to_forecast)}")
            print(f"{'#'*80}")

            result = await forecast_single_question(agent, question)
            results.append(result)

            # Small delay between questions
            if i < len(questions_to_forecast) - 1:
                await asyncio.sleep(2)

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    successful = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]

    print(f"Successful: {len(successful)}/{len(results)}")
    print(f"Errors: {len(errors)}/{len(results)}")

    # Calculate average Brier score for binary questions
    brier_scores = [r["brier_score"] for r in successful if r.get("brier_score") is not None]
    if brier_scores:
        avg_brier = sum(brier_scores) / len(brier_scores)
        print(f"\nAverage Brier Score: {avg_brier:.4f}")
        print(f"(Perfect score = 0.0, Random = 0.25, Worst = 1.0)")

    print(f"\nForecasts saved to: forecasts/current_json/")


if __name__ == "__main__":
    asyncio.run(main())
