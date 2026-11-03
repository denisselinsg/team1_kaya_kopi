"""Authenticated local retrieval; original bodies must not enter external logs."""

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import hmac
import logging
import os
import time
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
import pymysql

from etl.documents.document_store import (
    SchemaNotReady, check_schema, cited_record, connection, coverage, get_record, search,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    key = os.environ.get("DOCUMENT_API_KEY", "")
    if len(key) < 32:
        raise RuntimeError("DOCUMENT_API_KEY must contain at least 32 characters")
    app.state.api_key = key
    yield


app = FastAPI(title="Kaya Kopi document retrieval", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)


def authorize(request: Request,
              key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> None:
    if key is None or not hmac.compare_digest(
            key.encode("utf-8"), request.app.state.api_key.encode("utf-8")):
        raise HTTPException(401, "A valid document API key is required")


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=200)
    source_type: Literal["email", "whatsapp"] | None = None
    date_from: date | None = None
    date_to: date | None = None
    outlet_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}-[0-9][A-Z0-9]$")
    limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def validate_dates(self) -> "SearchRequest":
        if self.date_to == date.max:
            raise ValueError("date_to must precede 9999-12-31")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not follow date_to")
        if not (self.query.strip() or self.source_type or self.date_from
                or self.date_to or self.outlet_code):
            raise ValueError("Provide a query or at least one filter")
        if len(self.query.split()) > 12:
            raise ValueError("Use at most 12 query terms")
        return self


@app.middleware("http")
async def trace_request(request: Request, call_next):
    request.state.trace_id = str(uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request.state.trace_id
    response.headers["X-Latency-Ms"] = str(elapsed)
    logger.info("document_request request_id=%s method=%s status=%s latency_ms=%s",
                request.state.trace_id, request.method, response.status_code, elapsed)
    return response


@app.exception_handler(pymysql.MySQLError)
def database_error(request: Request, exc: pymysql.MySQLError):
    logger.error("document_database_unavailable request_id=%s error_type=%s",
                 request.state.trace_id, type(exc).__name__)
    return JSONResponse(status_code=503, content={
        "detail": "Document evidence could not be checked; database unavailable",
        "request_id": request.state.trace_id,
    })


@app.exception_handler(SchemaNotReady)
def schema_error(request: Request, exc: SchemaNotReady):
    logger.error("document_service_not_ready request_id=%s error_type=%s",
                 request.state.trace_id, type(exc).__name__)
    return JSONResponse(status_code=503, content={
        "detail": "Document service is not ready; check schema deployment",
        "request_id": request.state.trace_id,
    })


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready", dependencies=[Depends(authorize)])
def ready():
    with connection() as conn:
        check_schema(conn)
        state = coverage(conn)
    return {"status": "ready", "coverage": state}


@app.post("/v1/documents/search", dependencies=[Depends(authorize)])
def search_documents(filters: SearchRequest, request: Request):
    with connection() as conn:
        check_schema(conn)
        state = coverage(conn)
        rows = search(
            conn, query=filters.query, source_type=filters.source_type,
            date_from=datetime.combine(filters.date_from, datetime.min.time())
            if filters.date_from else None,
            date_to=datetime.combine(filters.date_to + timedelta(days=1), datetime.min.time())
            if filters.date_to else None,
            outlet_code=filters.outlet_code, limit=filters.limit)
    logger.info("document_search request_id=%s result_count=%s coverage=%s record_ids=%s",
                request.state.trace_id, len(rows), state["status"],
                ",".join(row["record_id"] for row in rows))
    return {"request_id": request.state.trace_id, "coverage": state,
            "results": [cited_record(row) for row in rows]}


@app.get("/v1/documents/{record_id}", dependencies=[Depends(authorize)])
def document(record_id: UUID, request: Request):
    with connection() as conn:
        check_schema(conn)
        state = coverage(conn)
        row = get_record(conn, str(record_id))
    if row is None:
        raise HTTPException(404, "Record not found in the current published dataset")
    return {"request_id": request.state.trace_id, "coverage": state,
            "record": cited_record(row)}
