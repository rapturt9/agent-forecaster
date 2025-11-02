# AI Extinction Risk Forecasting Guide

This guide explains how to use the deep research forecasting system for complex AI safety questions.

## Overview

The deep research mode is specifically designed for high-stakes, complex questions like:
- "When will AI be powerful enough to pose extinction-level risk?"
- "What is the probability of AI alignment being solved by 2030?"
- "Will AGI be developed before 2040?"

## Features

### 1. Enhanced JSON Export
All forecasts export complete JSON with:
- **All models**: Every Squiggle model with code, assumptions, and results
- **All reasoning steps**: Complete thought process captured
- **Research findings**: All tool calls with inputs and outputs
- **Final forecast**: Probability, confidence, and detailed reasoning

### 2. Configurable Reasoning Depth

Choose research intensity:
- **Standard** (25 turns, 3 models, 5 research calls): Quick forecasts
- **Deep** (50 turns, 5 models, 10 research calls): Recommended for complex questions
- **Extensive** (100 turns, 7 models, 15 research calls): Critical decisions
- **Custom**: Set your own parameters

### 3. Full Research Reports

Three output formats:
- `trajectory.json`: Complete execution trace with all data
- `conversation.md`: Human-readable conversation format
- `report.json`: Structured report with research findings

## Quick Start

### 1. Basic Usage

```bash
python scripts/deep_research_forecast.py
```

Then follow the prompts:
1. Enter your question
2. Select question type (binary/numerical/categorical)
3. Add context (optional)
4. Choose research depth

### 2. Example: AI Extinction Risk

```bash
python scripts/deep_research_forecast.py
```

Input:
```
Question: When will AI be powerful enough to cause extinction-level risk on its own?
Type: 2 (numerical)
Context: Consider current AI capabilities, scaling trends, safety research progress
Research depth: 3 (extensive)
```

The agent will:
1. Search recent AI safety news
2. Research AI capability trends
3. Find expert forecasts (Metaculus, Good Judgment, etc.)
4. Analyze historical technology timelines
5. Build 7+ forecasting models
6. Generate comprehensive report

### 3. Output Files

All files saved to `research_reports/` directory:

**Trajectory JSON** (`*_trajectory.json`):
```json
{
  "question": "When will AI...",
  "tool_calls": [
    {
      "tool_name": "search_news",
      "inputs": {"query": "AI safety progress 2025"},
      "outputs": "Recent developments in AI safety...",
      "timestamp": "2025-11-02T12:00:00"
    },
    ...
  ],
  "squiggle_models": [
    {
      "model_id": 1,
      "name": "Bio-anchors Model",
      "code": "// Squiggle code...",
      "description": "Based on biological anchors...",
      "result": null
    },
    ...
  ],
  "final_forecast": 2035,
  "confidence": "moderate",
  "final_reasoning": "..."
}
```

**Conversation MD** (`*_conversation.md`):
- Full conversation in markdown format
- All research findings
- All models with Squiggle code
- Final reasoning

**Report JSON** (`*_report.json`):
- Structured summary
- Statistics (tool calls, models, timing)
- Research findings organized
- All models with metadata
- Final forecast with reasoning

## Advanced Usage

### Python API

```python
from scripts.deep_research_forecast import (
    deep_research_forecast,
    DeepResearchConfig
)

# Configure deep research
config = DeepResearchConfig(
    max_turns=100,  # More conversation turns
    min_models=7,   # Require 7+ models
    min_research_calls=20,  # Extensive research
    generate_full_report=True
)

# Run forecast
result = await deep_research_forecast(
    question="When will AI pose extinction-level risk?",
    question_type="numerical",
    context="Consider AGI timelines, alignment difficulty, and current trends",
    config=config,
    output_dir="ai_risk_reports"
)

# Access results
print(f"Forecast: {result['forecast']}")
print(f"Files: {result['files']}")
```

### With MLflow Tracking

Combine deep research with MLflow:

```python
from src.agent.mlflow_forecaster import MLflowForecastingAgent
from scripts.deep_research_forecast import DeepResearchConfig

async with MLflowForecastingAgent(
    model_name="ai_risk_forecaster_v1",
    experiment_name="ai_extinction_risk",
    use_enhanced=True,
) as agent:
    # Override max_turns for deep research
    agent.forecaster.max_turns = 100

    forecast, run_id = await agent.forecast(
        question="When will AI pose extinction-level risk?",
        question_type="numerical",
        context="Deep research mode - extensive analysis required",
        question_id="ai_xrisk_timeline"
    )

    print(f"MLflow Run: {run_id}")
    print(f"View at: http://127.0.0.1:5000")
```

## Example Questions for AI Safety

### Binary Questions
- "Will AGI be developed before 2030?"
- "Will AI alignment be solved before transformative AI?"
- "Will there be an AI-caused catastrophe (>1M deaths) by 2040?"

### Numerical Questions
- "When will AI systems be powerful enough to pose extinction risk?"
- "What year will we achieve human-level AGI?"
- "How many years between AGI and superintelligence?"

### Research Focus Areas

The deep research mode will investigate:
1. **Historical trends**: Moore's law, compute scaling, algorithmic progress
2. **Current developments**: Latest model capabilities, safety research
3. **Expert opinions**: Metaculus, forecasters, AI safety researchers
4. **Scaling laws**: Chinchilla, Kaplan et al., emergent capabilities
5. **Timelines**: Bio-anchors, compute trends, trial-and-error models
6. **Safety progress**: Alignment research, interpretability, control
7. **Wildcard scenarios**: Unexpected breakthroughs, coordination failures

## Tips for AI Risk Forecasting

### 1. Use Extensive Research Mode
AI risk questions require deep analysis:
```bash
Research depth: 3 (extensive)
```

### 2. Provide Rich Context
Include relevant considerations:
```
Context: Consider:
- Current frontier model capabilities (GPT-4, Claude 3.5 Sonnet)
- Compute scaling trends (10x/year)
- AI safety research progress
- Alignment difficulty (inner/outer alignment, deception)
- Deployment timelines vs safety work
- International coordination
```

### 3. Review Multiple Models
The agent should generate models like:
- Bio-anchors model (Cotra)
- Compute-based extrapolation
- Trial-and-error model (Davidson)
- Expert aggregation
- Inside view (causal model)
- Outside view (reference class)
- Fermi estimation

### 4. Check Research Quality
After forecast, verify:
- ✅ At least 15 research calls for extensive mode
- ✅ Recent AI safety news searched
- ✅ Expert forecasts consulted
- ✅ Multiple model classes represented
- ✅ Uncertainty quantified

### 5. Iterate and Refine
Run multiple forecasts:
```bash
# Run 1: Initial forecast
python scripts/deep_research_forecast.py

# Run 2: After reviewing output, refine context
python scripts/deep_research_forecast.py

# Compare results in research_reports/
```

## Output Examples

### Example Model: Bio-Anchors

```squiggle
// Bio-anchors model for AGI timeline
// Based on Cotra (2020) report

// Compute requirements (FLOP)
neuronCount = 100B to 100T
synapseCount = 100T to 1000T
neuralCompute = neuronCount * synapseCount * 100 // Hz

// When will we have this compute?
mooresLaw = 2 // Doubling every 2 years
currentYear = 2025
computeAvailableYear(flop) = currentYear + log2(flop / currentCompute) * mooresLaw

// AGI timeline distribution
shortTimeline = computeAvailableYear(1e28)  // ~2030
mediumTimeline = computeAvailableYear(1e32) // ~2040
longTimeline = computeAvailableYear(1e36)   // ~2050

// Weighted mixture
mixture(
  [shortTimeline, mediumTimeline, longTimeline],
  [0.2, 0.5, 0.3]
)
```

### Example Final Reasoning

```
FINAL FORECAST: 2037 (median), range 2030-2050

CONFIDENCE: Moderate

REASONING:
Based on comprehensive analysis of AI capability trends, expert forecasts,
and multiple modeling approaches, transformative AI capable of posing
extinction-level risk is most likely to emerge in the mid-2030s.

Key factors:
1. Compute scaling continues at historical rates (10x/2 years)
2. Algorithmic progress remains significant but not accelerating
3. No major coordination on safety slowing deployment
4. Bio-anchors and trial-and-error models converge on 2035-2040
5. Expert forecasts (Metaculus, Good Judgment) cluster around 2037

Major uncertainties:
- Algorithmic breakthroughs (transformers-level paradigm shift)
- Alignment difficulty (inner alignment may be harder than expected)
- International coordination on safety standards
- Compute availability (chip restrictions, power constraints)
- Takeoff speed (fast vs slow takeoff changes risk profile)

This forecast assumes "business as usual" - no major shocks or coordination
changes. A successful pause-and-safety-catch-up could push timeline to 2050+,
while algorithmic breakthroughs could bring it to early 2030s.
```

## Integration with Research Workflow

### 1. Initial Forecast
```bash
python scripts/deep_research_forecast.py
# Save to research_reports/
```

### 2. Review Output
```bash
# Read the reports
cat research_reports/*_report.json | jq '.models'
cat research_reports/*_conversation.md
```

### 3. Extract for Publications
```python
import json

# Load trajectory
with open("research_reports/20251102_120000_AI_risk_trajectory.json") as f:
    data = json.load(f)

# Extract models for paper
models = data["squiggle_models"]

# Extract sources for bibliography
sources = [tc["outputs"] for tc in data["tool_calls"]
           if "url" in tc["outputs"].lower()]
```

### 4. Compare Across Time
```bash
# Run monthly forecasts
# Compare how estimates change with new evidence
python scripts/deep_research_forecast.py  # Jan 2025
python scripts/deep_research_forecast.py  # Feb 2025
python scripts/deep_research_forecast.py  # Mar 2025

# Analyze drift in forecasts
```

## Resources

- **OpenPhil AI Timelines**: https://www.openphilanthropy.org/research/ai-timelines/
- **Metaculus AI Questions**: https://www.metaculus.com/questions/?topic=ai
- **Alignment Forum**: https://www.alignmentforum.org/
- **AI Impacts**: https://aiimpacts.org/
- **Forecasting Research Institute**: https://forecastingresearch.org/

## Troubleshooting

### Not Enough Research
If agent doesn't use tools enough:
- Increase max_turns (50 → 100)
- Use "extensive" research mode
- Add explicit instructions in context: "Use at least 15 research tool calls"

### Models Too Simple
If models aren't detailed enough:
- Increase min_models (5 → 7)
- Provide example model in context
- Use "extensive" mode for more thinking time

### Environment Variables Not Loading
Make sure `.env` has:
```bash
ANTHROPIC_API_KEY=...
ASKNEWS_CLIENT_ID=...
ASKNEWS_CLIENT_SECRET=...
PERPLEXITY_API_KEY=...
```

All agents now automatically load from `.env` on initialization.

## Next Steps

1. Run your first AI risk forecast
2. Review the generated models
3. Iterate with refined context
4. Track forecasts over time with MLflow
5. Generate research reports for publications
