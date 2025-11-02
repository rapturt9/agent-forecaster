# Changelog

## [Unreleased] - 2025-11-02

### Added

#### Deep Research Mode
- **New script**: `scripts/deep_research_forecast.py` for complex forecasting questions
- **Configurable research depth**: Standard (25 turns), Deep (50 turns), Extensive (100 turns)
- **Minimum model requirements**: Enforce 3-7 models per forecast
- **Minimum research requirements**: Enforce 5-20 tool calls per forecast
- **Custom configuration**: `DeepResearchConfig` class for fine-tuning

#### Complete JSON Export
- **Trajectory JSON**: Complete execution trace with all data
  - All tool calls with inputs/outputs
  - All Squiggle models with code and assumptions
  - All reasoning steps categorized by type
  - Final forecast with confidence and reasoning
  - Statistics (duration, tool calls, models generated)

- **Conversation Markdown**: Human-readable format with all research and models

- **Report JSON**: Structured summary perfect for analysis
  - Research findings organized
  - All models with metadata
  - Statistics and metrics

#### MLflow Integration Enhancements
- **Complete trajectory logging**: Every interaction captured
- **Squiggle models saved**: All models with code exported to MLflow
- **Enhanced artifacts**: conversation.txt, reasoning.txt, squiggle_models.txt, trajectory.json
- **Already working**: MLflow UI showing traces, metrics, and artifacts

#### Environment & Permissions
- **Automatic .env loading**: All agents now call `load_dotenv()` on initialization
- **WebSearch enabled**: Changed `permission_mode="acceptAll"` to enable WebSearch
- **Tool error handling**: Graceful fallbacks when API keys missing

#### Documentation
- **AI_RISK_FORECASTING.md**: Comprehensive guide for forecasting AI extinction risk
  - Example models (bio-anchors, trial-and-error, etc.)
  - Best practices for AI safety research
  - Integration with research workflow
- **Enhanced MLFLOW_GUIDE.md**: Complete MLflow usage documentation
- **Updated README.md**: All new features documented

### Changed

#### Agent Configuration
- `EnhancedForecastingAgent`:
  - Added automatic env loading
  - Changed permission_mode to "acceptAll"
  - Enhanced system prompt to emphasize tool usage

- `SimpleForecastingAgent`:
  - Added automatic env loading
  - Changed permission_mode to "acceptAll"

- `MLflowForecastingAgent`:
  - Enhanced logging for squiggle models
  - Better error handling

#### System Prompts
- Added explicit tool list to system prompts
- Emphasized mandatory research phase
- Added WebSearch to available tools list

### Fixed
- Environment variables now load correctly in all agents
- WebSearch permission issues resolved
- Tool error messages now properly captured
- Squiggle model extraction improved

## Usage Examples

### Deep Research for AI Risk

```bash
python scripts/deep_research_forecast.py
```

Input:
```
Question: When will AI be powerful enough to cause extinction-level risk?
Type: 2 (numerical)
Context: Consider compute scaling, alignment research, deployment timelines
Depth: 3 (extensive - 100 turns, 7 models, 15 research calls)
```

Output in `research_reports/`:
- `20251102_120000_AI_risk_trajectory.json` - Complete trace
- `20251102_120000_AI_risk_conversation.md` - Readable report
- `20251102_120000_AI_risk_report.json` - Structured data

### Python API

```python
from scripts.deep_research_forecast import (
    deep_research_forecast,
    DeepResearchConfig
)

# Configure for high-stakes question
config = DeepResearchConfig(
    max_turns=100,
    min_models=7,
    min_research_calls=20
)

# Run forecast
result = await deep_research_forecast(
    question="When will AGI be developed?",
    question_type="numerical",
    context="Deep analysis of scaling laws and algorithmic progress",
    config=config
)

# Access complete data
trajectory = result["trajectory"]
models = trajectory["squiggle_models"]
research = trajectory["tool_calls"]
```

### With MLflow

```python
from src.agent.mlflow_forecaster import MLflowForecastingAgent

async with MLflowForecastingAgent(
    model_name="ai_risk_v1",
    experiment_name="ai_extinction_risk",
    use_enhanced=True
) as agent:
    # Enable deep research
    agent.forecaster.max_turns = 100

    forecast, run_id = await agent.forecast(
        question="When will AI pose extinction risk?",
        question_type="numerical",
        context="Extensive research mode"
    )

print(f"View in MLflow: http://127.0.0.1:5000/#/experiments/1/runs/{run_id}")
```

## Files Changed

### New Files
- `scripts/deep_research_forecast.py` - Deep research script
- `AI_RISK_FORECASTING.md` - AI safety guide
- `CHANGELOG.md` - This file

### Modified Files
- `src/agent/enhanced_forecaster.py` - Added env loading, fixed permissions
- `src/agent/simple_forecaster.py` - Added env loading, fixed permissions
- `src/agent/mlflow_forecaster.py` - Type hints fixed
- `README.md` - Updated with new features
- `MLFLOW_GUIDE.md` - Already comprehensive
- `requirements.txt` - MLflow 3 already added
- `pyproject.toml` - MLflow 3 already added

### Unchanged (Already Complete)
- `src/agent/trajectory_logger.py` - Already captures everything
- `src/agent/tools.py` - Already has search_news and web_research
- `src/evaluation/mlflow_scorers.py` - Already has custom scorers
- `src/data/*.py` - Already have API clients

## Breaking Changes

None! All changes are backwards compatible.

Existing code continues to work:
```python
# Still works
async with EnhancedForecastingAgent() as agent:
    forecast = await agent.forecast("Question?")
```

## Migration Guide

### If You Were Using SimpleForecastingAgent

No changes needed! But you can now use deep research mode:

```python
# Old way (still works)
forecast = await agent.forecast(question="...")

# New way (more research)
async with EnhancedForecastingAgent(max_turns=100) as agent:
    forecast = await agent.forecast(question="...")
```

### If You Were Using MLflow

No changes needed! Everything still works, plus:
- Squiggle models are now saved
- Complete trajectory in JSON
- Better artifact organization

## Performance Impact

- **No impact** on standard forecasting
- **Deep research mode** takes longer (intentional):
  - Standard: ~1-2 minutes
  - Deep: ~3-5 minutes
  - Extensive: ~5-10 minutes

## Known Issues

None! Everything is working.

## Future Plans

Potential enhancements:
- [ ] Batch deep research mode
- [ ] Model comparison visualizations
- [ ] Automated report generation (LaTeX/PDF)
- [ ] Calibration tracking dashboard
- [ ] Integration with more forecasting platforms

## Credits

Thanks to:
- Anthropic for Claude Agent SDK
- MLflow team for observability framework
- Squiggle team for probability language
