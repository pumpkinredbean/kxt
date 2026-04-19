# AGENTS.md - kxt

Guidelines for AI coding agents working in this repository.

## Project Overview

`kxt` is a library-first Python package for Korean securities market access. Keep it focused on reusable market-access models and client boundaries, not hub/runtime platform concerns.

## Commands

```bash
# Sync dev environment (creates .venv, installs all extras)
uv sync --all-extras

# Run tests
uv run pytest

# Build docs (strict)
uv run mkdocs build --strict

# Build sdist + wheel
uv build

# Basic import check
uv run python -c "import kxt; print(kxt.__all__)"
```

## Testing

```bash
uv run pytest
```

## Project Structure

```text
kxt/
├── src/kxt/             # library package
│   ├── clients/          # provider-facing client interfaces and namespaces
│   ├── models/           # broker-neutral enums and market-data contracts
│   └── streams/          # streaming subscription request models
├── docs/development/     # package direction and architecture notes
├── pyproject.toml        # package metadata and build config
└── README.md             # public positioning and non-goals
```

## Boundaries

### Always Do
- Keep the package import-safe and free from network/runtime side effects.
- Preserve the distinction between request scope and venue identity.
- Add provider-specific details at the client edge instead of leaking them into core models.
- Keep wording honest about current implementation depth.

### Ask First
- Adding runtime stack concerns such as Kafka, web servers, databases, or admin APIs.
- Renaming public model types or package paths after they are introduced.
- Adding heavy dependencies before a concrete need is established.

### Never Do
- Never read, copy, or commit `.env` secrets or local credentials.
- Never turn this repo into the dashboard/hub application stack.
- Never claim placeholder namespaces are production-ready integrations.

## Release Discipline

`kxt` is published to PyPI. Releases are immutable and the README ships as the
PyPI long description, so release hygiene is part of the package contract.

### When a release is required
A new pre-release (`0.1.0aN`) is required when any of the following change:
- Packaged code under `src/kxt/` (public API, CLI behavior, importable surface).
- Runtime-visible dependencies in `pyproject.toml`.
- `README.md` content, because it is the PyPI long description and is baked
  into every uploaded artefact.

### When a release is NOT required
Docs-only fixes that do not touch packaged code or the README/long description
ship without a new version bump:
- Edits under `docs/` only.
- `mkdocs.yml` navigation/styling.
- Internal notes (`AGENTS.md`, development docs) with no packaging impact.

### Pre-release preflight (run in order)
1. Bump `version` in `pyproject.toml` to the next `0.1.0aN`.
2. Ensure `README.md` has **no hardcoded stale version phrase**. Prefer
   version-agnostic alpha wording (e.g. `0.1.x alpha`) to avoid long-description
   drift. Any hardcoded stale version in README is a release-blocking defect.
3. Scan for stale version strings across shipped/user-facing surfaces:
   ```bash
   rg -n '0\.1\.0a[0-9]+' README.md docs/ mkdocs.yml pyproject.toml
   ```
   Only `pyproject.toml` should legitimately pin the current version.
4. Local verification (all must pass):
   ```bash
   uv run pytest -q
   uv run kxt --help         # CLI smoke check (entry point must import cleanly)
   uv build                  # sdist + wheel must build
   ```

### Release flow
1. Commit the bump on `main` with a `release:` prefix message.
2. `git push origin main`.
3. `git tag -a vX.Y.ZaN -m "kxt X.Y.ZaN"` and `git push origin vX.Y.ZaN`.
4. Observe the tag-triggered `publish` workflow:
   ```bash
   gh run list --workflow=publish.yml -L 5
   gh run watch <run-id>
   ```
5. Verify on PyPI:
   ```bash
   curl -sI https://pypi.org/pypi/kxt/X.Y.ZaN/json    # must be HTTP 200
   ```

### Immutability
- Published versions are immutable. Never reuse a version number.
- Never move, delete, or re-push an existing tag (`v0.1.0a1`, `v0.1.0a2`, ...).
- Never yank prior alphas as part of a routine release; leave historical
  artefacts reachable on PyPI.
- If a release is broken, fix forward with the next `aN+1`, not by mutating the
  previous one.
