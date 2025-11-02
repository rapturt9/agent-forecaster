"""Validator for comparing forecasts against Kalshi market outcomes."""

import json
from pathlib import Path
from typing import Any
from datetime import datetime

from src.agent.forecaster import Forecast
from src.data.kalshi import KalshiClient, KalshiMarket
from src.evaluation.scorer import ForecastScorer


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

    async def validate_forecast(self, forecast: Forecast) -> dict[str, Any] | None:
        """Validate a forecast against actual outcome.

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
            # For binary, outcome is typically "Yes" or "No"
            outcome_bool = outcome_data['resolution'].lower() == 'yes'

            # Calculate scores
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
            # For numerical markets, get the actual value
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

                # Reconstruct Forecast object
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

                # Validate
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
