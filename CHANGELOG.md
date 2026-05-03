# Changelog

All notable changes to `dagstack-logger` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/) pre-1.0 — `0.N.M` + `.devN`/`.rcN`.

## [Unreleased]

## [0.2.0] — 2026-05-03

Cross-binding parity wave per `dagstack/logger-spec` architect review epic
(`logger-spec#2`). Closes M1, M2, M3, M4, M5, S3, S9 findings. All changes
are additive — `0.2.0` is a safe drop-in upgrade from `0.1.4`.

### Added

- **Phase 1 redaction-config public API** (`RedactionConfig` + `configure(redaction=...)`)
  per logger-spec ADR-0001 v1.1 §10.4 (M3). Applications can now register
  extra secret suffixes at bootstrap without waiting for the Phase 2
  processor pipeline:

  ```python
  from dagstack.logger import RedactionConfig, configure

  configure(
      redaction=RedactionConfig(
          extra_suffixes=("_apikey", "_x_internal_token"),
          # replace_defaults=True,  # optional — narrows the safety net
      ),
  )
  ```

  Validation runs synchronously inside `configure()` (`ValueError` on empty /
  whitespace / non-lowercase-ASCII suffix). When `replace_defaults=True` and
  `extra_suffixes=()`, all suffix-based masking is disabled and a WARN is
  emitted on `dagstack.logger.internal` per spec §10.4.

- **`Logger.set_redaction_suffixes` + `Logger.effective_secret_suffixes`** —
  programmatic per-logger override + accessor, mirroring the configure-time
  surface. `RedactionConfig.build_effective_suffixes()` and
  `RedactionConfig.validate()` are exposed on the dataclass.

- **`INTERNAL_LOGGER_NAME`** — exported constant (`"dagstack.logger.internal"`)
  for the diagnostic channel per spec §7.4.

- **`auto_inject_trace_context` cross-binding parity flag (M2)** per
  logger-spec ADR-0001 v1.2 §3.4.2:

  ```python
  configure(auto_inject_trace_context=False)  # skip ambient OTel context lookup
  ```

  Python default is `True` (idiomatic — matches OTel's
  `opentelemetry.context` convention, which delegates to `contextvars`).
  Set to `False` for cross-binding parity with `go.dagstack.dev/logger`'s
  default explicit-context mode.

- **`Logger.reset()`** classmethod (M1) — clears the global registry to
  inherited defaults. For test isolation and hot-reload bootstrap loops.
  SAFETY: invalidates every logger handle held elsewhere; production code
  MUST NOT call it.

### Changed

- The default secret-suffix set is now formally documented as an
  opinionated 6-element subset of
  `config-spec/_meta/secret_patterns.yaml` (per spec §10.4). The
  `DEFAULT_SECRET_SUFFIXES` value is unchanged from `0.1.x`; the list is
  pinned at spec v1.1 to preserve API stability.
- **`dagstack.logger.internal` defaults to its own `ConsoleSink(mode="json", min_severity=WARN)`**
  on first `Logger.get` (per spec §7.4) — diagnostic warnings (sink failures,
  configure-time disable-all, etc.) no longer silently merge with
  application sinks. Operators may opt back in to merged delivery by
  calling `Logger.get(INTERNAL_LOGGER_NAME).set_sinks(...)` explicitly.

### Documentation

- **`Logger.set_min_severity` / `set_sinks` / `set_resource` docstrings** (M1)
  now warn explicitly that the method mutates the *shared* per-logger
  registry node — every concurrent caller observes the change. The
  surrounding section comment cross-references `with_sinks` /
  `append_sinks` / `scope_sinks` as the non-shared scoping alternatives.
- **`Sink.flush(timeout)` docstring** (M4) clarifies that the parameter is
  a Phase 1 hint accepted for forward-compatibility but **not enforced**;
  Phase 2 `OTLPSink` MUST honour the deadline. Cross-reference: spec §7.1.
- **`FileSink` docstring** (M5) adds an explicit symlink-follow caveat —
  `path` is opened verbatim via stdlib `RotatingFileHandler`, which follows
  symbolic links by default. Hosts MUST treat the value as trusted and never
  accept it from end-user input or plugin manifest.

### Fixed

- **Canonical JSON key order — UTF-16 code-unit sort per RFC 8785 §3.2.3
  (S3)**. Previously `json.dumps(sort_keys=True)` produced Python's UTF-32
  code-point order, which diverged from `@dagstack/logger` (TypeScript
  native `Object.keys().sort()`, UTF-16) on keys containing characters
  encoded as UTF-16 surrogate pairs (≥U+10000). Cross-binding wire-byte
  parity is now guaranteed even for non-BMP attribute keys. ASCII-only
  keys are unaffected.
- **`InMemorySink.id` collision** (S9) — multiple `InMemorySink` instances
  created in the same process now get distinct ids (per-instance counter
  suffix) instead of all sharing `"in-memory"`. This unblocks `set_sinks([a, b])`
  configurations where the registry deduplicates by id.

### Cross-binding parity

This release brings logger-python to parity with `logger-go` 0.2.0 and
`@dagstack/logger` 0.2.0 across all M-/S-level architect review findings
from the `dagstack/logger-spec` epic. Once the spec amendments
(§3.4.2 trace-context auto-injection, §10.4 RedactionConfig) land in a
tagged `logger-spec` v1.1+, the corresponding conformance fixtures will
be exercised by `pytest -m conformance` against the pinned `spec/`
submodule.

## [0.1.4] — 2026-05-03

Architect-review patch. Two security-relevant findings on `0.1.3`:

### Fixed

- **Recursive redaction now walks `list[dict]`** (`redaction.py`). Previously a secret key buried inside a list-of-dicts (`{"events": [{"api_key": "..."}]}`) escaped masking — privacy hole for structured payloads typical of webhook bodies and audit trails. Lists of primitives stay untouched; only dict items are recursed.
- **`FileSink` docstring** explicitly warns that `path` is opened verbatim — host MUST treat the value as trusted and never accept it from end-user input or plugin manifest. The runtime intentionally does not try to second-guess host policy here, but the contract is now explicit.

Both findings tracked in [`logger-spec` epic](https://git.goldix.org/dagstack/logger-spec/issues/2) (S8 + M5).

No functional change for code that does not use nested attributes — safe drop-in upgrade from `0.1.3`.

### Tests

- 2 new redaction tests for nested-list traversal.

## [0.1.3] — 2026-05-03

Privacy-scrub patch. Post-release linguist review on `0.1.1` flagged references to a private internal pilot consumer (`Astra` / `astra-m`) in module docstrings and test fixtures — these would have landed in the `.dist-info` metadata and example output of the public PyPI package.

No functional change; safe drop-in upgrade from `0.1.1`.

### Fixed

- `src/dagstack/logger/configuration.py`: removed parenthetical mention of a private pilot in the module docstring.
- `src/dagstack/logger/__init__.py`: example `service.name` and logger name in the module-level docstring switched to a generic `"order-service"` / `"order_service.checkout"`.
- `tests/test_wire.py`, `tests/test_records.py`, `tests/test_logger.py`: test fixtures use `"order-service"` instead of the private name.
- `pyproject.toml` mypy override for `tests.docs_examples.*` — verbatim MDX-snippet mirrors are pedagogical, not production-typed; new `disable_error_code` block keeps `pre-commit`/CI green without weakening core typing.

### Aborted

- `0.1.2` was tagged but the publish CI failed on a stricter `pre-commit` (mypy on `tests/docs_examples/*` snippets) before the wheel was uploaded. `v0.1.2` tag stays in the repo for traceability; PyPI never received the artifact. Per `dagstack/plugin-system-spec/RELEASING.md` Rule 6 "re-publish after yank is forbidden, the next available patch number is the only path", the fix ships as `0.1.3`.

## [0.1.1] — 2026-04-28

First stable public release on pypi.org. Cumulative changes since 0.1.0:

- Translate inline comments and docstrings to English across
  `src/dagstack/logger/` and `tests/` (rc1).
- Translate root markdown (README, CONTRIBUTING, legacy CHANGELOG entry)
  to English; bump `spec/` submodule to logger-spec v1.0 (rc2).
- Add `mirror.yml` and a `publish-pypi` step in `publish.yml` — same
  pattern as `dagstack-config` v0.4.1.

Non-functional relative to 0.1.0 — public API, runtime behaviour, and
type contracts unchanged. The corresponding logger-spec v1.0 contract
and the bilingual logger-docs site (logger.dagstack.dev) are also live.

## [0.1.1rc2] — 2026-04-27

Translate the remaining root markdown that the previous rc1 missed —
`README.md`, `CONTRIBUTING.md`, and the legacy `0.1.0` `CHANGELOG`
section — to English. Replace `git.goldix.org/dagstack/...` links with
`github.com/dagstack/...` per the public-docs convention. Bump the
`spec/` submodule to `dagstack/logger-spec` v1.0 (English ADR + README).

## [0.1.1rc1] — 2026-04-27

First public-publish release candidate. Tests the pypi.org publish
pipeline (a new `publish-pypi` job alongside the existing Nexus upload)
and the new `mirror.yml` workflow that snapshots main + tags to
github.com/dagstack/logger-python.

Bundled non-functional changes since 0.1.0:

- Translate inline comments and docstrings to English across
  `src/dagstack/logger/` (16 modules) and `tests/` (13 modules).
  Public API, runtime behaviour, and type contracts unchanged.
- Add `mirror.yml` and a `publish-pypi` step in `publish.yml` — same
  pattern as `dagstack-config` v0.4.1.

Verification: 192 pytests pass at 98% coverage; ruff + mypy --strict
clean. The corresponding logger-spec v1.0 contract is now also English.

## [0.1.0] — 2026-04-19

First Phase 1 MVP release. Covers logger-spec ADR-0001 v1.0 §1 (OTel Log Data Model wire format), §2 (severity model), §3 (Logger API + hierarchy), §4 (scope / resource), §6 (scoped overrides), §7.1–§7.2 (Sink Protocol + Phase 1 sinks), §9 (config-spec bootstrap integration via `configure()`), §10 (redaction).

### Added
- **Skeleton** — pyproject (`dagstack-logger` PEP 420 namespace), CI workflows (3.11 / 3.12 / 3.13 matrix), `spec/` submodule, publish workflow for Nexus `gx-pypi`.
- **Core primitives** — `LogRecord` / `InstrumentationScope` / `Resource` dataclasses (OTel field names); `Severity` IntEnum + the six canonical `severity_text` strings; `trace_id` / `span_id` hex-encoding helpers; Canonical JSON serializer; the dagstack JSON-lines wire format.
- **Sinks** — a runtime-checkable `Sink` Protocol plus `ConsoleSink` (auto / json / pretty modes with TTY auto-detect and ANSI colors), `FileSink` (backed by stdlib `RotatingFileHandler`), and `InMemorySink` (a test ring buffer). Thread-safe via `threading.Lock`.
- **Logger API** — `Logger.get(name, version)` with dot-hierarchy and sink / level / resource inheritance; severity methods (`trace` / `debug` / `info` / `warn` / `error` / `fatal` / `log` / `exception`); `with` / `child` for bound attributes; `with_sinks` / `append_sinks` / `without_sinks` / `scope_sinks` for scoped overrides; mandatory OTel context propagation (trace / span / baggage auto-injection); sink failure isolation.
- **Redaction** — suffix-based masking (`*_key`, `*_secret`, `*_token`, `*_password`, `*_passphrase`, `*_credentials`) applied recursively to nested dicts.
- **Configuration bootstrap** — `configure(root_level, sinks, per_logger_levels, resource_attributes)` — no hard dependency on `dagstack-config`; the application passes the dumped config section via `**kwargs`.
- **Subscription** — a `Subscription` handle that is inactive in Phase 1 and emits a warning to `dagstack.logger.internal`.

### Metadata
- 192 tests, 98% coverage, ruff + mypy strict clean.
- **Mandatory dependency**: `opentelemetry-api>=1.20,<2.0` (context propagation per §3.4).
- **Optional extras**: `[otlp]` — OTel SDK + OTLP exporter for the Phase 2+ `OTLPSink`.

[0.1.0]: https://github.com/dagstack/logger-python/releases/tag/v0.1.0
