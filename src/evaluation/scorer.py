"""Scoring functions for evaluating forecast accuracy."""

import numpy as np
from typing import Any


def brier_score(forecast: float, outcome: bool) -> float:
    """Calculate Brier score for a binary forecast.

    Args:
        forecast: Predicted probability (0-1)
        outcome: Actual outcome (True/False)

    Returns:
        Brier score (lower is better, range 0-1)
    """
    outcome_value = 1.0 if outcome else 0.0
    return (forecast - outcome_value) ** 2


def log_score(forecast: float, outcome: bool) -> float:
    """Calculate logarithmic scoring rule.

    Args:
        forecast: Predicted probability (0-1)
        outcome: Actual outcome (True/False)

    Returns:
        Log score (higher is better)
    """
    # Clip to avoid log(0)
    forecast = np.clip(forecast, 0.001, 0.999)

    if outcome:
        return np.log(forecast)
    else:
        return np.log(1 - forecast)


def calibration_error(forecasts: list[float], outcomes: list[bool], n_bins: int = 10) -> float:
    """Calculate calibration error for a set of forecasts.

    Args:
        forecasts: List of predicted probabilities
        outcomes: List of actual outcomes
        n_bins: Number of bins for calibration

    Returns:
        Mean absolute calibration error
    """
    if len(forecasts) != len(outcomes):
        raise ValueError("Forecasts and outcomes must have same length")

    if not forecasts:
        return 0.0

    # Create bins
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(forecasts, bins) - 1

    calibration_errors = []

    for i in range(n_bins):
        # Get forecasts in this bin
        in_bin = bin_indices == i
        if not np.any(in_bin):
            continue

        bin_forecasts = np.array(forecasts)[in_bin]
        bin_outcomes = np.array(outcomes)[in_bin]

        # Calculate mean forecast and actual frequency
        mean_forecast = np.mean(bin_forecasts)
        actual_freq = np.mean(bin_outcomes)

        # Absolute error for this bin
        calibration_errors.append(abs(mean_forecast - actual_freq))

    return np.mean(calibration_errors) if calibration_errors else 0.0


def continuous_ranked_probability_score(
    forecast_distribution: dict[str, float],
    outcome: float
) -> float:
    """Calculate CRPS for a numerical forecast with distribution.

    This is a simplified version. For full implementation, would need
    the complete forecast distribution.

    Args:
        forecast_distribution: Dict with 'mean', 'p10', 'p90', etc.
        outcome: Actual numerical outcome

    Returns:
        CRPS (lower is better)
    """
    # Simplified: use quantiles if available
    if 'mean' in forecast_distribution:
        mean = forecast_distribution['mean']
        # Simple approximation
        return abs(outcome - mean)

    return 0.0


class ForecastScorer:
    """Class for scoring and tracking forecast accuracy."""

    def __init__(self):
        """Initialize scorer."""
        self.forecasts: list[dict[str, Any]] = []
        self.scores: list[dict[str, float]] = []

    def add_forecast(
        self,
        forecast_value: float | dict[str, float],
        outcome: Any,
        question_type: str = "binary",
    ) -> dict[str, float]:
        """Add a forecast and calculate scores.

        Args:
            forecast_value: The forecast (probability or distribution)
            outcome: The actual outcome
            question_type: Type of question

        Returns:
            Dict of scores
        """
        scores = {}

        if question_type == "binary":
            if not isinstance(forecast_value, float):
                raise ValueError("Binary forecast must be a float")

            scores['brier'] = brier_score(forecast_value, bool(outcome))
            scores['log_score'] = log_score(forecast_value, bool(outcome))

        elif question_type == "numerical":
            if not isinstance(forecast_value, dict):
                raise ValueError("Numerical forecast must be a distribution dict")

            scores['crps'] = continuous_ranked_probability_score(
                forecast_value,
                float(outcome)
            )

        self.forecasts.append({
            'forecast': forecast_value,
            'outcome': outcome,
            'type': question_type,
        })
        self.scores.append(scores)

        return scores

    def get_average_scores(self) -> dict[str, float]:
        """Get average scores across all forecasts.

        Returns:
            Dict of average scores
        """
        if not self.scores:
            return {}

        # Collect all score types
        all_keys = set()
        for score_dict in self.scores:
            all_keys.update(score_dict.keys())

        averages = {}
        for key in all_keys:
            values = [s[key] for s in self.scores if key in s]
            if values:
                averages[f'avg_{key}'] = np.mean(values)

        return averages

    def get_calibration_stats(self) -> dict[str, float]:
        """Get calibration statistics for binary forecasts.

        Returns:
            Dict with calibration metrics
        """
        binary_forecasts = [
            (f['forecast'], f['outcome'])
            for f in self.forecasts
            if f['type'] == 'binary'
        ]

        if not binary_forecasts:
            return {}

        forecasts, outcomes = zip(*binary_forecasts)

        calibration_err = calibration_error(list(forecasts), list(outcomes))

        return {
            'calibration_error': calibration_err,
            'num_forecasts': len(binary_forecasts),
        }

    def summary(self) -> dict[str, Any]:
        """Get summary of all scoring metrics.

        Returns:
            Dict with comprehensive summary
        """
        return {
            'total_forecasts': len(self.forecasts),
            'average_scores': self.get_average_scores(),
            'calibration': self.get_calibration_stats(),
        }
