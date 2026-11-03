import sys

import pymysql
import pytest

from etl.documents import ingest_documents


@pytest.mark.parametrize("status,exit_code", [("complete", 0), ("incomplete", 2)])
def test_cli_reports_publication_status(monkeypatch, capsys, status, exit_code):
    monkeypatch.setattr(sys, "argv", ["ingest", "--source", "all"])
    monkeypatch.setattr(ingest_documents, "ingest",
                        lambda root, source: {"run_status": status})
    assert ingest_documents.main() == exit_code
    assert status in capsys.readouterr().out


def test_cli_database_error_is_explicit_without_sensitive_details(monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", ["ingest"])
    def failed(root, source):
        raise pymysql.OperationalError(2003, "private connection info")
    monkeypatch.setattr(ingest_documents, "ingest", failed)
    assert ingest_documents.main() == 1
    assert "document_ingestion_failed" in caplog.text
    assert "private connection info" not in caplog.text


def test_bootstrap_cli(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ingest", "--bootstrap"])
    monkeypatch.setattr(ingest_documents, "bootstrap", lambda: None)
    assert ingest_documents.main() == 0
    assert "schema_ready" in capsys.readouterr().out
