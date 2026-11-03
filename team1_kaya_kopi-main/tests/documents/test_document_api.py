from contextlib import contextmanager
from datetime import datetime
import logging

from fastapi.testclient import TestClient
import pymysql
import pytest

from app import document_api
from etl.documents.document_store import SchemaNotReady
from tests.documents.test_document_parser import EMAIL


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DOCUMENT_API_KEY", "a" * 40)
    @contextmanager
    def fake_connection():
        yield object()
    monkeypatch.setattr(document_api, "connection", fake_connection)
    monkeypatch.setattr(document_api, "check_schema", lambda conn: None)
    monkeypatch.setattr(document_api, "coverage", lambda conn: {"status": "incomplete"})
    with TestClient(document_api.app) as test_client:
        yield test_client


def headers():
    return {"X-API-Key": "a" * 40}


def test_authentication_and_health(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 401
    assert client.get("/health/ready", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/health/ready", headers=headers()).status_code == 200


@pytest.mark.parametrize("payload", [
    {}, {"query": "x", "limit": 51},
    {"query": "x", "date_from": "2026-02-02", "date_to": "2026-01-01"},
    {"query": "x", "source_type": "sql"},
    {"query": "x", "outlet_code": "' OR 1=1"},
    {"query": "x", "date_to": "9999-12-31"},
    {"query": "x " * 13},
    {"query": "x", "unexpected": True},
])
def test_invalid_search_is_explicit(client, payload):
    assert client.post("/v1/documents/search", json=payload, headers=headers()).status_code == 422


def test_no_matches_is_success_with_coverage(client, monkeypatch):
    monkeypatch.setattr(document_api, "search", lambda conn, **kwargs: [])
    response = client.post("/v1/documents/search", json={"query": "unknown"}, headers=headers())
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["coverage"]["status"] == "incomplete"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_original_body_citation_and_logs(client, monkeypatch, caplog):
    body = EMAIL.split("\n\n", 1)[1]
    row = {
        "record_id": "00000000-0000-0000-0000-000000000001",
        "source_file": "docs/emails/test.txt", "source_type": "email",
        "revision": "test", "line_start": 1, "line_end": 9,
        "timestamp": datetime(2026, 5, 18), "utc_offset_minutes": 480,
        "subject": "Outlet rename", "sender": None, "body": body,
        "source_status": "complete",
    }
    monkeypatch.setattr(document_api, "search", lambda conn, **kwargs: [row])
    with caplog.at_level(logging.INFO, logger=document_api.__name__):
        response = client.post("/v1/documents/search",
                               json={"query": "AMK-03"}, headers=headers())
    record = response.json()["results"][0]
    assert record["body"] == body
    assert record["citation"] == "docs/emails/test.txt:L1-L9"
    assert body not in caplog.text and "AMK-03" not in caplog.text
    assert "result_count=1" in caplog.text


def test_database_failure_is_not_no_matches(client, monkeypatch):
    def broken(conn, **kwargs):
        raise pymysql.OperationalError(2003, "sensitive connection details")
    monkeypatch.setattr(document_api, "search", broken)
    response = client.post("/v1/documents/search", json={"query": "milk"}, headers=headers())
    assert response.status_code == 503
    assert "results" not in response.json()
    assert "sensitive" not in response.text


def test_record_not_found(client, monkeypatch):
    monkeypatch.setattr(document_api, "get_record", lambda conn, record_id: None)
    response = client.get("/v1/documents/00000000-0000-0000-0000-000000000001",
                          headers=headers())
    assert response.status_code == 404


def test_unsupported_schema_is_explicit(client, monkeypatch):
    def outdated(conn):
        raise SchemaNotReady("unsupported schema")
    monkeypatch.setattr(document_api, "check_schema", outdated)
    response = client.get("/health/ready", headers=headers())
    assert response.status_code == 503
    assert "schema deployment" in response.json()["detail"]


def test_service_refuses_empty_key(monkeypatch):
    monkeypatch.setenv("DOCUMENT_API_KEY", "")
    with pytest.raises(RuntimeError, match="DOCUMENT_API_KEY"):
        with TestClient(document_api.app):
            pass
