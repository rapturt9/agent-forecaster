"""CLI interface for the AI forecasting agent."""

import asyncio
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from dotenv import load_dotenv

from src.agent.forecaster import ForecastingAgent
from src.data.kalshi import KalshiClient
from src.evaluation.validator import ForecastValidator

# Load environment variables
load_dotenv()

app = typer.Typer(
    name="forecast",
    help="AI-powered forecasting system using Claude Agent SDK",
    add_completion=False,
)
console = Console()


@app.command()
def forecast(
    question: str = typer.Argument(..., help="The forecasting question"),
    type: str = typer.Option("binary", help="Question type: binary, categorical, or numerical"),
    context: str = typer.Option("", help="Additional context for the forecast"),
    output: Optional[str] = typer.Option(None, help="Output file path (JSON)"),
):
    """Generate a forecast for a question."""

    async def _forecast():
        console.print(f"\n[bold cyan]Forecasting Question:[/bold cyan] {question}")
        console.print(f"[dim]Type: {type}[/dim]\n")

        with console.status("[bold green]Researching and analyzing...", spinner="dots"):
            async with ForecastingAgent() as agent:
                forecast_obj = await agent.forecast(
                    question=question,
                    question_type=type,
                    context=context,
                )

        # Display results
        console.print("\n" + "=" * 80)
        console.print(Panel(
            f"[bold green]Forecast: {forecast_obj.forecast_value}[/bold green]\n"
            f"[yellow]Confidence: {forecast_obj.confidence}[/yellow]",
            title="Result",
            border_style="green"
        ))

        console.print(f"\n[bold]Reasoning:[/bold]\n{forecast_obj.reasoning}\n")

        if forecast_obj.research_summary:
            console.print(f"[bold]Research Summary:[/bold]\n{forecast_obj.research_summary[:500]}...\n")

        # Save if requested
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            forecast_obj.save_json(str(output_path))
            console.print(f"\n[green]Forecast saved to: {output}[/green]")

    asyncio.run(_forecast())


@app.command()
def forecast_kalshi(
    ticker: str = typer.Argument(..., help="Kalshi market ticker"),
    output_dir: Optional[str] = typer.Option("forecasts", help="Output directory for forecasts"),
):
    """Generate a forecast for a Kalshi market."""

    async def _forecast_kalshi():
        console.print(f"\n[bold cyan]Fetching Kalshi Market:[/bold cyan] {ticker}\n")

        async with KalshiClient() as kalshi:
            # Get market details
            market = await kalshi.get_market(ticker)

            console.print(f"[bold]Title:[/bold] {market.title}")
            console.print(f"[bold]Question:[/bold] {market.question}")
            console.print(f"[bold]Type:[/bold] {market.market_type}")
            console.print(f"[bold]Status:[/bold] {market.status}\n")

            if not market.is_active():
                console.print("[yellow]Warning: Market is not active[/yellow]\n")

        # Generate forecast
        with console.status("[bold green]Generating forecast...", spinner="dots"):
            async with ForecastingAgent() as agent:
                forecast_obj = await agent.forecast_kalshi_market(market)

        # Display results
        console.print("\n" + "=" * 80)
        console.print(Panel(
            f"[bold green]Forecast: {forecast_obj.forecast_value}[/bold green]\n"
            f"[yellow]Confidence: {forecast_obj.confidence}[/yellow]",
            title=f"Forecast for {ticker}",
            border_style="green"
        ))

        # Save forecast
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            filename = f"{ticker}_{forecast_obj.created_at.strftime('%Y%m%d_%H%M%S')}.json"
            forecast_obj.save_json(str(output_path / filename))
            console.print(f"\n[green]Forecast saved to: {output_path / filename}[/green]")

    asyncio.run(_forecast_kalshi())


@app.command()
def batch_forecast(
    limit: int = typer.Option(5, help="Number of markets to forecast"),
    output_dir: str = typer.Option("forecasts", help="Output directory"),
    status: str = typer.Option("open", help="Market status filter"),
):
    """Generate forecasts for multiple Kalshi markets."""

    async def _batch_forecast():
        console.print(f"\n[bold cyan]Fetching {limit} Kalshi markets...[/bold cyan]\n")

        async with KalshiClient() as kalshi:
            markets = await kalshi.get_markets(limit=limit, status=status)

            console.print(f"Found {len(markets)} markets\n")

            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            async with ForecastingAgent() as agent:
                for i, market in enumerate(markets, 1):
                    console.print(f"\n[bold]({i}/{len(markets)})[/bold] {market.ticker}: {market.title}")

                    try:
                        with console.status(f"[green]Forecasting...", spinner="dots"):
                            forecast_obj = await agent.forecast_kalshi_market(market)

                        console.print(f"[green]✓[/green] Forecast: {forecast_obj.forecast_value}")

                        # Save
                        filename = f"{market.ticker}_{forecast_obj.created_at.strftime('%Y%m%d_%H%M%S')}.json"
                        forecast_obj.save_json(str(output_path / filename))

                    except Exception as e:
                        console.print(f"[red]✗ Error: {str(e)}[/red]")

            console.print(f"\n[bold green]Batch forecasting complete![/bold green]")
            console.print(f"Forecasts saved to: {output_dir}")

    asyncio.run(_batch_forecast())


@app.command()
def evaluate(
    forecast_dir: str = typer.Argument("forecasts", help="Directory containing forecast JSON files"),
    show_details: bool = typer.Option(False, "--details", help="Show detailed results"),
):
    """Evaluate forecasts against actual outcomes."""

    async def _evaluate():
        console.print(f"\n[bold cyan]Evaluating forecasts from:[/bold cyan] {forecast_dir}\n")

        async with ForecastValidator() as validator:
            with console.status("[green]Validating forecasts...", spinner="dots"):
                results = await validator.load_and_validate_forecasts(forecast_dir)

            # Display summary
            console.print("\n" + "=" * 80)
            console.print(Panel(
                f"[bold]Total Files:[/bold] {results.get('total_files', 0)}\n"
                f"[bold green]Validated:[/bold green] {results.get('validated', 0)}\n"
                f"[bold yellow]Pending:[/bold yellow] {results.get('pending', 0)}\n"
                f"[bold red]Errors:[/bold red] {results.get('errors', 0)}",
                title="Evaluation Summary",
                border_style="blue"
            ))

            # Display average scores
            avg_scores = results.get('average_scores', {})
            if avg_scores:
                console.print("\n[bold]Average Scores:[/bold]")
                for key, value in avg_scores.items():
                    console.print(f"  {key}: {value:.4f}")

            # Display calibration
            calibration = results.get('calibration', {})
            if calibration:
                console.print("\n[bold]Calibration:[/bold]")
                for key, value in calibration.items():
                    console.print(f"  {key}: {value}")

            # Show individual results if requested
            if show_details:
                console.print("\n[bold]Individual Results:[/bold]")
                for result in results.get('individual_results', []):
                    if result.get('status') == 'validated':
                        console.print(f"\n  {result['file']}")
                        console.print(f"    Forecast: {result['forecast']}")
                        console.print(f"    Outcome: {result['outcome']}")
                        console.print(f"    Scores: {result['scores']}")

    asyncio.run(_evaluate())


@app.command()
def list_markets(
    limit: int = typer.Option(10, help="Number of markets to list"),
    status: str = typer.Option("open", help="Market status filter"),
):
    """List active Kalshi markets."""

    async def _list_markets():
        console.print(f"\n[bold cyan]Fetching Kalshi markets...[/bold cyan]\n")

        async with KalshiClient() as kalshi:
            markets = await kalshi.get_markets(limit=limit, status=status)

            table = Table(title=f"Kalshi Markets ({status})")
            table.add_column("Ticker", style="cyan")
            table.add_column("Title", style="white")
            table.add_column("Type", style="yellow")
            table.add_column("Status", style="green")

            for market in markets:
                table.add_row(
                    market.ticker,
                    market.title[:60] + "..." if len(market.title) > 60 else market.title,
                    market.market_type,
                    market.status,
                )

            console.print(table)

    asyncio.run(_list_markets())


@app.command()
def version():
    """Show version information."""
    console.print("\n[bold]Agent Forecaster[/bold]")
    console.print("Version: 0.1.0")
    console.print("Powered by Claude Agent SDK\n")


if __name__ == "__main__":
    app()
