"""
GOAT Agent — Unified CLI
Merged from: goatcode CLI + goatclaw orchestrator + devos shell agent

Commands:
  goat code  <prompt>     — Generate code (from goatcode)
  goat shell <command>    — NLP → shell execution (from devos)
  goat chat               — Interactive coding chat
  goat config             — Manage configuration
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Fix Windows console encoding for emoji/unicode support
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.table import Table

from . import __version__
from .llm import create_llm, LLMResponse

app = typer.Typer(
    name="goat",
    help="GOAT Agent -- Local-first AI coding agent",
    add_completion=False,
    no_args_is_help=True,
)
console = Console(force_terminal=True)


def get_config() -> dict:
    """Load config from ~/.goat/config.toml"""
    config_path = Path.home() / ".goat" / "config.toml"
    if config_path.exists():
        import toml
        return toml.load(config_path)
    return {
        "provider": "ollama",
        "model": "llama3.2",
        "ollama_url": "http://localhost:11434",
    }


def save_config(config: dict):
    """Save config to ~/.goat/config.toml"""
    config_dir = Path.home() / ".goat"
    config_dir.mkdir(exist_ok=True)
    import toml
    with open(config_dir / "config.toml", "w") as f:
        toml.dump(config, f)


@app.command()
def code(
    prompt: str = typer.Argument(..., help="What code to generate"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """🔨 Generate production-ready code from a natural language prompt."""
    cfg = get_config()
    prov = provider or cfg.get("provider", "ollama")
    mdl = model or cfg.get("model", "llama3.2")

    console.print(Panel(
        f"[bold cyan]🐐 GOAT Code Generator[/bold cyan]\n"
        f"Provider: [green]{prov}[/green] | Model: [green]{mdl}[/green]",
        border_style="cyan",
    ))

    async def _run():
        llm = create_llm(provider=prov, model=mdl)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking LLM connection...", total=None)

            if hasattr(llm, "is_available"):
                available = await llm.is_available()
                if not available:
                    console.print(f"\n[red]❌ Cannot connect to {prov}[/red]")
                    if prov == "ollama":
                        console.print("[yellow]💡 Start Ollama: ollama serve[/yellow]")
                        console.print(f"[yellow]💡 Pull model: ollama pull {mdl}[/yellow]")
                    raise typer.Exit(1)

            progress.update(task, description="Generating code...")

            system = (
                "You are GOAT, a production-grade coding agent. "
                "Generate complete, working code with:\n"
                "- All necessary imports\n"
                "- Type hints\n"
                "- Docstrings\n"
                "- Error handling\n"
                "- NO placeholders or TODOs\n"
                "Return ONLY the code, no explanations."
            )

            response = await llm.generate(
                prompt=prompt,
                system=system,
                temperature=0.3,
                max_tokens=4000,
            )

            progress.update(task, description="Done!", completed=True)

        # Display result
        console.print()
        content = response.content.strip()

        # Try to extract code block
        if "```" in content:
            import re
            blocks = re.findall(r"```(\w*)\n(.*?)```", content, re.DOTALL)
            for lang, code_block in blocks:
                syntax = Syntax(code_block.strip(), lang or "python", theme="monokai", line_numbers=True)
                console.print(Panel(syntax, title=f"Generated Code ({lang or 'python'})", border_style="green"))

                if output:
                    Path(output).write_text(code_block.strip())
                    console.print(f"\n[green]✅ Saved to {output}[/green]")
        else:
            syntax = Syntax(content, "python", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title="Generated Code", border_style="green"))

            if output:
                Path(output).write_text(content)
                console.print(f"\n[green]✅ Saved to {output}[/green]")

        if response.tokens_used:
            console.print(f"\n[dim]Tokens used: {response.tokens_used}[/dim]")

    asyncio.run(_run())


@app.command()
def shell(
    command: str = typer.Argument(..., help="Natural language command to execute"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    execute: bool = typer.Option(False, "--execute", "-x", help="Auto-execute the command"),
):
    """🖥️ Translate natural language to shell commands (from DevOS)."""
    cfg = get_config()
    prov = provider or cfg.get("provider", "ollama")
    mdl = model or cfg.get("model", "llama3.2")

    import platform
    os_name = platform.system()
    shell_name = "PowerShell" if os_name == "Windows" else "bash"

    async def _run():
        llm = create_llm(provider=prov, model=mdl)

        system = (
            f"You are a {os_name} system administrator. "
            f"Translate the user's request into a single {shell_name} command. "
            f"Return ONLY the command, no explanation, no markdown, no backticks."
        )

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            prog.add_task("Translating to shell command...", total=None)
            response = await llm.generate(prompt=command, system=system, temperature=0.1)

        shell_cmd = response.content.strip().strip("`").strip()

        console.print(Panel(
            f"[bold green]{shell_cmd}[/bold green]",
            title="🖥️ Shell Command",
            border_style="green",
        ))

        if execute:
            import subprocess
            console.print("\n[yellow]⚡ Executing...[/yellow]\n")
            result = subprocess.run(shell_cmd, shell=True, capture_output=True, text=True)
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")
            console.print(f"\n[dim]Exit code: {result.returncode}[/dim]")
        else:
            console.print("\n[dim]Add --execute or -x to run this command[/dim]")

    asyncio.run(_run())


@app.command()
def chat(
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
):
    """💬 Interactive coding chat session."""
    cfg = get_config()
    prov = provider or cfg.get("provider", "ollama")
    mdl = model or cfg.get("model", "llama3.2")

    console.print(Panel(
        f"[bold cyan]🐐 GOAT Interactive Chat[/bold cyan]\n"
        f"Provider: [green]{prov}[/green] | Model: [green]{mdl}[/green]\n"
        f"Type [bold]/exit[/bold] to quit, [bold]/clear[/bold] to reset",
        border_style="cyan",
    ))

    messages = [
        {"role": "system", "content": (
            "You are GOAT, a production-grade AI coding assistant. "
            "Help with code generation, debugging, architecture, and best practices. "
            "Always provide complete, working code with proper error handling."
        )}
    ]

    async def _run():
        llm = create_llm(provider=prov, model=mdl)

        while True:
            try:
                user_input = console.input("\n[bold cyan]You>[/bold cyan] ").strip()

                if not user_input:
                    continue
                if user_input == "/exit":
                    console.print("[yellow]👋 Goodbye![/yellow]")
                    break
                if user_input == "/clear":
                    messages.clear()
                    messages.append({"role": "system", "content": "You are GOAT, a coding assistant."})
                    console.print("[green]🔄 Chat cleared[/green]")
                    continue

                messages.append({"role": "user", "content": user_input})

                with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
                    prog.add_task("Thinking...", total=None)
                    response = await llm.chat(messages=messages, temperature=0.5)

                messages.append({"role": "assistant", "content": response.content})

                console.print()
                md = Markdown(response.content)
                console.print(Panel(md, title="🐐 GOAT", border_style="green"))

            except KeyboardInterrupt:
                console.print("\n[yellow]👋 Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"\n[red]❌ Error: {e}[/red]")

    asyncio.run(_run())


@app.command()
def config(
    key: Optional[str] = typer.Argument(None, help="Config key to set (e.g., provider, model)"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
):
    """⚙️ View or set GOAT configuration."""
    cfg = get_config()

    if key and value:
        cfg[key] = value
        save_config(cfg)
        console.print(f"[green]✅ Set {key} = {value}[/green]")
    else:
        table = Table(title="🐐 GOAT Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        for k, v in cfg.items():
            table.add_row(k, str(v))
        console.print(table)
        console.print(f"\n[dim]Config file: ~/.goat/config.toml[/dim]")


@app.command()
def version():
    """📌 Show version info."""
    console.print(f"[bold cyan]🐐 GOAT Agent v{__version__}[/bold cyan]")
    console.print(f"[dim]Author: Shivay Singh Rajput[/dim]")
    console.print(f"[dim]License: Apache-2.0[/dim]")


def main():
    app()


if __name__ == "__main__":
    main()
