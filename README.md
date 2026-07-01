# Hyver SDK

Typed Python client for the Hyver Runtime API. Built with [httpx](https://www.python-httpx.org/) and [Pydantic v2](https://docs.pydantic.dev/).

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

## Authentication

The Hyver Runtime authenticates every request with a **Cognito JWT** passed as a
Bearer token (`Authorization: Bearer <jwt>`). The SDK adds this header for you —
you just supply the token as `api_key`.

**Use the Cognito _ID token_, not the access token.** The runtime validates the
token's `aud` (audience) claim against the Cognito app-client id, and only the ID
token carries that claim. An access token will be rejected with
`AuthenticationError` (401).

Two endpoints are public and need no token: `GET /health`
(`client.health.check()`) and `GET /v1/capabilities`
(`client.capabilities.get()`). Everything else requires a valid token.

### Obtaining an ID token

Tokens are short-lived (~1 hour); mint a fresh one and refresh as needed. Any
Cognito auth flow works — the browser app uses Amplify. For scripts/services,
`USER_PASSWORD_AUTH` via boto3 is the simplest:

```python
import boto3

def get_id_token(*, region: str, client_id: str, email: str, password: str) -> str:
    cognito = boto3.client("cognito-idp", region_name=region)
    resp = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )
    return resp["AuthenticationResult"]["IdToken"]  # ← ID token, not AccessToken
```

> `USER_PASSWORD_AUTH` must be enabled on the app client. Accounts with MFA or a
> `NEW_PASSWORD_REQUIRED` challenge return a challenge instead of tokens and need
> the corresponding follow-up call.

## Quick Start

```python
from hyver import HyverSDK

client = HyverSDK(
    api_key="your-cognito-id-token",  # JWT ID token (see Authentication above)
    base_url="https://your-hyver-endpoint.example.com",
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
from hyver import HyverSDK

with HyverSDK(api_key="your-token") as client:
    health = client.health.check()
    print(health.status)
# Client automatically closed
```

### Async Usage

```python
import asyncio
from hyver import AsyncHyverSDK

async def main():
    async with AsyncHyverSDK(
        api_key="your-cognito-id-token",
        base_url="https://your-hyver-endpoint.example.com",
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
| `HYVER_API_KEY` | Cognito JWT **ID token** | (required) |
| `HYVER_BASE_URL` | Hyver runtime URL | `http://localhost:8643` |
| `HYVER_LOADER_BASE_URL` | Hyver loader URL (for `client.sessions.*`) | (unset — sessions disabled) |

```bash
export HYVER_API_KEY="eyJhbGciOi..."
export HYVER_BASE_URL="https://hyver.your-domain.com"
export HYVER_LOADER_BASE_URL="https://loader.hyver.your-domain.com"
```

```python
client = HyverSDK()  # reads from environment
```

### Timeouts, retries, and per-request options

```python
client = HyverSDK(api_key=..., timeout=30.0, max_retries=4)

# Per-call overrides (all resource methods accept these):
client.runs.create(input="...", session_id="s1", timeout=5.0,
                   extra_headers={"X-Session-Id": "s1"})
```

Every request sends a versioned `User-Agent` (`hyver-sdk/<version> python/<x.y.z>`)
— override it per call via `extra_headers={"User-Agent": "..."}`. The installed
version is available as `hyver.__version__`.

### Sessions (loader service)

`runs.create(...)` needs a `session_id`. Sessions are owned by the Hyver
**loader** service — a different base URL from the runtime, same Cognito ID-token
auth. Configure `loader_base_url` (or `HYVER_LOADER_BASE_URL`) to enable
`client.sessions.*`; without it, session calls raise `ValueError`.

```python
client = HyverSDK(
    api_key="...",
    base_url="https://hyver.your-domain.com",           # runtime
    loader_base_url="https://loader.hyver.your-domain.com",  # loader
)

# Full flow: create a session, then run against it
session = client.sessions.create(title="Quarterly review")
run = client.runs.create(input="Summarize Q3", session_id=session.session_id)
for event in client.runs_events.stream(run_id=run.run_id):
    ...

# Manage sessions
for s in client.sessions.list(status="active", limit=20).sessions:
    print(s.session_id, s.title)
history = client.sessions.history(session_id=session.session_id, limit=50)
client.sessions.delete(session_id=session.session_id)
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

**Sessions** (loader service — requires `loader_base_url`):

| Method | HTTP | Description |
|--------|------|-------------|
| `client.sessions.create(...)` | `POST /sessions` | Create a session |
| `client.sessions.list(...)` | `GET /sessions` | List the user's sessions |
| `client.sessions.retrieve(session_id=...)` | `GET /sessions/{id}` | Get one session |
| `client.sessions.delete(session_id=...)` | `DELETE /sessions/{id}` | End a session |
| `client.sessions.history(session_id=...)` | `GET /sessions/{id}/history` | Paginated message history |

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
| `run.completed` | | Run completed (Hyver native) |
| `response.failed` | | Run failed (Responses API) |
| `run.failed` | | Run failed (Hyver native) |
| `error` | | Error occurred |
| `response.output_item.added` | | Output item added (tool call, image) |
| `response.output_item.done` | | Output item completed |
| `done` | `message_stop` | Stream finished |

## Error Handling

```python
from hyver import HyverSDK, AuthenticationError, RateLimitError, APIError

client = HyverSDK(api_key="your-token")

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
├── src/hyver/            # SDK source (generated + patched)
│   ├── __init__.py        # Public exports
│   ├── _client.py         # HyverSDK + AsyncHyverSDK
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

### Unreleased

- Add `client.sessions` (loader-backed): `create` / `list` / `retrieve` /
  `delete` / `history`, enabling the full create-session → run → stream flow.
  Configure `loader_base_url` / `HYVER_LOADER_BASE_URL` (same Cognito auth)
- Send a versioned `User-Agent` header (`hyver-sdk/<version> python/<x.y.z>`) on
  every request; overridable via `extra_headers`
- Expose the installed package version as `hyver.__version__`
- Fix Python 3.10 compatibility: import `Required`/`TypedDict` from
  `typing_extensions` instead of `typing` (`typing.Required` is 3.11+)
- Fix async `runs.stop()` / `runs_approval.submit()` to URL-encode `run_id`
  (previously only the sync variants were encoded)
- Documented authentication: Cognito **ID token** required, with a token-minting
  example and the list of public (no-auth) endpoints
- Green `make check`: modernized generated annotations (PEP 585/604), added
  `__all__` to `resources`, and scoped mypy strictness for generated code

### v0.1.0 (2026-05-25)

- Initial release
- 7 Hyver Runtime API endpoints
- Sync + async clients
- SSE streaming with typed events
- Automatic retries with exponential backoff
- JWT authentication

## License

Proprietary. See [LICENSE](LICENSE) for details.
