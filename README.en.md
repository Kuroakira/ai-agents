# AI Agents Repository

A repository for experimenting and developing AI agents using LangGraph.

## Purpose

- Building and validating AI agents using the LangGraph framework
- Accumulating reusable tools and patterns
- Prototyping agents for various use cases

## Tech Stack

| Item | Technology |
|------|------------|
| Framework | LangGraph |
| LLM | Google Gemini |
| Language | Python 3.11+ |
| Package Management | pip + venv |
| Linter/Formatter | ruff |

## Setup

### 1. Create and Activate Virtual Environment

```bash
# Create virtual environment (first time only)
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Edit the `.env` file and set your API key:

```
GOOGLE_API_KEY=your-api-key-here
```

## Project Structure

```
ai-agents/
├── agents/           # Agent implementations
│   └── {agent_name}/ # Individual agent directories
├── shared/           # Shared modules
│   └── tools/        # Reusable tools
├── tests/            # Test code
├── pyproject.toml    # Project configuration and dependencies
└── .env.example      # Environment variable template
```

## Development Commands

```bash
# Run tests
pytest

# Lint check
ruff check .

# Auto format
ruff format .
```

## Agent Development Guidelines

### Directory Structure

Create new agents under `agents/{agent_name}/`:

```
agents/my_agent/
├── __init__.py
├── graph.py      # LangGraph graph definition
├── nodes.py      # Node functions
├── state.py      # State schema
└── README.md     # Agent documentation
```

### Coding Conventions

- Type hints are required
- Use Google-style docstrings
- Define state schemas with `TypedDict` or `Pydantic BaseModel`
- Node functions should follow the single responsibility principle

### Shared Tools

Place tools used by multiple agents in `shared/tools/` for reusability.

## Future Plans

- [ ] MCP server integration
- [ ] Inter-agent orchestration
- [ ] Additional LLM provider support (Anthropic, OpenAI, etc.)
