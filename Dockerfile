# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
&& apt-get install -y --no-install-recommends build-essential git \
&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data/charts \
    && adduser --disabled-password --gecos "" trader \
    && chown -R trader:trader /app

USER trader

CMD ["python", "main.py"]
