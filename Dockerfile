FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8000

COPY backend/requirements.txt backend/requirements-gmail.txt ./
RUN pip install -r requirements.txt && \
    pip install -r requirements-gmail.txt

RUN addgroup --system app && adduser --system --ingroup app app

COPY --chown=app:app backend ./backend

RUN mkdir -p /app/data /app/logs && chown -R app:app /app/data /app/logs

USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.environ.get('PORT', '8000').strip(); token = os.environ.get('AGENT_API_KEY', '').strip(); request = urllib.request.Request(f'http://127.0.0.1:{port}/api/v1/health', headers={'Authorization': f'Bearer {token}'} if token else {}); urllib.request.urlopen(request, timeout=5)" || exit 1

CMD ["sh", "-lc", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
