# Sandbox evidence

[phase2_evidence.json](phase2_evidence.json) records actual local calls through the
tool registry, persisted simulated objects and trusted state checks. It was
captured during Phase 2 implementation and contains no Hermes/model execution,
live service effects, credentials, generated repairs or reference patches. The
application does not load this evidence as tool results or scenario answers.

The five cases show a passing release workflow, a checklist serialization failure
after ticket creation, absent directory lookup, a successful notification sent to
the historical channel that fails outcome verification, and denied/invalid calls
plus an attempted call to the protected evaluator. Event UUIDs, timestamps and
sequences were emitted by the real sandbox; every business object and reference
is explicitly simulated.

This capture uses evaluator `release-state-v2`. Its developer-reviewed release
matching accepts sentence punctuation after a release number while rejecting
different releases and patch versions. Earlier actual Hermes attempts are
retained separately; this simulation evidence does not replace their results.

Developer setup seeds scenarios in `Sandbox.initialize`; the adapter serializer
and trusted evaluator are separate modules. Current and historical runbook
documents remain available with explicit versions and project scope. The
directory holds authorized simulated records but has no executor lookup tool.

From `backend/`, reproduce the behavioral checks with:

```powershell
uv run --frozen pytest tests/test_sandbox.py tests/test_tool_registry.py -q
```

The tests also verify different projects/releases/owners, durable reopen,
concurrent retry idempotency, coherent object links, independent reset and
retained evidence. Reset is an administrative action; it is never an MCP tool.
The local simulation is not a security boundary for generated code. Container
isolation and executable repair publication belong to later phases.
