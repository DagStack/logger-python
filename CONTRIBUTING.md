# Contributing

## Development environment

```bash
git clone --recurse-submodules https://github.com/dagstack/logger-python.git
cd logger-python
uv sync --group dev
uv run pre-commit install
```

If you cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

## Workflow

- **Base branch**: `main`.
- **Feature branches**: `feature/<phase|topic>-<short-desc>` (e.g., `feature/phase-b-records`).
- **PRs** target `main`; one PR equals one logical change.
- **Commit style**: conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`) or phase-tagged (`phase-b:`).

## Identity

- `user.name = "Evgenii Demchenko"`
- `user.email = "demchenkoev@gmail.com"` (dagstack/* uses a personal identity, not a corporate one).

## Pre-PR checks

```bash
make lint
make typecheck
make test
```

## Spec submodule updates

`spec/` is a submodule of `dagstack/logger-spec`. Update:

```bash
cd spec && git fetch origin && git checkout main && git pull && cd ..
git add spec && git commit -m "chore(spec): bump logger-spec submodule"
```

## Versioning

`src/dagstack/logger/_version.py::__version__` is the single source. A release is a git tag `v<version>`; the publish workflow then ships the artefact to Nexus `gx-pypi` and to PyPI.

Pre-1.0 versions follow `0.N.M` plus `.devN` / `.rcN` for pre-releases.
