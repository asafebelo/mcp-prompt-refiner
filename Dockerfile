FROM python:3.12-slim

RUN useradd --uid 1000 --create-home --shell /bin/bash appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY tools/ ./tools/
COPY config.example.json ./config.example.json

RUN mkdir -p projects && chown -R appuser:appuser /app

USER appuser

ENV MCP_MODE=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

EXPOSE 8000

ENTRYPOINT ["python", "server.py", "--mode", "http"]
