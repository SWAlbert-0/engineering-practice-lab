FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 lab \
    && useradd --uid 10001 --gid lab --no-create-home lab
COPY requirements.container.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.container.txt
COPY server.py index.html README.md ./
COPY demos/ ./demos/
COPY shared/ ./shared/
COPY report/ ./report/
COPY docs/ ./docs/
COPY scripts/healthcheck.py ./scripts/healthcheck.py
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "scripts/healthcheck.py"]
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8765"]
