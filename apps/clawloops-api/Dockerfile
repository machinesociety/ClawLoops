FROM python:3.12.8-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

ARG APT_MIRROR=deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN if [ -f /etc/apt/sources.list ]; then sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; fi \
    && if [ -f /etc/apt/sources.list.d/debian.sources ]; then sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; fi \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/clawloops-api/pyproject.toml /app/pyproject.toml
COPY apps/clawloops-api/app /app/app

ENV PIP_INDEX_URL=${PIP_INDEX_URL}
# RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
