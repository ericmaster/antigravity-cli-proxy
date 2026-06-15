# Contributing to antigravity-cli-proxy

## Quick Start

```bash
git clone https://github.com/nimblersoft/antigravity-cli-proxy.git
cd antigravity-cli-proxy
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Submitting Changes

1. Fork the repo
2. Create a branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push (`git push origin feature/your-feature`)
5. Open a Pull Request

## Code Style

- Ruff for linting (`ruff check .`)
- Target Python 3.11+
- Async first (no blocking calls)
