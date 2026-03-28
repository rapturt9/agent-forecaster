"""Validator for comparing forecasts against outcomes.

Supports both Kalshi market validation and direct outcome validation
for standalone evaluations (e.g., BTC price direction, custom questions).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING
from datetime import datetime

from src.evaluation.scorer import ForecastScorer

if TYPE_CHECKING:
    from src.agent.forecaster import Forecast
    from src.data.kalshi import KalshiClient, KalshiMarket


class ForecastValidator:
    """Validates forecasts against actual outcomes."""

    def __init__(self, kalshi_client: KalshiClient | None = None):
        """Initialize validator.

        Args:
            kalshi_client: Optional existing Kalshi client
        """
        self.kalshi_client = kalshi_client
        self.owns_client = kalshi_client is None
        self.scorer = ForecastScorer()

    async def _ensure_kalshi_client(self) -> KalshiClient:
        """Ensure we have a Kalshi client."""
        if not self.kalshi_client:
            self.kalshi_client = KalshiClient()
        return self.kalshi_client

    def validate_against_outcome(
        self,
        forecast_prob: float,
        outcome: bool,
        question: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate a binary forecast directly against a known outcome.

        This is the simplest evaluation path -- no Kalshi needed.

        Args:
            forecast_prob: Predicted probability of "yes" (0-1)
            outcome: Actual outcome (True/False)
            question: Optional question text for logging
            metadata: Optional extra metadata to include in result

        Returns:
            Validation result dict with scores
        """
        scores = self.scorer.add_forecast(forecast_prob, outcome, question_type="binary")
        result = {
            "status": "validated",
            "question": question,
            "forecast": forecast_prob,
            "outcome": outcome,
            "scores": scores,
            "validated_at": datetime.now().isoformat(),
        }
        if metadata:
            result["metadata"] = metadata
        return result

    def validate_numerical_outcome(
        self,
        forecast_distribution: dict[str, float],
        outcome: float,
        question: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate a numerical forecast directly against a known outcome.

        Args:
            forecast_distribution: Dict with 'mean', 'p10', 'p90', etc.
            outcome: Actual numerical outcome
            question: Optional question text
            metadata: Optional extra metadata

        Returns:
            Validation result dict with scores
        """
        scores = self.scorer.add_forecast(forecast_distribution, outcome, question_type="numerical")
        result = {
            "status": "validated",
            "question": question,
            "forecast": forecast_distribution,
            "outcome": outcome,
            "scores": scores,
            "validated_at": datetime.now().isoformat(),
        }
        if metadata:
            result["metadata"] = metadata
        return result

    async def validate_forecast(self, forecast: Forecast) -> dict[str, Any] | None:
        """Validate a forecast against actual outcome via Kalshi.

        Args:
            forecast: Forecast to validate

        Returns:
            Validation results or None if market not resolved
        """
        if not forecast.kalshi_ticker:
            return {"error": "No Kalshi ticker associated with forecast"}

        client = await self._ensure_kalshi_client()

        # Get market outcome
        outcome_data = await client.get_market_outcome(forecast.kalshi_ticker)

        if not outcome_data:
            return {"status": "pending", "message": "Market not yet resolved"}

        # Parse outcome based on market type
        if forecast.question_type == "binary":
            outcome_bool = outcome_data['resolution'].lower() == 'yes'

            if isinstance(forecast.forecast_value, float):
                scores = self.scorer.add_forecast(
                    forecast.forecast_value,
                    outcome_bool,
                    question_type="binary"
                )

                return {
                    "status": "validated",
                    "forecast": forecast.forecast_value,
                    "outcome": outcome_bool,
                    "scores": scores,
                    "market_ticker": forecast.kalshi_ticker,
                    "validated_at": datetime.now().isoformat(),
                }

        elif forecast.question_type == "numerical":
            outcome_value = outcome_data.get('resolution_value')

            if outcome_value is not None and isinstance(forecast.forecast_value, dict):
                scores = self.scorer.add_forecast(
                    forecast.forecast_value,
                    outcome_value,
                    question_type="numerical"
                )

                return {
                    "status": "validated",
                    "forecast": forecast.forecast_value,
                    "outcome": outcome_value,
                    "scores": scores,
                    "market_ticker": forecast.kalshi_ticker,
                    "validated_at": datetime.now().isoformat(),
                }

        return {"error": "Unable to validate forecast against outcome"}

    async def validate_forecast_batch(
        self,
        forecasts: list[Forecast],
    ) -> list[dict[str, Any]]:
        """Validate multiple forecasts.

        Args:
            forecasts: List of forecasts to validate

        Returns:
            List of validation results
        """
        results = []
        for forecast in forecasts:
            result = await self.validate_forecast(forecast)
            if result:
                results.append(result)

        return results

    def get_performance_summary(self) -> dict[str, Any]:
        """Get summary of forecast performance.

        Returns:
            Performance summary with scores
        """
        return self.scorer.summary()

    async def load_and_validate_forecasts(
        self,
        forecast_dir: str | Path,
    ) -> dict[str, Any]:
        """Load forecasts from directory and validate them.

        Args:
            forecast_dir: Directory containing forecast JSON files

        Returns:
            Validation summary
        """
        forecast_dir = Path(forecast_dir)

        if not forecast_dir.exists():
            return {"error": f"Directory not found: {forecast_dir}"}

        # Load all forecast files
        forecast_files = list(forecast_dir.glob("*.json"))
        results = []

        for filepath in forecast_files:
            try:
                with open(filepath) as f:
                    data = json.load(f)

                # Check if this is a direct evaluation result (has outcome already)
                if 'actual_outcome' in data and 'forecast' in data:
                    result = self.validate_against_outcome(
                        forecast_prob=float(data['forecast']),
                        outcome=bool(data['actual_outcome']),
                        question=data.get('question', ''),
                        metadata=data.get('metadata'),
                    )
                    result['file'] = str(filepath.name)
                    results.append(result)
                    continue

                # Otherwise try Kalshi-based validation
                forecast = Forecast(
                    question=data['question'],
                    question_type=data['question_type'],
                    forecast_value=data['forecast_value'],
                    confidence=data.get('confidence', 'unknown'),
                    reasoning=data.get('reasoning', ''),
                    models=data.get('models', []),
                    research_summary=data.get('research_summary', ''),
                    base_rates=data.get('base_rates'),
                    created_at=datetime.fromisoformat(data['created_at']),
                    kalshi_ticker=data.get('kalshi_ticker'),
                    session_id=data.get('session_id'),
                )

                result = await self.validate_forecast(forecast)
                if result:
                    result['file'] = str(filepath.name)
                    results.append(result)

            except Exception as e:
                results.append({
                    "file": str(filepath.name),
                    "error": f"Failed to process: {str(e)}"
                })

        # Get summary
        summary = self.get_performance_summary()
        summary['individual_results'] = results
        summary['total_files'] = len(forecast_files)
        summary['validated'] = len([r for r in results if r.get('status') == 'validated'])
        summary['pending'] = len([r for r in results if r.get('status') == 'pending'])
        summary['errors'] = len([r for r in results if 'error' in r])

        return summary

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.owns_client and self.kalshi_client:
            await self.kalshi_client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
