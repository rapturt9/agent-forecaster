"""Deep research forecasting with full report generation for complex questions."""

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


class DeepResearchConfig:
    """Configuration for deep research mode."""

    def __init__(
        self,
        max_turns: int = 50,  # More turns for complex questions
        min_models: int = 5,  # Require at least 5 forecasting models
        min_research_calls: int = 10,  # Minimum research tool calls
        generate_full_report: bool = True,
    ):
        self.max_turns = max_turns
        self.min_models = min_models
        self.min_research_calls = min_research_calls
        self.generate_full_report = generate_full_report


def create_deep_research_prompt(question: str, context: str = "") -> str:
    """Create an enhanced prompt for deep research."""
    return f"""# DEEP RESEARCH FORECASTING TASK

You are conducting deep research to forecast: **{question}**

{"Context: " + context if context else ""}

## Requirements

You MUST conduct extensive research before forecasting:

### Phase 1: Comprehensive Research (MANDATORY)
1. **Historical Analysis**: Use web_research to find historical data, trends, and base rates
2. **Recent Developments**: Use search_news to find latest news and developments
3. **Expert Opinions**: Use web_research to find expert forecasts and analyses
4. **Alternative Perspectives**: Research contrarian views and edge cases
5. **Key Uncertainties**: Identify and research major unknowns

Conduct AT LEAST 10 research calls across these tools:
- search_news (recent developments)
- web_research (deep analysis)
- WebSearch (general context)

### Phase 2: Model Building (Create AT LEAST 5 models)
Build multiple forecasting models with different approaches:

1. **Base Rate Model**: Historical frequency approach
2. **Trend Extrapolation Model**: Current trends extended
3. **Expert Consensus Model**: Synthesize expert opinions
4. **Inside View Model**: Detailed causal reasoning
5. **Outside View Model**: Reference class forecasting
6. **Monte Carlo Model** (optional): Multiple scenarios
7. **Fermi Estimation Model** (optional): Bottom-up calculation

For each model, provide:
- Model name and approach
- Complete Squiggle code
- Key assumptions
- Limitations
- Probability estimate

### Phase 3: Model Comparison & Selection
- Compare all models side-by-side
- Discuss where they agree/disagree
- Explain uncertainty sources
- Select best model or weighted combination

### Phase 4: Final Forecast
Provide:
- FINAL FORECAST: [probability as decimal]
- CONFIDENCE: [low/moderate/high]
- REASONING: [2-3 paragraph explanation]

## Research Report Structure

Present your findings in this format:

```
# RESEARCH REPORT: [Question]

## EXECUTIVE SUMMARY
[2-3 sentences]

## RESEARCH FINDINGS

### Historical Analysis
[Findings from historical research]

### Recent Developments
[Latest news and trends]

### Expert Opinions
[What experts are saying]

### Key Uncertainties
[Major unknowns and wild cards]

## FORECASTING MODELS

### MODEL 1: [Name]
```squiggle
[Squiggle code]
```
- Assumptions: [list]
- Estimate: [probability]
- Limitations: [list]

[Repeat for each model]

## MODEL COMPARISON
[Compare models, discuss differences]

## SELECTED APPROACH
[Explain which model(s) inform final forecast]

## FINAL FORECAST: [probability]

## CONFIDENCE: [level]

## REASONING
[Detailed explanation]

## RESEARCH SOURCES
[List key sources]
```

Remember: This is a DEEP RESEARCH task. Take your time, use tools extensively, and build multiple detailed models."""


async def deep_research_forecast(
    question: str,
    question_type: str = "binary",
    context: str = "",
    config: DeepResearchConfig | None = None,
    output_dir: str = "research_reports"
) -> dict:
    """Run deep research forecasting and generate full report.

    Args:
        question: The forecasting question
        question_type: Type of question (binary, categorical, numerical)
        context: Additional context
        config: Deep research configuration
        output_dir: Directory to save reports

    Returns:
        Dictionary with forecast results and paths to saved files
    """
    if config is None:
        config = DeepResearchConfig()

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create timestamp-based filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_question = "".join(c if c.isalnum() or c in " -_" else "_" for c in question[:50])
    base_filename = f"{timestamp}_{safe_question}"

    print(f"\n{'='*80}")
    print(f"DEEP RESEARCH FORECAST")
    print(f"{'='*80}")
    print(f"Question: {question}")
    print(f"Type: {question_type}")
    print(f"Max Turns: {config.max_turns}")
    print(f"Min Models Required: {config.min_models}")
    print(f"Min Research Calls: {config.min_research_calls}")
    print(f"{'='*80}\n")

    # Create enhanced prompt
    deep_prompt = create_deep_research_prompt(question, context)

    # Initialize agent with more turns
    async with EnhancedForecastingAgent(max_turns=config.max_turns) as agent:
        print("🔬 Starting deep research forecasting...")
        print("This may take several minutes for complex questions.\n")

        # Override the prompt to use deep research version
        original_forecast_method = agent.forecast

        async def enhanced_forecast(*args, **kwargs):
            # Modify the prompt
            trajectory = await original_forecast_method(*args, **kwargs)
            return trajectory

        # Run forecast
        trajectory = await agent.forecast(
            question=question,
            question_type=question_type,
            context=context
        )

        print(f"\n✅ Forecast complete!")
        print(f"   Duration: {trajectory.duration_seconds:.1f} seconds")
        print(f"   Tool Calls: {trajectory.total_tool_calls}")
        print(f"   Models Generated: {trajectory.total_models_generated}")
        print(f"   Reasoning Steps: {trajectory.total_reasoning_steps}")

        # Check if requirements met
        warnings = []
        if trajectory.total_tool_calls < config.min_research_calls:
            warnings.append(
                f"⚠️  Only {trajectory.total_tool_calls} research calls "
                f"(minimum {config.min_research_calls} recommended)"
            )
        if trajectory.total_models_generated < config.min_models:
            warnings.append(
                f"⚠️  Only {trajectory.total_models_generated} models "
                f"(minimum {config.min_models} recommended)"
            )

        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"   {warning}")

        # Export complete trajectory as JSON
        json_path = output_path / f"{base_filename}_trajectory.json"
        trajectory_dict = trajectory.to_dict()

        with open(json_path, "w") as f:
            json.dump(trajectory_dict, f, indent=2, default=str)

        print(f"\n📄 Saved trajectory JSON: {json_path}")

        # Export full conversation as markdown
        md_path = output_path / f"{base_filename}_conversation.md"
        with open(md_path, "w") as f:
            f.write(f"# Research Report: {question}\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Type**: {question_type}\n\n")
            f.write("---\n\n")
            f.write(trajectory.full_conversation)

        print(f"📄 Saved conversation markdown: {md_path}")

        # Export structured report
        report_path = output_path / f"{base_filename}_report.json"
        report = {
            "question": question,
            "question_type": question_type,
            "context": context,
            "generated_at": datetime.now().isoformat(),
            "duration_seconds": trajectory.duration_seconds,
            "statistics": {
                "total_tool_calls": trajectory.total_tool_calls,
                "total_models_generated": trajectory.total_models_generated,
                "total_reasoning_steps": trajectory.total_reasoning_steps,
            },
            "research_findings": {
                "tool_calls": [
                    {
                        "tool": tc.tool_name,
                        "inputs": tc.inputs,
                        "outputs": tc.outputs[:500],  # Truncate long outputs
                        "timestamp": tc.timestamp.isoformat(),
                    }
                    for tc in trajectory.tool_calls
                ],
            },
            "models": [
                {
                    "id": model.model_id,
                    "name": model.name,
                    "code": model.code,
                    "description": model.description,
                    "result": model.result,
                    "error": model.error,
                }
                for model in trajectory.squiggle_models
            ],
            "final_forecast": {
                "value": trajectory.final_forecast,
                "confidence": trajectory.confidence,
                "reasoning": trajectory.final_reasoning,
                "selected_model_id": trajectory.selected_model_id,
            },
        }

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"📄 Saved structured report: {report_path}")

        # Print summary
        print(f"\n{'='*80}")
        print("FORECAST SUMMARY")
        print(f"{'='*80}")
        print(f"Forecast: {trajectory.final_forecast}")
        print(f"Confidence: {trajectory.confidence}")
        print(f"\nReasoning:")
        print(trajectory.final_reasoning or "(No final reasoning provided)")
        print(f"\n{'='*80}\n")

        return {
            "trajectory": trajectory_dict,
            "files": {
                "trajectory_json": str(json_path),
                "conversation_md": str(md_path),
                "report_json": str(report_path),
            },
            "forecast": trajectory.final_forecast,
            "confidence": trajectory.confidence,
        }


async def main():
    """Main entry point."""
    print("="*80)
    print("DEEP RESEARCH FORECASTING")
    print("="*80)
    print("\nThis mode is designed for complex, high-stakes questions that require")
    print("extensive research and multiple forecasting models.")
    print("\nExamples:")
    print("- AI extinction risk timing")
    print("- Geopolitical developments")
    print("- Long-term technological trends")
    print("="*80)

    # Get question from user
    print("\nEnter your forecasting question:")
    question = input("> ").strip()

    if not question:
        print("No question provided. Exiting.")
        return

    # Ask for question type
    print("\nQuestion type:")
    print("1. Binary (yes/no, will/won't)")
    print("2. Numerical (how many, what value)")
    print("3. Categorical (which option)")
    choice = input("Select (1/2/3) [default: 1]: ").strip() or "1"

    question_type_map = {"1": "binary", "2": "numerical", "3": "categorical"}
    question_type = question_type_map.get(choice, "binary")

    # Ask for context
    print("\nOptional context (press Enter to skip):")
    context = input("> ").strip()

    # Configure deep research
    print("\nResearch depth:")
    print("1. Standard (25 turns, 3 models)")
    print("2. Deep (50 turns, 5 models) - Recommended for complex questions")
    print("3. Extensive (100 turns, 7 models) - For critical decisions")
    print("4. Custom")
    depth_choice = input("Select (1/2/3/4) [default: 2]: ").strip() or "2"

    if depth_choice == "1":
        config = DeepResearchConfig(max_turns=25, min_models=3, min_research_calls=5)
    elif depth_choice == "2":
        config = DeepResearchConfig(max_turns=50, min_models=5, min_research_calls=10)
    elif depth_choice == "3":
        config = DeepResearchConfig(max_turns=100, min_models=7, min_research_calls=15)
    elif depth_choice == "4":
        max_turns = int(input("Max turns: "))
        min_models = int(input("Min models: "))
        min_research_calls = int(input("Min research calls: "))
        config = DeepResearchConfig(
            max_turns=max_turns,
            min_models=min_models,
            min_research_calls=min_research_calls
        )
    else:
        config = DeepResearchConfig()

    # Run deep research
    result = await deep_research_forecast(
        question=question,
        question_type=question_type,
        context=context,
        config=config
    )

    print("\n✅ Deep research forecasting complete!")
    print(f"\nFiles saved:")
    for file_type, file_path in result["files"].items():
        print(f"   {file_type}: {file_path}")


if __name__ == "__main__":
    asyncio.run(main())
