# Hyver SDK

Typed Python client for the Hyver Hermes Runtime API. Built with [httpx](https://www.python-httpx.org/) and [Pydantic v2](https://docs.pydantic.dev/).

## Features

- Fully typed request/response models (Pydantic v2)
- Sync and async clients with context manager support
- SSE streaming for real-time run events
- Automatic retries with exponential backoff + jitter
- Bearer token (JWT) authentication
- OpenAI-compatible chat completions endpoint

## Installation

Install from GitHub:

```bash
pip install git+https://github.com/DressPD/Hyver_SDK.git
# or with uv
uv add git+https://github.com/DressPD/Hyver_SDK.git
```

For development:

```bash
git clone https://github.com/DressPD/Hyver_SDK.git
cd Hyver_SDK
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
    if event.type in ("message.delta", "response.output_text.delta"):
        print(event.delta, end="", flush=True)
    elif event.type == "tool.start":
        print(f"\n[Tool: {event.name}]")
    elif event.type in ("run.completed", "response.completed"):
        print("\n--- Done ---")

# Chat completions (OpenAI-compatible)
completion = client.chat_completions.create(
    messages=[{"role": "user", "content": "Hello!"}],
    model="default",
)
print(completion.choices[0].message.content)

# Close when done
client.close()
```

### Context Manager

```python
from hermes import HermesSDK

with HermesSDK(api_key="your-token") as client:
    health = client.health.check()
    print(health.status)
# Client automatically closed
```

### Async Usage

```python
import asyncio
from hermes import AsyncHermesSDK

async def main():
    async with AsyncHermesSDK(
        api_key="your-cognito-jwt-token",
        base_url="https://your-hermes-endpoint.example.com",
    ) as client:
        run = await client.runs.create(
            input="What is the weather?",
            session_id="session-xyz",
        )

        stream = await client.runs_events.stream(run_id=run.run_id)
        async for event in stream:
            if event.type in ("message.delta", "response.output_text.delta"):
                print(event.delta, end="", flush=True)

asyncio.run(main())
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HERMES_API_KEY` | Cognito JWT token | (required) |
| `HERMES_BASE_URL` | Hermes runtime URL | `http://localhost:8643` |

```bash
export HERMES_API_KEY="eyJhbGciOi..."
export HERMES_BASE_URL="https://hermes.your-domain.com"
```

```python
client = HermesSDK()  # reads from environment
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

| Event | Aliases | Description |
|-------|---------|-------------|
| `response.created` | | Run lifecycle started |
| `response.output_text.delta` | `message.delta` | Text content chunk |
| `reasoning.available` | `response.reasoning`, `hermes.reasoning` | Reasoning step |
| `tool.start` | | Tool execution started |
| `tool.progress` | `hermes.tool.progress` | Tool execution progress |
| `tool.result` | | Tool execution completed |
| `approval.required` | `hermes.approval_required` | Human approval needed |
| `hermes.usage` | | Token usage statistics |
| `response.completed` | | Run completed (Responses API) |
| `run.completed` | | Run completed (Hermes native) |
| `response.failed` | | Run failed (Responses API) |
| `run.failed` | | Run failed (Hermes native) |
| `error` | | Error occurred |
| `response.output_item.added` | | Output item added (tool call, image) |
| `response.output_item.done` | | Output item completed |
| `done` | `message_stop` | Stream finished |

## Error Handling

```python
from hermes import HermesSDK, AuthenticationError, RateLimitError, APIError

client = HermesSDK(api_key="your-token")

try:
    run = client.runs.create(input="test", session_id="s1")
except AuthenticationError:
    print("Invalid or expired JWT token")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.response.headers.get('retry-after')}")
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
```

## Development

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

### Setup

```bash
git clone https://github.com/DressPD/Hyver_SDK.git
cd Hyver_SDK
uv sync --all-extras
```

### Regenerate SDK from OpenAPI Spec

The SDK is generated from `openapi.yaml` using [stainful](https://github.com/stainlu/stainful), with post-generation patches applied automatically:

```bash
make generate    # stainful generate + post_generate.py patches
```

### Code Quality

```bash
make lint        # ruff check + format check
make format      # auto-format
make typecheck   # mypy
make test        # pytest
make coverage    # pytest with coverage report
make check       # lint + typecheck + test
make build       # build package
make all         # generate + check
```

## Project Structure

```
Hyver_SDK/
├── openapi.yaml           # OpenAPI 3.1 spec (source of truth)
├── stainless.yml          # stainful generation config
├── pyproject.toml         # Package metadata + dependencies
├── Makefile               # Dev workflow targets
├── uv.lock                # Locked dependencies
├── LICENSE                # Proprietary license
├── scripts/
│   └── post_generate.py   # Post-generation patches for stainful bugs
├── src/hermes/            # SDK source (generated + patched)
│   ├── __init__.py        # Public exports
│   ├── _client.py         # HermesSDK + AsyncHermesSDK
│   ├── _core/             # Base infrastructure
│   ├── resources/         # API resource classes
│   └── types/             # Pydantic request/response models
└── tests/                 # SDK tests
```

## Adding New Endpoints

1. Add the endpoint to `openapi.yaml`
2. Add the resource mapping in `stainless.yml`
3. Run `make generate` (applies patches automatically)
4. Run `make check` to verify

## Changelog

### v0.1.0 (2026-05-25)

- Initial release
- 7 Hermes Runtime API endpoints
- Sync + async clients
- SSE streaming with typed events
- Automatic retries with exponential backoff
- JWT authentication

## License

Proprietary. See [LICENSE](LICENSE) for details.
