"""Forecast custom questions with MLflow tracking for full trajectory viewing."""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import mlflow

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from src.agent.mlflow_forecaster import MLflowForecastingAgent


async def main():
    """Forecast a custom question with MLflow tracking."""

    print("="*80)
    print("CUSTOM FORECAST WITH MLFLOW")
    print("="*80)
    print("\nThis will log your forecast to MLflow for full trajectory viewing.")
    print("View results at: http://127.0.0.1:5000")
    print("="*80)

    # Get question from user
    print("\nEnter your forecasting question:")
    question = input("> ").strip()

    if not question:
        print("No question provided. Exiting.")
        return

    # Question type
    print("\nQuestion type:")
    print("1. Binary (yes/no)")
    print("2. Numerical (how many, what value)")
    print("3. Categorical (which option)")
    choice = input("Select (1/2/3) [default: 1]: ").strip() or "1"

    question_type_map = {"1": "binary", "2": "numerical", "3": "categorical"}
    question_type = question_type_map.get(choice, "binary")

    # Context
    print("\nOptional context (press Enter to skip):")
    context = input("> ").strip()

    # Research depth
    print("\nResearch depth (affects max_turns):")
    print("1. Standard (25 turns)")
    print("2. Deep (50 turns) - Recommended")
    print("3. Extensive (100 turns)")
    depth = input("Select (1/2/3) [default: 2]: ").strip() or "2"

    max_turns_map = {"1": 25, "2": 50, "3": 100}
    max_turns = max_turns_map.get(depth, 50)

    # Set up MLflow
    print(f"\n{'='*80}")
    print("STARTING FORECAST")
    print(f"{'='*80}")
    print(f"Question: {question}")
    print(f"Type: {question_type}")
    print(f"Max Turns: {max_turns}")
    print(f"Context: {context if context else '(none)'}")
    print(f"{'='*80}\n")

    mlflow.set_tracking_uri("file:./mlruns")
    experiment_name = "custom_forecasts"

    print(f"🔧 MLflow Setup:")
    print(f"   Experiment: {experiment_name}")
    print(f"   Tracking URI: ./mlruns")
    print(f"   View UI: mlflow ui (already running at http://127.0.0.1:5000)")
    print()

    # Run forecast
    async with MLflowForecastingAgent(
        model_name="superforecaster_v1",
        experiment_name=experiment_name,
        use_enhanced=True,
    ) as agent:
        # Set max_turns for deep research
        agent.forecaster.max_turns = max_turns

        print("🔬 Generating forecast with superforecaster methodology...")
        print("   This may take several minutes for complex questions.\n")

        try:
            forecast_result, run_id = await agent.forecast(
                question=question,
                question_type=question_type,
                context=context,
                question_id="custom"
            )

            # Save reports locally
            output_dir = Path("research_reports")
            output_dir.mkdir(exist_ok=True)

            # Generate filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_question = "".join(c if c.isalnum() or c in " -_" else "_" for c in question[:50])
            base_name = f"{timestamp}_{safe_question}"

            # Save trajectory JSON
            trajectory_path = output_dir / f"{base_name}_trajectory.json"
            with open(trajectory_path, "w") as f:
                json.dump(forecast_result.to_dict(), f, indent=2, default=str)

            # Save markdown report
            md_path = output_dir / f"{base_name}_conversation.md"
            with open(md_path, "w") as f:
                f.write(f"# Research Report: {question}\n\n")
                f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Type**: {question_type}\n\n")
                if context:
                    f.write(f"**Context**: {context}\n\n")
                f.write("---\n\n")
                f.write(forecast_result.full_conversation)

            # Save structured report JSON
            report_path = output_dir / f"{base_name}_report.json"
            report_data = {
                "question": question,
                "question_type": question_type,
                "context": context,
                "timestamp": datetime.now().isoformat(),
                "forecast": forecast_result.final_forecast if hasattr(forecast_result, 'final_forecast') else forecast_result.forecast_value,
                "confidence": forecast_result.confidence,
                "reasoning": forecast_result.final_reasoning if hasattr(forecast_result, 'final_reasoning') else forecast_result.reasoning,
                "models": [model.to_dict() for model in forecast_result.squiggle_models] if hasattr(forecast_result, 'squiggle_models') else [],
                "duration_seconds": forecast_result.duration_seconds if hasattr(forecast_result, 'duration_seconds') else None,
                "total_tool_calls": forecast_result.total_tool_calls if hasattr(forecast_result, 'total_tool_calls') else 0,
                "total_models": forecast_result.total_models_generated if hasattr(forecast_result, 'total_models_generated') else 0,
            }
            with open(report_path, "w") as f:
                json.dump(report_data, f, indent=2, default=str)

            # Display results
            print(f"\n{'='*80}")
            print("FORECAST COMPLETE")
            print(f"{'='*80}")

            if hasattr(forecast_result, 'final_forecast'):
                print(f"📊 Forecast: {forecast_result.final_forecast}")
                print(f"💭 Confidence: {forecast_result.confidence}")
                print(f"⏱️  Duration: {forecast_result.duration_seconds:.1f} seconds")
                print(f"🔧 Tool Calls: {forecast_result.total_tool_calls}")
                print(f"📐 Models: {forecast_result.total_models_generated}")
                print(f"\n🧠 Reasoning:")
                print(forecast_result.final_reasoning or "(No final reasoning)")
            else:
                print(f"📊 Forecast: {forecast_result.forecast_value}")
                print(f"💭 Confidence: {forecast_result.confidence}")
                print(f"\n🧠 Reasoning:")
                print(forecast_result.reasoning)

            print(f"\n{'='*80}")
            print("REPORTS SAVED")
            print(f"{'='*80}")
            print(f"📄 Markdown Report: {md_path}")
            print(f"📊 Trajectory JSON: {trajectory_path}")
            print(f"📋 Structured Report: {report_path}")

            print(f"\n{'='*80}")
            print("MLFLOW TRACKING")
            print(f"{'='*80}")
            print(f"✅ MLflow Run ID: {run_id}")
            print(f"\n📊 View in MLflow UI:")
            print(f"   1. Open: http://127.0.0.1:5000")
            print(f"   2. Click on '{experiment_name}' experiment")
            print(f"   3. Find run: {run_id[:8]}...")
            print(f"   4. View tabs:")
            print(f"      - Traces: Complete agent execution")
            print(f"      - Metrics: Forecast value, duration, tool calls")
            print(f"      - Artifacts: conversation.txt, trajectory.json, squiggle_models.txt")
            print(f"\n✨ Complete trajectory available in both local files and MLflow!")
            print(f"{'='*80}\n")

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
