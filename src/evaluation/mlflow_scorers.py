"""Custom MLflow scorers for evaluating forecasting agent quality."""

import mlflow
from mlflow.genai import scorer
from mlflow.genai.judges import make_judge


# Brier Score Scorer
@scorer
def brier_score_scorer(predictions, targets):
    """Calculate Brier score for binary forecasts.

    Args:
        predictions: Forecast probability (0-1)
        targets: Actual outcome (True/False or "yes"/"no")

    Returns:
        Brier score (lower is better, 0 = perfect, 1 = worst)
    """
    from src.evaluation.scorer import brier_score

    # Convert targets to boolean
    if isinstance(targets, str):
        target_bool = targets.lower() == "yes"
    else:
        target_bool = bool(targets)

    # Calculate Brier score
    if isinstance(predictions, (int, float)):
        return brier_score(predictions, target_bool)

    return 1.0  # Worst score if prediction is invalid


# Research Quality Scorer
@scorer
def research_quality(trace):
    """Evaluate if agent properly researched the question.

    Args:
        trace: MLflow trace object

    Returns:
        Dictionary with research quality metrics
    """
    tool_calls = [
        span for span in trace.data.spans
        if span.span_type == "TOOL"
    ]

    # Get unique tools used
    tools_used = set(span.name for span in tool_calls)

    # Check if both search_news and web_research were used
    used_search_news = any("search_news" in tool for tool in tools_used)
    used_web_research = any("web_research" in tool for tool in tools_used)

    # Calculate score
    score = 0.0
    if len(tool_calls) >= 1:
        score += 0.3  # Used at least one tool
    if used_search_news:
        score += 0.35  # Used news search
    if used_web_research:
        score += 0.35  # Used web research

    return {
        "research_quality_score": score,
        "num_tool_calls": len(tool_calls),
        "used_both_tools": used_search_news and used_web_research,
        "tools_used": list(tools_used),
    }


# Tool Efficiency Scorer
@scorer
def tool_efficiency(trace):
    """Evaluate tool usage efficiency (avoid redundancy).

    Args:
        trace: MLflow trace object

    Returns:
        Dictionary with efficiency metrics
    """
    tool_calls = [
        span for span in trace.data.spans
        if span.span_type == "TOOL"
    ]

    if len(tool_calls) == 0:
        return {"efficiency_score": 0.0, "num_tool_calls": 0}

    # Check for redundant calls (same tool with similar inputs)
    redundant_calls = 0
    tool_inputs = set()

    for span in tool_calls:
        # Create a simplified key from tool name and input
        tool_key = f"{span.name}"
        if tool_key in tool_inputs:
            redundant_calls += 1
        tool_inputs.add(tool_key)

    # Calculate efficiency (penalize redundancy and excessive calls)
    redundancy_penalty = redundant_calls * 0.2
    excess_penalty = max(0, (len(tool_calls) - 3) * 0.1)  # Penalty for > 3 calls

    efficiency_score = max(0.0, 1.0 - redundancy_penalty - excess_penalty)

    return {
        "efficiency_score": efficiency_score,
        "num_tool_calls": len(tool_calls),
        "redundant_calls": redundant_calls,
    }


# Model Generation Scorer
@scorer
def model_generation_quality(trace):
    """Evaluate if agent generated multiple forecasting models.

    Args:
        trace: MLflow trace object

    Returns:
        Dictionary with model generation metrics
    """
    # Look for evidence of multiple models in the trace
    response_text = ""

    for span in trace.data.spans:
        if hasattr(span, "outputs") and span.outputs:
            response_text += str(span.outputs)

    # Count references to models
    model_indicators = ["MODEL 1", "MODEL 2", "Model 1", "Model 2", "model 1", "model 2"]
    models_found = sum(1 for indicator in model_indicators if indicator in response_text)

    # Normalize to unique models (divide by number of indicators per model)
    num_models = models_found // 2  # Each model has 2 indicators typically

    score = min(1.0, num_models / 3.0)  # 3 models = perfect score

    return {
        "model_generation_score": score,
        "num_models_generated": num_models,
        "generated_multiple": num_models >= 2,
    }


# Reasoning Clarity Scorer (using Anthropic Claude judge)
def create_reasoning_clarity_judge():
    """Create an LLM judge for reasoning quality.

    Returns:
        MLflow judge for reasoning clarity
    """
    return make_judge(
        name="reasoning_clarity",
        model="claude-3-haiku-20240307",  # Fast and cheap Claude model
        instructions="""
Evaluate if the forecast reasoning is clear, logical, and well-explained.

Check for:
1. Clear explanation of key factors
2. Logical flow of reasoning
3. Specific evidence cited
4. Transparent about uncertainties

Look at the trace outputs and final reasoning.

Return 'pass' if reasoning is clear and well-structured, 'fail' if it's vague or poorly explained.

Trace: {{trace}}
        """
    )


# Base Rate Usage Judge (using Anthropic Claude)
def create_base_rate_judge():
    """Create an LLM judge for base rate usage.

    Returns:
        MLflow judge for base rate consideration
    """
    return make_judge(
        name="base_rate_usage",
        model="claude-3-haiku-20240307",
        instructions="""
Analyze if the forecast reasoning mentions or considers historical base rates or frequencies.

Good forecasts should:
1. Reference historical frequency of similar events
2. Start with base rates before adjusting
3. Mention past occurrences or typical rates

Return 'pass' if base rates are clearly considered, 'fail' if they're ignored.

Trace: {{trace}}
        """
    )


# Calibration Monitor (for tracking over time)
class CalibrationMonitor:
    """Track calibration of forecasts over time."""

    def __init__(self):
        """Initialize calibration tracker."""
        self.forecasts = []
        self.outcomes = []

    def add_forecast(self, forecast_prob: float, actual_outcome: bool):
        """Add a forecast-outcome pair.

        Args:
            forecast_prob: Forecasted probability (0-1)
            actual_outcome: Actual outcome (True/False)
        """
        self.forecasts.append(forecast_prob)
        self.outcomes.append(actual_outcome)

    def get_calibration_error(self, n_bins: int = 10) -> float:
        """Calculate calibration error.

        Args:
            n_bins: Number of bins for calibration

        Returns:
            Mean absolute calibration error
        """
        from src.evaluation.scorer import calibration_error
        return calibration_error(self.forecasts, self.outcomes, n_bins)

    def log_to_mlflow(self, run_id: str = None):
        """Log calibration metrics to MLflow.

        Args:
            run_id: Optional MLflow run ID
        """
        if len(self.forecasts) < 5:
            # Need at least 5 forecasts for calibration
            return

        calib_error = self.get_calibration_error()

        with mlflow.start_run(run_id=run_id):
            mlflow.log_metric("calibration_error", calib_error)
            mlflow.log_metric("num_forecasts_for_calibration", len(self.forecasts))


# Export all scorers and judges
ALL_SCORERS = [
    brier_score_scorer,
    research_quality,
    tool_efficiency,
    model_generation_quality,
]

ALL_JUDGES = [
    create_reasoning_clarity_judge,
    create_base_rate_judge,
]
