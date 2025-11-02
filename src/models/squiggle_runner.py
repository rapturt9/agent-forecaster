"""Squiggle model runner for probability distributions."""

import json
from typing import Any
from src.utils.sandbox import SandboxManager, CodeExecutionResult


class SquiggleModel:
    """Represents a Squiggle probability model."""

    def __init__(
        self,
        code: str,
        name: str = "forecast",
        description: str = "",
    ):
        """Initialize a Squiggle model.

        Args:
            code: Squiggle code defining the model
            name: Name of the model
            description: Description of the modeling approach
        """
        self.code = code
        self.name = name
        self.description = description
        self.result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "result": self.result,
        }


class SquiggleRunner:
    """Runner for executing Squiggle models in Vercel Sandbox."""

    def __init__(self, sandbox: SandboxManager | None = None):
        """Initialize Squiggle runner.

        Args:
            sandbox: Optional existing sandbox manager
        """
        self.sandbox = sandbox
        self.owns_sandbox = sandbox is None

    async def _ensure_sandbox(self) -> SandboxManager:
        """Ensure we have a sandbox ready."""
        if not self.sandbox:
            self.sandbox = SandboxManager()
            await self.sandbox.create_sandbox()
        return self.sandbox

    async def run_squiggle(self, code: str) -> CodeExecutionResult:
        """Run Squiggle code and get results.

        Args:
            code: Squiggle code to execute

        Returns:
            CodeExecutionResult with Squiggle output
        """
        sandbox = await self._ensure_sandbox()

        # Create Python wrapper to run Squiggle
        # Note: We'll use squiggle-lang Python package
        python_code = f'''
import json
from squiggle import run

# Squiggle code
squiggle_code = """
{code}
"""

try:
    # Run Squiggle code
    result = run(squiggle_code)

    # Output as JSON
    output = {{
        "success": True,
        "result": result.to_dict() if hasattr(result, "to_dict") else str(result),
        "error": None
    }}
    print(json.dumps(output))

except Exception as e:
    output = {{
        "success": False,
        "result": None,
        "error": str(e)
    }}
    print(json.dumps(output))
'''

        # Install squiggle-lang package and run
        return await sandbox.execute_with_packages(
            python_code,
            packages=["squiggle-lang"],
            timeout_seconds=30
        )

    async def evaluate_model(self, model: SquiggleModel) -> bool:
        """Evaluate a Squiggle model and store results.

        Args:
            model: SquiggleModel to evaluate

        Returns:
            True if evaluation successful
        """
        result = await self.run_squiggle(model.code)

        if result.success:
            try:
                # Parse JSON output
                output = json.loads(result.stdout.strip())
                if output.get("success"):
                    model.result = output.get("result")
                    return True
                else:
                    model.result = {"error": output.get("error")}
                    return False
            except json.JSONDecodeError:
                model.result = {"error": "Failed to parse Squiggle output", "raw": result.stdout}
                return False
        else:
            model.result = {"error": result.error, "stderr": result.stderr}
            return False

    async def extract_probability(
        self,
        model: SquiggleModel,
        question_type: str = "binary"
    ) -> float | dict[str, float] | None:
        """Extract probability from an evaluated model.

        Args:
            model: Evaluated SquiggleModel
            question_type: Type of question (binary, categorical, numerical)

        Returns:
            Probability value(s) or None if extraction failed
        """
        if not model.result or "error" in model.result:
            return None

        # For binary questions, expect a single probability
        if question_type == "binary":
            # Try to extract probability from result
            result = model.result
            if isinstance(result, (int, float)):
                return float(result)
            elif isinstance(result, dict):
                # Common Squiggle result structures
                if "value" in result:
                    return float(result["value"])
                elif "mean" in result:
                    return float(result["mean"])
            return None

        # For categorical, expect a distribution
        elif question_type == "categorical":
            if isinstance(model.result, dict):
                return model.result
            return None

        # For numerical, return full distribution info
        elif question_type == "numerical":
            return model.result

        return None

    async def cleanup(self) -> None:
        """Cleanup sandbox if we own it."""
        if self.owns_sandbox and self.sandbox:
            await self.sandbox.cleanup()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()


async def create_and_run_squiggle_model(
    code: str,
    name: str = "forecast",
    description: str = "",
    question_type: str = "binary",
) -> tuple[SquiggleModel, float | dict[str, float] | None]:
    """Helper function to create and run a Squiggle model.

    Args:
        code: Squiggle code
        name: Model name
        description: Model description
        question_type: Question type

    Returns:
        Tuple of (model, probability)
    """
    model = SquiggleModel(code, name, description)

    async with SquiggleRunner() as runner:
        success = await runner.evaluate_model(model)
        if success:
            prob = await runner.extract_probability(model, question_type)
            return model, prob
        return model, None


# Example Squiggle code templates
BINARY_TEMPLATE = """
// Binary forecasting model for: {question}
// Reasoning: {reasoning}

// Define key factors
baseRate = {base_rate}
adjustmentFactor = {adjustment}

// Calculate final probability
probability = baseRate * adjustmentFactor
probability = min(max(probability, 0.01), 0.99)  // Bound between 1% and 99%

probability
"""

NUMERICAL_TEMPLATE = """
// Numerical forecasting model for: {question}
// Reasoning: {reasoning}

// Define distribution parameters
low = {low}
high = {high}
mode = {mode}

// Create distribution
dist = triangular(low, mode, high)

// Output summary statistics
{{
  mean: mean(dist),
  median: quantile(dist, 0.5),
  p10: quantile(dist, 0.1),
  p90: quantile(dist, 0.9),
  distribution: dist
}}
"""


def generate_binary_squiggle(
    question: str,
    base_rate: float,
    adjustment: float,
    reasoning: str,
) -> str:
    """Generate Squiggle code for a binary question.

    Args:
        question: The forecasting question
        base_rate: Historical base rate (0-1)
        adjustment: Adjustment factor based on current evidence
        reasoning: Explanation of the model

    Returns:
        Squiggle code string
    """
    return BINARY_TEMPLATE.format(
        question=question,
        base_rate=base_rate,
        adjustment=adjustment,
        reasoning=reasoning,
    )


def generate_numerical_squiggle(
    question: str,
    low: float,
    high: float,
    mode: float,
    reasoning: str,
) -> str:
    """Generate Squiggle code for a numerical question.

    Args:
        question: The forecasting question
        low: Lower bound
        high: Upper bound
        mode: Most likely value
        reasoning: Explanation of the model

    Returns:
        Squiggle code string
    """
    return NUMERICAL_TEMPLATE.format(
        question=question,
        low=low,
        high=high,
        mode=mode,
        reasoning=reasoning,
    )
