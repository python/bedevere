FROM python:3.15-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bedevere bedevere

CMD ["python", "-m", "bedevere"]
