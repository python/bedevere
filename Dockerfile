FROM python:3.11-slim

COPY requirements.txt requirements.txt
COPY dev-requirements.txt dev-requirements.txt

RUN mkdir -p /github/workspace/bedevere
COPY bedevere /github/workspace/bedevere

RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir -r requirements.txt

RUN dir -s

CMD ["python", "-m", "bedevere"]
