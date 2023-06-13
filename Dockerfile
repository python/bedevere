FROM python:3.11-slim

COPY requirements.txt requirements.txt
COPY dev-requirements.txt dev-requirements.txt


COPY entrypoint.sh /entrypoint.sh
COPY bedevere/ /bedevere/

RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["/entrypoint.sh"]
