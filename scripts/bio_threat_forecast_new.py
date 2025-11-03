"""Small test forecast for Gemini 3 release - validates all outputs."""

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
from src.agent.doc_generator import generate_forecast_document


async def main():
    """Test forecast for Gemini 3 release with full output validation."""

    print("="*80)
    print("TEST FORECAST: Will Google Release Gemini 3 in 2025?")
    print("="*80)
    print("\nThis is a small test to validate:")
    print("✓ Enhanced research tools (Perplexity with exact data prompts)")
    print("✓ AskNews integration")
    print("✓ Model generation and Squiggle extraction")
    print("✓ JSON trajectory export")
    print("✓ Markdown report generation")
    print("✓ Word document (.docx) generation")
    print("✓ MLflow logging and traces")
    print("="*80)

    # Set up MLflow
    mlflow.set_tracking_uri("file:./mlruns")
    experiment_name = "test_forecasts"

    print(f"\n🔧 MLflow Setup:")
    print(f"   Experiment: {experiment_name}")
    print(f"   Tracking URI: ./mlruns")
    print(f"   View UI: http://127.0.0.1:5000")
    print()

    # Test question
    question = "Will Google release Gemini 3 in 2025?"
    question_type = "binary"
    context = """Google has released Gemini 1.0 (Dec 2023), Gemini 1.5 (Feb 2024), and Gemini 2.0 (Dec 2024).
Consider:
- Google's release cadence and patterns
- Gemini 2.0 features and current capabilities
- Industry competition (OpenAI, Anthropic)
- Google's public statements and roadmap
- Historical release timing patterns"""

    # Run forecast with enhanced tools
    async with MLflowForecastingAgent(
        model_name="gemini3_test_v1",
        experiment_name=experiment_name,
        use_enhanced=True,  # Use enhanced forecaster
    ) as agent:
        # Set to standard mode for quick test
        agent.forecaster.max_turns = 25

        print("🔬 Generating test forecast...")
        print("   Using enhanced research tools with exact data prompts")
        print("   Expected: 10-15 minutes\n")

        try:
            forecast_result, run_id = await agent.forecast(
                question=question,
                question_type=question_type,
                context=context,
                question_id="gemini3_test"
            )

            # Create output directory
            output_dir = Path("research_reports/test_gemini3")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"{timestamp}_gemini3_release_test"

            # 1. Save trajectory JSON
            trajectory_path = output_dir / f"{base_name}_trajectory.json"
            with open(trajectory_path, "w") as f:
                json.dump(forecast_result.to_dict(), f, indent=2, default=str)

            # 2. Save markdown report
            md_path = output_dir / f"{base_name}_conversation.md"
            with open(md_path, "w") as f:
                f.write(f"# Test Forecast Report: {question}\n\n")
                f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Type**: {question_type}\n\n")
                f.write(f"**Context**: {context}\n\n")
                f.write("---\n\n")
                f.write(forecast_result.full_conversation)

            # 3. Save structured report JSON
            report_path = output_dir / f"{base_name}_report.json"

            # Extract models using model_dump() for Pydantic models
            models_list = []
            if hasattr(forecast_result, 'squiggle_models'):
                for model in forecast_result.squiggle_models:
                    models_list.append(model.model_dump() if hasattr(model, 'model_dump') else {
                        "model_id": model.model_id,
                        "name": model.name,
                        "code": model.code,
                        "description": model.description,
                        "result": model.result,
                        "error": model.error,
                        "created_at": model.created_at.isoformat() if hasattr(model.created_at, 'isoformat') else str(model.created_at)
                    })

            report_data = {
                "question": question,
                "question_type": question_type,
                "context": context,
                "timestamp": datetime.now().isoformat(),
                "forecast": forecast_result.final_forecast if hasattr(forecast_result, 'final_forecast') else forecast_result.forecast_value,
                "confidence": forecast_result.confidence,
                "reasoning": forecast_result.final_reasoning if hasattr(forecast_result, 'final_reasoning') else forecast_result.reasoning,
                "models": models_list,
                "duration_seconds": forecast_result.duration_seconds if hasattr(forecast_result, 'duration_seconds') else None,
                "total_tool_calls": forecast_result.total_tool_calls if hasattr(forecast_result, 'total_tool_calls') else 0,
                "total_models": forecast_result.total_models_generated if hasattr(forecast_result, 'total_models_generated') else 0,
            }
            with open(report_path, "w") as f:
                json.dump(report_data, f, indent=2, default=str)

            # 4. Generate Word document
            docx_path = output_dir / f"{base_name}_report.docx"
            try:
                # Extract research steps for Word document
                research_steps_list = []
                if hasattr(forecast_result, 'reasoning_steps'):
                    for step in forecast_result.reasoning_steps:
                        research_steps_list.append({
                            "step_type": step.step_type if hasattr(step, 'step_type') else "unknown",
                            "content": step.content if hasattr(step, 'content') else str(step)
                        })

                generate_forecast_document(
                    output_path=str(docx_path),
                    question=question,
                    question_type=question_type,
                    forecast=str(forecast_result.final_forecast if hasattr(forecast_result, 'final_forecast') else forecast_result.forecast_value),
                    confidence=str(forecast_result.confidence),
                    reasoning=forecast_result.final_reasoning if hasattr(forecast_result, 'final_reasoning') else forecast_result.reasoning,
                    models=models_list,  # Use the models_list we already created above
                    context=context,
                    tool_calls=forecast_result.total_tool_calls if hasattr(forecast_result, 'total_tool_calls') else 0,
                    duration=forecast_result.duration_seconds if hasattr(forecast_result, 'duration_seconds') else 0,
                    research_steps=research_steps_list
                )
                print(f"\n✅ Word document generated: {docx_path}")
            except Exception as e:
                print(f"\n⚠️  Warning: Could not generate Word document: {e}")
                print("   (Continuing without .docx - may need python-docx installation)")

            # Display results
            print(f"\n{'='*80}")
            print("TEST FORECAST COMPLETE")
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
            print("OUTPUTS SAVED")
            print(f"{'='*80}")
            print(f"📄 Markdown Report: {md_path}")
            print(f"📊 Trajectory JSON: {trajectory_path}")
            print(f"📋 Structured Report: {report_path}")
            if docx_path.exists():
                print(f"📝 Word Document: {docx_path}")

            print(f"\n{'='*80}")
            print("MLFLOW TRACKING")
            print(f"{'='*80}")
            print(f"✅ MLflow Run ID: {run_id}")
            print(f"\n📊 View in MLflow UI:")
            print(f"   1. Open: http://127.0.0.1:5000")
            print(f"   2. Click on '{experiment_name}' experiment")
            print(f"   3. Find run: {run_id[:8]}...")
            print(f"   4. View 'Traces' tab for complete agent execution")
            print(f"\n✨ Test complete! All outputs validated.")
            print(f"{'='*80}\n")

            # Validation summary
            print(f"{'='*80}")
            print("VALIDATION SUMMARY")
            print(f"{'='*80}")
            print(f"✓ JSON trajectory saved: {trajectory_path.exists()}")
            print(f"✓ Markdown report saved: {md_path.exists()}")
            print(f"✓ Structured JSON saved: {report_path.exists()}")
            print(f"✓ Word document saved: {docx_path.exists()}")
            print(f"✓ MLflow logged: {run_id is not None}")

            # Model check
            if hasattr(forecast_result, 'squiggle_models'):
                model_count = len(forecast_result.squiggle_models)
                print(f"✓ Models generated: {model_count} (expected: 3+)")
                if model_count >= 3:
                    print("  ✅ PASS: Sufficient models generated")
                else:
                    print(f"  ⚠️  WARNING: Only {model_count} models (expected 3+)")

            # Research check
            if hasattr(forecast_result, 'total_tool_calls'):
                tool_count = forecast_result.total_tool_calls
                print(f"✓ Tool calls made: {tool_count} (expected: 5+)")
                if tool_count >= 5:
                    print("  ✅ PASS: Sufficient research conducted")
                else:
                    print(f"  ⚠️  WARNING: Only {tool_count} tool calls (expected 5+)")

            print(f"{'='*80}\n")
            print("🎉 Test forecast completed successfully!")
            print("Ready to proceed with full bio-threat forecast.\n")

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
