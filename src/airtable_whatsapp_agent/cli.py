"""
Command-line interface for the Airtable WhatsApp Agent.
"""

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .config import settings

app = typer.Typer(
    name="airtable-whatsapp-agent",
    help="Autonomous AI agent for Airtable and WhatsApp Business API integration",
    add_completion=False,
)
console = Console()


@app.command()
def run(
    host: str = typer.Option(settings.host, "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(settings.port, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(settings.reload, "--reload", help="Enable auto-reload"),
    workers: int = typer.Option(settings.workers, "--workers", "-w", help="Number of workers"),
    log_level: str = typer.Option(settings.log_level.lower(), "--log-level", help="Log level"),
):
    """Run the Airtable WhatsApp Agent server."""
    console.print(f"🚀 Starting Airtable WhatsApp Agent on {host}:{port}", style="bold green")
    if settings.is_development:
        console.print("🔧 Running in development mode", style="yellow")
    uvicorn.run(
        "airtable_whatsapp_agent.api.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level=log_level,
    )


@app.command()
def config():
    """Show current configuration."""
    table = Table(title="Airtable WhatsApp Agent Configuration")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")
    table.add_row("Environment", settings.environment)
    table.add_row("Debug", str(settings.debug))
    table.add_row("Log Level", settings.log_level)
    table.add_row("API Version", settings.api_v1_str)
    table.add_row("Agent Name", settings.agent_name)
    table.add_row("Max Iterations", str(settings.agent_max_iterations))
    table.add_row("Timeout (seconds)", str(settings.agent_timeout_seconds))
    table.add_row("WhatsApp API Version", settings.whatsapp_api_version)
    table.add_row("Airtable Base ID", settings.airtable_base_id[:10] + "..." if len(settings.airtable_base_id) > 10 else settings.airtable_base_id)
    console.print(table)


@app.command()
def health():
    """Check the health of the agent and its dependencies."""
    console.print("🔍 Checking agent health...", style="bold blue")
    health_checks = [
        ("Configuration", "✅ Loaded"),
        ("Environment", f"✅ {settings.environment}"),
        ("Database URL", "✅ Configured" if settings.database_url else "❌ Missing"),
        ("Redis URL", "✅ Configured" if settings.redis_url else "❌ Missing"),
        ("OpenAI API Key", "✅ Configured" if settings.openai_api_key else "❌ Missing"),
        ("WhatsApp Token", "✅ Configured" if settings.whatsapp_access_token else "❌ Missing"),
        ("Airtable API Key", "✅ Configured" if settings.airtable_api_key else "❌ Missing"),
    ]
    table = Table(title="Health Check Results")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="magenta")
    for component, status in health_checks:
        table.add_row(component, status)
    console.print(table)


@app.command()
def version():
    """Show version information."""
    from . import __version__, __author__
    console.print(f"Airtable WhatsApp Agent v{__version__}", style="bold green")
    console.print(f"Author: {__author__}", style="dim")


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()