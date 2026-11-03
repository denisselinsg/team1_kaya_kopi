# Cleaned Schema ER Diagram

**Workstream:** A
**Status:** Template - cleaned schema not yet agreed.

Show the cleaned tables, primary and foreign keys, join columns, and
cardinalities. Keep names aligned with [schema_contract.md](schema_contract.md).

## Diagram

The entities below are placeholders, not actual schema names. Replace them with
the verified cleaned schema before review.

```mermaid
erDiagram
    PARENT_PLACEHOLDER ||--o{ CHILD_PLACEHOLDER : joins
    PARENT_PLACEHOLDER {
        int id PK
    }
    CHILD_PLACEHOLDER {
        int id PK
        int parent_id FK
    }
```

## Join rules and exceptions

TODO: Document join keys, unmatched records, nullable relationships, and any
relationships that cannot be enforced as foreign keys.

## Implemented document subsystem (not the cleaned POS schema)

The placeholder above still needs replacement for the full cleaned schema.
This separate diagram reflects [sql/documents.sql](../sql/documents.sql).

```mermaid
erDiagram
    ingestion_runs ||--o{ source_files : latest_attempt
    source_files ||--o{ document_records : contains
    document_records ||--o{ record_outlets : mentions
    ingestion_runs {
        char id PK
        varchar source_scope
        varchar status
    }
    source_files {
        char id PK
        varchar source_path UK
        char last_run_id FK
        char revision
        varchar status
    }
    document_records {
        char id PK
        char file_id FK
        char revision
        datetime occurred_at
        int utc_offset_minutes
    }
    record_outlets {
        char record_id PK,FK
        varchar original_code PK
        varchar canonical_code
    }
```
