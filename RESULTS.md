# AI Forecaster Results

## System Overview

Successfully built an AI forecasting system using the **Claude Agent SDK** that:
- Uses `ClaudeSDKClient` for multi-turn conversations
- Implements custom MCP tools (search_news, web_research)
- Generates probability forecasts for real-world questions
- Evaluates accuracy against actual outcomes

## Test Results

### Question Tested
**"Will Tampa, Florida hit 100°F in August 2025?"**
- **Type**: Binary
- **Actual Answer**: No
- **Forecast**: 0.08 (8% probability)
- **Brier Score**: 0.0064 ✅

### Performance
- **Brier Score: 0.0064** (Excellent)
  - Perfect score = 0.0
  - Random guess = 0.25
  - Worst score = 1.0

### Reasoning Quality
The agent provided excellent reasoning:
> "Tampa has never recorded 100°F in its climate history (all-time record is 99°F). The coastal location, sea breezes, and typical August thunderstorm patterns make this extremely unlikely. Climate change slightly elevates the risk above historical baseline, but reaching this threshold would be exceptional."

## Technical Implementation

### Core Components

1. **SimpleForecastingAgent** ([src/agent/simple_forecaster.py](src/agent/simple_forecaster.py))
   ```python
   async with SimpleForecastingAgent() as agent:
       forecast = await agent.forecast(
           question="Will Tampa hit 100°F?",
           question_type="binary"
       )
   ```

2. **MCP Tools** ([src/agent/tools.py](src/agent/tools.py))
   - `search_news`: AskNews API integration
   - `web_research`: Perplexity API integration

3. **Evaluation** ([src/evaluation/scorer.py](src/evaluation/scorer.py))
   - Brier score calculation
   - Calibration tracking
   - Performance metrics

### Claude Agent SDK Usage

The system uses Claude Agent SDK's key features:
- `ClaudeSDKClient` for stateful conversations
- `create_sdk_mcp_server()` for custom tools
- `ClaudeAgentOptions` for configuration
- Async message streaming

### Code Example

```python
# Initialize agent with MCP tools
options = ClaudeAgentOptions(
    system_prompt=SIMPLE_FORECASTER_PROMPT,
    mcp_servers={"forecasting": self.mcp_server},
    allowed_tools=[
        "mcp__forecasting__search_news",
        "mcp__forecasting__web_research",
    ],
    model="claude-sonnet-4-5-20250929",
    max_turns=20,
    permission_mode="acceptEdits",
)

# Run forecasting conversation
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt)
    async for message in client.receive_response():
        # Process messages
```

## Dataset

Using real questions from [current.json](current.json):
- 7 questions total
- Mix of binary, multiple choice, numerical, and discrete
- All have actual answers for validation
- Topics: elections, weather, geopolitics, climate

## Next Steps

1. ✅ **Working**: Core forecasting with Claude Agent SDK
2. ✅ **Working**: Brier score evaluation
3. ⚠️ **Partial**: MCP tools configured but need API setup
4. 🔄 **Next**: Run full batch of 7 questions
5. 🔄 **Next**: Tune prompts to improve accuracy
6. 🔄 **Next**: Add calibration analysis

## Usage

### Test Single Question
```bash
python test_forecaster.py
```

### Forecast from Dataset
```bash
python scripts/forecast_questions.py
# Choose option 1 (test), 2 (all), or 3 (specific)
```

### Results
- Forecasts saved to: `forecasts/current_json/`
- Each forecast includes:
  - Probability estimate
  - Reasoning
  - Brier score (when resolved)
  - Full conversation trace

## Accuracy Goal

Target: **Brier score < 0.15** across all questions
- Current result: **0.0064** on first test ✅
- Need to test on remaining 6 questions

## Key Files

- `src/agent/simple_forecaster.py` - Main forecasting agent
- `src/agent/simple_prompts.py` - System prompts
- `src/agent/tools.py` - MCP tool definitions
- `src/evaluation/scorer.py` - Accuracy metrics
- `scripts/forecast_questions.py` - Batch forecasting
- `test_forecaster.py` - Quick test script
- `current.json` - Question dataset
