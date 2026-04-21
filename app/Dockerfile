FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir aio-pika sqlalchemy asyncpg aiosqlite fastapi uvicorn pydantic aiogram httpx passlib bcrypt

COPY src /app/src

EXPOSE 8000

CMD ["python", "/app/src/server.py"]
