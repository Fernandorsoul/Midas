FROM node:22-bookworm-slim AS frontend

WORKDIR /app
RUN corepack enable && corepack prepare yarn@1.22.22 --activate
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile
COPY web ./web
RUN yarn build

FROM node:22-bookworm-slim AS python-node-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
    && python3 -m venv /opt/venv \
    && ln -sf /opt/venv/bin/python3 /opt/venv/bin/python \
    && ln -sf /opt/venv/bin/pip3 /opt/venv/bin/pip \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable \
    && corepack prepare yarn@1.22.22 --activate

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

FROM python-node-base AS dev

COPY . .
CMD ["python", "midas.py"]

FROM python-node-base AS production

COPY midas_core ./midas_core
COPY --from=frontend /app/web/dist ./web
COPY midas.py ./

USER 65534:65534
CMD ["python", "midas.py"]
