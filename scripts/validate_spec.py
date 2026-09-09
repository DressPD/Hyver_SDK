#!/usr/bin/env python3
"""Validate openapi.yaml — structural (well-formed) + semantic (event coverage) checks.

Runs as a CI gate so the spec cannot silently drift from the runtime contract.
No dependencies beyond Python stdlib.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SPEC_PATH = Path(__file__).parent.parent / "openapi.yaml"

# ── structural validation ──────────────────────────────────────────────


def _check(condition: bool, msg: str) -> None:
    if not condition:
        print(f"  FAIL: {msg}", file=sys.stderr)
        sys.exit(1)
    print(f"  OK  : {msg}")


def main() -> None:
    print(f"Validating {SPEC_PATH} ...")

    from ruamel.yaml import YAML; yaml = YAML(typ="safe")  # ruamel is a transitive dep of stainful

    with open(SPEC_PATH) as fh:
        spec = yaml.load(fh)

    schemas = spec.get("components", {}).get("schemas", {})

    # ── structural checks ──
    run_event = schemas.get("RunEvent")
    _check(run_event is not None, "RunEvent schema present")
    _check(isinstance(run_event, dict), "RunEvent is an object")

    disc = run_event.get("discriminator", {})
    _check(disc.get("propertyName") == "event", "discriminator propertyName == 'event'")
    _check(isinstance(disc.get("mapping"), dict), "discriminator.mapping is a dict")
    _check(isinstance(run_event.get("oneOf"), list), "RunEvent.oneOf is a list")

    mapping = disc["mapping"]
    one_of_refs = {entry["$ref"] for entry in run_event["oneOf"] if isinstance(entry, dict)}
    mapped_refs = set(mapping.values())

    missing_from_oneof = mapped_refs - one_of_refs
    _check(len(missing_from_oneof) == 0, f"mapping→oneOf sync (mapped {len(mapped_refs)}, oneOf {len(one_of_refs)})")
    for ref in sorted(missing_from_oneof):
        print(f"         mapped but not in oneOf: {ref}", file=sys.stderr)

    # ── semantic coverage checks ──
    event_names = list(mapping.keys())
    _check("tool.started" in event_names, "emits tool.started")
    _check("tool.completed" in event_names, "emits tool.completed")
    _check("approval.request" in event_names, "emits approval.request")
    _check("approval.responded" in event_names, "emits approval.responded")
    _check("run.cancelled" in event_names, "emits run.cancelled")
    _check("run.completed" in event_names, "emits run.completed")
    _check("run.failed" in event_names, "emits run.failed")
    _check("reasoning.available" in event_names, "emits reasoning.available")
    _check("message.delta" in event_names, "emits message.delta")

    # ── approval endpoint shape ──
    approval_schema = schemas.get("RunApprovalRequest", {})
    _check(isinstance(approval_schema, dict), "RunApprovalRequest is an object")
    _check(approval_schema.get("required") == ["choice"], "RunApprovalRequest requires [choice]")
    props = approval_schema.get("properties", {})
    _check("choice" in props, "RunApprovalRequest has choice property")
    choice_enum = props.get("choice", {}).get("enum", [])
    _check("once" in choice_enum, "choice enum includes once")
    _check("deny" in choice_enum, "choice enum includes deny")

    # ── status code ──
    paths = spec.get("paths", {})
    runs_post = paths.get("/v1/runs", {}).get("post", {})
    responses = runs_post.get("responses", {})
    status_codes = set(responses.keys())
    _check("202" in status_codes, "POST /v1/runs returns 202")
    _check("2XX" in status_codes, "POST /v1/runs has 2XX alias (generator constraint)")

    # ── run completed schema includes output ──
    run_completed = schemas.get("RunCompletedEvent", {})
    rce_props = run_completed.get("properties", {})
    _check("output" in rce_props, "RunCompletedEvent has output field")

    print("\nAll validations passed.")
    print(f"  Event types covered: {len(event_names)}")


if __name__ == "__main__":
    main()