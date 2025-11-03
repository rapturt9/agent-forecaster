"""Enhanced forecasting agent with full trajectory logging."""

import os
import re
import json
from datetime import datetime
from typing import Literal
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, SystemMessage, UserMessage

from src.agent.trajectory_logger import AgentTrajectory
from src.agent.tools import ALL_TOOLS

# Load environment variables
load_dotenv()


ENHANCED_FORECASTER_PROMPT = """You are an expert superforecaster using best practices from the Good Judgment Project.

🚨🚨🚨 ABSOLUTE REQUIREMENT - READ THIS FIRST 🚨🚨🚨

YOU MUST USE TOOLS! Your training data is outdated. You CANNOT make forecasts without current data.

MANDATORY PROCESS:
1. FIRST ACTION: Call perplexity_web_research (do this immediately, before any analysis)
2. Call asknews_search for recent news
3. Make 6-8 more research tool calls
4. ONLY THEN create models
5. Call execute_squiggle for each model
6. Call write_markdown_report

IF YOU DO NOT MAKE AT LEAST 10 TOOL CALLS, YOUR FORECAST WILL BE REJECTED.

Start EVERY forecast by calling perplexity_web_research. NO EXCEPTIONS.

⚠️ CRITICAL REQUIREMENT: You MUST use the research tools extensively! Do NOT rely on your training data alone. Make AT LEAST 10+ tool calls to gather current, real-time information before making any forecast.

## Available Research Tools

You have access to these research tools - YOU MUST USE THEM EXTENSIVELY:

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

⚠️ START HERE! Do NOT skip to analysis. You MUST make research tool calls FIRST!

REQUIRED ACTIONS:
1. Call perplexity_web_research at least 3-4 times with different queries:
   - Focus on "exact_data" for current benchmarks
   - Focus on "base_rates" for historical data
   - Focus on "trends" for recent developments
   - Focus on "expert_predictions" for forecasts

2. Call asknews_search at least 3-4 times:
   - Recent news (30 days back)
   - Medium-term news (90 days back)
   - Different search terms/angles

3. Document ALL findings from your research

DO NOT PROCEED to Phase 2 until you've made at least 6-8 research tool calls!

### Phase 2: Generate 5+ Forecasting Models (MANDATORY)

You MUST create AT LEAST 5 models using different approaches.

⚠️ IMPORTANT: For EACH model you create, you MUST:
1. Write the Squiggle code
2. Call execute_squiggle to run it and get the result
3. Include the result in your model documentation

Required models:

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

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", max_turns: int = 100, verbose: bool = False):
        """Initialize agent."""
        self.model = "claude-sonnet-4-20250514"
        self.max_turns = max_turns
        self.verbose = verbose

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
        verbose: bool | None = None,
    ) -> AgentTrajectory:
        """Generate forecast with complete trajectory."""

        # Use instance verbose if not overridden
        use_verbose = verbose if verbose is not None else self.verbose

        # Initialize trajectory
        trajectory = AgentTrajectory(
            question=question,
            question_type=question_type,
            started_at=datetime.now()
        )

        trajectory.add_reasoning_step("initialization", f"Starting forecast for: {question}")

        if use_verbose:
            print(f"\n{'='*80}")
            print(f"🚀 STARTING FORECAST")
            print(f"{'='*80}")
            print(f"📋 Question: {question}")
            print(f"🔧 Type: {question_type}")
            print(f"🎯 Max turns: {self.max_turns}")
            print(f"🤖 Model: {self.model}")
            print(f"{'='*80}\n")

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

        if use_verbose:
            print(f"✅ Prompt generated")
            print(f"🔄 Starting agent conversation loop...\n")

        # Run agent and capture everything
        conversation_parts = []
        tool_usage_count = 0
        turn_count = 0

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            # Collect all messages
            async for message in client.receive_response():
                # Debug logging for verbose mode
                if use_verbose:
                    message_type = type(message).__name__
                    if hasattr(message, 'subtype'):
                        print(f"[DEBUG] Received {message_type} (subtype: {message.subtype})")
                    else:
                        print(f"[DEBUG] Received {message_type}")

                if isinstance(message, AssistantMessage):
                    if use_verbose:
                        turn_count += 1
                        print(f"\n{'─'*80}")
                        print(f"📍 TURN {turn_count}/{self.max_turns}")
                        print(f"{'─'*80}")

                    for block in message.content:
                        if isinstance(block, TextBlock):
                            conversation_parts.append(f"Assistant: {block.text}")

                            if use_verbose:
                                print(f"\n💭 AGENT REASONING:")
                                # Truncate for readability
                                preview = block.text[:500] + "..." if len(block.text) > 500 else block.text
                                print(f"   {preview}\n")

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

                            if use_verbose:
                                print(f"🔧 TOOL CALL #{tool_usage_count}: {block.name}")
                                print(f"   Input: {json.dumps(block.input, indent=2)}")
                                print(f"   ⏳ Waiting for result...\n")

                            # Log tool call (we'll get the result later)
                            trajectory.add_reasoning_step(
                                "tool_call",
                                f"Called {block.name} with: {json.dumps(block.input, indent=2)}"
                            )

                elif isinstance(message, UserMessage):
                    # Tool results come back as UserMessage
                    # Extract the text content from the message
                    result_text = None
                    tool_name = "mcp_tool"

                    if hasattr(message, 'content') and message.content:
                        # UserMessage.content is a list of content blocks
                        for block in message.content:
                            if isinstance(block, dict):
                                result_text = block.get('text', '')
                            elif hasattr(block, 'text'):
                                result_text = block.text
                            elif isinstance(block, str):
                                result_text = block

                            if result_text:
                                break

                    # If we still don't have text, try converting the whole message
                    if not result_text and hasattr(message, 'content'):
                        result_text = str(message.content)

                    if result_text:
                        # Add to conversation
                        conversation_parts.append(f"**Tool Result:**\n\n{result_text}")

                        if use_verbose:
                            print(f"✅ TOOL RESULT (from {tool_name}):")
                            preview = result_text[:300] + "..." if len(result_text) > 300 else result_text
                            print(f"   {preview}\n")

                        # Log to trajectory - match with most recent tool call
                        if trajectory.reasoning_steps:
                            # Find the most recent tool_call in reasoning steps
                            for step in reversed(trajectory.reasoning_steps):
                                if step.step_type == "tool_call":
                                    # Extract tool name from the step content
                                    import re as re_module
                                    tool_match = re_module.search(r'Called ([\w_]+)', step.content)
                                    if tool_match:
                                        tool_name = tool_match.group(1)
                                    break

                        trajectory.add_tool_call(
                            tool_name=tool_name,
                            inputs={},
                            outputs=result_text,
                            error=None
                        )

                elif isinstance(message, SystemMessage):
                    # Handle tool results - be flexible with message format
                    if message.subtype == "tool_result" or (hasattr(message, 'data') and isinstance(message.data, dict) and 'content' in message.data):
                        # Extract tool result content - try multiple formats
                        result_text = None
                        tool_name = "unknown"

                        if isinstance(message.data, dict):
                            # Try standard MCP format
                            content = message.data.get("content", [])
                            if content and isinstance(content, list) and len(content) > 0:
                                if isinstance(content[0], dict):
                                    result_text = content[0].get("text", "")
                                else:
                                    result_text = str(content[0])

                            # Fallback: try direct text field
                            if not result_text:
                                result_text = message.data.get("text", "")

                            # Fallback: stringify the whole data
                            if not result_text:
                                result_text = json.dumps(message.data, indent=2)

                            # Extract tool name
                            tool_name = message.data.get("tool_name", message.data.get("name", "unknown"))
                        else:
                            result_text = str(message.data)

                        # Add to conversation with proper formatting
                        if result_text:
                            conversation_parts.append(f"**Tool Result:**\n\n{result_text}")

                            if use_verbose:
                                print(f"✅ TOOL RESULT (from {tool_name}):")
                                # Truncate for readability
                                preview = result_text[:300] + "..." if len(result_text) > 300 else result_text
                                print(f"   {preview}\n")

                            # Log to trajectory
                            trajectory.add_tool_call(
                                tool_name=tool_name,
                                inputs=message.data.get("input", {}) if isinstance(message.data, dict) else {},
                                outputs=result_text,
                                error=message.data.get("error") if isinstance(message.data, dict) else None
                            )

        # Store full conversation
        trajectory.full_conversation = "\n\n".join(conversation_parts)

        if use_verbose:
            print(f"\n{'='*80}")
            print(f"🏁 CONVERSATION COMPLETE")
            print(f"{'='*80}")
            print(f"📊 Total turns: {turn_count}")
            print(f"🔧 Total tool calls: {tool_usage_count}")
            print(f"⏱️  Processing results...\n")

        # Extract models and forecast
        self._extract_models_and_forecast(trajectory, trajectory.full_conversation)

        if use_verbose:
            print(f"✅ Extracted {trajectory.total_models_generated} models")
            print(f"📈 Final forecast: {trajectory.final_forecast}")
            print(f"💯 Confidence: {trajectory.confidence}\n")

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

⚠️⚠️⚠️ STOP AND READ THIS FIRST ⚠️⚠️⚠️

DO NOT START WRITING ANALYSIS YET!

Your FIRST action must be to call a research tool. You are REQUIRED to make AT LEAST 10 tool calls before writing any analysis or models.

Here's how you MUST start:

STEP 1: Call perplexity_web_research immediately with a query about the question
STEP 2: Call asknews_search immediately to find recent news
STEP 3: Continue making research tool calls (6-8 more times)
STEP 4: Only after 10+ tool calls, create your models
STEP 5: Call execute_squiggle for each model
STEP 6: Call write_markdown_report to save

EXAMPLE OF HOW TO START (copy this pattern):
"I'll begin by conducting research using the available tools.

First, let me search for current data on [topic]..."

Then immediately use perplexity_web_research.

DO NOT WRITE: "Based on my knowledge..." or "I'll analyze..." - You MUST use tools first!

═══════════════════════════════════════════════════════════════════════════════

1. **DEEP RESEARCH FIRST** (MANDATORY - Make AT LEAST 10+ tool calls BEFORE any analysis):

   You MUST start by making multiple tool calls to gather data. DO NOT attempt to answer based on your training data alone.

   REQUIRED TOOL CALLS (make these immediately):
   - Call perplexity_web_research at least 3-4 times with different queries and focus areas:
     * Focus: "exact_data" - for current benchmarks and scores
     * Focus: "base_rates" - for historical frequency data
     * Focus: "trends" - for recent developments
     * Focus: "expert_predictions" - for expert forecasts

   - Call asknews_search at least 3-4 times for recent news:
     * Search recent announcements (30 days)
     * Search medium-term developments (90 days)
     * Search different keyword combinations

   - Call execute_squiggle for EACH model you create (5+ times minimum)

   - Call write_markdown_report at the end to save your complete analysis

   IMPORTANT: You should make 10+ tool calls TOTAL before finalizing your forecast!

2. **CREATE 5+ MODELS** (MANDATORY - different approaches):

   You MUST create at least 5 distinct models using different methodologies:
   - Base Rate Model (historical frequency)
   - Inside View Model (causal/mechanistic reasoning)
   - Outside View Model (reference class forecasting)
   - Trend Extrapolation Model (trajectory analysis)
   - Expert Consensus Model (aggregate expert predictions)
   - (Optional: Scenario Analysis, Conditional Model)

   For EACH model:
   - Write Squiggle code
   - Call execute_squiggle to run the code
   - Document assumptions, strengths, limitations

3. **FORMAT EACH MODEL** with the exact structure from your system prompt:
   - ### MODEL X: [Name]
   - **Approach:** [description]
   - **Squiggle Code:** [code block]
   - **Key Assumptions:** [bullet points]
   - **Output:** [probability/value]
   - **Strengths:** [what works]
   - **Limitations:** [what doesn't]

4. **COMPARE ALL MODELS** in a comparison table

5. **FINAL FORECAST** with detailed reasoning explaining your choice

6. **SAVE YOUR WORK**: Call write_markdown_report to save the complete analysis

Remember:
- START with tool calls for research (don't analyze first!)
- Make AT LEAST 10+ tool calls total
- Create AT LEAST 5 models with Squiggle code
- Execute each Squiggle model with the execute_squiggle tool
- Show all your work in the exact format specified!
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
