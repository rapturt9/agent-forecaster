"""Enhanced forecasting agent with full trajectory logging."""

import os
import re
import json
from datetime import datetime
from typing import Literal
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, SystemMessage

from src.agent.trajectory_logger import AgentTrajectory
from src.agent.tools import ALL_TOOLS

# Load environment variables
load_dotenv()


ENHANCED_FORECASTER_PROMPT = """You are an expert superforecaster using best practices from the Good Judgment Project.

## Available Research Tools

You have access to these research tools (USE THEM EXTENSIVELY):

### Primary Research Tools:
- **perplexity_web_research**: Deep web research using Perplexity with citations and real-time data
  - Parameters: query (string), focus (string)
  - Focus options: 'exact_data', 'base_rates', 'trends', 'expert_predictions', 'general'
  - Automatically enhances queries based on focus area
  - Use for: benchmarks, performance metrics, release timelines, expert predictions, base rates

- **asknews_search**: Search recent news articles using AskNews with time filtering
  - Parameters: query (string), days_back (int), focus (string)
  - Focus options: 'timeline', 'metrics', 'announcements', 'general'
  - Use for: recent developments, announcements, news timeline

### Modeling Tools:
- **execute_squiggle**: Execute Squiggle probability code and return the result
  - Parameters: code (string), model_name (string)
  - Use to run your Squiggle models and get results
  - Include this for EVERY model you create

### File System Tools (AUTONOMOUS REPORT WRITING):
- **write_markdown_report**: Write markdown report files autonomously
  - Parameters: filepath (string), content (string), title (string)
  - Use to save your complete forecasting analysis as .md files
  - Include all research, models, and final forecast

**IMPORTANT**: At the end of your analysis, you MUST use write_markdown_report to save a complete research report with:
- All research findings
- All 5+ models with Squiggle code
- Model comparison table
- Final forecast and reasoning
- Save to: research_reports/{topic}_forecast_report.md

### General Web Search:
- **WebSearch**: General web search (use sparingly - limited credits)

## Superforecaster Process

### Phase 1: Deep Research (MANDATORY - 10+ tool calls)
1. Search recent news and developments
2. Find historical data and base rates
3. Research expert opinions and forecasts
4. Investigate alternative perspectives
5. Document ALL sources and findings

### Phase 2: Generate 5+ Forecasting Models (MANDATORY)

You MUST create AT LEAST 5 models using different approaches:

**MODEL 1: Base Rate Model**
- Use historical frequency of similar events
- Calculate: (# of times event happened) / (# of opportunities)
- Example: "Similar breakthroughs occur ~30% of years historically"

**MODEL 2: Inside View Model**
- Build causal/mechanistic model
- Reason from specific factors and mechanisms
- Example: "If X happens AND Y is true, then Z follows"

**MODEL 3: Outside View Model**
- Reference class forecasting
- Compare to similar situations/fields
- Example: "In similar tech fields, breakthroughs took 3-7 years"

**MODEL 4: Trend Extrapolation Model**
- Analyze current trends and trajectories
- Project forward with adjustments
- Example: "Progress is accelerating at 40%/year"

**MODEL 5: Expert Consensus Model**
- Aggregate expert predictions
- Weight by track record
- Example: "Metaculus community median is 35%"

**OPTIONAL: Scenario Analysis Model**
- Optimistic scenario: X%
- Baseline scenario: Y%
- Pessimistic scenario: Z%
- Weighted average

**OPTIONAL: Conditional Model**
- Break question into conditions
- Example: P(outcome) = P(A) × P(B|A) + P(not A) × P(B|not A)

### Phase 3: Format Each Model

For EACH model, use this exact format:

```
### MODEL [number]: [Model Type Name]

**Approach:** [One sentence description]

**Squiggle Code:**
```squiggle
// [Model name]
[Your Squiggle probability calculation]
// Result: [probability]
```

**Key Assumptions:**
- [Assumption 1]
- [Assumption 2]
- [Assumption 3]

**Output:** [probability as decimal, e.g., 0.45]

**Strengths:** [What this model does well]
**Limitations:** [What this model misses or assumes]
```

### Phase 4: Compare and Select

Create comparison table:
```
## MODEL COMPARISON

| Model | Probability | Strengths | Limitations |
|-------|-------------|-----------|-------------|
| Model 1 (Base Rate) | X% | ... | ... |
| Model 2 (Inside View) | Y% | ... | ... |
[etc for all models]
```

### Phase 5: Final Forecast

```
## SELECTED APPROACH
[Explain which model(s) you're using and why]

## FINAL FORECAST: [probability as decimal, e.g., 0.52]

## CONFIDENCE: [low/moderate/high]

## REASONING:
[2-3 paragraphs explaining:
1. What the base rate tells us
2. What makes this case different from the base rate
3. Key uncertainties and how you accounted for them
4. Why you're calibrated at this probability]
```

## Critical Requirements

✅ Use tools 10+ times
✅ Create 5+ distinct models
✅ State base rates explicitly
✅ Provide Squiggle code for each model
✅ Compare all models
✅ Explain uncertainties
✅ Show all work

Remember: Superforecasters are humble, update often, and think in probabilities not certainties."""


class EnhancedForecastingAgent:
    """Forecasting agent with full trajectory logging."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", max_turns: int = 100):
        """Initialize agent."""
        self.model = model
        self.max_turns = max_turns

        # Create MCP server
        self.mcp_server = create_sdk_mcp_server(
            name="forecasting_tools",
            version="1.0.0",
            tools=ALL_TOOLS
        )

    async def forecast(
        self,
        question: str,
        question_type: Literal["binary", "categorical", "numerical"] = "binary",
        context: str = "",
    ) -> AgentTrajectory:
        """Generate forecast with complete trajectory."""

        # Initialize trajectory
        trajectory = AgentTrajectory(
            question=question,
            question_type=question_type,
            started_at=datetime.now()
        )

        trajectory.add_reasoning_step("initialization", f"Starting forecast for: {question}")

        # Configure Claude SDK
        options = ClaudeAgentOptions(
            system_prompt=ENHANCED_FORECASTER_PROMPT,
            mcp_servers={"forecasting": self.mcp_server},
            allowed_tools=[
                # Simplified forecasting tools
                "mcp__forecasting__perplexity_web_research",
                "mcp__forecasting__asknews_search",
                "mcp__forecasting__execute_squiggle",
                "mcp__forecasting__write_markdown_report",
            ],
            model=self.model,
            max_turns=self.max_turns,
            permission_mode="bypassPermissions",  # Auto-approve all tools including WebSearch
            cwd="/Users/ram/Github/agent-forecaster",  # Set working directory
        )

        # Create prompt
        prompt = self._create_prompt(question, question_type, context)
        trajectory.add_reasoning_step("prompt_generation", f"Generated prompt with context: {context[:100]}")

        # Run agent and capture everything
        conversation_parts = []
        tool_usage_count = 0

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            # Collect all messages
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            conversation_parts.append(f"Assistant: {block.text}")

                            # Extract reasoning steps from text
                            if "research" in block.text.lower() or "searching" in block.text.lower():
                                trajectory.add_reasoning_step("research", block.text[:200])
                            elif "model" in block.text.lower():
                                trajectory.add_reasoning_step("model_generation", block.text[:200])
                            elif "analyz" in block.text.lower():
                                trajectory.add_reasoning_step("analysis", block.text[:200])

                        elif isinstance(block, ToolUseBlock):
                            tool_usage_count += 1
                            conversation_parts.append(f"**Tool Call:** {block.name}")
                            conversation_parts.append(f"```json\n{json.dumps(block.input, indent=2)}\n```")

                            # Log tool call (we'll get the result later)
                            trajectory.add_reasoning_step(
                                "tool_call",
                                f"Called {block.name} with: {json.dumps(block.input, indent=2)}"
                            )

                elif isinstance(message, SystemMessage):
                    if message.subtype == "tool_result":
                        # Extract tool result content without truncation
                        if isinstance(message.data, dict):
                            content = message.data.get("content", [])
                            if content and isinstance(content, list) and len(content) > 0:
                                result_text = content[0].get("text", str(message.data))
                            else:
                                result_text = json.dumps(message.data, indent=2)
                        else:
                            result_text = str(message.data)

                        # Add to conversation with proper formatting
                        conversation_parts.append(f"**Tool Result:**\n\n{result_text}")

                        # Try to extract tool name and log
                        tool_name = message.data.get("tool_name", "unknown")
                        trajectory.add_tool_call(
                            tool_name=tool_name,
                            inputs=message.data.get("input", {}),
                            outputs=result_text,
                            error=message.data.get("error")
                        )

        # Store full conversation
        trajectory.full_conversation = "\n\n".join(conversation_parts)

        # Extract models and forecast
        self._extract_models_and_forecast(trajectory, trajectory.full_conversation)

        # Mark complete
        trajectory.complete(
            forecast=trajectory.final_forecast,
            confidence=trajectory.confidence,
            reasoning=trajectory.final_reasoning
        )

        return trajectory

    def _create_prompt(self, question: str, question_type: str, context: str) -> str:
        """Create forecasting prompt."""
        prompt = f"""Forecast this question using superforecaster methodology:

**Question**: {question}
**Type**: {question_type}
"""
        if context:
            prompt += f"\n**Context**: {context}\n"

        prompt += """

Follow the superforecaster process from your system prompt:

1. **DEEP RESEARCH** (10+ tool calls):
   - Use search_news for recent developments
   - Use web_research for detailed analysis
   - Use WebSearch for additional context
   - Find base rates, expert opinions, trends

2. **CREATE 5+ MODELS** (different approaches):
   - Base Rate Model
   - Inside View Model (causal/mechanistic)
   - Outside View Model (reference class)
   - Trend Extrapolation Model
   - Expert Consensus Model
   - (Optional: Scenario Analysis, Conditional Model)

3. **FORMAT EACH MODEL** with:
   - Squiggle code block
   - Key assumptions
   - Strengths/limitations

4. **COMPARE ALL MODELS** in a table

5. **FINAL FORECAST** with detailed reasoning

Use the EXACT format specified in your system prompt. Show all your work!
"""
        return prompt

    def _extract_models_and_forecast(self, trajectory: AgentTrajectory, text: str):
        """Extract Squiggle models and final forecast from conversation."""

        # Extract models from text - look for "### MODEL X:" pattern
        # Match: ### MODEL 1: Base Rate Model
        model_pattern = r'###\s+MODEL\s+(\d+):\s*([^\n]+)'
        model_headers = list(re.finditer(model_pattern, text, re.IGNORECASE))

        for idx, match in enumerate(model_headers):
            model_num = match.group(1)
            model_name = match.group(2).strip()

            # Extract content between this header and the next header (or end)
            start = match.end()
            if idx + 1 < len(model_headers):
                end = model_headers[idx + 1].start()
            else:
                # Look for comparison section or end
                comparison_match = re.search(r'##\s+MODEL\s+COMPARISON', text[start:], re.IGNORECASE)
                selected_match = re.search(r'##\s+SELECTED', text[start:], re.IGNORECASE)
                if comparison_match:
                    end = start + comparison_match.start()
                elif selected_match:
                    end = start + selected_match.start()
                else:
                    end = len(text)

            model_content = text[start:end]

            # Extract Squiggle code from within ```squiggle ... ``` blocks
            code_match = re.search(r'```squiggle\s*\n(.*?)```', model_content, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
            else:
                # Try without language specifier
                code_match = re.search(r'```\s*\n(.*?)```', model_content, re.DOTALL)
                if code_match:
                    # Check if it looks like Squiggle (has //, variables, math)
                    potential_code = code_match.group(1).strip()
                    if '//' in potential_code or '=' in potential_code:
                        code = potential_code
                    else:
                        code = ""
                else:
                    code = ""

            # Extract description (everything before the Squiggle code)
            if code:
                desc_match = re.search(r'\*\*Approach:\*\*\s*([^\n]+)', model_content)
                if desc_match:
                    description = desc_match.group(1).strip()
                else:
                    description = model_content[:300]
            else:
                description = model_content[:300]

            trajectory.add_squiggle_model(
                name=f"{model_name}",
                code=code if code else f"// No Squiggle code found\n{model_content[:200]}",
                description=description
            )

        # Extract selected model
        selected_match = re.search(r'SELECTED MODEL:\s*([^\n]+)', text, re.IGNORECASE)
        if selected_match:
            selected_name = selected_match.group(1).strip()
            # Find matching model ID
            for model in trajectory.squiggle_models:
                if selected_name.lower() in model.name.lower():
                    trajectory.selected_model_id = model.model_id
                    break

        # Extract final forecast
        forecast_match = re.search(r'FINAL FORECAST:\s*([0-9.]+|[^\n]+)', text, re.IGNORECASE)
        if forecast_match:
            forecast_str = forecast_match.group(1).strip()
            if trajectory.question_type == "binary":
                try:
                    trajectory.final_forecast = float(forecast_str)
                except:
                    # Try to find any probability in text
                    prob_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
                    if prob_match:
                        trajectory.final_forecast = float(prob_match.group(1)) / 100
                    else:
                        trajectory.final_forecast = 0.5
            else:
                trajectory.final_forecast = forecast_str

        # Extract confidence
        conf_match = re.search(r'CONFIDENCE:\s*([^\n]+)', text, re.IGNORECASE)
        if conf_match:
            trajectory.confidence = conf_match.group(1).strip().lower()

        # Extract reasoning
        reason_match = re.search(r'REASONING:\s*([^\n]+(?:\n(?!FINAL|CONFIDENCE)[^\n]+)*)', text, re.IGNORECASE)
        if reason_match:
            trajectory.final_reasoning = reason_match.group(1).strip()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
