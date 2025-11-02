"""MLflow-enabled forecasting agent with automatic tracing and evaluation."""

import mlflow
from typing import Literal, Any, Union
from datetime import datetime

from src.agent.simple_forecaster import SimpleForecastingAgent
from src.agent.enhanced_forecaster import EnhancedForecastingAgent, AgentTrajectory


# Enable MLflow automatic tracing for Claude Agent SDK
mlflow.anthropic.autolog()


class MLflowForecastingAgent:
    """Forecasting agent with MLflow tracing and logging."""

    def __init__(
        self,
        model_name: str = "forecasting_agent",
        experiment_name: str = "forecasting",
        use_enhanced: bool = True,
    ):
        """Initialize MLflow-enabled forecasting agent.

        Args:
            model_name: Name for the MLflow logged model
            experiment_name: Name of the MLflow experiment
            use_enhanced: Use enhanced forecaster with trajectory logging
        """
        self.model_name = model_name
        self.experiment_name = experiment_name

        # Set up MLflow experiment
        mlflow.set_experiment(experiment_name)

        # Set active model for tracing
        mlflow.set_active_model(name=model_name)

        # Choose forecaster type
        if use_enhanced:
            self.forecaster = EnhancedForecastingAgent()
        else:
            self.forecaster = SimpleForecastingAgent()

        self.use_enhanced = use_enhanced

    async def forecast(
        self,
        question: str,
        question_type: Literal["binary", "categorical", "numerical"] = "binary",
        context: str = "",
        question_id: str | None = None,
    ) -> tuple[Union[AgentTrajectory, Any], str]:
        """Generate forecast with MLflow tracking.

        Args:
            question: The forecasting question
            question_type: Type of question
            context: Additional context
            question_id: Optional question ID for tracking

        Returns:
            Tuple of (forecast/trajectory, run_id)
        """
        # Get active model ID for linking
        active_model_id = mlflow.get_active_model_id()

        # Start MLflow run for this forecast
        with mlflow.start_run(run_name=f"forecast_{question_id or 'unknown'}") as run:
            # Log parameters
            mlflow.log_params({
                "question": question[:200],  # Truncate for display
                "question_type": question_type,
                "question_id": question_id or "unknown",
                "model_name": self.model_name,
                "forecaster_type": "enhanced" if self.use_enhanced else "simple",
            })

            # Run forecast (this will be automatically traced by MLflow)
            forecast_result = await self.forecaster.forecast(
                question=question,
                question_type=question_type,
                context=context
            )

            # Log forecast results based on type
            if self.use_enhanced:
                # Enhanced forecaster returns AgentTrajectory
                trajectory = forecast_result

                # Log metrics
                metrics = {
                    "forecast_value": trajectory.final_forecast if isinstance(trajectory.final_forecast, (int, float)) else 0.5,
                    "duration_seconds": trajectory.duration_seconds,
                    "total_tool_calls": trajectory.total_tool_calls,
                    "total_reasoning_steps": trajectory.total_reasoning_steps,
                    "total_models_generated": trajectory.total_models_generated,
                }

                # Add confidence score
                confidence_map = {"low": 0.3, "moderate": 0.6, "high": 0.9, "unknown": 0.5}
                metrics["confidence_score"] = confidence_map.get(trajectory.confidence, 0.5)

                mlflow.log_metrics(metrics, model_id=active_model_id)

                # Log artifacts
                mlflow.log_text(trajectory.full_conversation, "conversation.txt")
                mlflow.log_text(trajectory.final_reasoning, "reasoning.txt")

                # Log Squiggle models if any
                if trajectory.squiggle_models:
                    models_text = "\n\n".join([
                        f"MODEL {m.model_id}: {m.name}\n{m.code}\n{m.description}"
                        for m in trajectory.squiggle_models
                    ])
                    mlflow.log_text(models_text, "squiggle_models.txt")

                # Log trajectory as JSON
                import json
                mlflow.log_dict(trajectory.to_dict(), "trajectory.json")

            else:
                # Simple forecaster
                forecast = forecast_result

                metrics = {
                    "forecast_value": forecast.forecast_value if isinstance(forecast.forecast_value, (int, float)) else 0.5,
                }

                confidence_map = {"low": 0.3, "moderate": 0.6, "high": 0.9, "unknown": 0.5}
                metrics["confidence_score"] = confidence_map.get(forecast.confidence, 0.5)

                mlflow.log_metrics(metrics, model_id=active_model_id)
                mlflow.log_text(forecast.reasoning, "reasoning.txt")
                mlflow.log_text(forecast.full_response, "full_response.txt")

            # Log tags
            mlflow.set_tags({
                "question_type": question_type,
                "question_id": str(question_id) if question_id else "none",
                "forecaster": "enhanced" if self.use_enhanced else "simple",
            })

            return forecast_result, run.info.run_id

    async def evaluate_forecast(
        self,
        forecast_result: Union[AgentTrajectory, Any],
        actual_answer: Any,
        run_id: str,
    ) -> dict:
        """Evaluate a forecast against actual answer.

        Args:
            forecast_result: The forecast or trajectory
            actual_answer: The actual outcome
            run_id: MLflow run ID to log metrics to

        Returns:
            Dictionary of evaluation metrics
        """
        from src.evaluation.scorer import brier_score

        metrics = {}

        # Calculate Brier score for binary questions
        if self.use_enhanced:
            forecast_value = forecast_result.final_forecast
            question_type = forecast_result.question_type
        else:
            forecast_value = forecast_result.forecast_value
            question_type = forecast_result.question_type

        if question_type == "binary" and isinstance(forecast_value, float):
            actual_bool = actual_answer if isinstance(actual_answer, bool) else actual_answer.lower() == "yes"
            metrics["brier_score"] = brier_score(forecast_value, actual_bool)

        # Log evaluation metrics to the run
        active_model_id = mlflow.get_active_model_id()

        with mlflow.start_run(run_id=run_id):
            mlflow.log_metrics(metrics, model_id=active_model_id)
            mlflow.set_tag("evaluated", "true")

        return metrics

    def get_traces_for_model(self, limit: int = 100):
        """Get recent traces for this model.

        Args:
            limit: Maximum number of traces to return

        Returns:
            DataFrame of traces
        """
        active_model_id = mlflow.get_active_model_id()
        return mlflow.search_traces(model_id=active_model_id, max_results=limit)

    def get_model_metrics(self):
        """Get aggregated metrics for this model.

        Returns:
            Dictionary of metrics
        """
        active_model_id = mlflow.get_active_model_id()

        # Search for runs linked to this model
        runs = mlflow.search_runs(
            experiment_names=[self.experiment_name],
            filter_string=f"tags.mlflow.parentModelId = '{active_model_id}'",
            order_by=["start_time DESC"],
        )

        if runs.empty:
            return {}

        # Aggregate metrics
        metrics = {}

        if "metrics.brier_score" in runs.columns:
            brier_scores = runs["metrics.brier_score"].dropna()
            if len(brier_scores) > 0:
                metrics["avg_brier_score"] = brier_scores.mean()
                metrics["num_evaluated"] = len(brier_scores)

        if "metrics.duration_seconds" in runs.columns:
            durations = runs["metrics.duration_seconds"].dropna()
            if len(durations) > 0:
                metrics["avg_duration_seconds"] = durations.mean()

        if "metrics.total_tool_calls" in runs.columns:
            tool_calls = runs["metrics.total_tool_calls"].dropna()
            if len(tool_calls) > 0:
                metrics["avg_tool_calls"] = tool_calls.mean()

        metrics["total_forecasts"] = len(runs)

        return metrics

    async def __aenter__(self):
        """Async context manager entry."""
        await self.forecaster.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.forecaster.__aexit__(exc_type, exc_val, exc_tb)
