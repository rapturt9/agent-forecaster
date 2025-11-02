"""Forecast questions with MLflow tracing and evaluation."""

import asyncio
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
import mlflow

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from src.agent.mlflow_forecaster import MLflowForecastingAgent
from src.evaluation.mlflow_scorers import CalibrationMonitor


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


async def forecast_with_mlflow_tracking(
    agent: MLflowForecastingAgent,
    question: dict,
    calibration_monitor: CalibrationMonitor,
) -> dict:
    """Forecast a question with MLflow tracking."""

    title = question["title"]
    q_type = map_question_type(question["type"])
    actual_answer = parse_answer(question["actual_answer"], question["type"])

    print(f"\n{'='*80}")
    print(f"Question: {title}")
    print(f"Type: {question['type']} -> {q_type}")
    print(f"Actual Answer: {actual_answer}")
    print(f"{'='*80}\n")

    try:
        # Generate forecast with MLflow tracing
        print("🔍 Forecasting with MLflow tracing...")

        forecast_result, run_id = await agent.forecast(
            question=title,
            question_type=q_type,
            context=f"Question opened on {question['open_time']}",
            question_id=str(question['question_id'])
        )

        # Extract forecast value
        if hasattr(forecast_result, 'final_forecast'):
            forecast_value = forecast_result.final_forecast
            confidence = forecast_result.confidence
            reasoning = forecast_result.final_reasoning
            print(f"\n📊 Forecast: {forecast_value}")
            print(f"💭 Confidence: {confidence}")
            print(f"🔧 Tool Calls: {forecast_result.total_tool_calls}")
            print(f"📐 Models: {forecast_result.total_models_generated}")
        else:
            forecast_value = forecast_result.forecast_value
            confidence = forecast_result.confidence
            reasoning = forecast_result.reasoning
            print(f"\n📊 Forecast: {forecast_value}")
            print(f"💭 Confidence: {confidence}")

        # Evaluate against actual answer
        if actual_answer is not None:
            print("\n📈 Evaluating forecast...")
            metrics = await agent.evaluate_forecast(forecast_result, actual_answer, run_id)

            if "brier_score" in metrics:
                print(f"   Brier Score: {metrics['brier_score']:.4f}")

                # Add to calibration monitor
                if isinstance(forecast_value, float) and isinstance(actual_answer, bool):
                    calibration_monitor.add_forecast(forecast_value, actual_answer)

        print(f"\n✅ MLflow Run ID: {run_id}")
        print(f"💾 Trace saved to MLflow")

        return {
            "question_id": question["question_id"],
            "forecast": forecast_value,
            "actual": actual_answer,
            "run_id": run_id,
            "success": True,
        }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "question_id": question["question_id"],
            "error": str(e),
            "success": False,
        }


async def main():
    """Main forecasting loop with MLflow."""

    # Load questions
    questions = load_questions()
    print(f"Loaded {len(questions)} questions from current.json\n")

    # Set up MLflow
    print("🔧 Setting up MLflow...")
    mlflow.set_tracking_uri("file:./mlruns")
    experiment_name = "forecasting_v1"

    print(f"   Experiment: {experiment_name}")
    print(f"   Tracking URI: ./mlruns")
    print(f"   View UI: mlflow ui\n")

    # Ask which questions to forecast
    print("Options:")
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

    # Initialize calibration monitor
    calibration_monitor = CalibrationMonitor()

    # Forecast each question
    results = []

    async with MLflowForecastingAgent(
        model_name="forecasting_agent_v1",
        experiment_name=experiment_name,
        use_enhanced=True,
    ) as agent:
        for i, question in enumerate(questions_to_forecast):
            print(f"\n\n{'#'*80}")
            print(f"# Question {i+1}/{len(questions_to_forecast)}")
            print(f"{'#'*80}")

            result = await forecast_with_mlflow_tracking(agent, question, calibration_monitor)
            results.append(result)

            # Small delay between questions
            if i < len(questions_to_forecast) - 1:
                await asyncio.sleep(2)

        # Log calibration metrics
        print(f"\n\n{'='*80}")
        print("CALIBRATION")
        print(f"{'='*80}")

        if len(calibration_monitor.forecasts) >= 5:
            calib_error = calibration_monitor.get_calibration_error()
            print(f"Calibration Error: {calib_error:.4f}")
            print(f"Forecasts used: {len(calibration_monitor.forecasts)}")

            # Log to MLflow
            with mlflow.start_run(run_name="calibration_summary"):
                mlflow.log_metric("calibration_error", calib_error)
                mlflow.log_metric("num_forecasts", len(calibration_monitor.forecasts))
        else:
            print("Need at least 5 forecasts for calibration analysis")

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    successful = [r for r in results if r.get("success")]
    errors = [r for r in results if not r.get("success")]

    print(f"Successful: {len(successful)}/{len(results)}")
    print(f"Errors: {len(errors)}/{len(results)}")

    print("\n📊 MLflow Tracking:")
    print(f"   Experiment: {experiment_name}")
    print(f"   Location: ./mlruns")
    print(f"\n   View results: mlflow ui")
    print(f"   Then navigate to: http://127.0.0.1:5000")

    print("\n✨ What's in MLflow:")
    print("   • Complete agent traces with all tool calls")
    print("   • Squiggle models generated")
    print("   • Research sources and reasoning")
    print("   • Brier scores and calibration metrics")
    print("   • Conversation logs and artifacts")


if __name__ == "__main__":
    asyncio.run(main())
