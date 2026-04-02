FROM python:3.12.8-slim

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

WORKDIR /app

COPY services/runtime-manager/pyproject.toml /app/pyproject.toml
COPY services/runtime-manager/app /app/app
# RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    .

EXPOSE 18080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18080"]
