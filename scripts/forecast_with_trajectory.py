"""Forecast questions with complete trajectory logging for research reports."""

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

from src.agent.enhanced_forecaster import EnhancedForecastingAgent
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


async def forecast_with_full_trajectory(agent: EnhancedForecastingAgent, question: dict) -> dict:
    """Forecast with complete trajectory logging."""

    title = question["title"]
    q_type = map_question_type(question["type"])
    actual_answer = parse_answer(question["actual_answer"], question["type"])

    print(f"\n{'='*80}")
    print(f"Question: {title}")
    print(f"Type: {question['type']} -> {q_type}")
    print(f"Actual Answer: {actual_answer}")
    print(f"{'='*80}\n")

    try:
        # Generate forecast with full trajectory
        print("🔍 Researching and forecasting (with trajectory logging)...")
        trajectory = await agent.forecast(
            question=title,
            question_type=q_type,
            context=f"Question opened on {question['open_time']}"
        )

        print(f"\n📊 Forecast: {trajectory.final_forecast}")
        print(f"💭 Confidence: {trajectory.confidence}")
        print(f"⏱️  Duration: {trajectory.duration_seconds:.1f}s")
        print(f"🔧 Tool Calls: {trajectory.total_tool_calls}")
        print(f"🧠 Reasoning Steps: {trajectory.total_reasoning_steps}")
        print(f"📐 Models Generated: {trajectory.total_models_generated}")

        # Calculate score if binary
        score = None
        if question["type"] == "binary" and isinstance(trajectory.final_forecast, float):
            score = brier_score(trajectory.final_forecast, actual_answer)
            print(f"📈 Brier Score: {score:.4f}")

        # Save trajectory
        output_dir = Path("trajectories")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"trajectory_q{question['question_id']}.json"

        trajectory_data = trajectory.to_dict()
        trajectory_data["question_id"] = question["question_id"]
        trajectory_data["post_id"] = question["post_id"]
        trajectory_data["actual_answer"] = actual_answer
        trajectory_data["brier_score"] = score

        with open(output_file, 'w') as f:
            json.dump(trajectory_data, f, indent=2)

        print(f"💾 Full trajectory saved to: {output_file}")

        # Also print trajectory summary
        print(f"\n{'─'*80}")
        print("TRAJECTORY SUMMARY")
        print(f"{'─'*80}")

        if trajectory.tool_calls:
            print(f"\nTool Calls ({len(trajectory.tool_calls)}):")
            for i, tc in enumerate(trajectory.tool_calls, 1):
                print(f"  {i}. {tc.tool_name}")
                print(f"     Input: {tc.inputs}")
                print(f"     Output: {tc.outputs[:100]}...")

        if trajectory.squiggle_models:
            print(f"\nSquiggle Models ({len(trajectory.squiggle_models)}):")
            for model in trajectory.squiggle_models:
                print(f"  {model.model_id}. {model.name}")
                print(f"     Code: {model.code[:100]}...")
                if model.model_id == trajectory.selected_model_id:
                    print(f"     ⭐ SELECTED")

        print(f"\nFinal Reasoning:\n{trajectory.final_reasoning}\n")

        return {
            "question_id": question["question_id"],
            "forecast": trajectory.final_forecast,
            "actual": actual_answer,
            "score": score,
            "trajectory_file": str(output_file)
        }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "question_id": question["question_id"],
            "error": str(e)
        }


async def main():
    """Main forecasting loop."""
    questions = load_questions()
    print(f"Loaded {len(questions)} questions from current.json")

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

    async with EnhancedForecastingAgent() as agent:
        for i, question in enumerate(questions_to_forecast):
            print(f"\n\n{'#'*80}")
            print(f"# Question {i+1}/{len(questions_to_forecast)}")
            print(f"{'#'*80}")

            result = await forecast_with_full_trajectory(agent, question)
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

    # Calculate average Brier score
    brier_scores = [r["score"] for r in successful if r.get("score") is not None]
    if brier_scores:
        avg_brier = sum(brier_scores) / len(brier_scores)
        print(f"\nAverage Brier Score: {avg_brier:.4f}")

    print(f"\nFull trajectories saved to: trajectories/")
    print("Each trajectory contains:")
    print("  - Complete conversation log")
    print("  - All tool calls with inputs/outputs")
    print("  - All Squiggle models generated")
    print("  - Reasoning steps")
    print("  - Final forecast with metadata")


if __name__ == "__main__":
    asyncio.run(main())
