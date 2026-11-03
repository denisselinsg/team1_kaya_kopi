"""Run with python -m etl.documents.ingest_documents; no automatic source deletion."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

import pymysql

from etl.documents.document_parser import (
    PROCESSING_VERSION, ParseIssue, ParseResult, parse_email, parse_whatsapp,
)
from etl.documents.document_store import (
    bootstrap, check_schema, connection, coverage, file_state, publish_file,
)

logger = logging.getLogger(__name__)
SOURCES = {"emails": ("email", "emails"), "whatsapp": ("whatsapp", "whatsapp_exports")}


def ingest(root: Path, source: str) -> dict:
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    run_id = str(uuid4())
    errors: list[dict] = []
    files_seen = published = skipped = 0
    scopes = SOURCES if source == "all" else {source: SOURCES[source]}
    with connection() as conn:
        check_schema(conn)
        with conn.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(CONCAT(DATABASE(), ':publish'), 5) AS locked")
            if cursor.fetchone()["locked"] != 1:
                raise RuntimeError("Another ingestion is publishing; retry later")
        # Schema inspection can start a snapshot before another publisher commits.
        conn.commit()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO ingestion_runs "
                    "(id,source_scope,status,processing_version,started_at,errors_json) "
                    "VALUES (%s,%s,'running',%s,%s,'[]')",
                    (run_id, source, PROCESSING_VERSION, started))
            observed: set[str] = set()
            for source_type, directory_name in scopes.values():
                directory = root / directory_name
                if not directory.is_dir():
                    errors.append({"source": source_type, "code": "missing_directory"})
                    paths = []
                else:
                    paths = sorted(directory.rglob("*"))
                actual_files = [path for path in paths if path.is_file()]
                if not actual_files and directory.is_dir():
                    errors.append({"source": source_type, "code": "empty_directory"})
                for path in actual_files:
                    files_seen += 1
                    relative = "docs/" + path.relative_to(root).as_posix()
                    observed.add(relative)
                    if path.suffix.lower() != ".txt":
                        result = ParseResult(issues=[ParseIssue(1, "unsupported_file_type")])
                        digest = None
                    else:
                        try:
                            raw = path.read_bytes()
                            text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
                        except (OSError, UnicodeError):
                            result = ParseResult(issues=[ParseIssue(1, "unreadable_utf8_file")])
                            digest = None
                        else:
                            digest = hashlib.sha256(raw).hexdigest()
                            existing = file_state(conn, relative)
                            if (existing and existing["content_hash"] == digest
                                    and existing["processing_version"] == PROCESSING_VERSION
                                    and existing["status"] == "complete"):
                                skipped += 1
                                continue
                            parser = parse_email if source_type == "email" else parse_whatsapp
                            result = parser(text)
                            if not result.records and not result.issues:
                                result.issues.append(ParseIssue(1, "no_records"))
                    for issue in result.issues:
                        errors.append({"source_file": relative, "line": issue.line,
                                       "code": issue.code})
                    _, count = publish_file(conn, run_id, relative, source_type, digest, result)
                    published += count
                with conn.cursor() as cursor:
                    cursor.execute("SELECT source_path,revision FROM source_files "
                                   "WHERE source_type=%s", (source_type,))
                    for old in cursor.fetchall():
                        if old["source_path"] not in observed:
                            status = "stale" if old["revision"] else "unavailable"
                            cursor.execute("UPDATE source_files SET status=%s,last_run_id=%s "
                                           "WHERE source_path=%s",
                                           (status, run_id, old["source_path"]))
                            errors.append({"source_file": old["source_path"],
                                           "code": "missing_source_retained"})
            status = "incomplete" if errors else "complete"
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE ingestion_runs SET status=%s,finished_at=%s,files_seen=%s,"
                    "records_published=%s,errors_json=%s WHERE id=%s",
                    (status, datetime.now(timezone.utc).replace(tzinfo=None),
                     files_seen, published, json.dumps(errors), run_id))
            conn.commit()
            summary = coverage(conn)
            conn.commit()
            return {"run_id": run_id, "run_status": status, "files_seen": files_seen,
                    "published": published, "skipped": skipped, "coverage": summary}
        except (pymysql.MySQLError, RuntimeError, ValueError):
            conn.rollback()
            raise
        finally:
            with conn.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(CONCAT(DATABASE(), ':publish'))")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("all", "emails", "whatsapp"), default="all")
    parser.add_argument("--root", type=Path, default=Path(os.getenv("DOCUMENT_SOURCE_ROOT", "/sources")))
    parser.add_argument("--bootstrap", action="store_true")
    args = parser.parse_args()
    try:
        if args.bootstrap:
            bootstrap()
            print(json.dumps({"status": "schema_ready"}))
            return 0
        summary = ingest(args.root, args.source)
        print(json.dumps(summary, default=str))
        return 2 if summary["run_status"] == "incomplete" else 0
    except (pymysql.MySQLError, OSError, ValueError, RuntimeError, KeyError) as exc:
        # Exception text can contain database details; log only the failure class.
        logger.error("document_ingestion_failed error_type=%s", type(exc).__name__)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
