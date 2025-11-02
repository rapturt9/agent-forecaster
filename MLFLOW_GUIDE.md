# MLflow Integration Guide

## Overview

The forecasting agent now includes **MLflow 3** integration for complete observability and evaluation. This captures:

- ✅ Complete agent traces with all tool calls
- ✅ Squiggle models generated with code
- ✅ Research sources and reasoning
- ✅ Brier scores and calibration metrics
- ✅ Conversation logs and artifacts

## Quick Start

### 1. Install MLflow

```bash
pip install mlflow>=3.1.0
# or
pip install -r requirements.txt
```

### 2. Run Forecasts with MLflow

```bash
python scripts/forecast_with_mlflow.py
```

Choose option:
- `1` - Test on first question
- `2` - Run all questions
- `3` - Run specific question

### 3. View MLflow UI

```bash
mlflow ui
```

Then open: http://127.0.0.1:5000

## What Gets Tracked

### Automatic Tracing

MLflow automatically captures:
- **Tool Calls**: All MCP tool invocations (search_news, web_research)
- **Inputs/Outputs**: Complete data for each step
- **Timing**: Duration of each operation
- **Errors**: Any failures or exceptions

### Logged Artifacts

Each forecast run includes:
- `conversation.txt` - Complete agent conversation
- `reasoning.txt` - Final reasoning explanation
- `squiggle_models.txt` - All models generated
- `trajectory.json` - Complete execution trace

### Metrics Tracked

**Per Forecast:**
- `forecast_value` - The probability estimate
- `confidence_score` - Mapped confidence level
- `duration_seconds` - Total forecast time
- `total_tool_calls` - Number of research calls
- `total_models_generated` - Squiggle models created
- `brier_score` - Accuracy metric (when resolved)

**Aggregated:**
- `avg_brier_score` - Average across all forecasts
- `calibration_error` - How well-calibrated predictions are
- `avg_duration_seconds` - Average forecast time
- `avg_tool_calls` - Average research thoroughness

## Custom Evaluation Scorers

### Built-in Scorers

1. **Brier Score Scorer** - Core accuracy metric
   ```python
   @scorer
   def brier_score_scorer(predictions, targets):
       # Calculates (forecast - outcome)²
   ```

2. **Research Quality Scorer** - Did agent research properly?
   ```python
   @scorer
   def research_quality(trace):
       # Checks if both search_news and web_research used
       # Returns score 0-1
   ```

3. **Tool Efficiency Scorer** - Avoid redundant calls
   ```python
   @scorer
   def tool_efficiency(trace):
       # Penalizes redundant and excessive tool calls
   ```

4. **Model Generation Scorer** - Generated multiple models?
   ```python
   @scorer
   def model_generation_quality(trace):
       # Looks for MODEL 1, MODEL 2, etc.
   ```

### LLM-Based Judges

Uses Claude Haiku (fast + cheap) to evaluate:

1. **Reasoning Clarity Judge**
   - Evaluates if reasoning is clear and logical
   - Checks for evidence and transparency

2. **Base Rate Usage Judge**
   - Verifies consideration of historical frequencies
   - Ensures proper forecasting methodology

## MLflow UI Navigation

### Experiments Tab

View all forecasting experiments:
- Click on `forecasting_v1` experiment
- See list of all forecast runs
- Filter by tags (question_type, question_id)

### Runs Tab

For each run, view:
- **Parameters**: Question, type, ID
- **Metrics**: Forecast value, Brier score, duration
- **Artifacts**: Conversation logs, models, trajectory
- **Tags**: Metadata and categorization

### Traces Tab

See detailed execution traces:
- Tool call sequence
- Timing breakdown
- Input/output data
- Error tracking

### Models Tab

View grouped forecasts by model:
- `forecasting_agent_v1` - All forecasts from this version
- Aggregated metrics
- Performance trends

## Comparing Forecast Iterations

### Scenario: Test Prompt Changes

```python
# Version 1: Original prompt
async with MLflowForecastingAgent(
    model_name="forecasting_agent_v1",
    experiment_name="prompt_comparison"
) as agent:
    forecast1, run_id1 = await agent.forecast(question)

# Version 2: Modified prompt
# (After updating prompts.py)
async with MLflowForecastingAgent(
    model_name="forecasting_agent_v2",
    experiment_name="prompt_comparison"
) as agent:
    forecast2, run_id2 = await agent.forecast(question)
```

Then in MLflow UI:
1. Go to "prompt_comparison" experiment
2. Select both runs
3. Click "Compare"
4. See side-by-side metrics, traces, artifacts

## Evaluation with MLflow

### Run Batch Evaluation

```python
import mlflow
from src.evaluation.mlflow_scorers import ALL_SCORERS

# Load your questions as dataset
dataset = mlflow.genai.create_dataset(
    name="forecasting_questions",
    experiment_id=experiment.experiment_id,
)

# Run evaluation
results = mlflow.genai.evaluate(
    data=dataset,
    predict_fn=run_forecast_with_mlflow,
    scorers=ALL_SCORERS,
    model="forecasting_agent_v1",
)
```

### View Evaluation Results

Results include:
- Individual question scores
- Aggregate statistics
- Pass/fail rates for judges
- Comparison tables

## Export Research Reports

### Get Complete Trajectory

```python
import mlflow

# Get run by ID
run = mlflow.get_run(run_id)

# Download artifacts
client = mlflow.MlflowClient()
artifacts = client.list_artifacts(run_id)

# Get trajectory
trajectory_path = client.download_artifacts(run_id, "trajectory.json")
with open(trajectory_path) as f:
    trajectory = json.load(f)

# Now you have:
# - trajectory["tool_calls"] - All research
# - trajectory["squiggle_models"] - All models
# - trajectory["reasoning_steps"] - Thought process
# - trajectory["final_forecast"] - Prediction
```

### Generate LaTeX Report

```python
def generate_research_report(run_id):
    """Generate LaTeX report from MLflow run."""
    run = mlflow.get_run(run_id)
    trajectory = load_trajectory(run_id)

    report = r"""\documentclass{article}
\begin{document}

\section{Question}
""" + trajectory["question"] + r"""

\section{Research}
"""
    for tool_call in trajectory["tool_calls"]:
        report += f"\\subsection{{{tool_call['tool_name']}}}\n"
        report += tool_call["outputs"][:500] + "\n\n"

    report += r"""
\section{Squiggle Models}
"""
    for model in trajectory["squiggle_models"]:
        report += f"\\subsection{{{model['name']}}}\n"
        report += "\\begin{verbatim}\n" + model["code"] + "\n\\end{verbatim}\n"

    report += r"""
\section{Final Forecast}
""" + str(trajectory["final_forecast"]) + r"""

\end{document}
"""
    return report
```

## Best Practices

1. **Consistent Model Names** - Use versioned names like `forecasting_agent_v1`, `v2`, etc.

2. **Tag Everything** - Add tags for:
   - Question category
   - Question difficulty
   - Date/time of forecast
   - Model version

3. **Regular Evaluation** - Run batch evaluations after changes:
   - Prompt modifications
   - Tool updates
   - Model changes

4. **Track Calibration** - Monitor calibration error over time:
   ```python
   calibration_monitor = CalibrationMonitor()
   # Add forecasts...
   calibration_monitor.log_to_mlflow()
   ```

5. **Clean Experiments** - Archive old experiments:
   ```bash
   mlflow experiments delete --experiment-id <id>
   ```

## Troubleshooting

### MLflow UI Not Starting

```bash
# Check if port 5000 is in use
lsof -i :5000

# Use different port
mlflow ui --port 5001
```

### Traces Not Appearing

Make sure you call:
```python
mlflow.anthropic.autolog()  # Enable auto-tracing
mlflow.set_active_model(name="your_model")  # Set active model
```

### Large Artifact Sizes

If artifacts are too large:
```python
# Truncate long outputs
mlflow.log_text(text[:1000], "output.txt")  # Only first 1000 chars
```

## API Keys

- **MLflow**: No API key needed (open source)
- **LLM Judges**: Need `ANTHROPIC_API_KEY` for Claude-based judges
  - Optional: Can skip judges and use only Python scorers
  - Judges cost ~$0.001 per evaluation (Haiku pricing)

## Next Steps

1. Run test forecast: `python scripts/forecast_with_mlflow.py`
2. View UI: `mlflow ui`
3. Explore traces, metrics, artifacts
4. Compare different prompt versions
5. Export research reports

## Resources

- MLflow 3 Documentation: https://mlflow.org/docs/latest/index.html
- MLflow Tracing: https://mlflow.org/docs/latest/llms/tracing/index.html
- GenAI Evaluation: https://mlflow.org/docs/latest/llms/llm-evaluate/index.html
