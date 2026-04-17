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
