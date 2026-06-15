# antigravity-cli-proxy

<p align="left">
  <a href="https://pypi.org/project/antigravity-cli-proxy/"><img src="https://img.shields.io/pypi/v/antigravity-cli-proxy?color=blue" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://github.com/nimblersoft/antigravity-cli-proxy/actions"><img src="https://img.shields.io/badge/tests-20%2F20%20passing-brightgreen" alt="Tests: 20/20 passing"></a>
  <a href="https://github.com/nimblersoft/antigravity-cli-proxy/stargazers"><img src="https://img.shields.io/github/stars/nimblersoft/antigravity-cli-proxy" alt="GitHub stars"></a>
</p>

**OpenAI-compatible HTTP proxy** that bridges any OpenAI protocol client to the **antigravity** (`agy`) CLI for headless Gemini-powered execution.

## Universal Design

This proxy is **not tied to any specific consumer**. It speaks standard OpenAI `/chat/completions` and can serve any tool, SDK, or application that uses the OpenAI protocol:

| Consumer | How it works |
|----------|-------------|
| **AgentMemory** | Set `OPENAI_BASE_URL=http://localhost:3120` |
| **Any OpenAI SDK** (Python, Node, Go, etc.) | Set `base_url` in client config |
| **LangChain / LlamaIndex** | `ChatOpenAI(openai_api_base="http://localhost:3120")` |
| **LiteLLM** | Add provider entry with `api_base: http://localhost:3120` |
| **Oobabooga / Open WebUI** | Add as custom OpenAI-compatible endpoint |

The proxy translates `POST /chat/completions` into `agy --print` calls and returns standard OpenAI JSON. No consumer-side changes needed — just point the base URL.

## Architecture

```
Any OpenAI client (POST /chat/completions)
    ↓ HTTP
antigravity-cli-proxy (FastAPI, port 3120)
    ↓ subprocess
antigravity cli (--print --dangerously-skip-permissions)
    ↓ stdout parsing
OpenAI-compatible JSON response
```

### Why use this proxy?

- **Use your existing OpenAI client code** — no SDK changes, just swap the `base_url`
- **Free Gemini access** — powered by your antigravity CLI subscription
- **Built-in timeouts** — configurable per-call timeout prevents hung CLI invocations
- **Large prompt support** — automatically switches to stdin for prompts >8KB
- **Zero LLM API keys** — runs locally, no external API credentials needed

## Quick Start

### Installation

```bash
pip install antigravity-cli-proxy
```

### Run the proxy

```bash
python -m antigravity_cli_proxy
# → Uvicorn running on http://0.0.0.0:3120
```

### Verify

```bash
curl http://localhost:3120/healthz
# → {"status":"ok","version":"0.1.0"}

curl -sS -X POST http://localhost:3120/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"agy","messages":[{"role":"user","content":"Say hello in exactly 2 words."}]}'
# → {"id":"agy-abc123","object":"chat.completion","model":"agy","choices":[{"message":{"role":"assistant","content":"Hello there."},"finish_reason":"stop"}]}
```

### Local development

```bash
git clone https://github.com/nimblersoft/antigravity-cli-proxy.git
cd antigravity-cli-proxy
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m src
```

### Docker

```bash
cp .env.example .env
docker compose up --build
```

## Endpoints

| Method | Path | Status |
|--------|------|--------|
| `GET` | `/healthz` | ✅ 200 — health check with CLI availability |
| `POST` | `/chat/completions` | ✅ 200 — full implementation (OpenAI format in/out) |

## Configuration

All settings via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3120` | HTTP listen port |
| `LOG_LEVEL` | `info` | Python log level |
| `ANTIGRAVITY_COMMAND` | `agy` | CLI binary name (`agy` is the antigravity CLI binary) |
| `ANTIGRAVITY_TIMEOUT` | `120` | Max seconds per CLI invocation |

## Requirements

- Python 3.11+
- antigravity CLI (`agy`, installed separately) — available on all platforms supported by antigravity

## License

MIT
