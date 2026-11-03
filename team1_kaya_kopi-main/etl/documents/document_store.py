"""MySQL access with bounded timeouts and transactional publication."""

from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Iterator
from uuid import NAMESPACE_URL, uuid5

import pymysql
from pymysql.connections import Connection

from etl.documents.document_parser import (
    ALIAS_PROVENANCE, OUTLET_PATTERN, PROCESSING_VERSION, ParseResult, canonical_outlet,
)


class SchemaNotReady(RuntimeError):
    """The document schema requires an explicit deployment step."""


def database_name() -> str:
    name = os.getenv("DOCUMENT_DB_NAME", "kaya_documents")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
        raise ValueError("DOCUMENT_DB_NAME must be a safe MySQL identifier")
    return name


def connect(*, admin: bool = False) -> Connection:
    prefix = "DOCUMENT_ADMIN" if admin else "DOCUMENT_DB"
    password = os.environ[f"{prefix}_PASSWORD"]
    if not password:
        raise ValueError(f"{prefix}_PASSWORD must not be empty")
    user = "root" if admin else os.environ["DOCUMENT_DB_USER"]
    return pymysql.connect(
        host=os.getenv("DOCUMENT_DB_HOST", "mysql"),
        port=int(os.getenv("DOCUMENT_DB_PORT", "3306")),
        user=user, password=password, database=None if admin else database_name(),
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5, read_timeout=10, write_timeout=10, autocommit=False,
        init_command="SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ",
    )


@contextmanager
def connection(*, admin: bool = False) -> Iterator[Connection]:
    conn = connect(admin=admin)
    try:
        yield conn
    finally:
        conn.close()


def check_schema(conn: Connection) -> None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT version FROM document_schema")
        if [row["version"] for row in cursor.fetchall()] != [1]:
            raise SchemaNotReady("Unsupported document schema; run bootstrap")


def bootstrap() -> None:
    name = database_name()
    for variable in ("DOCUMENT_WRITER_PASSWORD", "DOCUMENT_READER_PASSWORD"):
        if len(os.environ.get(variable, "")) < 32:
            raise ValueError(f"{variable} must contain at least 32 characters")
    with connection(admin=True) as conn, conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` "
                       "CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
        cursor.execute(f"USE `{name}`")
        ddl = (Path(__file__).resolve().parents[2] / "sql" / "documents.sql").read_text()
        for statement in ddl.split(";"):
            if statement.strip():
                cursor.execute(statement)
        check_schema(conn)
        for user, password_var, permissions in (
            ("document_writer", "DOCUMENT_WRITER_PASSWORD",
             "SELECT, INSERT, UPDATE, DELETE"),
            ("document_reader", "DOCUMENT_READER_PASSWORD", "SELECT"),
        ):
            password = os.environ[password_var]
            if not password:
                raise ValueError(f"{password_var} must not be empty")
            cursor.execute("CREATE USER IF NOT EXISTS %s@'%%' IDENTIFIED BY %s",
                           (user, password))
            cursor.execute("ALTER USER %s@'%%' IDENTIFIED BY %s", (user, password))
            cursor.execute(f"GRANT {permissions} ON `{name}`.* TO %s@'%%'", (user,))
        conn.commit()


def file_state(conn: Connection, path: str) -> dict | None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM source_files WHERE source_path=%s", (path,))
        return cursor.fetchone()


def publish_file(conn: Connection, run_id: str, path: str, source_type: str,
                 digest: str | None, result: ParseResult) -> tuple[str, int]:
    existing = file_state(conn, path)
    file_id = existing["id"] if existing else str(uuid5(NAMESPACE_URL, path))
    status = "incomplete" if result.issues else "complete"
    with conn.cursor() as cursor:
        if not result.records:
            status = "stale" if existing and existing["revision"] else "unavailable"
            cursor.execute(
                "INSERT INTO source_files "
                "(id, source_path, source_type, status, last_run_id) "
                "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "status=VALUES(status), last_run_id=VALUES(last_run_id)",
                (file_id, path, source_type, status, run_id))
            return status, 0
        revision = str(uuid5(NAMESPACE_URL,
                            f"{path}:{digest}:{PROCESSING_VERSION}"))
        cursor.execute(
            "INSERT INTO source_files (id,source_path,source_type,content_hash,"
            "processing_version,revision,status,last_run_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
            "content_hash=VALUES(content_hash),processing_version=VALUES(processing_version),"
            "revision=VALUES(revision),status=VALUES(status),last_run_id=VALUES(last_run_id)",
            (file_id, path, source_type, digest, PROCESSING_VERSION, revision,
             status, run_id))
        cursor.execute("DELETE FROM document_records WHERE file_id=%s", (file_id,))
        for record in result.records:
            record_id = str(uuid5(NAMESPACE_URL, f"{revision}:{record.line_start}"))
            cursor.execute(
                "INSERT INTO document_records "
                "(id,file_id,revision,line_start,line_end,occurred_at,"
                "utc_offset_minutes,subject,sender,body) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (record_id, file_id, revision, record.line_start, record.line_end,
                 record.timestamp, record.offset_minutes, record.subject,
                 record.sender, record.body))
            for code in record.outlets:
                cursor.execute("INSERT INTO record_outlets VALUES (%s,%s,%s)",
                               (record_id, code, canonical_outlet(code)))
    return status, len(result.records)


def coverage(conn: Connection) -> dict:
    with conn.cursor() as cursor:
        cursor.execute("SELECT id,source_scope,status,finished_at,errors_json "
                       "FROM ingestion_runs ORDER BY started_at DESC,id DESC LIMIT 1")
        latest = cursor.fetchone()
        cursor.execute("SELECT source_path,source_type,revision,status FROM "
                       "source_files ORDER BY source_path")
        files = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) AS total FROM document_records")
        total = cursor.fetchone()["total"]
    complete = bool(latest and latest["status"] == "complete" and files
                    and all(row["status"] == "complete" for row in files)
                    and {row["source_type"] for row in files} == {"email", "whatsapp"})
    if latest:
        latest["errors"] = json.loads(latest.pop("errors_json"))
    return {
        "status": "complete" if complete else "incomplete",
        "latest_run": latest, "files": files, "record_count": total,
        "privacy": "original_bodies_and_sender_labels_authenticated_local_access",
        "alias_rule": {
            "aliases": ["AMK-03", "AMK-3A"], "canonical": "AMK-3A",
            "source_file": ALIAS_PROVENANCE,
            "effective_date": "2026-01-01", "version": "alias-v1",
        },
    }


def search(conn: Connection, *, query: str = "", source_type: str | None = None,
           date_from: datetime | None = None, date_to: datetime | None = None,
           outlet_code: str | None = None, limit: int = 10) -> list[dict]:
    clauses = []
    params: list = []
    # Literal substring search preserves short identifiers and treats %/_ as text.
    for term in query.split():
        if OUTLET_PATTERN.fullmatch(term.upper()):
            clauses.append("EXISTS (SELECT 1 FROM record_outlets o WHERE "
                           "o.record_id=r.id AND o.canonical_code=%s)")
            params.append(canonical_outlet(term.upper()))
        else:
            clauses.append("(LOCATE(%s, LOWER(r.subject)) > 0 OR "
                           "LOCATE(%s, LOWER(r.body)) > 0)")
            params.extend([term.lower(), term.lower()])
    if source_type:
        clauses.append("f.source_type=%s")
        params.append(source_type)
    if date_from:
        clauses.append("r.occurred_at >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("r.occurred_at < %s")
        params.append(date_to)
    if outlet_code:
        clauses.append("EXISTS (SELECT 1 FROM record_outlets o WHERE "
                       "o.record_id=r.id AND o.canonical_code=%s)")
        params.append(canonical_outlet(outlet_code))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT r.id AS record_id,f.source_path AS source_file,f.source_type,"
            "r.revision,r.line_start,r.line_end,r.occurred_at AS timestamp,"
            "r.utc_offset_minutes,r.subject,r.sender,r.body,f.status AS source_status "
            "FROM document_records r JOIN source_files f ON f.id=r.file_id"
            + where + " ORDER BY r.occurred_at DESC,r.id LIMIT %s",
            (*params, limit))
        return cursor.fetchall()


def get_record(conn: Connection, record_id: str) -> dict | None:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT r.id AS record_id,f.source_path AS source_file,f.source_type,"
            "r.revision,r.line_start,r.line_end,r.occurred_at AS timestamp,"
            "r.utc_offset_minutes,r.subject,r.sender,r.body,f.status AS source_status "
            "FROM document_records r JOIN source_files f ON f.id=r.file_id "
            "WHERE r.id=%s", (record_id,))
        return cursor.fetchone()


def cited_record(row: dict) -> dict:
    return {
        **row,
        "citation": f"{row['source_file']}:L{row['line_start']}-L{row['line_end']}",
        "timezone": "unspecified" if row["utc_offset_minutes"] is None else "source_offset",
    }
