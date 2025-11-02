"""Tests for the forecasting agent."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.evaluation.scorer import brier_score, log_score, ForecastScorer
from src.agent.forecaster import Forecast
from src.data.kalshi import KalshiMarket


class TestBrierScore:
    """Test Brier score calculation."""

    def test_perfect_forecast_yes(self):
        """Test perfect forecast for positive outcome."""
        score = brier_score(1.0, True)
        assert score == 0.0

    def test_perfect_forecast_no(self):
        """Test perfect forecast for negative outcome."""
        score = brier_score(0.0, False)
        assert score == 0.0

    def test_worst_forecast_yes(self):
        """Test worst forecast for positive outcome."""
        score = brier_score(0.0, True)
        assert score == 1.0

    def test_worst_forecast_no(self):
        """Test worst forecast for negative outcome."""
        score = brier_score(1.0, False)
        assert score == 1.0

    def test_fifty_percent_forecast(self):
        """Test 50% forecast."""
        score_yes = brier_score(0.5, True)
        score_no = brier_score(0.5, False)
        assert score_yes == 0.25
        assert score_no == 0.25


class TestLogScore:
    """Test log score calculation."""

    def test_confident_correct(self):
        """Test confident and correct forecast."""
        score = log_score(0.9, True)
        assert score > log_score(0.5, True)

    def test_confident_incorrect(self):
        """Test confident but incorrect forecast."""
        score = log_score(0.9, False)
        assert score < log_score(0.5, False)


class TestForecastScorer:
    """Test ForecastScorer class."""

    def test_add_binary_forecast(self):
        """Test adding a binary forecast."""
        scorer = ForecastScorer()
        scores = scorer.add_forecast(0.7, True, "binary")

        assert "brier" in scores
        assert "log_score" in scores
        assert len(scorer.forecasts) == 1

    def test_average_scores(self):
        """Test calculating average scores."""
        scorer = ForecastScorer()

        # Add multiple forecasts
        scorer.add_forecast(0.8, True, "binary")
        scorer.add_forecast(0.6, False, "binary")
        scorer.add_forecast(0.9, True, "binary")

        avg_scores = scorer.get_average_scores()

        assert "avg_brier" in avg_scores
        assert "avg_log_score" in avg_scores
        assert 0 <= avg_scores["avg_brier"] <= 1

    def test_calibration_stats(self):
        """Test calibration statistics."""
        scorer = ForecastScorer()

        # Add calibrated forecasts (70% should happen ~70% of time)
        for _ in range(7):
            scorer.add_forecast(0.7, True, "binary")
        for _ in range(3):
            scorer.add_forecast(0.7, False, "binary")

        calibration = scorer.get_calibration_stats()

        assert "calibration_error" in calibration
        assert "num_forecasts" in calibration
        assert calibration["num_forecasts"] == 10


class TestForecast:
    """Test Forecast model."""

    def test_create_forecast(self):
        """Test creating a forecast."""
        forecast = Forecast(
            question="Will it rain tomorrow?",
            question_type="binary",
            forecast_value=0.6,
            confidence="moderate",
            reasoning="Based on weather patterns",
            models=[],
            research_summary="Recent news shows...",
            created_at=datetime.now(),
        )

        assert forecast.question == "Will it rain tomorrow?"
        assert forecast.forecast_value == 0.6
        assert forecast.question_type == "binary"

    def test_forecast_to_dict(self):
        """Test converting forecast to dictionary."""
        forecast = Forecast(
            question="Test question",
            question_type="binary",
            forecast_value=0.5,
            confidence="low",
            reasoning="Test",
            models=[],
            research_summary="Test",
            created_at=datetime.now(),
        )

        forecast_dict = forecast.to_dict()

        assert isinstance(forecast_dict, dict)
        assert "question" in forecast_dict
        assert "forecast_value" in forecast_dict
        assert "created_at" in forecast_dict


class TestKalshiMarket:
    """Test KalshiMarket model."""

    def test_is_active(self):
        """Test checking if market is active."""
        market = KalshiMarket(
            ticker="TEST-001",
            title="Test Market",
            question="Will this test pass?",
            market_type="binary",
            status="open",
        )

        assert market.is_active() is True

    def test_is_not_active(self):
        """Test checking if market is not active."""
        market = KalshiMarket(
            ticker="TEST-002",
            title="Test Market",
            question="Will this test pass?",
            market_type="binary",
            status="closed",
        )

        assert market.is_active() is False

    def test_is_resolved(self):
        """Test checking if market is resolved."""
        market = KalshiMarket(
            ticker="TEST-003",
            title="Test Market",
            question="Was this resolved?",
            market_type="binary",
            status="settled",
            resolution="Yes",
        )

        assert market.is_resolved() is True


@pytest.mark.asyncio
class TestSquiggleExecution:
    """Test Squiggle code execution (integration test)."""

    @pytest.mark.skip(reason="Requires Vercel Sandbox setup")
    async def test_simple_squiggle(self):
        """Test executing simple Squiggle code."""
        from src.models.squiggle_runner import create_and_run_squiggle_model

        code = """
        probability = 0.6
        probability
        """

        model, prob = await create_and_run_squiggle_model(
            code=code,
            name="test",
            question_type="binary"
        )

        assert prob is not None
        assert 0 <= prob <= 1


# Mark all async tests
pytest_plugins = ('pytest_asyncio',)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
