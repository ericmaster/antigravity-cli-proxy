# AGENTS.md — antigravity-cli-proxy

## Purpose

**antigravity-cli-proxy** is an OpenAI-compatible HTTP proxy. Any application using the OpenAI protocol can point its `base_url` to this proxy, which translates `/chat/completions` requests into calls to the **antigravity** (`agy`) CLI in headless mode.

## Use Cases

| Consumer | How to connect |
|----------|---------------|
| **AgentMemory** | `OPENAI_BASE_URL=http://localhost:3120` |
| **LangChain** | `ChatOpenAI(openai_api_base="http://localhost:3120")` |
| **LiteLLM** | Add as custom OpenAI endpoint |
| **Any OpenAI SDK** | Set `base_url` in your client config |

## Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Server:** uvicorn
- **Validation:** Pydantic v2
- **Config:** python-dotenv + environment variables
- **Containerization:** Docker + docker-compose

## Key Commands

```bash
# Install for local development
pip install -e .

# Run the proxy
python -m src

# Docker
docker compose up --build

# Health check
curl http://localhost:3120/healthz
```

## Project Structure

```
antigravity-cli-proxy/
├── AGENTS.md              # This file — project context for agents
├── README.md              # User-facing docs
├── pyproject.toml         # Dependencies and build config
├── Dockerfile             # Production container (python:3.11-slim)
├── docker-compose.yml     # Local dev orchestration
├── .env.example           # Environment variable template
├── .gitignore
└── src/
    ├── __init__.py        # Package init, version
    ├── __main__.py        # Entry point for `python -m src`
    ├── main.py            # FastAPI app + routes (Phase 2: fully implemented)
    ├── models.py          # Pydantic models (OpenAI request/response)
    └── cli_invoker.py     # Async CLI wrapper for antigravity (Phase 2)
```

## Plan Reference

Full implementation plan: `~/.hermes/plans/antigravity-openai-proxy-plan.md`

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ COMPLETE | Project bootstrap, FastAPI scaffold, stub endpoints |
| 2 | ✅ COMPLETE | CLI pipe: OpenAI → antigravity → parse → response |
| 3 | 🚧 TODO | AgentMemory integration + E2E testing |

## Architecture Summary

```
Any OpenAI client (POST /chat/completions)
    ↓ HTTP
antigravity-cli-proxy (FastAPI, port 3120)
    ↓ subprocess
antigravity cli (--print --dangerously-skip-permissions)
    ↓ stdout parsing
OpenAI-compatible JSON response
```
