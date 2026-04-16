FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY src /app/src

EXPOSE 8000

CMD ["python", "/app/src/server.py"]
