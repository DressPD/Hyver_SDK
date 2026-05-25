# Hyver SDK

Typed Python client for the Hyver Hermes Runtime API. Built with [httpx](https://www.python-httpx.org/) and [Pydantic v2](https://docs.pydantic.dev/).

## Features

- Fully typed request/response models (Pydantic v2)
- Sync and async clients
- SSE streaming for real-time run events
- Automatic retries with exponential backoff
- Bearer token (JWT) authentication
- OpenAI-compatible chat completions endpoint

## Installation

```bash
pip install hyver-sdk
```

Or install from GitHub:

```bash
pip install git+https://github.com/DressPD/hyver-sdk.git
# or with uv
uv add git+https://github.com/DressPD/hyver-sdk.git
```

For development:

```bash
git clone https://github.com/DressPD/hyver-sdk.git
cd hyver-sdk
uv sync --all-extras
```

## Quick Start

```python
from hermes import HermesSDK

client = HermesSDK(
    api_key="your-cognito-jwt-token",
    base_url="https://your-hermes-endpoint.example.com",
)

# Health check
health = client.health.check()
print(health.status)  # "healthy"

# Create a run
run = client.runs.create(
    input="Summarize the latest quarterly report",
    session_id="session-abc-123",
    metadata={"reasoning": True, "search_enabled": False, "human_control": False},
)

# Stream run events (SSE)
stream = client.runs_events.stream(run_id=run.run_id)
for event in stream:
    if event.type == "message.delta":
        print(event.delta, end="", flush=True)
    elif event.type == "tool.start":
        print(f"\n[Tool: {event.name}]")
    elif event.type == "run.completed":
        print("\n--- Done ---")

# Chat completions (OpenAI-compatible)
completion = client.chat_completions.create(
    messages=[{"role": "user", "content": "Hello!"}],
    model="default",
)
print(completion.choices[0].message.content)
```

### Async Usage

```python
import asyncio
from hermes import AsyncHermesSDK

async def main():
    client = AsyncHermesSDK(
        api_key="your-cognito-jwt-token",
        base_url="https://your-hermes-endpoint.example.com",
    )

    run = await client.runs.create(
        input="What is the weather?",
        session_id="session-xyz",
    )

    stream = await client.runs_events.stream(run_id=run.run_id)
    async for event in stream:
        if event.type == "message.delta":
            print(event.delta, end="", flush=True)

asyncio.run(main())
```

## API Reference

| Method | HTTP | Description |
|--------|------|-------------|
| `client.health.check()` | `GET /health` | Runtime health status |
| `client.capabilities.get()` | `GET /v1/capabilities` | List available capabilities |
| `client.chat_completions.create(...)` | `POST /v1/chat/completions` | OpenAI-compatible chat |
| `client.runs.create(...)` | `POST /v1/runs` | Create an agent run |
| `client.runs.stop(run_id=...)` | `POST /v1/runs/{run_id}/stop` | Stop a running agent |
| `client.runs_events.stream(run_id=...)` | `GET /v1/runs/{run_id}/events` | Stream run events (SSE) |
| `client.runs_approval.submit(run_id=..., approved=...)` | `POST /v1/runs/{run_id}/approval` | Approve/reject tool use |

## SSE Event Types

The streaming endpoint emits the following event types:

| Event | Description |
|-------|-------------|
| `response.created` | Run lifecycle started |
| `message.delta` | Text content chunk |
| `hermes.reasoning` | Reasoning step available |
| `tool.start` | Tool execution started |
| `hermes.tool.progress` | Tool execution progress |
| `tool.result` | Tool execution completed |
| `hermes.approval_required` | Human approval needed |
| `hermes.usage` | Token usage statistics |
| `response.completed` | Run completed successfully |
| `run.completed` | Run completed (legacy) |
| `response.failed` | Run failed |
| `run.failed` | Run failed (legacy) |
| `error` | Error occurred |
| `response.output_item.added` | Output item added |
| `response.output_item.done` | Output item completed |
| `message_stop` | Stream finished |

## Authentication

The SDK uses Cognito JWT tokens for authentication. Pass your token via `api_key`:

```python
client = HermesSDK(api_key="eyJhbGciOi...")
```

Or set the `HERMES_API_KEY` environment variable:

```bash
export HERMES_API_KEY="eyJhbGciOi..."
```

```python
client = HermesSDK()  # reads from HERMES_API_KEY
```

## Development

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

### Setup

```bash
git clone https://github.com/DressPD/hyver-sdk.git
cd hyver-sdk
uv sync --all-extras   # install all deps including dev tools
```

### Regenerate SDK from OpenAPI Spec

The SDK is generated from `openapi.yaml` using [stainful](https://github.com/stainlu/stainful):

```bash
make generate           # regenerate src/hermes/ from openapi.yaml + stainless.yml
```

### Code Quality

```bash
make lint               # ruff check
make format             # ruff format
make typecheck          # mypy
make test               # pytest
make all                # lint + typecheck + test
```

## Project Structure

```
hyver-sdk/
├── openapi.yaml        # OpenAPI 3.1 spec (source of truth)
├── stainless.yml       # stainful generation config
├── pyproject.toml      # Package metadata + dependencies
├── Makefile            # Dev workflow targets
├── uv.lock             # Locked dependencies
├── src/hermes/         # Generated SDK
│   ├── __init__.py     # Public exports
│   ├── _client.py      # HermesSDK + AsyncHermesSDK
│   ├── _core/          # Base infrastructure
│   ├── resources/      # API resource classes
│   └── types/          # Pydantic request/response models
└── tests/              # SDK tests
```

## Adding New Endpoints

1. Add the endpoint to `openapi.yaml`
2. Add the resource mapping in `stainless.yml`
3. Run `make generate`
4. Run `make all` to verify

## License

Internal use only.
