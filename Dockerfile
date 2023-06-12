FROM python:3.11-slim

COPY requirements.txt requirements.txt
COPY dev-requirements.txt dev-requirements.txt

RUN pip install -U pip
RUN pip install -r requirements.txt

CMD ["python", "-m", "bedevere"]