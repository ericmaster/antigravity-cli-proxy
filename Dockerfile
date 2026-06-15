FROM python:3.11-slim

# Non-root user for security
RUN groupadd --system cliff && \
    useradd --system --create-home --gid cliff cliff

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || \
    pip install --no-cache-dir fastapi uvicorn[standard] pydantic python-dotenv

# Copy application
COPY --chown=cliff:cliff src/ src/

USER cliff

ENV PORT=3120
ENV LOG_LEVEL=info

EXPOSE 3120

CMD ["python", "-m", "src"]
