FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY etl ./etl
COPY app ./app
COPY sql/documents.sql ./sql/documents.sql
COPY tests ./tests
RUN useradd --uid 10001 --create-home document
USER document
ENTRYPOINT ["python", "-m", "etl.documents.ingest_documents"]

FROM runtime AS test
USER root
RUN pip install --no-cache-dir -r requirements-dev.txt
USER document
