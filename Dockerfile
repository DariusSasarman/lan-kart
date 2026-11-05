FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server ./server
COPY static ./static
RUN useradd -m -u 10001 app
USER app
EXPOSE 8000
# --ws-max-size drops oversized WebSocket frames before they are buffered
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-max-size", "2048"]
