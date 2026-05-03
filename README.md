# dagstack-logger

Python binding for [dagstack/logger-spec](https://github.com/dagstack/logger-spec) — OTel-compatible structured logging with a named-logger hierarchy, W3C trace context propagation, pluggable sinks, and scoped overrides.

Typically configured from a [dagstack-config](https://github.com/dagstack/config-python) `logging:` section, but `dagstack-config` is **not** a runtime dependency — see [Dependencies](#dependencies) below.

**Status: Phase 1 MVP.** Console / File / In-memory sinks ship; OTLP, redaction processor chain, and the AI-agent extension pack land in Phase 2+.

## Roadmap

- **Phase 1 release (`0.x` series)** — current. `LogRecord` / `Severity` / W3C hex encoding / dagstack JSON-lines wire format; `ConsoleSink` (JSON/pretty TTY-aware), `FileSink` (rotation), `InMemorySink` (ring buffer); `Logger` hierarchy with context propagation, suffix-based redaction (`RedactionConfig`), and scoped overrides. The module-level `configure(...)` accepts a section dumped from `dagstack-config`; no hard runtime dependency on the config binding. No OTLP sink, no LogProcessor chain, no AI-agent extension pack (§5.5 of logger-spec) yet.
- **Phase 2+** — `OTLPSink`, `LokiSink`, `SentrySink`, the LogProcessor chain (redaction / sampling), AI-agent conventions.

## Spec

The spec lives as a submodule in `spec/` → [dagstack/logger-spec](https://github.com/dagstack/logger-spec). The core decisions are in `spec/adr/0001-logger-contract.md`.

## Local development

```bash
git clone --recurse-submodules https://github.com/dagstack/logger-python.git
cd logger-python
uv sync --group dev

make test           # pytest
make lint           # ruff check + format --check
make typecheck      # mypy --strict
```

## Dependencies

- `opentelemetry-api>=1.20,<2.0` — for trace / span / baggage context propagation (mandatory per spec §3.4).
- `opentelemetry-sdk` + exporter (optional via `[otlp]` extras) — for `OTLPSink` in Phase 2+.

`dagstack-logger` does **not** declare a runtime dependency on `dagstack-config`: the application loads its config via the config binding and passes the resolved `logging:` section to `configure(**section)` (see [`dagstack/config-python`](https://github.com/dagstack/config-python)).

## Licensing

Apache-2.0.

## Related

- [`dagstack/logger-spec`](https://github.com/dagstack/logger-spec) — language-agnostic spec.
- [`dagstack/config-python`](https://github.com/dagstack/config-python) — config binding; the logger reads its `logging:` section through this binding.
- [`dagstack/plugin-system-python`](https://github.com/dagstack/plugin-system-python) — plugin system; the logger's `instrumentation_scope` can be derived from a plugin manifest.
