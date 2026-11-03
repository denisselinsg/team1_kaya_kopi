from pathlib import Path
import os

from fastapi.testclient import TestClient
import httpx
import pymysql
import pytest

from app.document_api import app
from etl.documents.document_store import bootstrap, connection, coverage, search
from etl.documents.ingest_documents import ingest
from tests.documents.test_document_parser import EMAIL, CHAT

pytestmark = pytest.mark.skipif(
    os.getenv("DOCUMENT_INTEGRATION") != "1",
    reason="Use the isolated Docker test project for MySQL integration",
)


@pytest.fixture
def database(monkeypatch):
    if os.getenv("DOCUMENT_DB_NAME") != "kaya_documents_test":
        pytest.fail("Integration tests may only use kaya_documents_test")
    bootstrap()
    with connection() as conn, conn.cursor() as cursor:
        for table in ("record_outlets", "document_records", "source_files", "ingestion_runs"):
            cursor.execute(f"DELETE FROM {table}")
        conn.commit()
    yield


@pytest.fixture
def sources(tmp_path):
    (tmp_path / "emails").mkdir()
    (tmp_path / "whatsapp_exports").mkdir()
    (tmp_path / "emails" / "test.txt").write_text(EMAIL, encoding="utf-8")
    (tmp_path / "whatsapp_exports" / "test.txt").write_text(CHAT, encoding="utf-8")
    return tmp_path


def test_repeat_ingestion_aliases_and_citations(database, sources, monkeypatch):
    first = ingest(sources, "all")
    assert first["coverage"]["status"] == "complete"
    assert first["coverage"]["record_count"] == 3
    second = ingest(sources, "all")
    assert second["skipped"] == 2 and second["published"] == 0
    with connection() as conn:
        old = search(conn, outlet_code="AMK-03")
        new = search(conn, outlet_code="AMK-3A")
        assert {row["record_id"] for row in old} == {row["record_id"] for row in new}
        assert len(old) == 3
        assert len(search(conn, query="amk-3a")) == 3
        assert not search(conn, query="' OR 1=1 --")
        assert not search(conn, query="%")
    monkeypatch.setenv("DOCUMENT_DB_USER", "document_reader")
    monkeypatch.setenv("DOCUMENT_DB_PASSWORD", os.environ["DOCUMENT_READER_PASSWORD"])
    with TestClient(app) as client:
        response = client.post("/v1/documents/search", json={
            "source_type": "email", "query": "rename", "date_to": "2026-05-18",
        }, headers={"X-API-Key": os.environ["DOCUMENT_API_KEY"]})
        assert response.status_code == 200
        assert response.json()["coverage"]["status"] == "complete"
        result = response.json()["results"][0]
        assert result["citation"] == "docs/emails/test.txt:L1-L8"
        assert "example.invalid" not in result["body"]
        fetched = client.get("/v1/documents/" + result["record_id"],
                             headers={"X-API-Key": os.environ["DOCUMENT_API_KEY"]})
        assert fetched.status_code == 200
    with connection() as conn, conn.cursor() as cursor:
        with pytest.raises(pymysql.MySQLError):
            cursor.execute("DELETE FROM document_records")


def test_partial_then_total_failure_retains_previous_revision(database, sources):
    ingest(sources, "all")
    path = sources / "whatsapp_exports" / "test.txt"
    path.write_text(CHAT + "31/02/26, 10:00 - Person: bad date\n", encoding="utf-8")
    partial = ingest(sources, "all")
    assert partial["run_status"] == "incomplete"
    assert partial["coverage"]["record_count"] == 3
    before = next(row["revision"] for row in partial["coverage"]["files"]
                  if row["source_type"] == "whatsapp")
    path.write_text("invalid input\n", encoding="utf-8")
    failed = ingest(sources, "all")
    assert failed["coverage"]["record_count"] == 3
    chat = next(row for row in failed["coverage"]["files"] if row["source_type"] == "whatsapp")
    assert chat["status"] == "stale" and chat["revision"] == before
    path.write_text(CHAT, encoding="utf-8")
    assert ingest(sources, "all")["coverage"]["status"] == "complete"


def test_changed_file_missing_file_and_empty_mount(database, sources):
    ingest(sources, "all")
    email_path = sources / "emails" / "test.txt"
    email_path.write_text(EMAIL.replace("Outlet rename", "Updated subject"), encoding="utf-8")
    changed = ingest(sources, "all")
    assert changed["coverage"]["record_count"] == 3
    with connection() as conn:
        assert len(search(conn, query="Updated subject")) == 1
        assert not search(conn, query="Outlet rename")
    email_path.unlink()
    missing = ingest(sources, "all")
    assert missing["coverage"]["record_count"] == 3
    assert missing["run_status"] == "incomplete"
    assert "missing_source_retained" in str(missing["coverage"]["latest_run"]["errors"])
    empty = sources / "absent"
    result = ingest(empty, "all")
    assert result["coverage"]["record_count"] == 3
    assert result["run_status"] == "incomplete"


def test_publication_rolls_back_on_write_failure(database, sources, monkeypatch):
    ingest(sources, "all")
    import etl.documents.ingest_documents as module
    real_publish = module.publish_file
    def failing_publish(*args):
        real_publish(*args)
        raise pymysql.OperationalError(2013, "simulated failure")
    monkeypatch.setattr(module, "publish_file", failing_publish)
    (sources / "emails" / "test.txt").write_text(EMAIL + "changed\n", encoding="utf-8")
    with pytest.raises(pymysql.MySQLError):
        ingest(sources, "all")
    with connection() as conn:
        assert coverage(conn)["record_count"] == 3
        assert not search(conn, query="changed")


def test_concurrent_publisher_rejected(database, sources):
    with connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(CONCAT(DATABASE(), ':publish'), 0)")
        try:
            with pytest.raises(RuntimeError, match="Another ingestion"):
                ingest(sources, "all")
        finally:
            cursor.execute("SELECT RELEASE_LOCK(CONCAT(DATABASE(), ':publish'))")


def test_bootstrap_repeat_safe(database, sources):
    ingest(sources, "all")
    bootstrap()
    with connection() as conn:
        assert coverage(conn)["record_count"] == 3


def test_real_http_service_and_client_data(database):
    root_value = os.getenv("DOCUMENT_RAW_ROOT")
    if not root_value:
        pytest.skip("Optional read-only client source mount is absent")
    root = Path(root_value)
    result = ingest(root, "all")
    assert result["coverage"]["record_count"] == 162
    assert result["coverage"]["status"] == "complete"
    with httpx.Client(base_url="http://document-api:8081", timeout=10) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 401
        headers = {"X-API-Key": os.environ["DOCUMENT_API_KEY"]}
        assert client.get("/health/ready", headers=headers).status_code == 200
        response = client.post("/v1/documents/search", headers=headers, json={
            "source_type": "email", "outlet_code": "AMK-3A",
        })
        assert response.status_code == 200
        records = response.json()["results"]
        assert len(records) == 1
        assert records[0]["source_file"] == "docs/emails/2026-05-18_outlet_rename.txt"
        assert records[0]["timestamp"].startswith("2026-05-18")
        assert records[0]["utc_offset_minutes"] == 480
        assert records[0]["sender"] is None
        assert response.headers["X-Request-ID"] == response.json()["request_id"]
        assert response.json()["coverage"]["alias_rule"]["effective_date"] == "2026-01-01"
        chat = client.post("/v1/documents/search", headers=headers, json={
            "source_type": "whatsapp", "outlet_code": "AMK-3A", "limit": 50,
        })
        assert chat.status_code == 200 and len(chat.json()["results"]) > 0
        assert all(row["utc_offset_minutes"] is None for row in chat.json()["results"])
    again = ingest(root, "all")
    assert again["skipped"] == 3 and again["coverage"]["record_count"] == 162
