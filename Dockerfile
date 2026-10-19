FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 lab \
    && useradd --uid 10001 --gid lab --no-create-home lab
RUN mkdir -p /data && chown 10001:10001 /data && chmod 0770 /data
ENV LAB_DATA_DIR=/data
COPY requirements.container.txt ./
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install --disable-pip-version-check --timeout 120 --retries 6 --only-binary=:all: --index-url "$PIP_INDEX_URL" -r requirements.container.txt
COPY server.py index.html README.md ./
COPY demos/ ./demos/
COPY shared/ ./shared/
COPY report/ ./report/
COPY docs/ ./docs/
COPY scripts/healthcheck.py scripts/parse_process_pdf.py scripts/backup_process_data.py scripts/repair_worker.py scripts/train_mlops.py ./scripts/
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "scripts/healthcheck.py"]
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8765"]
