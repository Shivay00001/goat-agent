# 🐐 GOAT Agent

> **Local-first AI coding agent** with Ollama, OpenAI & Anthropic support.  
> Generate code, translate shell commands, and chat — all from your terminal.

[![PyPI](https://img.shields.io/pypi/v/goat-agent)](https://pypi.org/project/goat-agent/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](https://opensource.org/licenses/Apache-2.0)

## Quick Start

```bash
pip install goat-agent

# Use with local Ollama (free, private)
goat code "Create a FastAPI CRUD app with SQLite"

# Use with OpenAI
goat --provider openai --model gpt-4o code "Build a React todo app"

# Translate natural language to shell commands
goat shell "find all Python files larger than 1MB"

# Interactive chat
goat chat
```

## Features

| Command | Description | Source |
|:--------|:-----------|:-------|
| `goat code <prompt>` | Generate production-ready code | goatcode |
| `goat shell <command>` | NLP → shell command translation | devos |
| `goat chat` | Interactive coding assistant | goatclaw |
| `goat config` | Manage settings | — |

## Providers

| Provider | Cost | Setup |
|:---------|:-----|:------|
| **Ollama** (default) | Free | `ollama serve && ollama pull llama3.2` |
| **OpenAI** | Pay-per-token | `export OPENAI_API_KEY=sk-...` |
| **Anthropic** | Pay-per-token | `export ANTHROPIC_API_KEY=sk-ant-...` |

## Configuration

```bash
# Set default provider
goat config provider ollama
goat config model llama3.2

# View config
goat config
```

Config stored at `~/.goat/config.toml`.

## Architecture

```
goat-agent/
├── goat_agent/
│   ├── __init__.py    # Package metadata
│   ├── cli.py         # Typer CLI (code, shell, chat, config)
│   └── llm.py         # Unified LLM interface (Ollama/OpenAI/Anthropic)
├── sources/           # Original source repos (reference)
│   ├── goatcode/      # Deterministic coding agent
│   ├── goatclaw/      # Multi-agent orchestrator
│   ├── devos/         # AI developer OS
│   ├── aria-runtime/  # Agent runtime
│   └── ai-worker/     # Single-agent executor
├── pyproject.toml     # PyPI package config
└── README.md
```

## Built By

**Shivay Singh Rajput** — Building the future of AI-powered development tools.

- GitHub: [@Shivay00001](https://github.com/Shivay00001)
- Email: shivaysinghrajputofficial@gmail.com

## License

Apache-2.0 — Free for personal and commercial use.
