# Schema Contract

**Workstream:** A
**Status:** Draft - names and rules awaiting agreement.

This is the agreed schema used across workstreams B, C, and D. Proposed changes
must be reviewed across workstreams A, B, C, and D before consumers are updated.

## Tables

| Table | Purpose | Row grain | Primary key | Source | Status |
|---|---|---|---|---|---|

## Columns

| Table | Column | Type | Nullable | Meaning/unit | Constraints | Provenance |
|---|---|---|---|---|---|---|

## Shared rules

TODO: Agree join keys, outlet identifiers, date/time conventions, currency,
GST treatment, missing-value handling, and source citation fields.

## Change review

| Date | Proposed change | Consumer impact/migration | Workstream A review | Workstream B review | Workstream C review | Workstream D review | Decision |
|---|---|---|---|---|---|---|---|

Update [er_diagram.md](er_diagram.md) when relationships change.

## Implemented document storage contract (schema version 1)

This isolated subsystem uses database `kaya_documents` and does not rename or
alter cleaned POS tables. The executable column/type/key contract is
[sql/documents.sql](../sql/documents.sql). Review future schema changes through
the change table above; runtime services reject unsupported schema versions.

| Table | Row grain | Primary key | Relationships/purpose |
|---|---|---|---|
| `document_schema` | Schema version | `version` | Runtime compatibility check |
| `ingestion_runs` | Publication attempt | `id` | Scoped status, processing version, counts, error metadata |
| `source_files` | Source path | `id`; unique `source_path` | Latest attempt links to `ingestion_runs`; active revision and source state |
| `document_records` | Email or WhatsApp message | `id` | Links to `source_files`; original body, subject, sender, lines, source timestamp and explicit offset |
| `record_outlets` | Outlet mention per record | `record_id`, `original_code` | Links to `document_records`; canonical alias used for filtering |

UTC offset is nullable; WhatsApp timezone remains unspecified. Record IDs and
revisions change when file content or processing rules change. The API returns
current active records only, with source citations and incomplete/stale coverage.
The reviewed alias rule and authenticated original-text privacy decision are
documented in [document_processing.md](document_processing.md).
