"""Trajectory logging for detailed agent analysis."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ToolCall(BaseModel):
    """Record of a tool being called."""
    timestamp: datetime
    tool_name: str
    inputs: dict[str, Any]
    outputs: str
    error: str | None = None


class ReasoningStep(BaseModel):
    """A step in the agent's reasoning process."""
    timestamp: datetime
    step_type: str  # "research", "analysis", "model_generation", "synthesis"
    content: str


class SquiggleModel(BaseModel):
    """A Squiggle probability model."""
    model_id: int
    name: str
    code: str
    description: str
    result: Any | None = None
    error: str | None = None
    created_at: datetime


class AgentTrajectory(BaseModel):
    """Complete trajectory of agent's forecasting process."""

    question: str
    question_type: str
    started_at: datetime
    completed_at: datetime | None = None

    # Tool usage
    tool_calls: list[ToolCall] = []

    # Reasoning process
    reasoning_steps: list[ReasoningStep] = []

    # Squiggle models (if used)
    squiggle_models: list[SquiggleModel] = []
    selected_model_id: int | None = None

    # Final output
    final_forecast: float | str | dict | None = None
    confidence: str = "unknown"
    final_reasoning: str = ""

    # Raw conversation
    full_conversation: str = ""

    # Metadata
    total_tool_calls: int = 0
    total_reasoning_steps: int = 0
    total_models_generated: int = 0
    duration_seconds: float = 0.0

    def add_tool_call(self, tool_name: str, inputs: dict, outputs: str, error: str | None = None):
        """Add a tool call to trajectory."""
        self.tool_calls.append(ToolCall(
            timestamp=datetime.now(),
            tool_name=tool_name,
            inputs=inputs,
            outputs=outputs,
            error=error
        ))
        self.total_tool_calls += 1

    def add_reasoning_step(self, step_type: str, content: str):
        """Add a reasoning step."""
        self.reasoning_steps.append(ReasoningStep(
            timestamp=datetime.now(),
            step_type=step_type,
            content=content
        ))
        self.total_reasoning_steps += 1

    def add_squiggle_model(self, name: str, code: str, description: str, result: Any = None, error: str | None = None):
        """Add a Squiggle model."""
        model_id = len(self.squiggle_models) + 1
        self.squiggle_models.append(SquiggleModel(
            model_id=model_id,
            name=name,
            code=code,
            description=description,
            result=result,
            error=error,
            created_at=datetime.now()
        ))
        self.total_models_generated += 1
        return model_id

    def complete(self, forecast: Any, confidence: str, reasoning: str):
        """Mark trajectory as complete."""
        self.completed_at = datetime.now()
        self.final_forecast = forecast
        self.confidence = confidence
        self.final_reasoning = reasoning
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "question": self.question,
            "question_type": self.question_type,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,

            # Tool calls
            "tool_calls": [
                {
                    "timestamp": tc.timestamp.isoformat(),
                    "tool_name": tc.tool_name,
                    "inputs": tc.inputs,
                    "outputs": tc.outputs[:500] if tc.outputs else "",  # Truncate long outputs
                    "error": tc.error
                }
                for tc in self.tool_calls
            ],

            # Reasoning
            "reasoning_steps": [
                {
                    "timestamp": rs.timestamp.isoformat(),
                    "step_type": rs.step_type,
                    "content": rs.content
                }
                for rs in self.reasoning_steps
            ],

            # Squiggle models
            "squiggle_models": [
                {
                    "model_id": sm.model_id,
                    "name": sm.name,
                    "code": sm.code,
                    "description": sm.description,
                    "result": sm.result,
                    "error": sm.error,
                    "created_at": sm.created_at.isoformat()
                }
                for sm in self.squiggle_models
            ],
            "selected_model_id": self.selected_model_id,

            # Final output
            "final_forecast": self.final_forecast,
            "confidence": self.confidence,
            "final_reasoning": self.final_reasoning,

            # Full conversation
            "full_conversation": self.full_conversation,

            # Summary stats
            "statistics": {
                "total_tool_calls": self.total_tool_calls,
                "total_reasoning_steps": self.total_reasoning_steps,
                "total_models_generated": self.total_models_generated,
                "duration_seconds": self.duration_seconds
            }
        }
