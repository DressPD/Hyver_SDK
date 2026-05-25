"""
Integration test: SDK against live Hermes Runtime.

Requires:
  - AWS credentials (aws sso login --profile hyver-dev)
  - Hyver_BE/.env with RUNTIME_API, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID,
    TEST_USER_EMAIL, TEST_USER_PASSWORD

Run:
  cd Hyver_SDK
  source ../Hyver_BE/.env
  uv run python tests/test_integration.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid

# Load .env from Hyver_BE if not already set
_be_env = os.path.join(os.path.dirname(__file__), "..", "..", "Hyver_BE", ".env")
if os.path.exists(_be_env) and not os.getenv("RUNTIME_API"):
    from pathlib import Path

    for line in Path(_be_env).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def _get_cognito_jwt() -> str:
    """Authenticate via Cognito USER_PASSWORD_AUTH → return IdToken."""
    import boto3

    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    client_id = os.getenv("COGNITO_USER_POOL_CLIENT_ID") or os.environ["COGNITO_CLIENT_ID"]
    email = os.environ["TEST_USER_EMAIL"]
    password = os.environ["TEST_USER_PASSWORD"]
    region = pool_id.split("_")[0]

    client = boto3.client("cognito-idp", region_name=region)
    resp = client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )
    token = resp["AuthenticationResult"]["IdToken"]
    print(f"  ✓ Cognito JWT obtained ({len(token)} chars)")
    return token


def _sep(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def main() -> int:
    from hermes import HermesSDK
    from hermes._core._exceptions import APIError
    from hermes.types.runs_create_params import RunCreateParamsMetadata

    base_url = os.environ.get("RUNTIME_API", "https://api.hyver.app")
    print(f"Base URL: {base_url}")

    # ── Auth ──
    _sep("1. Cognito Authentication")
    try:
        jwt = _get_cognito_jwt()
    except Exception as e:
        print(f"  ✗ Auth failed: {e}")
        print("  → Run: aws sso login --profile hyver-dev")
        return 1

    # ── Client ──
    client = HermesSDK(api_key=jwt, base_url=base_url, timeout=30)

    passed = 0
    failed = 0
    errors: list[str] = []

    # ── Test 1: Health ──
    _sep("2. GET /health")
    try:
        health = client.health.check()
        assert health.status == "healthy", f"Expected 'healthy', got {health.status!r}"
        print(f"  ✓ Health: {health.status}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Health failed: {e}")
        errors.append(f"health: {e}")
        failed += 1

    # ── Test 2: Capabilities ──
    _sep("3. GET /v1/capabilities")
    try:
        caps = client.capabilities.get()
        print(f"  ✓ Capabilities: {type(caps).__name__}")
        if isinstance(caps, dict):
            print(f"    Keys: {list(caps.keys())[:10]}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Capabilities failed: {e}")
        errors.append(f"capabilities: {e}")
        failed += 1

    # ── Test 3: Create Run ──
    _sep("4. POST /v1/runs (create run)")
    run_id = None
    session_id = f"sdk-test-{uuid.uuid4().hex[:8]}"
    try:
        run = client.runs.create(
            input="Say exactly: 'SDK integration test successful'. Nothing else.",
            session_id=session_id,
            metadata=RunCreateParamsMetadata(reasoning=False, search_enabled=False, human_control=False),
        )
        run_id = run.run_id or run.id
        assert run_id, f"No run_id in response: {run}"
        print(f"  ✓ Run created: {run_id}")
        passed += 1
    except Exception as e:
        print(f"  ✗ Create run failed: {e}")
        errors.append(f"create_run: {e}")
        failed += 1

    # ── Test 4: SSE Stream ──
    if run_id:
        _sep("5. GET /v1/runs/{run_id}/events (SSE stream)")
        try:
            stream = client.runs_events.stream(run_id=run_id)
            event_types: list[str] = []
            content_chunks: list[str] = []
            event_count = 0
            start = time.time()

            for event in stream:
                event_count += 1
                etype = getattr(event, "type", "unknown")
                event_types.append(etype)

                # Collect content deltas
                delta = getattr(event, "delta", None)
                if delta:
                    content_chunks.append(delta)

                # Terminal events
                if etype in ("run.completed", "run.failed", "response.completed", "response.failed", "done"):
                    break

                # Safety timeout
                if time.time() - start > 60:
                    print("  ⚠ Timeout after 60s")
                    break

            elapsed = time.time() - start
            content = "".join(content_chunks)
            unique_types = sorted(set(event_types))

            print(f"  ✓ Stream completed: {event_count} events in {elapsed:.1f}s")
            print(f"    Event types: {unique_types}")
            print(f"    Content ({len(content)} chars): {content[:200]}{'...' if len(content) > 200 else ''}")
            passed += 1
        except Exception as e:
            print(f"  ✗ SSE stream failed: {e}")
            errors.append(f"sse_stream: {e}")
            failed += 1

    # ── Test 5: Stop Run (if still alive) ──
    if run_id:
        _sep("6. POST /v1/runs/{run_id}/stop")
        try:
            client.runs.stop(run_id=run_id)
            print(f"  ✓ Stop sent (may be no-op if already completed)")
            passed += 1
        except APIError as e:
            status = getattr(e, "status_code", None)
            if status in (404, 409):
                print(f"  ✓ Stop returned {status} (run already finished — expected)")
                passed += 1
            else:
                print(f"  ✗ Stop failed: {e}")
                errors.append(f"stop: {e}")
                failed += 1
        except Exception as e:
            print(f"  ✗ Stop failed: {e}")
            errors.append(f"stop: {e}")
            failed += 1

    # ── Summary ──
    _sep("RESULTS")
    total = passed + failed
    print(f"  {passed}/{total} passed, {failed} failed")
    if errors:
        print(f"\n  Failures:")
        for err in errors:
            print(f"    ✗ {err}")

    client.close()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
